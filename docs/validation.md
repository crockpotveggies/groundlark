# A2 validation and release gates

## Current DAQHAT-01 GNSS, calibration and power revision

The 140 × 56 mm board includes MAX-M10S-00B GNSS on I2C1, BCM24 PPS and a
side-facing SMA with a 3.3 V active-antenna supply. BCM4 remains geophone DRDY;
BCM6/13 retain the TI power-supervisor handshake. FPGA interfaces and the
independent adapter supply remain unchanged. Native checks report zero ERC
findings, zero DRC findings and zero unconnected items. The complete
12,704-track/via SES reproduces identical copper. Independent pin/no-connect,
power, RF geometry, fabrication and analog-layout checks pass.

Four underside calibration pads expose ground, geophone bias, analog supply and
data-ready without adding GPIO. Static calibration fits measured gain/offset
with instrument/configuration binding and retains raw counts. Local miniSEED
export preserves timing gaps and requires valid UTC intervals. See the
[calibration guide](calibration.md) and [timing limits](utc-timing.md).

The commit-isolated software suite runs 246 tests successfully (two optional
device-tree checks skipped in the local Python environment). The portable
software profile passes, including contract compatibility and FPGA loopback.
The workbench HTTP check and browser interaction check pass. Its Groundlark
signal bench passes 11/11 checks on 3,272 modeled samples, including GNSS timing.
Lock-loss and missing-PPS controls preserve independent sensor acquisition.
Modeled UTC correlation and miniSEED round trips do not qualify physical 1 ms
sample alignment; receiver RF, acquisition latency and filter delay need measurement.

The 159 × 118 × 75 mm R3 enclosure adds a side SMA slot. Geometric/component
checks, 560 native PCB underside checks and 25 enclosure fault tests pass.
The README renders use current CAD. Physical first-print fit remains pending.
The supervisor battery policy stays disabled with unset thresholds; target MCU
firmware and Pi shutdown integration remain pending.

