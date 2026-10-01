"""Bounded, offline PPS/TIM-TP association. No extrapolation or clock setting.

All bounds are supplied with evidence and bound to the input recording hash.
POSIX cannot represent a leap second: conservatively omit UTC around midnight.
"""
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timezone
import hashlib
import re
import struct
from .calibration import canonical
from .gnss_timing import configuration_evidence
from .recording import Reader, Writer
from .session import Sessions
from .calibration import Calibrations

S = 1_000_000_000
WEEK = 604800
GPS_EPOCH = 315964800
MAX_EVENTS = 32768


def integer(value, lo, hi, name):
    if type(value) is not int or not lo <= value <= hi: raise ValueError(name)
    return value


def policy_check(policy, digest, source):
    required = {'version', 'recording_sha256', 'evidence', 'scope', 'transport_max_ns',
                'edge_error_ns', 'pulse_error_ns', 'capture_age_max_ns',
                'clock_rate_ppm', 'sample_error_ns'}
    if not isinstance(policy, dict) or set(policy) != required or type(policy['version']) is not int or policy['version'] != 1:
        raise ValueError('UTC policy fields/version')
    if policy['recording_sha256'] != digest: raise ValueError('UTC policy recording hash mismatch')
    if not isinstance(policy['evidence'], str) or not 1 <= len(policy['evidence']) <= 256:
        raise ValueError('UTC policy evidence required')
    if policy['scope'] != ('modeled' if source == 'modeled-timing' else 'bench'):
        raise ValueError('UTC policy scope does not match recording')
    for key, high in [('transport_max_ns', 400_000_000), ('edge_error_ns', 10_000_000),
                      ('pulse_error_ns', 10_000_000), ('capture_age_max_ns', 500_000_000),
                      ('clock_rate_ppm', 5000)]: integer(policy[key], 1, high, key)
    if not isinstance(policy['sample_error_ns'], dict) or not policy['sample_error_ns']:
        raise ValueError('per-sensor acquisition error bounds required')
    for key, value in policy['sample_error_ns'].items():
        if key not in ('1', '2', '3', '4', '5', '6', '8', '9'): raise ValueError('local sensor bounds only')
        integer(value, 1, 100_000_000, 'sample error')


def tim_tp(payload):
    if len(payload) != 16: raise ValueError('TIM-TP length')
    tow, sub, qerr, week, flags, ref = struct.unpack('<IIiHBB', payload)
    if flags & 3 != 3 or flags & 0x30 or flags & 0xc0: raise ValueError('TIM-TP unlocked/invalid UTC/error')
    if ref >> 4 not in range(1, 9): raise ValueError('unknown UTC standard')
    if tow >= WEEK * 1000 or tow % 1000 or sub: raise ValueError('TIM-TP not whole UTC second')
    utc = (GPS_EPOCH + week * WEEK) * S + tow * 1_000_000
    if not 946684800 * S <= utc < 4102444800 * S: raise ValueError('TIM-TP date outside 2000..2099')
    # qErr is not applied with an assumed sign: its magnitude enlarges the bound.
    return utc, (abs(qerr) + 999) // 1000, ref >> 4


def timeutc(payload):
    if len(payload) != 20: raise ValueError('TIMEUTC length')
    tow, accuracy, nano, year, month, day, hour, minute, second, flags = struct.unpack('<IIiH6B', payload)
    if flags & 7 != 7 or flags >> 4 not in range(1, 9) or accuracy > 100_000_000:
        raise ValueError('TIMEUTC invalid or insufficiently resolved')
    if not 2000 <= year < 2100 or not -S < nano < S or tow >= WEEK * 1000:
        raise ValueError('TIMEUTC range')
    if second == 60: raise ValueError('leap second has no unambiguous POSIX mapping')
    stamp = int(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp()) * S + nano
    return stamp, accuracy, flags >> 4


def midnight_guard(utc):
    day = utc % (86400 * S)
    return day < 5 * S or day >= (86400 - 5) * S


