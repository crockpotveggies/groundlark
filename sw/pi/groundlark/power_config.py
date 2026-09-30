"""Validate the optional DAQHAT-01 supervisor policy; no hardware I/O.

Battery values deliberately have no defaults. This schema is the handoff to
future MSPM0 firmware; loading it does not program or enable the supervisor.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PowerPolicy:
    battery_description: str
    shutdown_v: float
    restart_v: float
    shutdown_confirm_s: float
    restart_confirm_s: float
    shutdown_timeout_s: float
    minimum_off_s: float


def load_policy(config: dict) -> PowerPolicy | None:
    """Return None for an explicitly disabled policy; reject unsafe settings."""
    if type(config.get("enabled")) is not bool:
        raise ValueError("enabled must be a boolean")
    if not config["enabled"]:
        return None
    description = config.get("battery_description")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Select and describe the protected battery/controller first")
    fields = ("shutdown_v", "restart_v", "shutdown_confirm_s",
              "restart_confirm_s", "shutdown_timeout_s", "minimum_off_s")
    values = {}
    for key in fields:
        value = config.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number; placeholders cannot enable power")
        values[key] = float(value)
    if not 8.5 <= values["shutdown_v"] <= 17.5:
        raise ValueError("shutdown_v must leave margin above the 8 V hardware minimum")
    if not values["shutdown_v"] + .5 <= values["restart_v"] <= 18:
        raise ValueError("restart_v must provide at least 0.5 V hysteresis and remain <=18 V")
    for key in ("shutdown_confirm_s", "restart_confirm_s"):
        if not 1 <= values[key] <= 3600:
            raise ValueError(f"{key} must be between 1 and 3600 seconds")
    if not 10 <= values["shutdown_timeout_s"] <= 300:
        raise ValueError("shutdown_timeout_s must be between 10 and 300 seconds")
    if not 30 <= values["minimum_off_s"] <= 86400:
        raise ValueError("minimum_off_s must be between 30 and 86400 seconds")
    return PowerPolicy(description.strip(), **values)
