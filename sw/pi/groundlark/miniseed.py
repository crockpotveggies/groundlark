"""Bounded miniSEED 3 INT32 output for raw DAQHAT seismic channels.

FDSN v3 header/CRC32C, little endian, uncompressed signed counts. No resampling,
orientation transform, response correction or calibration is performed here.
"""
from datetime import datetime, timezone
import re
import struct
from .calibration import Calibrations, canonical, configuration_hash
from .recording import Reader, RecordingError, is_acquisition_metadata
from .session import Sessions

SECOND = 1_000_000_000
HEADER = struct.Struct('<2sBBIHHBBBBdIIBBHI')


def _crc_table():
    result = []
    for n in range(256):
        for _ in range(8): n = (n >> 1) ^ (0x82F63B78 if n & 1 else 0)
        result.append(n)
    return result


CRC_TABLE = _crc_table()


def crc32c(data):
    crc = 0xffffffff
    for byte in data: crc = CRC_TABLE[(crc ^ byte) & 255] ^ (crc >> 8)
    return crc ^ 0xffffffff


def utc_origin(value):
    """Explicit UTC calendar origin for simulation only; never infer an epoch."""
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('miniSEED simulation origin must be YYYY-MM-DDTHH:MM:SSZ')
    date = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    if not 2000 <= date.year < 2100: raise ValueError('miniSEED origin must be in 2000..2099')
    return int(date.timestamp()) * SECOND


def record(source, start_ns, period_ns, counts, extra, questionable):
    seconds, nanos = divmod(start_ns, SECOND)
    date = datetime.fromtimestamp(seconds, timezone.utc)
    if not 2000 <= date.year < 2100: raise ValueError('miniSEED time outside 2000..2099')
    sid = source.encode('ascii')
    metadata = canonical(extra)
    if not 0 < period_ns or not 1 <= len(counts) <= 128 or len(sid) > 255 or len(metadata) > 8192:
        raise ValueError('miniSEED record bounds')
    payload = struct.pack('<' + 'i' * len(counts), *counts)
    header = HEADER.pack(b'MS', 3, 2 if questionable else 0, nanos, date.year,
                         date.timetuple().tm_yday, date.hour, date.minute, date.second,
                         3, SECOND / period_ns, len(counts), 0, 1, len(sid), len(metadata), len(payload))
    data = bytearray(header + sid + metadata + payload)
    struct.pack_into('<I', data, 28, crc32c(data))
    return bytes(data)