def intervals(events, policy):
    """Associate only one timely, valid TIM-TP and TIMEUTC per observed pulse."""
    if len(events) > MAX_EVENTS: raise ValueError('timing event bound')
    counts = Counter()
    edges, messages, barriers = [], [], []
    configured = False
    for arrival, event in events:
        code = event['code']
        if code == 'gnss_timing_config':
            if event.get('effective') != configuration_evidence(): raise ValueError('timing configuration readback evidence')
            configured = True
            barriers.append(arrival)
        elif code == 'timing_fault': barriers.append(arrival)
        elif code == 'pps_edge':
            raw = integer(event.get('estimated_raw_ns'), 0, 1 << 63, 'PPS RAW time')
            mono = integer(event.get('monotonic_ns'), 0, 1 << 63, 'PPS MONOTONIC time')
            mapped = integer(event.get('mapping_monotonic_ns'), mono, 1 << 63, 'PPS clock bridge')
            bracket = integer(event.get('mapping_bracket_ns'), 0, 10_000_000, 'PPS bridge bracket')
            age = mapped - mono
            if age > policy['capture_age_max_ns'] or raw > arrival:
                barriers.append(arrival); counts['stale_edge'] += 1; continue
            error = policy['edge_error_ns'] + (bracket + 1)//2 + (age * policy['clock_rate_ppm'] + 999999)//1_000_000
            edges.append((raw, error))
        elif code in ('gnss_tim_tp', 'gnss_timeutc'):
            start = integer(event.get('read_start_ns'), 0, arrival, 'timing read start')
            end = integer(event.get('read_end_ns'), start, arrival, 'timing read end')
            if not configured: counts['before_configuration'] += 1; continue
            messages.append((start, end, code, event.get('payload_hex')))
    if not configured: raise ValueError('no acknowledged/read-back timing configuration')
    times = [t for t, _ in edges]
    if times != sorted(set(times)): raise ValueError('PPS duplicate or backward timestamp')
    buckets = {}
    for start, end, kind, payload in messages:
        index = bisect_right(times, end)
        if not 0 < index < len(edges): counts['unbracketed_message'] += 1; continue
        before, before_error = edges[index - 1]
        after, after_error = edges[index]
        bucket = buckets.setdefault(index, [])
        # Do not silently ignore an ambiguous packet and accept another one.
        if start <= before + before_error or end - policy['transport_max_ns'] <= before + before_error or end >= after - after_error:
            bucket.append(('ambiguous', None)); counts['ambiguous_transport'] += 1; continue
        try:
            if not isinstance(payload, str) or len(payload) > 40 or not re.fullmatch('[0-9a-f]+', payload):
                raise ValueError('timing payload encoding')
            value = (tim_tp if kind == 'gnss_tim_tp' else timeutc)(bytes.fromhex(payload))
            bucket.append((kind, value))
        except ValueError:
            bucket.append(('invalid', None)); counts['invalid_timing'] += 1
    anchors = {}
    for index, bucket in buckets.items():
        kinds = Counter(k for k, _ in bucket)
        if kinds != {'gnss_tim_tp': 1, 'gnss_timeutc': 1}:
            counts['ambiguous_or_missing_pair'] += 1; continue
        pair = dict(bucket)
        utc, qerr, standard = pair['gnss_tim_tp']
        nav, accuracy, nav_standard = pair['gnss_timeutc']
        if standard != nav_standard or not 0 < utc - nav < 1_100_000_000 or midnight_guard(utc) or midnight_guard(nav):
            counts['calendar_or_leap_guard'] += 1; continue
        raw, edge_error = edges[index]
        if any(times[index - 1] - S <= b <= raw + S for b in barriers):
            counts['configuration_or_fault_guard'] += 1; continue
        anchors[index] = (raw, utc, edge_error + policy['pulse_error_ns'] + accuracy + qerr)
    result = []
    for index, left in sorted(anchors.items()):
        right = anchors.get(index + 1)
        if right is None: continue
        duration = right[0] - left[0]
        allowed = policy['clock_rate_ppm'] * 1000 + left[2] + right[2]
        if right[1] - left[1] != S or abs(duration - S) > allowed:
            counts['pulse_or_utc_discontinuity'] += 1; continue
        result.append(dict(raw_start_ns=left[0], raw_end_ns=right[0], utc_start_ns=left[1],
                           anchor_error_ns=max(left[2], right[2])))
    return result, dict(counts)


