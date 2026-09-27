# Groundlark FPGA HAT — DAQHAT-01

The active 85 × 56 mm, six-layer Trenz carrier combines three XYZ IMUs and
an ADS122C04 input for an external Racotech geophone. The stack is Raspberry Pi,
DAQHAT-01, then Trenz TE0712-03-81I36-A. Physical qualification remains pending.

- [Electrical source](elec/hat_trenz.ato)
- [Placement inputs](layout/placement.json)
- [Routed KiCad project](boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pro)
- [Native routing snapshot](boards/groundlark-daqhat-01/groundlark-daqhat-01.ses)
- [Hardware and power specifications](../../docs/trenz-hat.md)
- [Assembly instructions](../../docs/stack-assembly.md)

Build target: `trenz_hat` in [hw/ato.yaml](../ato.yaml). Use the root portable lab
for validation. `simulation/` contains bounded supporting-circuit models;
`mechanical/` retains earlier mechanical artifacts with their recorded status.
FPGA sources remain under [sw/fpga/](../../sw/fpga/README.md).
