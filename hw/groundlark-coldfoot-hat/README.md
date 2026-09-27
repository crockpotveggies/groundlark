# Groundlark Coldfoot HAT

The 120 × 56 mm A2 ASIC HAT is retained as a separate hardware design.
Coldfoot ASIC/runtime/RTL integration is deferred while work focuses on the
Groundlark FPGA HAT. Existing CAD is prototype material, not a fabrication release.

- [Electrical source](elec/hat.ato)
- [Placement inputs](layout/placement.json)
- [Fixed connector routing](layout/fixed-routes.json)
- [Routed KiCad project](boards/groundlark-hat/groundlark-hat.kicad_pro)
- [Design specifications](../../docs/design-a0.md)
- [Coldfoot integration](../../docs/coldfoot-integration.md)

Build target: `hat` in [hw/ato.yaml](../ato.yaml). Vendor attribution and reference
boards remain in [shared/vendor/wafer-space/](../shared/vendor/wafer-space/).