def correlate(source, output, policy):
    """Two streaming passes; retain at most 32768 timing events, never all samples."""
    from .cli import replay
    if not replay(source)['completed']: raise ValueError('complete input recording required')
    with open(source, 'rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    events, local_owners = [], set()
    with open(source, 'rb') as stream:
        reader = Reader(stream)
        metadata = reader.metadata
        if metadata.get('utc_capture') != 'm10-tim-tp-v1' or 'utc_correlation' in metadata:
            raise ValueError('original UTC-capture recording required')
        if metadata.get('source') not in ('linux-fifo', 'modeled-timing'): raise ValueError('UTC recording source')
        policy_check(policy, digest, metadata['source'])
        for arrival, item in reader:
            if isinstance(item, dict):
                if item.get('code') in ('pps_edge', 'gnss_timing_config', 'gnss_tim_tp', 'gnss_timeutc'):
                    events.append((arrival, item))
            elif item.WhichOneof('body') == 'status' and item.status.sensor_id == 6 and item.status.code != 1:
                events.append((arrival, dict(code='timing_fault')))
            elif item.WhichOneof('body') == 'identity' and item.identity.board == 1:
                local_owners.add((item.device_id, item.boot_id))
            elif item.WhichOneof('body') == 'batch' and any(s.time.HasField('utc_unix_ns') for s in item.batch.samples):
                raise ValueError('input already has UTC estimates')
            if len(events) > MAX_EVENTS: raise ValueError('timing event bound')
    if len(local_owners) != 1: raise ValueError('UTC requires one local Pi producer and boot per capture')
    spans, rejected = intervals(events, policy)
    if not spans: raise ValueError('no unambiguous consecutive UTC pulse pairs')
    starts = [x['raw_start_ns'] for x in spans]
    report = dict(version=1, source_sha256=digest, policy_sha256=hashlib.sha256(canonical(policy)).hexdigest(),
                  scope=policy['scope'], evidence=policy['evidence'], intervals=spans, rejected=rejected,
                  samples_correlated=0, samples_unlabelled=0, qualification='conditional on supplied timing bounds')
    with open(source, 'rb') as src, open(output, 'xb') as dst:
        reader = Reader(src)
        header = dict(metadata, utc_correlation=dict(policy=policy, source_sha256=digest, algorithm='bracketed-utc-v1'))
        writer = Writer(dst, header)
        sessions = Sessions(Calibrations(metadata.get('calibrations', [])), checkpoint=metadata.get("session_checkpoint"))
        for arrival, item in reader:
            if isinstance(item, dict):
                if item.get('code') == 'usb_disconnected' and item.get('device') is not None:
                    sessions.disconnect(item['device'])
                writer.record(2, canonical(item), arrival)
                continue
            if item.WhichOneof('body') == 'batch':
                sid = str(item.batch.sensor_id)
                for sample in item.batch.samples:
                    stamp = sample.time
                    if stamp.HasField('utc_unix_ns'): raise ValueError('input already has UTC estimates')
                    raw = stamp.acquisition_ns
                    index = bisect_right(starts, raw) - 1
                    error = policy['sample_error_ns'].get(sid)
                    if error is not None and stamp.HasField('uncertainty_ns'): error = max(error, stamp.uncertainty_ns)
                    span = spans[index] if index >= 0 else None
                    if stamp.domain != 1 or error is None or span is None or sample.quality not in (1, 3) or not span['raw_start_ns'] + error <= raw <= span['raw_end_ns'] - error:
                        report['samples_unlabelled'] += 1; continue
                    delta, duration = raw - span['raw_start_ns'], span['raw_end_ns'] - span['raw_start_ns']
                    estimate = span['utc_start_ns'] + (delta * S + duration//2)//duration
                    variation = (2 * min(delta, duration-delta) * policy['clock_rate_ppm'] + 999999)//1_000_000
                    stamp.utc_unix_ns = estimate
                    stamp.utc_uncertainty_ns = span['anchor_error_ns'] + (error * S + duration-1)//duration + variation + 1
                    report['samples_correlated'] += 1
            sessions.accept(item)
            writer.message(item, arrival)
    with open(output, 'rb') as stream: report['output_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return report
