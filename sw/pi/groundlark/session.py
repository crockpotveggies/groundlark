"""Bounded, transactional cross-message validation for live input and replay."""
from dataclasses import dataclass, field
from groundlark_contract.validation import validate, require


@dataclass
class State:
    boot: int
    identity: bytes
    sensors: frozenset
    retired: set = field(default_factory=set)
    configuration: bytes = b""
    revision: int = 0
    settings: dict = field(default_factory=dict)
    last: dict = field(default_factory=dict)
    identity_seen: bool = True
    config_seen: bool = False
    dropped_totals: dict = field(default_factory=dict)
    board: int = 0


class Sessions:
    def __init__(self, calibrations=None, max_devices=4, max_resets=32):
        if not 1 <= max_devices <= 16 or not 1 <= max_resets <= 256:
            raise ValueError("session capacity outside supported bounds")
        self.devices = {}
        self.max_devices, self.max_resets = max_devices, max_resets
        self.calibrations = calibrations

    def disconnect(self, device=None):
        for key, state in self.devices.items():
            if device is None or key == device:
                state.identity_seen = state.config_seen = False

    def accept(self, message):
        validate(message)
        device, boot, kind = message.device_id, message.boot_id, message.WhichOneof("body")
        state = self.devices.get(device)
        if kind == "identity":
            wire = message.identity.SerializeToString(deterministic=True)
            if state is not None and state.boot == boot:
                require(state.identity == wire, "identity changed within boot")
                state.identity_seen = True
                return kind
            retired = set() if state is None else state.retired | {state.boot}
            require(boot not in retired, "retired boot replay")
            require(len(retired) <= self.max_resets, "reset history exhausted; open a new recording")
            require(state is not None or len(self.devices) < self.max_devices, "device capacity exhausted")
            self.devices[device] = State(boot, wire, frozenset(message.identity.sensors), retired, board=message.identity.board)
            return kind
        require(state is not None and state.boot == boot and state.identity_seen, "identity handshake required")
        if kind == "configuration":
            c = message.configuration
            require({s.sensor_id for s in c.sensors} <= state.sensors, "configuration for undeclared sensor")
            wire = c.SerializeToString(deterministic=True)
            require(c.revision >= state.revision, "stale configuration")
            if c.revision == state.revision:
                require(wire == state.configuration, "configuration changed without revision")
            state.configuration, state.revision = wire, c.revision
            state.settings = {s.sensor_id: type(s).FromString(s.SerializeToString()) for s in c.sensors}
            state.config_seen = True
        elif kind == "status":
            s = message.status
            require(s.sensor_id == 0 or s.sensor_id in state.sensors, "status for undeclared sensor")
            if s.HasField("dropped_total"):
                require(s.dropped_total >= state.dropped_totals.get(s.sensor_id, 0), "loss total regressed")
                state.dropped_totals[s.sensor_id] = s.dropped_total
        else:
            b = message.batch
            require(state.config_seen and b.configuration_revision == state.revision, "effective configuration required")
            cfg = state.settings.get(b.sensor_id)
            require(cfg is not None and cfg.enabled, "sensor not enabled")
            if b.sensor_id == 8:
                require(all(s.time.domain == (1 if state.board == 1 else 2) for s in b.samples),
                        'pressure clock does not match board identity')
            previous = state.last.get(b.sensor_id)
            first, last = b.samples[0], b.samples[-1]
            next_sequence = 0 if previous is None else previous[0] + 1
            require(first.sequence >= next_sequence, "duplicate or reordered sample")
            if b.HasField("dropped_before"):
                require(first.sequence - next_sequence == b.dropped_before, "sequence gap disagrees with loss count")
            if previous is not None:
                require(first.time.acquisition_ns > previous[1], "acquisition clock moved backwards")
            if b.calibration_id:
                require(self.calibrations is not None, "calibration metadata missing")
                self.calibrations.verify(b.calibration_id, b.sensor_id, cfg, device)
            state.last[b.sensor_id] = (last.sequence, last.time.acquisition_ns)
        return kind
