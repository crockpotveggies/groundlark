"""Deterministic M10 I2C/PPS fixture through the production timing driver.

The synthetic UTC epoch and ideal edges are simulation inputs, not measurements.
"""
from datetime import datetime, timezone
import struct

from .gnss_timing import TimedGNSS
from .sensors import ubx_packet
from .simulation import Simulated

SECOND = 1_000_000_000
EPOCH = 1790769600  # 2026-09-30 12:00:00 UTC, away from midnight guard.


class TimingBus:
    def __init__(self, scenario, clock):
        self.scenario, self.clock = scenario, clock
        self.model = Simulated(6, scenario=scenario, clock=clock)
        self.pending, self.configured, self.last = b'', False, -1

    def exchange(self, address, write, count):
        if address != 0x42:
            raise OSError('M10 fixture requires I2C address 0x42')
        if not count:
            if write[2:4] == b'\x06\x8a':
                self.fields = write[10:-2]
                self.pending = ubx_packet(5, 1, b'\x06\x8a')
            elif write[2:4] == b'\x06\x8b':
                self.pending = ubx_packet(6, 0x8b, b'\x01\0\0\0' + self.fields)
                self.configured = True
            else:
                raise OSError('Unexpected M10 fixture command')
            return b''
        if write == b'\xfd':
            second, phase = divmod(self.clock(), SECOND)
            if self.configured and not self.pending and second != self.last and phase >= 250_000_000:
                self.last = second
                state, _ = self.scenario.state_at(self.clock())
                locked = state['gnss_fix']
                stamp = EPOCH + second
                d = datetime.fromtimestamp(stamp, timezone.utc)
                nav = struct.pack('<IIiH6B', second * 1000, 25, 0,
                    d.year, d.month, d.day, d.hour, d.minute, d.second, 0x37 if locked else 0)
                week, tow = divmod(stamp + 1 - 315964800, 604800)
                pulse = struct.pack('<IIiHBB', tow * 1000, 0, 0, week, 3 if locked else 0, 0x30)
                self.pending = (ubx_packet(1, 7, self.model.read().raw['nav_pvt']) +
                    ubx_packet(1, 0x21, nav) + ubx_packet(0x0d, 1, pulse))
            return len(self.pending).to_bytes(2, 'big')
        result, self.pending = self.pending[:count], self.pending[count:]
        return result

    def close(self):
        pass


class GNSSSimulation:
    buffered = True

    def __init__(self, scenario, clock):
        self.scenario, self.clock = scenario, clock
        self.driver = TimedGNSS(TimingBus(scenario, clock), sleep=lambda _: None, clock_ns=clock)

    def configure(self, settings):
        return self.driver.configure(settings)

    def ready(self):
        return False

    def read(self):
        state, _ = self.scenario.state_at(self.clock())
        fault = state['sensor_faults'].get('6', 'none')
        if fault == 'timeout':
            raise TimeoutError('Modeled GNSS timeout')
        if fault in ('disconnect', 'nack', 'short_read'):
            raise OSError('Modeled GNSS ' + fault)
        return self.driver.read()

    def close(self):
        self.driver.close()


def emit_pps(scenario, now, emit):
    if now and now % SECOND == 0:
        state, _ = scenario.state_at(now)
        if state.get('gnss_pps', True) and state['sensor_faults'].get('6', 'none') != 'disconnect':
            emit('pps_edge', 'Modeled BCM24 rising edge; UTC requires correlation', now,
                 monotonic_ns=now, estimated_raw_ns=now,
                 mapping_monotonic_ns=now, mapping_bracket_ns=0)


def modeled_policy(digest):
    return dict(version=1, recording_sha256=digest, scope='modeled',
        evidence='Ideal GNSS fixture and 1 ms simulation clock; not physical qualification',
        transport_max_ns=100_000_000, edge_error_ns=1000, pulse_error_ns=1000,
        capture_age_max_ns=200_000_000, clock_rate_ppm=100,
        sample_error_ns={str(s): 1000 for s in (1, 2, 3, 6, 8, 9)})
