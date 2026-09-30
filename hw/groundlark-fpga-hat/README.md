# Groundlark FPGA HAT — DAQHAT-01

The active 140 × 56 mm, six-layer Trenz carrier combines three XYZ IMUs and
an ADS122C04 input for an external Racotech geophone, plus a fitted DLVR-F50D
infrasound pressure sensor on I2C1 (0x28). The stack is Raspberry Pi,
DAQHAT-01, then Trenz TE0712-03-81I36-A. Physical qualification remains pending.
J90 uses a horizontal Phoenix 1803280 header with the existing 1803581 cable
plug. Pin order remains positive, negative, shield.

J83 takes a Nexys Video-compatible 12 V, center-positive 5.5/2.1 mm adapter
rated at least 3 A. It faces the opposite edge from the geophone. U80 supplies
the FPGA independently of the Pi, with a 3 A output allocation; SW80 turns this
supply off/on. The first 25 mm of the extension contains FPGA input protection and conversion. Check the documented voltage, thermal and enclosure limits before
building; the supply remains an unqualified prototype.

- [Electrical source](elec/hat_trenz.ato)
- [Placement inputs](layout/placement.json)
- [Routed KiCad project](boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pro)
- [Native routing snapshot](boards/groundlark-daqhat-01/groundlark-daqhat-01.ses)
- [Hardware and power specifications](../../docs/trenz-hat.md)
- [Pi and external source budgets](../../docs/power-supplies.md)
- [Sensor bandwidth and timing](../../docs/sensor-response.md)
- [Assembly instructions](../../docs/stack-assembly.md)

Build target: `trenz_hat` in [hw/ato.yaml](../ato.yaml). Use the root portable lab
for validation. `simulation/` contains bounded supporting-circuit models;
`mechanical/` retains earlier mechanical artifacts with their recorded status.
FPGA sources remain under [sw/fpga/](../../sw/fpga/README.md).

Assembly uses an 8.5 mm JLCPCB socket, two external GPIO risers and measured
supports (28.06 mm nominal Pi gap). Sensor supply and bias returns have local
ground stitches. Procurement accepts in-stock PCB selections with component
MOQ 1; see [JLCPCB assembly](../../docs/jlcpcb-assembly.md).

Use the [R3 enclosure](../mechanical/daqhat-01-case/README.md) for the 140 × 56 mm
board. It adds power-wing supports, a rear DC opening opposite the geophone and
switch access. First-print fit and thermal qualification remain pending.

## Pi power supervisor

J130 accepts **8–18 V DC** from an externally protected battery/controller.
U130 is TI MSPM0L1105TRHBR; U131 powers it continuously while U132/U133 supply
and disconnect the Pi through header pins 2/4. The combined Pi/HAT allocation
is 3 A at nominal 5.149 V, for the Pi 4 stack. Do not simultaneously power the
Pi through USB-C. Keep J83's separate 12 V FPGA input independent.

Battery thresholds and delays are configurable placeholders, shipped disabled
in [power-policy.example.json](../../sw/pi/deploy/power-policy.example.json).
Target MCU firmware and physical power qualification remain pending. An
unprogrammed MCU leaves the Pi off; fitting the JP130 shunt provides manual
bench operation. Remove it before automatic supervision. See the
[operating specification](../../docs/power-supplies.md#pi-supervisor-and-battery-input).
