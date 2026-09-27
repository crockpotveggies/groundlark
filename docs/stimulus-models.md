# Virtual sensor stimulus models

For a first experiment, use the [browser workbench walkthrough](sensor-workbench.md).
This page describes advanced JSON inputs and model limits. The current HAT has
three IMUs and one geophone input; GNSS/inclinometer controls below are legacy only.

`ideal-v1` replaces the old fixed counter patterns with controllable, time-based
signals. It runs through the same acquisition, validation, calibration and
recording code as the live drivers. The browser workbench uses this scenario
API, and saved scenarios can also run from the command line.

## Try the example

The [demo scenario](../sw/pi/profiles/stimulus-demo.json) combines rocking and
vibration, magnetic drift/a pulse, a separately rotated remote head, a pressure
wave/overrange step. It also retains GNSS movement/fix-loss inputs for legacy
experiments; those do not produce a GNSS stream on the current HAT. To excite
the geophone, use its browser controls or add `geophone_velocity_m_s` to the JSON.

```sh
python sw/tools/sensor.py simulate --remote --seconds 2 --seed 7 \
  --scenario sw/pi/profiles/stimulus-demo.json --output sw/build/stimulus.ssrec
python sw/tools/sensor.py replay sw/build/stimulus.ssrec
python sw/tools/sensor.py export-scenario sw/build/stimulus.ssrec \
  --output sw/build/saved-scenario.json
```

Use the schema/runtime setup in the [software guide](sensor-software.md).
Alternatively, `./lab.ps1 test -Profile software` runs the models and retains a
demo in the existing bounded lab results. That demo combines this scenario with
the older sample-index fault fixture. Direct outputs use exclusive creation.

Re-run an exported scenario with the same seed, `--remote` setting, duration,
queue settings and any separate `--faults` fixture to reproduce a run. Export
prints the recorded seed and remote setting. It recovers stimulus controls,
including timed faults; separate sample-index fault fixtures remain separate.
`replay` validates existing samples; `simulate` generates a fresh experiment.

## Scenario format

```json
{
  "version": 1,
  "initial": {
    "orientation_deg": [0, 0, 0],
    "acceleration_m_s2": [{"amplitude": 0.2, "frequency_hz": 3}, 0, 0],
    "pressure_pa": {"amplitude": 4, "frequency_hz": 1, "noise_peak": 0.05}
  },
  "events": [
    {"at_ns": 1000000000, "set": {"orientation_deg": [0, 30, 0]}},
    {"at_ns": 2000000000, "set": {"sensor_faults": {"1": "disconnect"}}},
    {"at_ns": 2200000000, "set": {"sensor_faults": {}}}
  ]
}
```

Omitted controls use defaults. An event replaces only the named controls; a
vector or fault map is replaced as a whole. Events are chronological, apply at
`time >= at_ns`, and preserve file order when timestamps match. Waves use global
simulation time, so replacing a waveform does not restart its phase or drift.
The CLI advances in 1 ms ticks; control events are recorded before acquisition
on the first tick at/after their requested time. Requested time and recorded
application time are both retained. A sample sees the state at its own time.

