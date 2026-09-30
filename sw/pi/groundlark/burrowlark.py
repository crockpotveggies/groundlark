"""Burrowlark SHT45 fixed heater-off profile and injected-bus acquisition.

The MCU port/USB firmware remains separate. This bounded driver is exercised
against a command-aware modeled bus by the browser's sensor simulation.
"""
import time

from groundlark_contract.validation import sht_crc
from .sensors import Reading

SETTINGS = dict(sensor_id=17, enabled=True, period_ns=1_000_000_000)


def decode_frame(frame):
    if len(frame) != 6:
        raise OSError("short SHT45 response")
    if any(sht_crc(frame[i:i+2]) != frame[i+2] for i in (0, 3)):
        raise OSError("SHT45 CRC mismatch")
    return Reading(dict(response=bytes(frame)))


class SHT45:
    """Bus exposes write(address, bytes) and read(address, count), with STOP.

    High precision command 0xFD; wait beyond 8.3 ms maximum conversion time.
    No heater command is exposed. A worker must bound real bus I/O timeouts.
    """
    ADDRESS = 0x44

    def __init__(self, bus, sleep=time.sleep):
        self.bus, self.sleep = bus, sleep

    def configure(self, settings):
        if settings != SETTINGS:
            raise ValueError("unsupported SHT45 heater-off 1 Hz profile")
        self.bus.write(self.ADDRESS, b"\x94")
        self.sleep(.001)
        return dict(settings)

    def read(self):
        self.bus.write(self.ADDRESS, b"\xfd")
        self.sleep(.009)
        return decode_frame(self.bus.read(self.ADDRESS, 6))

    def close(self):
        self.bus.close()


class ModeledBus:
    """Ideal transfer function with command/conversion-delay enforcement."""
    def __init__(self, temperature, humidity):
        self.temperature, self.humidity = temperature, humidity
        self.elapsed, self.ready = 0., None

    def write(self, address, data):
        if address != 0x44 or data not in (b"\x94", b"\xfd"):
            raise OSError("unsupported SHT45 address/command; heater forbidden")
        self.ready = None if data == b"\x94" else self.elapsed + .0083

    def sleep(self, seconds):
        self.elapsed += seconds

    def read(self, address, count):
        if address != 0x44 or count != 6 or self.ready is None or self.elapsed < self.ready:
            raise OSError("SHT45 conversion not ready")
        self.ready = None
        from .skylark import climate_frame
        return climate_frame(self.temperature, self.humidity)

    def close(self):
        pass


def modeled_reading(scenario, now, seed):
    from .stimulus import signal
    state, _ = scenario.state_at(now)
    temperature = signal(state['temperature_c'], now, seed, 17, 'temperature_c')[0]
    humidity = signal(state['humidity_percent'], now, seed, 17, 'humidity_percent')[0]
    bus = ModeledBus(temperature, humidity)
    driver = SHT45(bus, sleep=bus.sleep)
    driver.configure(SETTINGS)
    return driver.read()
