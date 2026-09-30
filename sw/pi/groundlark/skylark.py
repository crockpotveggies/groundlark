"""Skylark fixed Rev A profile and ideal environmental stimulus.

Gas channels remain separate raw ADC counts. No calibrated gas concentration
or outdoor detection limit is inferred from the nominal sensitivity model.
"""
import struct
from groundlark_contract.validation import sht_crc
from .sensors import Reading

SENSORS = tuple(range(10, 17))
NAMES = {10: 'SO₂ working', 11: 'SO₂ auxiliary', 12: 'H₂S working',
         13: 'H₂S auxiliary', 14: 'Particulate', 15: 'Temperature / humidity',
         16: 'Barometer'}


def defaults():
    return [dict(sensor_id=i, enabled=True, period_ns=32_000_000 if i < 14 else 1_000_000_000)
            for i in SENSORS]


def pms_frame(pm25):
    data = bytearray(32)
    data[:4] = b'\x42\x4d\x00\x1c'
    for offset, scale in ((4, .6), (6, 1), (8, 1.3), (10, .6), (12, 1), (14, 1.3)):
        struct.pack_into('>H', data, offset, max(0, min(65535, round(pm25 * scale))))
    data[28] = 1
    struct.pack_into('>H', data, 30, sum(data[:30]))
    return bytes(data)


def climate_frame(temperature, humidity):
    def word(value):
        data = max(0, min(65535, round(value))).to_bytes(2, 'big')
        return data + bytes([sht_crc(data)])
    return word((temperature + 45) * 65535 / 175) + word((humidity + 6) * 65535 / 125)


def modeled_reading(sensor, scenario, now, seed):
    from .stimulus import signal
    state, _ = scenario.state_at(now)
    def value(key): return signal(state[key], now, seed, sensor, key)[0]
    if sensor < 14:
        volts = 1.25
        if sensor in (10, 12): volts += value('so2_ppm' if sensor == 10 else 'h2s_ppm') * (.04 if sensor == 10 else .034)
        count = round(volts / 2.5 * 8388608)
        return Reading(dict(counts=max(-8388608, min(8388607, count)),
                            conversion_counter=((now // 32_000_000) * 4 + sensor - 10) % 256),
                       3 if not -8388608 < count < 8388607 else 1)
    if sensor == 14: return Reading(dict(response=pms_frame(value('pm25_ug_m3'))))
    if sensor == 15: return Reading(dict(response=climate_frame(value('temperature_c'), value('humidity_percent'))))
    # Deliberately synthetic trim, chosen to give T=25 C and linear pressure.
    # Raw data are retained; this does not model Bosch factory variation.
    trim = struct.pack('<HHbhhbbHHbbhbb', 25600, 32768, 0, 24576, 16384, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    pressure = max(0, min(16777215, round(value('ambient_pressure_pa') * 128)))
    temp = max(0, min(16777215, round(value('temperature_c') * 32768 + 6553600)))
    return Reading(dict(response=pressure.to_bytes(3, 'little') + temp.to_bytes(3, 'little'), calibration=trim))


def barometer_units(response, trim):
    """Bosch BMP3 floating-point factory compensation (datasheet section 3.11)."""
    t1,t2,t3,p1,p2,p3,p4,p5,p6,p7,p8,p9,p10,p11 = struct.unpack('<HHbhhbbHHbbhbb', trim)
    pt, tt = int.from_bytes(response[:3], 'little'), int.from_bytes(response[3:], 'little')
    dt = tt - t1 * 256
    temperature = dt * t2 / 2**30 + dt**2 * t3 / 2**48
    offset = p5 * 8 + p6 / 64 * temperature + p7 / 256 * temperature**2 + p8 / 32768 * temperature**3
    scale = (p1 - 16384) / 2**20 + (p2 - 16384) / 2**29 * temperature + p3 / 2**32 * temperature**2 + p4 / 2**37 * temperature**3
    pressure = offset + pt * scale + pt**2 * (p9 / 2**48 + p10 / 2**48 * temperature) + pt**3 * p11 / 2**65
    return pressure, temperature
