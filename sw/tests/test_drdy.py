"""ADC delivery, consumer stalls, loss markers and worker isolation fixtures."""
import io
import queue
import struct
import time
import unittest
from unittest.mock import patch
from groundlark.drdy import AutonomousADC, CaptureBuffer
from groundlark.geophone import ADS122C04, SETTINGS
from groundlark.sensors import Reading, DataGap
from groundlark.linux_io import FallingEdges, RisingEdges
from groundlark.runtime import Acquisition, Channel
from groundlark.recording import Writer, Reader
from groundlark.session import Sessions
from groundlark.worker import Worker
from test_geophone import WireBus


class Steps:
    def __init__(self, bus):
        self.queue = queue.Queue()
        self.bus = bus
    def wait(self, timeout):
        try: self.bus.counter, self.bus.word = self.queue.get(timeout=timeout)
        except queue.Empty: pass
    def close(self): pass


class ClockedDevice:
    """Conversion clock is independent of the parent's IPC read requests."""
    def configure(self, settings):
        self.origin = time.perf_counter_ns(); self.calls = 0
        return settings
    def read(self):
        self.calls += 1
        if self.calls == 3: raise DataGap('fixture conversion gap')
        n = (time.perf_counter_ns() - self.origin) // 10_000_000
        return Reading(dict(counts=int(n), conversion_counter=int(n) % 256))
    def close(self): pass


class ClockedEdges:
    def wait(self, timeout): time.sleep(.01)
    def close(self): pass


class ClockedFactory:
    drdy = True
    def __call__(self): return AutonomousADC(ClockedDevice(), ClockedEdges(), time.perf_counter_ns)


class StuckDevice(ClockedDevice):
    def read(self): time.sleep(10)


class StuckFactory:
    drdy = True
    def __call__(self): return AutonomousADC(StuckDevice(), ClockedEdges(), time.perf_counter_ns)


