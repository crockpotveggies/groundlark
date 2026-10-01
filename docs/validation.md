# Hardware validation and release gates

## Current DAQHAT-01 GNSS, calibration and power revision

The 140 × 56 mm board includes MAX-M10S-00B GNSS on I2C1, BCM24 PPS and a
side-facing SMA with a 3.3 V active-antenna supply. BCM4 remains geophone DRDY;
BCM6/13 retain the TI power-supervisor handshake. FPGA interfaces and the
independent adapter supply remain unchanged. Native checks report zero ERC
findings, zero DRC findings and zero unconnected items. The complete
13,010-track/via SES reproduces identical copper. Independent pin/no-connect,
power, RF geometry, fabrication and analog-layout checks pass.
The antenna limiter and local bypasses are routed; ISO1640 side 2 faces GNSS.
Pi rail calculations include resistor temperature drift and an unmeasured
±20 mV ripple/transient allowance. Thermal, short-circuit and timing acceptance
still require physical measurements.

Four underside calibration pads expose ground, geophone bias, analog supply and
data-ready without adding GPIO. Static calibration fits measured gain/offset
with instrument/configuration binding and retains raw counts. Local miniSEED
export preserves timing gaps and requires valid UTC intervals. See the
[calibration guide](calibration.md) and [timing limits](utc-timing.md).

The portable software checks run 253 tests successfully, including device-tree
checks, contract compatibility and FPGA loopback.
The workbench HTTP check and browser interaction check pass. Its Groundlark
signal bench passes 12/12 checks on 4,072 modeled samples from all six HAT sensors.
Infrasound uses the raw-response model; its Pi hardware driver remains pending.
Antenna open/short, lock-loss and missing-PPS controls preserve independent
sensor acquisition. Fault/recovery, replay and rejection of invalid UTC references
are covered. Supply checks include Pi temperature corners, invalid envelope
inputs, antenna fault current and the added GNSS bypass charge.
Modeled UTC correlation and miniSEED round trips do not qualify physical 1 ms
sample alignment; receiver RF, acquisition latency and filter delay need measurement.

The 159 × 118 × 75 mm R3 enclosure adds a side SMA slot. Geometric/component
checks, 560 native PCB underside checks and 25 enclosure fault tests pass.
The README renders use current CAD. Physical first-print fit remains pending.
The supervisor battery policy stays disabled with unset thresholds; target MCU
firmware and Pi shutdown integration remain pending.

The full portable run executes all 25 stages; 24 pass. Hardware regressions
report 186 tests, 13 failures and 16 errors from the existing
procurement-registry/source and supplier-pad mismatches, retaining
the existing assembly export hold. Exact GNSS and replacement-part stock
observations are recorded; full procurement and supplier-pad/rotation approval
remain pending. Ten focused GNSS pin/layout tests pass, including missing
bypass and ground-stitch faults. No physical
power, noise, thermal, battery or RF qualification is implied. See
[power operation](power-supplies.md#pi-supervisor-and-battery-input) and
[assembly status](jlcpcb-assembly.md).

## Reproducible checks and release limits

Run the [portable lab](portable-lab.md) for the three current hardware targets:
DAQHAT-01, Burrowlark and Skylark. It checks compiled circuits, independent
pin fixtures, native ERC/DRC, routing replay, supporting-circuit simulations
and the software profile. The shared sensor fixture is fixed independently of
current CAD and includes missing-pin and incorrect-supply fault tests.

See each product's guide for current electrical and mechanical limits.
[Shared SPICE models](../hw/shared/simulation/README.md) cover 18 sensor/USB
support-circuit cases; FPGA power and geophone checks are separate.
CAD and behavioral checks do not establish physical power, noise, timing,
USB, thermal, RF or assembly qualification. Fabrication approval remains
with the user. Follow the [bench procedure](bench-procedure.md) and preserve
missing measurements as unqualified results.