| Control | Units/meaning | Default |
| --- | --- | --- |
| `orientation_deg` | HAT roll, pitch, yaw; three numbers or smooth waveforms | `[0,0,0]` |
| `head_orientation_deg` | Independent remote-head roll, pitch, yaw | `[0,0,0]` |
| `acceleration_m_s2` | World east/north/up linear acceleration, excluding gravity; three signals | `[0,0,0]` |
| `geophone_velocity_m_s` | External vertical velocity; constant or steady sinusoid, native 4.5 Hz mechanical response plus passive RC | `0` |
| `magnetic_ut` | World east/north/up field, microtesla; three signals | `[0,20,-45]` |
| `pressure_pa` | Differential pressure; scalar signal | `0` |
| `temperature_c` | IMU/legacy-inclinometer and Skylark ambient temperature; scalar signal | `25` |
| `so2_ppm` / `h2s_ppm` | Nominal Skylark gas stimulus; uncalibrated working/auxiliary ADC outputs | `0` / `0` |
| `pm25_ug_m3` | Skylark atmospheric PM2.5; synthetic PM1/PM10 ratios | `5` |
| `humidity_percent` | Skylark relative humidity | `50` |
| `ambient_pressure_pa` | Skylark absolute barometric pressure | `101325` |
| `pressure_temperature_count` | Explicit unsigned 11-bit DLVR temperature fixture | `768` |
| `gnss_position` | Origin latitude degrees, longitude degrees, height metres; numbers only | `[49,-123,0]` |
| `gnss_velocity_ned_m_s` | Constant north/east/down velocity until changed | `[0,0,0]` |
| `gnss_fix` | Boolean 3D fix / no fix | `true` |
| `sensor_faults` | Map of ID strings to held faults: current IDs `"1"`, `"2"`, `"3"`, `"7"`, `"8"`, `"9"`; IDs 10–16 are Skylark; IDs 4–6 are legacy | `{}` |

Signals accept a constant number or these optional waveform fields:

| Field | Meaning |
| --- | --- |
| `offset` | Constant baseline in the control's units |
| `amplitude`, `frequency_hz`, `phase_deg` | Sine wave amplitude, frequency and phase |
| `drift_per_s` | Linear change per second since simulation time zero |
| `noise_peak` | Peak of deterministic uniform measurement noise |
| `pulse_start_s`, `pulse_duration_s`, `pulse_amplitude` | Added rectangular pulse, start inclusive/end exclusive |

All omitted waveform fields are zero. Orientation signals allow sine/drift but
exclude noise and rectangular pulses, because those have no finite angular-rate
derivative. A timed pose change is an instantaneous repositioning; it does not
invent a gyro impulse. Use a smooth orientation waveform to test rotation rates.
Noise is keyed by seed, sensor ID, field/axis and time. Sensor read order, retries
and unrelated streams cannot perturb its random sequence. Same-runtime repeats
are byte-identical; cross-platform math-library bit identity is not promised.

Fault actions are `none`, `timeout`, `nack`, `disconnect`, `not_ready`,
`saturation`, and `short_read`. They persist until replaced and enter the normal
bounded recovery path. `none` overrides a simultaneous sample-index fault;
an absent sensor entry falls back to `--faults`. Clearing an input fault does
not bypass the application's cooldown or replenish its restart budget.
GNSS fix loss is controlled by `gnss_fix`, not `saturation`.

## Physical model and raw encoding

World axes are east/north/up, with package axes aligned at zero orientation.
Orientation uses `Rz(yaw) Ry(pitch) Rx(roll)`. Acceleration is linear acceleration
plus an upward 9.80665 m/s² gravity contribution, rotated into package axes.
The three IMUs share motion, with independent noise when requested. Gyro rates
come from the analytic Euler-angle derivatives, including tilted-axis coupling.

LSM6DSO encoding uses nominal selected-range sensitivities and signed 16-bit
counts. The legacy SCL3300 model encodes acceleration using the selected mode and tilt angles
from the acceleration direction, with 16384 counts per 90 degrees. Zero
acceleration/freefall makes tilt undefined and yields FAULT. Temperature follows
the respective nominal register transfer functions. Sensor full-scale excess
or count-rail clipping is marked SATURATED; raw integers stay inside wire bounds.

The RM3100 model rotates the field using the **remote** orientation, applies a
nominal 75 counts/µT at cycle count 200 and clips signed 24-bit counts. Other
cycle counts are rejected until their transfer model is specified. This gain
is a simulation assumption, not fitted calibration or magnetic performance
qualification. It models count rails, not a validated magnetic full-scale limit.

Pressure maps the configured min/max Pa to 10%/90% of the 14-bit count span.
Outside the configured span it reports SATURATED; at ADC limits it clips rather
than wraps. Both status bits remain normal for VALID/SATURATED response payloads.
The explicit 11-bit temperature count is packed with five zero padding bits;
no pressure-temperature conversion is claimed.

