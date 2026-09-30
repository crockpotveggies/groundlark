"""Raw waveform, timing and failure fixtures, plus a libmseed-generated record."""
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from groundlark import messages as m
from groundlark.calibration import Calibrations, configuration_hash
from groundlark.miniseed import SeismicWriter, Mirror, crc32c, export, record, utc_origin
from groundlark.recording import Reader, RecordingError, Writer
from groundlark.simulation import defaults

ROOT = Path(__file__).resolve().parents[2]
META = dict(format='groundlark-acquisition-v1', source='simulation')
ORIGIN = '2024-02-29T23:59:59Z'
EPOCH = 1709251199000000000
RAW = dict(acceleration=(-32768, 0, 32767), angular_rate=(-3, 0, 3), temperature=10)
PERIOD = defaults()[0]['period_ns']
GEO_PERIOD = next(c for c in defaults() if c['sensor_id'] == 9)['period_ns']


def records(data):
    """Read explicit standard offsets without using the production header struct."""
    result = []
    while data:
        assert data[:3] == b'MS\x03'
        count = int.from_bytes(data[24:28], 'little')
        sid_len = data[33]
        extra_len = int.from_bytes(data[34:36], 'little')
        payload_len = int.from_bytes(data[36:40], 'little')
        offset = 40 + sid_len + extra_len
        end = offset + payload_len
        assert end <= len(data) and payload_len == count * 4
        result.append(dict(sid=data[40:40+sid_len].decode(), flags=data[3],
            nanos=int.from_bytes(data[4:8], 'little'),
            year=int.from_bytes(data[8:10], 'little'), day=int.from_bytes(data[10:12], 'little'),
            hour=data[12], minute=data[13], second=data[14],
            extra=json.loads(data[40+sid_len:offset]),
            counts=list(struct.unpack('<'+'i'*count, data[offset:end]))))
        data = data[end:]
    return result


def handshake(writer, sensors=(1,), boot=1, device='pi', arrival=0):
    writer.message(m.identity(device, boot, 1, sensors), arrival)
    writer.message(m.configuration(device, boot, [c for c in defaults() if c['sensor_id'] in sensors]), arrival)


def sample(seq=0, acquired=0, sensor=1, raw=RAW, **kwargs):
    if sensor == 9 and raw is not None: raw = dict(raw, conversion_counter=seq % 256)
    return m.batch('pi', 1, sensor, seq, acquired, raw, **kwargs)