class DrdyTests(unittest.TestCase):
    def test_overflow_preserves_prefix_and_inserts_ordered_unknown_loss(self):
        buffer = CaptureBuffer(3)
        for n in range(1, 10): buffer.put(Reading(dict(counts=n, conversion_counter=n), 1, n))
        result = buffer.read()
        self.assertEqual([r.raw['counts'] for r in result.readings[:3]], [1, 2, 3])
        self.assertEqual(result.readings[-1], Reading(None, 2, 9))
        self.assertIn('overflow', result.gaps[3])
        buffer.put(Reading(dict(counts=10, conversion_counter=10), 1, 10))
        self.assertEqual(buffer.read().readings[0].raw['counts'], 10)

    def test_full_delivery_bounds_and_terminal_fault_after_prefix(self):
        buffer = CaptureBuffer()
        for n in range(300): buffer.put(Reading({}, 1, n))
        buffer.fail('broken bus')
        output = []
        for _ in range(9):
            drain = buffer.read()
            self.assertLessEqual(len(drain.readings), 32)
            output.extend(drain.readings)
        self.assertEqual([r.acquisition_ns for r in output], list(range(256)) + [299])
        with self.assertRaisesRegex(OSError, 'broken bus'): buffer.read()

    def test_conversion_gaps_survive_thread_without_reset_or_losing_prefix(self):
        bus = WireBus()
        edges = Steps(bus)
        adc = AutonomousADC(ADS122C04(bus, sleep=lambda _: None), edges, time.perf_counter_ns)
        adc.configure(SETTINGS)
        try:
            # Feed independently chosen counter values, including an overwrite.
            for n, value in ((1, -8388607), (5, 55), (6, 123456)):
                edges.queue.put((n, value))
                deadline = time.monotonic() + 1
                while (adc.device.counter != n or edges.queue.qsize()) and time.monotonic() < deadline:
                    time.sleep(.001)
                self.assertEqual(adc.device.counter, n)
            adc.close()
            drain = adc.read()
            valid = [r for r in drain.readings if r.raw is not None]
            self.assertEqual([r.raw['counts'] for r in valid], [-8388607, 123456])
            self.assertTrue(any('gap' in detail for detail in drain.gaps.values()))
            self.assertEqual(bus.writes.count(b'\x06'), 1)
            self.assertEqual(bus.writes.count(b'\x08'), 1)
        finally:
            if adc.thread.is_alive(): adc.close()

    def test_worker_captures_during_parent_pause_and_preserves_ipc_gap_metadata(self):
        worker = Worker(ClockedFactory(), SETTINGS, startup_timeout=5)
        try:
            worker.configure()
            time.sleep(.12)
            drain = worker.read()
            self.assertGreaterEqual(len(drain.readings), 3)
            stamps = [r.acquisition_ns for r in drain.readings]
            self.assertEqual(stamps, sorted(set(stamps)))
            self.assertTrue(worker.buffered)
            self.assertIn('fixture conversion gap', drain.gaps.values())
            self.assertTrue(any(r.raw is None for r in drain.readings))
        finally: worker.close()

    def test_real_stuck_reader_faults_and_worker_is_reaped(self):
        worker = Worker(StuckFactory(), SETTINGS, startup_timeout=5)
        try:
            worker.configure()
            time.sleep(.3)
            with self.assertRaisesRegex(OSError, 'deadline'): worker.read()
            began = time.monotonic()
            worker.close()
            self.assertLess(time.monotonic() - began, 2)
            self.assertIsNone(worker.process)
        finally: worker.close()

    def test_stuck_reader_is_not_an_ever_healthy_empty_buffer(self):
        adc = AutonomousADC(ClockedDevice(), ClockedEdges(), time.perf_counter_ns)
        adc.progress = time.monotonic() - 1
        with self.assertRaisesRegex(OSError, 'deadline'): adc.read()
        self.assertTrue(adc.stop.is_set())

    def test_gpio_falling_wire_events_reject_rising_and_partial_records(self):
        edges = object.__new__(FallingEdges); edges.fd = 42
        self.assertEqual(edges.edge_kind, 2)
        self.assertEqual(RisingEdges.edge_kind, 1)
        with patch('groundlark.linux_io.os.read', return_value=struct.pack('=QI4x', 123, 2)):
            self.assertEqual(edges.read(), [123])
        for data in (struct.pack('=QI4x', 123, 1), b'bad'):
            with patch('groundlark.linux_io.os.read', return_value=data):
                with self.assertRaises(OSError): edges.read()

    def test_recording_preserves_buffered_samples_gap_and_recovery(self):
        buffer = CaptureBuffer(2)
        class Adapter:
            buffered = True
            def configure(self, settings): return settings
            def ready(self): return True
            def read(self): return buffer.read()
        stream = io.BytesIO()
        channel = Channel('pi', 1, dict(SETTINGS), Adapter())
        app = Acquisition(Writer(stream, {'format': 'groundlark-acquisition-v1'}), Sessions(), [channel])
        app.start(0)
        for n in (1, 2, 3, 4): buffer.put(Reading(dict(counts=-n, conversion_counter=n), 1, n))
        app.tick(lambda: 100)
        buffer.put(Reading(dict(counts=-5, conversion_counter=5), 1, 101))
        app.tick(lambda: 200)
        app.finish(201)
        stream.seek(0)
        items = [m for _, m in Reader(stream) if not isinstance(m, dict)]
        batches = [m.batch for m in items if m.WhichOneof('body') == 'batch']
        self.assertEqual([b.samples[0].sequence for b in batches], [0, 1, 2, 3])
        self.assertEqual([b.samples[0].quality for b in batches], [1, 1, 2, 1])
        self.assertEqual([b.samples[0].time.acquisition_ns for b in batches], [1, 2, 4, 101])
        self.assertTrue(all(not b.HasField('dropped_before') for b in batches))
        self.assertTrue(any(m.WhichOneof('body') == 'status' and m.status.code == 4 for m in items))
        self.assertEqual(app.missing, 1)
        self.assertEqual(channel.failures, 0)


if __name__ == '__main__': unittest.main()
