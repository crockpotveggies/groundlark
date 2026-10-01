"""Fitted DLVR-F50D fast-mode I2C sensor; preserve its four raw bytes."""
from .sensors import Reading, NotReady

SETTINGS = dict(sensor_id=8, enabled=True, period_ns=10_000_000,
                pressure_min_pa=-125, pressure_max_pa=125,
                pressure_part_number='DLVR-F50D-E1BS-I-NI3F')


class DLVR:
    def __init__(self, bus): self.bus = bus

    def configure(self, cfg):
        if any(cfg.get(k) != v for k, v in SETTINGS.items()):
            raise ValueError('DLVR requires the fitted F50D fast-mode profile')
        # This factory-configured part has no writable range or identity register.
        self.read()
        return cfg

    def read(self):
        data = self.bus.exchange(0x28, b'', 4)
        if len(data) != 4: raise OSError('short DLVR response')
        status = data[0] >> 6
        if status == 2: raise NotReady('DLVR busy/stale response')
        if status: raise OSError('DLVR command/diagnostic state')
        return Reading(dict(response=data))