class MiniSEEDTests(unittest.TestCase):
    def make(self, **kwargs):
        stream = io.BytesIO()
        return stream, SeismicWriter(stream, META, **kwargs)

    def test_crc_and_independent_libmseed_golden_record(self):
        self.assertEqual(crc32c(b'123456789'), 0xe3069283)
        # Generated with EarthScope pymseed 1.0.1 / libmseed, INT32, 100 Hz,
        # publication 1, questionable time, 2024 day 60 23:59:59.123456789.
        golden = bytes.fromhex(
            '4d53030215cd5b07e8073c00173b3b03000000000000594003000000d3b3a030'
            '011621000c0000004644534e3a58585f474c3030315f30395f495f485f33'
            '7b2247726f756e646c61726b223a7b22756e697473223a22636f756e7473227d7d'
            '000080ff00000000ffff7f00')
        self.assertEqual(record('FDSN:XX_GL001_09_I_H_3', EPOCH+123456789, 10_000_000,
            [-8388608, 0, 8388607], {'Groundlark': {'units':'counts'}}, True), golden)

    def test_all_19_channels_keep_raw_signed_counts_and_axis_identity(self):
        stream, writer = self.make(simulation_start=ORIGIN)
        handshake(writer, (1,2,3,9))
        for sensor in (1,2,3): writer.message(sample(sensor=sensor), 0)
        writer.message(sample(sensor=9, raw={'counts':-8388608}), 0)
        writer.flush()
        rows = records(stream.getvalue())
        self.assertEqual(len(rows), 19)
        expected = {f'FDSN:XX_GL001_{sensor:02d}_I_{code}_{axis}': value
            for sensor in (1,2,3) for code, values in [('N',[-32768,0,32767]),('J',[-3,0,3])]
            for axis, value in enumerate(values,1)}
        expected['FDSN:XX_GL001_09_I_H_3'] = -8388608
        self.assertEqual({r['sid']:r['counts'][0] for r in rows}, expected)
        for row in rows:
            self.assertEqual(row['flags'], 2)
            self.assertEqual(row['extra']['Groundlark']['units'], 'counts')
            self.assertFalse(row['extra']['Groundlark']['calibration_applied'])

    def test_exact_cadence_groups_but_jitter_and_unknown_loss_split(self):
        stream, writer = self.make(simulation_start=ORIGIN)
        handshake(writer)
        for seq, acquired, loss in [(0,0,0),(1,PERIOD,0),(2,2*PERIOD+1,0),
                                     (3,3*PERIOD+1,None),(4,4*PERIOD+1,None),(5,5*PERIOD+1,0)]:
            writer.message(sample(seq, acquired, dropped=loss), acquired)
        writer.flush()
        rows = [r for r in records(stream.getvalue()) if r['sid'].endswith('N_1')]
        self.assertEqual([len(r['counts']) for r in rows], [2,1,2,1])
        self.assertEqual([r['extra']['Groundlark']['dropped_before'] for r in rows], [0,0,None,0])

    def test_calibrated_companion_does_not_replace_raw_waveform_counts(self):
        cfg = m.configuration('pi',1,defaults()[:1]).configuration.sensors[0]
        calibrations = Calibrations()
        ident = calibrations.add(dict(sensor_id=1, configuration_sha256=configuration_hash(cfg),
            provenance='test fixture only', fields={'acceleration_m_s2':dict(scale=[2,3,4],offset=[1,2,3])}))
        stream = io.BytesIO()
        writer = SeismicWriter(stream,dict(META,calibrations=list(calibrations.records.values())),simulation_start=ORIGIN)
        handshake(writer)
        writer.message(calibrations.apply(sample(),ident,cfg),0)
        writer.flush()
        row = next(r for r in records(stream.getvalue()) if r['sid'].endswith('N_1'))
        self.assertEqual(row['counts'],[-32768])
        self.assertFalse(row['extra']['Groundlark']['calibration_applied'])

    def test_missing_fault_saturation_and_loss_never_insert_zero_samples(self):
        stream, writer = self.make(simulation_start=ORIGIN)
        handshake(writer, (9,))
        writer.message(sample(sensor=9, raw={'counts':0}), 0)
        writer.message(sample(1,GEO_PERIOD,sensor=9,raw=None), GEO_PERIOD)
        fault = sample(2,2*GEO_PERIOD,sensor=9,raw={'counts':123},quality=4)
        writer.message(fault, 2*GEO_PERIOD)
        writer.message(sample(4,4*GEO_PERIOD,sensor=9,raw={'counts':8388607},quality=3,dropped=1), 4*GEO_PERIOD)
        writer.flush()
        rows = records(stream.getvalue())
        self.assertEqual([r['counts'] for r in rows], [[0],[8388607]])
        self.assertEqual(rows[1]['extra']['Groundlark']['quality'], 3)
        self.assertEqual(rows[1]['extra']['Groundlark']['dropped_before'], 1)
        self.assertEqual(writer.summary()['omitted_missing_or_fault'], 2)

    def test_unknown_calendar_omitted_and_simulation_origin_restricted(self):
        stream, writer = self.make()
        handshake(writer)
        writer.message(sample(), 0)
        writer.flush()
        self.assertEqual(stream.getvalue(), b'')
        self.assertEqual(writer.summary()['omitted_without_calendar_time'], 1)
        with self.assertRaisesRegex(ValueError, 'only allowed for simulation'):
            SeismicWriter(io.BytesIO(), dict(META, source='linux-polling'), simulation_start=ORIGIN)
        for bad in ('1970-01-01T00:00:00Z', '2024-01-01', '2024-02-30T00:00:00Z'):
            with self.assertRaises(ValueError): utc_origin(bad)

    def test_recorded_utc_is_exact_including_midnight_and_uncertainty(self):
        stream, writer = self.make()
        handshake(writer, (9,))
        for seq, unix in enumerate((EPOCH+999999999,EPOCH+1000000001)):
            value = sample(seq,seq*GEO_PERIOD,sensor=9,raw={'counts':seq})
            value.batch.samples[0].time.utc_unix_ns = unix
            value.batch.samples[0].time.utc_uncertainty_ns = 123
            writer.message(value, seq)
        writer.flush()
        rows = records(stream.getvalue())
        self.assertEqual([(r['year'],r['day'],r['hour'],r['nanos']) for r in rows],
                         [(2024,60,23,999999999),(2024,61,0,1)])
        self.assertTrue(all(r['flags']==0 and r['extra']['Groundlark']['utc_uncertainty_ns']==123 for r in rows))

    def test_host_clock_evidence_single_use_and_backward_step_rejected(self):
        stream, writer = self.make()
        handshake(writer, (9,))
        writer.event('miniseed_system_clock','test',10,raw_ns=100,unix_ns=EPOCH+100,bracket_ns=10)
        writer.message(sample(acquired=50,sensor=9,raw={'counts':1}),10)
        # Same arrival cannot reuse the preceding observation for another batch.
        writer.message(sample(1,60,sensor=9,raw={'counts':2}),10)
        writer.flush()
        self.assertEqual(writer.untimed, 1)
        row = records(stream.getvalue())[0]
        self.assertEqual(row['nanos'],50)
        self.assertEqual(row['extra']['Groundlark']['timing_source'],'unverified-system-clock')
        self.assertIsNone(row['extra']['Groundlark']['utc_uncertainty_ns'])
        writer.event('miniseed_system_clock','test',11,raw_ns=100,unix_ns=EPOCH,bracket_ns=10)
        with self.assertRaisesRegex(ValueError,'calendar time regressed'):
            writer.message(sample(2,70,sensor=9,raw={'counts':3}),11)

    def test_stale_or_wrong_arrival_clock_observation_does_not_map_sample(self):
        for arrival, raw in [(2,100),(1,6_000_000_000),(1,0)]:
            stream, writer = self.make()
            handshake(writer, (9,))
            writer.event('miniseed_system_clock','test',1,raw_ns=raw,unix_ns=EPOCH,bracket_ns=0)
            writer.message(sample(acquired=100,sensor=9,raw={'counts':1}),arrival)
            self.assertEqual(writer.untimed,1)
            self.assertEqual(stream.getvalue(),b'')

    def test_configuration_reset_and_device_boundaries(self):
        stream, writer = self.make(simulation_start=ORIGIN)
        handshake(writer)
        writer.message(sample(),0)
        cfg = dict(defaults()[0], period_ns=2*PERIOD)
        writer.message(m.configuration('pi',1,[cfg],revision=2),1)
        writer.message(sample(1,2*PERIOD,revision=2),2)
        handshake(writer,boot=2,arrival=3)
        writer.message(m.batch('pi',2,1,0,4*PERIOD,RAW),4)
        writer.flush()
        rows = [r['extra']['Groundlark'] for r in records(stream.getvalue()) if r['sid'].endswith('N_1')]
        self.assertEqual([r['boot'] for r in rows], ['1','1','2'])
        self.assertNotEqual(rows[0]['configuration_sha256'],rows[1]['configuration_sha256'])
        handshake(writer, device='other', arrival=5)
        with self.assertRaisesRegex(ValueError,'multiple HAT identities'):
            writer.message(m.batch('other',1,1,0,5*PERIOD,RAW),6)

    def test_unidentified_usb_disconnect_does_not_invalidate_pi(self):
        stream, writer = self.make(simulation_start=ORIGIN)
        handshake(writer)
        writer.event('usb_disconnected','no identity',0,device=None)
        writer.message(sample(),1)
        writer.flush()
        self.assertEqual(len(records(stream.getvalue())),6)

    def test_buffers_and_byte_budget_are_bounded(self):
        stream, writer = self.make(simulation_start=ORIGIN)
        handshake(writer,(9,))
        for seq in range(300):
            writer.message(sample(seq,seq*GEO_PERIOD,sensor=9,raw={'counts':seq}),seq)
        writer.flush()
        self.assertEqual([len(r['counts']) for r in records(stream.getvalue())],[128,128,44])
        stream, writer = self.make(simulation_start=ORIGIN,max_bytes=4096)
        handshake(writer)
        with self.assertRaisesRegex(RecordingError,'byte budget'):
            for seq in range(10):
                writer.message(sample(seq,seq*PERIOD+seq),seq)
                writer.flush()
        self.assertLessEqual(len(stream.getvalue()),4096)

    def test_short_write_is_an_error(self):
        class Short(io.BytesIO):
            def write(self,data): return super().write(data[:-1])
        writer = SeismicWriter(Short(),META,simulation_start=ORIGIN)
        handshake(writer)
        writer.message(sample(),0)
        with self.assertRaisesRegex(RecordingError,'short miniSEED write'): writer.flush()

    def test_mirror_records_clock_evidence_and_export_reproduces_live_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/'capture.ssrec', Path(directory)/'export.mseed'
            waveform = io.BytesIO()
            with source.open('wb') as stream:
                writer = Mirror(Writer(stream,META),SeismicWriter(waveform,META),
                    lambda: dict(raw_ns=100,unix_ns=EPOCH+100,bracket_ns=0))
                handshake(writer,(9,))
                writer.message(sample(acquired=50,sensor=9,raw={'counts':-123}),100)
                writer.event('acquisition_summary','done',101)
            result = export(source,output)
            self.assertTrue(result['source_completed'])
            self.assertEqual(output.read_bytes(),waveform.getvalue())
            with source.open('rb') as stream:
                items = list(Reader(stream))
            self.assertEqual(items[-1][1]['miniseed']['channel_samples'],1)
            with self.assertRaises(FileExistsError): export(source,output)

    def test_cli_dual_recording_and_offline_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output, exported = [Path(directory)/n for n in ('run.ssrec','run.mseed','export.mseed')]
            command = [sys.executable,str(ROOT/'sw/tools/sensor.py'),'simulate','--seconds','0.1',
                       '--output',str(source),'--miniseed',str(output),'--mseed-start-utc',ORIGIN]
            run = subprocess.run(command,check=True,capture_output=True,text=True,timeout=15)
            report = json.loads(run.stdout)
            self.assertTrue(report['completed'])
            self.assertGreater(report['miniseed']['channel_samples'],0)
            export(source,exported,simulation_start=ORIGIN)
            self.assertEqual(output.read_bytes(),exported.read_bytes())
            self.assertEqual(len({r['sid'] for r in records(output.read_bytes())}),19)

    def test_incomplete_prefix_reported_and_corrupt_record_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'run.ssrec'
            with source.open('wb') as stream:
                writer = Writer(stream,META)
                handshake(writer,(9,))
                writer.message(sample(sensor=9,raw={'counts':42}),0)
            result = export(source,Path(directory)/'prefix.mseed',simulation_start=ORIGIN)
            self.assertFalse(result['source_completed'])
            source.write_bytes(source.read_bytes()[:-1])
            with self.assertRaises(RecordingError):
                export(source,Path(directory)/'bad.mseed',simulation_start=ORIGIN)

    def test_cli_rejects_missing_origin_conflicts_and_reused_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/'run.ssrec', Path(directory)/'run.mseed'
            base = [sys.executable,str(ROOT/'sw/tools/sensor.py'),'simulate','--seconds','0.1','--output',str(source)]
            for options in (['--miniseed',str(output)],
                            ['--miniseed',str(output),'--no-miniseed'],
                            ['--miniseed',str(source),'--mseed-start-utc',ORIGIN]):
                result = subprocess.run(base+options,capture_output=True,text=True,timeout=15)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(source.exists())
                self.assertFalse(output.exists())
            output.write_bytes(b'keep original')
            result = subprocess.run(base+['--miniseed',str(output),'--mseed-start-utc',ORIGIN],
                                    capture_output=True,text=True,timeout=15)
            self.assertNotEqual(result.returncode,0)
            self.assertFalse(source.exists())
            self.assertEqual(output.read_bytes(),b'keep original')


if __name__ == '__main__': unittest.main()