GNSS integrates piecewise constant NED velocity in a local tangent approximation
using a 6378137 m radius and longitude scale at the origin latitude. Velocity
changes preserve position; a new `gnss_position` resets the origin/displacement.
NAV-PVT contains iTOW, coordinates, height, velocity, heading and fix flags.
No-fix messages are successfully acquired raw data with invalid navigation
flags, not MISSING bus measurements. UTC validity is never asserted. Ellipsoid
and mean-sea-level heights are equal in this model; there is no geoid model.

These are application stimuli, not sensor silicon or environmental emulation.
They omit filtering/FIFO delays, sensor placement lever arms, actual package-to-PCB
mounting transforms, thermal drift physics, magnetic hysteresis, acoustic plumbing
and GNSS RF/orbital effects. Acceleration, GNSS velocity and position can be
controlled independently; they do not form a solved rigid-body trajectory.
Signals above sample Nyquist frequency alias normally; no resampling or
anti-alias filter is silently added. SCL3300 mode-specific accuracy near tilt
limits is not modeled.

## UI integration, traceability and limits

`Scenario.schedule(at_ns, changes)` validates an atomic future update;
`advance(now)` returns each due update once for the recorder. Send UI commands
to the acquisition thread, schedule beyond its last advanced time, then record
each update through `Acquisition.event("stimulus_change", ..., **change)` before
sampling. This API does not start a server or claim thread safety. The recording
header includes `ideal-v1`, initial scenario and seed; events capture controls
added after startup. `export-scenario` combines both into reusable JSON.

Limits: 64 KiB input JSON, 8192-byte normalized scenario, 256 events, 1536 bytes per event, one-hour
time horizon, frequency ≤500 Hz, finite waveform coefficients ≤1e6 magnitude,
nonnegative noise/pulse duration, initial latitude within ±85°, and NED velocities
within ±300 m/s. Polar trajectory excursions beyond ±89.9° fail the GNSS read.
Unknown fields and invalid values fail validation before acquisition. The v1
Protobuf contract and existing acquisition/file/queue limits are unchanged.

Tests check independent level/tilted/raw-count expectations, gyro derivatives,
remote orientation, sensor ranges, pulse boundaries, deterministic noise,
GNSS wire offsets/motion/fix loss, bounded transactional scheduling, timed faults,
recorded control events, export and byte-identical CLI regeneration.

References: [ST conversion routines](https://github.com/STMicroelectronics/stm32-lsm6dso/blob/main/lsm6dso_reg.c),
[SCL3300 datasheet](https://www.murata.com/-/media/webrenewal/products/sensor/pdf/datasheet/datasheet_scl3300-d01.ashx),
[DLVR transfer/data format](https://www.allsensors.com/hubfs/Product-Data-Sheets/DS-0300.pdf),
[u-blox M10 NAV-PVT](https://content.u-blox.com/sites/default/files/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf).

The geophone control accepts amplitude, frequency, phase and offset; noise, drift
and pulse controls are rejected for this steady-state model. Constant velocity
has zero steady output. Each tone applies the Racotech mechanical transfer and
loaded input RC before ADC quantization. ADC digital filtering and settling are
not modeled. See [current geophone scope](geophone-input.md).

Use `simulate --board skylark` for the seven air-quality streams. Gas stimulus
uses a nominal positive-going 1.25 V baseline with 40/34 mV per ppm SO₂/H₂S
working response and unchanged auxiliary response. This illustrative polarity
and sensitivity must not be used as field calibration. It omits cell impedance,
cross-sensitivity, environmental drift and warmup. PM frames use PM1=0.6×PM2.5
and PM10=1.3×PM2.5; they do not model aerosol composition. SHT transfer equations
and deliberately synthetic BMP trim provide deterministic raw-byte fixtures.
The physical firmware handles warmup separately as missing measurements.
