"""Autonomous ADC reads with bounded delivery to the recording process.

DRDY wakes the reader; timestamps remain RAW read-completion times. GPIO event
timestamps are deliberately not relabeled as conversion timestamps.
"""
from collections import deque
from dataclasses import dataclass, field
import threading
import time
from .fifo import Drain
from .sensors import Reading, NotReady, DataGap


@dataclass
class CaptureDrain(Drain):
    gaps: dict = field(default_factory=dict)


class CaptureBuffer:
    """Preserve the queued prefix, then one unknown-loss marker on overflow."""
    def __init__(self, capacity=256):
        if not 1 <= capacity <= 256: raise ValueError('ADC buffer capacity')
        self.capacity = capacity
        self.items = deque()
        self.overflow = None
        self.error = None
        self.lock = threading.Lock()

    def put(self, reading, gap=None):
        with self.lock:
            if self.overflow is not None or len(self.items) == self.capacity:
                self.overflow = Reading(None, 2, reading.acquisition_ns)
            else:
                self.items.append((reading, gap))

    def fail(self, error):
        with self.lock: self.error = str(error)[:160]

    def read(self):
        with self.lock:
            readings, gaps = [], {}
            while self.items and len(readings) < 32:
                reading, gap = self.items.popleft()
                if gap: gaps[len(readings)] = gap
                readings.append(reading)
            if not self.items and self.overflow is not None and len(readings) < 32:
                gaps[len(readings)] = 'ADC delivery buffer overflow; physical loss unknown'
                readings.append(self.overflow)
                self.overflow = None
            if not readings and self.error is not None: raise OSError(self.error)
            return CaptureDrain(readings, gaps)


class AutonomousADC:
    """Reader thread inside the killable sensor worker, independent of IPC stalls."""
    def __init__(self, device, edges, clock_ns=None):
        self.device, self.edges = device, edges
        self.clock = clock_ns or (lambda: time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW))
        self.buffer = CaptureBuffer()
        self.stop = threading.Event()
        self.thread = None
        self.progress = time.monotonic()

    def configure(self, settings):
        effective = self.device.configure(settings)
        self.progress = time.monotonic()
        self.thread = threading.Thread(target=self.capture, name='geophone-drdy', daemon=True)
        self.thread.start()
        return effective

    def capture(self):
        try:
            while not self.stop.is_set():
                # A missed GPIO edge still gets a readiness check within 20 ms.
                # Multiple queued edges cannot recover overwritten ADC registers.
                self.edges.wait(.02)
                if self.stop.is_set(): break
                gap = None
                try: reading = self.device.read()
                except NotReady: reading = Reading(None, 2)
                except DataGap as error:
                    reading, gap = Reading(None, 2), str(error)[:160]
                reading.acquisition_ns = self.clock()
                self.buffer.put(reading, gap)
                self.progress = time.monotonic()
        except Exception as error:
            # Preserve the valid prefix before reporting the terminal bus fault.
            # The parent worker deadline also bounds a stuck kernel bus call.
            self.buffer.fail(error)

    def read(self):
        if time.monotonic() - self.progress > .25:
            self.stop.set()
            self.buffer.fail('ADC reader deadline exceeded')
        return self.buffer.read()

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(.25)
            if self.thread.is_alive(): raise TimeoutError('ADC reader did not stop')
        try: self.edges.close()
        finally: self.device.close()