The full portable run stops at assembly regressions: 176 tests, 13 failures and
16 errors from procurement-registry/source and supplier-pad mismatches, retaining
the existing assembly export hold. Exact GNSS part identities are recorded;
current stock and supplier-pad/rotation approval remain pending. No physical
power, noise, thermal, battery or RF qualification is implied. See
[power operation](power-supplies.md#pi-supervisor-and-battery-input) and
[assembly status](jlcpcb-assembly.md).

## Earlier A2 validation scope

The separate FPGA DAQHAT-01 variant has its own [validation report](trenz-hat.md#verification-and-release-limits).
The A2 results below do not certify DAQHAT-01.

**Engineering prototype — not released for fabrication or assembly.** The
circuit is authored in atopile; the native KiCad layout and review schematic
are derived from its compiled pins. Coldfoot silicon was not changed.

A2 puts USB-C only on the Burrowlark (DAQUSB-01) remote sensor head and removes
the HAT cable interface.
The USB head requires firmware before it can enumerate. See [its circuit and
firmware contract](usb-sensor-head.md). USB connector mechanical holes are marked
on all copper layers in the local footprint, matching KiCad's multilayer PCB
representation; their drill dimensions and positions are unchanged.

## Recorded checks

Environment: atopile 0.15.9/Python 3.14.7, KiCad/pcbnew 9.0.9, ngspice 42,
Freerouting 1.9.0, WSL Ubuntu 24.04. The HAT has six copper layers (In1/In4 GND);
the field head has four (In1/In2 GND). Provisional minimum track/clearance is
0.15 mm, through-via diameter/drill 0.6/0.3 mm, copper-edge clearance 0.3 mm.
These rules are not a selected manufacturer's stackup or acceptance criteria.

| Board | Atopile pins compared | ERC findings | DRC errors | DRC warnings | Unconnected | Tracks/vias |
|---|---:|---:|---:|---:|---:|---:|
| groundlark-hat | 538 | 0 | 0 | 0 | 0 | 2197 |
| groundlark-field-head | 125 | 0 | 0 | 0 | 0 | 329 |

Evidence: each board's `validation.json`, `drc.json`, `erc.json` and exported
`schematic-netlist.xml` under each product's `boards/` directory. `hw/tools/check_design.py` checks source,
schematic and PCB pin agreement, independent Pi header corner coordinates and
the actual KiCad ERC/DRC engines. Library keepouts omitted during atopile board
conversion are restored before layout checks. No DRC violations are excluded.

- Explicit upstream atopile numeric solver: HAT and field-head rail/component
  constraints pass. The negative 5 V-to-3.6 V IMU case is correctly rejected.
- `hw/tools/check_circuit.py`: compiled pin assignments, source/BOM agreement,
  module bond/connector mapping, supply/clock/reset/UART direction and bypass
  invariants pass. Removed supervisor bypass and incorrect UART supply mutations
  are rejected. Burrowlark checks also reject reintroduced U3/C5 pressure parts
  and removal of the RM3100 module or its C4 bypass capacitor.
- **27 ngspice cases pass**: rail/load/USB cable corners, I2C rise time, UART RC,
  USB CC resistor corners, ideal buck power stage and behavioral reset.
  See [simulation scope](../hw/shared/simulation/README.md) and the actual decks/logs.
- Native KiCad schematics, assembly previews and 3D renders were visually
  inspected. Custom module/socket bodies are simplified dimensioned envelopes.
- [Artifact hashes](artifact-manifest.json) identify the checked sources and CAD.

The SPICE cases do not simulate MEMS internals, geomagnetic sensitivity,
Coldfoot RTL, vendor regulator control loops or extracted PCB parasitics.
Pin agreement establishes CAD consistency; it does not replace independent
supplier pinout/package review. No firmware, inference, silicon, CDC, EMC,
signal-integrity, magnetic-noise or physical bench qualification is claimed.

## Before fabrication

1. Independently review the run-1 bond map, mating connector orientation,
   current per contact, exact package revisions and ordered parts. The selected
   run-1 module replaces the earlier run-2 incompatibility; its complete support circuit is now present.
2. Select a fabrication stackup and review routing: power drops/neck-downs,
   decoupling and buck switching loops, copper thermal paths, via return paths,
   USB data pair geometry and GNSS RF impedance. Clean DRC is not SI/PI signoff.
3. Verify Pi model, underside socket, cooler/ports/ribbon cable clearance,
   overhang support and run-1 stack height. The 120 × 56 mm carrier extends
   beyond the normal HAT outline; no HAT+ compliance certification is claimed.
4. Confirm the assumed 200 mA sensor and 600 mA Coldfoot envelopes, capacitor
   DC-bias derating, standby/partial-power behavior and ISO1640 input-low margin.
5. Implement/test USB enumeration, current limits, suspend/resume, timestamped
   sensor transport, EEPROM contents, overlays, acquisition/timestamping and
   the existing Coldfoot runtime integration before system performance claims.
6. Export and independently inspect manufacturing outputs after these reviews.
   No fabrication or assembly order has been placed.

## Bench acceptance

| Area | Required evidence |
|---|---|
| Power | Current-limited startup, regulator stability and transient droop, reset/brownout and all Pi power states |
| Timing/links | Sensor IDs, CRC/FIFO behavior, SPI modes, USB enumeration/suspend and local I2C timing, PPS timestamp uncertainty and 2 Mbaud runtime round trips |
| Motion/level | Axis orientation, known-angle calibration, stationary noise, thermal drift and correlated noise across four IMUs |
| Magnetics | Remote installation offsets, orientation, hard/soft-iron calibration and noise with Pi/fan/Coldfoot active; reference-station comparison |
| Infrasound (DAQHAT-01 only) | See the [DAQHAT-01 guide](trenz-hat.md) for pressure calibration, noise, tubing response and saturation qualification |
| Coldfoot | Measured rail/contact currents and clocks, then deterministic recorded-input comparisons through its existing runtime |

The remote magnetometer needs its own orientation calibration; the HAT's
inclinometer does not automatically compensate a separately mounted head.
Aurora-related magnetic measurements are not optical aurora detection.
Acquisition/replay and fault tests are implemented in the portable software
profile; see [software evidence and limits](sensor-software.md). These tests
do not qualify USB-head firmware or physical sensor performance.

## Burrowlark climate checks

The RM3100/SHT45 revision retains the 70 x 45 mm outline and removes no existing
magnetic connections. Circuit and native CAD checks require U6/C10, verify the
independent four-pin SHT45 mapping and bypass nets, and reject former U3/C5.
Native DRC/airwire and schematic ERC reports, SES snapshot, README render and
browser model accompany the revision. CRC corruption, conversion timing, board
ownership, MCU clock domain, independent fault/recovery and recording/replay
fixtures cover sensor 17. These modeled checks do not establish physical USB,
magnetic noise, thermal performance or fabrication readiness.