class SeismicWriter:
    """At most 19 channels x 128 samples buffered, for one HAT identity.

    Each record follows the advertised period exactly. Any timestamp jitter,
    missing/fault sample, status, reset or configuration change ends a record.
    No missing sample is encoded as a numeric value. The companion SSREC retains
    all non-waveform events, original payloads and explicit unknown-loss markers.
    """
    def __init__(self, stream, metadata, *, station='GL001', network='XX',
                 max_bytes=64 * 1024 * 1024, simulation_start=None):
        if not re.fullmatch('[A-Z0-9]{1,5}', station) or not re.fullmatch('[A-Z0-9]{1,2}', network):
            raise ValueError('miniSEED station/network: uppercase letters/digits, max 5/2 characters')
        if not 4096 <= max_bytes <= 1024 * 1024 * 1024: raise ValueError('miniSEED byte limit')
        if not is_acquisition_metadata(metadata): raise ValueError('recording application metadata')
        if simulation_start is not None and metadata.get('source') != 'simulation':
            raise ValueError('miniSEED calendar origin is only allowed for simulation')
        self.origin = utc_origin(simulation_start) if simulation_start is not None else None
        self.stream, self.limit, self.written = stream, max_bytes, 0
        self.station, self.network = station, network
        self.sessions = Sessions(Calibrations(metadata.get('calibrations', [])), checkpoint=metadata.get("session_checkpoint"))
        self.pending, self.last_times = {}, {}
        self.device = None
        self.clock_observation = None
        self.records = self.samples = self.omitted = self.untimed = 0

    def _flush(self, key):
        block = self.pending.pop(key, None)
        if block is None: return
        source, start, period, values, extra, questionable = block
        data = record(source, start, period, values, extra, questionable)
        if self.written + len(data) > self.limit: raise RecordingError('miniSEED byte budget exhausted')
        if self.stream.write(data) != len(data): raise RecordingError('short miniSEED write')
        self.written += len(data)
        self.records += 1
        self.samples += len(values)

    def flush(self):
        for key in list(self.pending): self._flush(key)
        self.stream.flush()

    def event(self, code, detail, arrival_ns, **fields):
        self.flush()
        self.clock_observation = None
        if code == 'miniseed_system_clock':
            # Only applies to the immediately following message at this arrival.
            raw, unix, bracket = (fields.get(k) for k in ('raw_ns', 'unix_ns', 'bracket_ns'))
            if any(type(v) is not int or v < 0 for v in (raw, unix, bracket)) or bracket > 10_000_000:
                raise ValueError('invalid miniSEED system clock observation')
            self.clock_observation = (arrival_ns, raw, unix, bracket)
        if code == 'usb_disconnected' and fields.get('device') is not None:
            self.sessions.disconnect(fields['device'])

    def _time(self, stamp, arrival):
        if stamp.HasField('utc_unix_ns'):
            return stamp.utc_unix_ns, 'recorded-utc', stamp.utc_uncertainty_ns, False
        if self.origin is not None and stamp.domain == 1:
            return self.origin + stamp.acquisition_ns, 'synthetic-origin', None, True
        if self.clock_observation is not None and stamp.domain == 1:
            arrived, raw, unix, bracket = self.clock_observation
            if arrived == arrival and -bracket <= raw - stamp.acquisition_ns <= 5 * SECOND:
                return unix + stamp.acquisition_ns - raw, 'unverified-system-clock', None, True
        return None

    def message(self, message, arrival_ns):
        kind = self.sessions.accept(message)
        state = self.sessions.devices[message.device_id]
        if kind != 'batch':
            self.flush()
            self.clock_observation = None
            return
        b = message.batch
        if state.board != 1 or b.sensor_id not in (1, 2, 3, 9):
            self.clock_observation = None
            return
        if self.device is None: self.device = message.device_id
        if self.device != message.device_id: raise ValueError('miniSEED station cannot merge multiple HAT identities')
        cfg = state.settings[b.sensor_id]
        period = cfg.period_ns
        config_hash = configuration_hash(cfg)
        for index, sample in enumerate(b.samples):
            if sample.quality not in (1, 3):
                self.flush(); self.omitted += 1
                continue
            stamp = self._time(sample.time, arrival_ns)
            if stamp is None:
                self.flush(); self.untimed += 1
                continue
            unix, timing, error, questionable = stamp
            if b.sensor_id == 9:
                channels = [('H', '3', sample.geophone.counts)]
            else:
                channels = [(code, str(axis + 1), getattr(getattr(sample.imu, field), name))
                            for code, field in [('N', 'acceleration'), ('J', 'angular_rate')]
                            for axis, name in enumerate(('x', 'y', 'z'))]
            # I denotes irregular timing; package axes 1/2/3 do not claim N/E/Z.
            for instrument, axis, value in channels:
                sid = f'FDSN:{self.network}_{self.station}_{b.sensor_id:02d}_I_{instrument}_{axis}'
                loss = b.dropped_before if b.HasField('dropped_before') else None
                info = dict(device=message.device_id, boot=str(message.boot_id), sensor=b.sensor_id,
                            sequence=str(sample.sequence), acquisition_ns=str(sample.time.acquisition_ns),
                            clock_domain=sample.time.domain, quality=sample.quality,
                            units='counts', configuration_sha256=config_hash, calibration_applied=False,
                            timing_source=timing, utc_uncertainty_ns=error,
                            acquisition_uncertainty_ns=sample.time.uncertainty_ns if sample.time.HasField('uncertainty_ns') else None,
                            dropped_before=loss if index == 0 else 0 if loss is not None else None)
                if sid in self.last_times and unix <= self.last_times[sid]:
                    raise ValueError('miniSEED calendar time regressed; start a new capture after clock correction')
                self.last_times[sid] = unix
                previous = self.pending.get(sid)
                compatible = False
                if previous:
                    _, start, old_period, values, headers, old_questionable = previous
                    old = headers['Groundlark']
                    stable = ('device','boot','sensor','clock_domain','quality','configuration_sha256',
                              'timing_source','utc_uncertainty_ns','acquisition_uncertainty_ns')
                    compatible = (old_period == period and old_questionable == questionable
                        and len(values) < 128 and unix == start + len(values) * period
                        and sample.time.acquisition_ns == int(old['acquisition_ns']) + len(values) * period
                        and sample.sequence == int(old['sequence']) + len(values)
                        and all(old[k] == info[k] for k in stable)
                        and (old['dropped_before'] is None) == (info['dropped_before'] is None)
                        and (index != 0 or loss in (0, None)))
                if not compatible:
                    self._flush(sid)
                    self.pending[sid] = (sid, unix, period, [], {'Groundlark': info}, questionable)
                self.pending[sid][3].append(value)
        self.clock_observation = None

    def summary(self):
        return dict(format='miniSEED 3', records=self.records, channel_samples=self.samples,
                    bytes=self.written, omitted_missing_or_fault=self.omitted,
                    omitted_without_calendar_time=self.untimed, units='raw counts')


class Mirror:
    """Preserve the complete SSREC alongside the interoperable waveform file."""
    def __init__(self, writer, seismic, system_clock=None):
        self.writer, self.seismic, self.system_clock = writer, seismic, system_clock

    def message(self, message, arrival_ns):
        if self.system_clock and message.WhichOneof('body') == 'batch' and message.batch.sensor_id in (1, 2, 3, 9):
            observation = self.system_clock()
            self.event('miniseed_system_clock', 'Unverified system time; not qualified UTC', arrival_ns, **observation)
        self.writer.message(message, arrival_ns)
        self.seismic.message(message, arrival_ns)

    def event(self, code, detail, arrival_ns, **fields):
        # Finish waveform output before marking the companion capture complete.
        self.seismic.event(code, detail, arrival_ns, **fields)
        if code == 'acquisition_summary': fields['miniseed'] = self.seismic.summary()
        self.writer.event(code, detail, arrival_ns, **fields)


def export(recording, output, *, station='GL001', network='XX', simulation_start=None, max_bytes=64*1024*1024):
    """Validate and stream a saved SSREC. Unmapped times are reported, never guessed."""
    with open(recording, 'rb') as source:
        reader = Reader(source)
        with open(output, 'xb') as target:
            writer = SeismicWriter(target, reader.metadata, station=station, network=network,
                                   simulation_start=simulation_start, max_bytes=max_bytes)
            completed = False
            for arrival, item in reader:
                completed = isinstance(item, dict) and item.get('code') == 'acquisition_summary'
                if isinstance(item, dict):
                    fields = {k:v for k,v in item.items() if k not in ('code','detail')}
                    writer.event(item.get('code'), item.get('detail',''), arrival, **fields)
                else: writer.message(item, arrival)
            writer.flush()
            report = dict(writer.summary(), source_completed=completed)
            if not writer.samples: raise ValueError('No timed seismic samples; provide a simulation origin or recorded clock evidence')
            return report
