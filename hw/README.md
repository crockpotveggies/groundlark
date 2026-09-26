# Hardware

| Board | Native CAD | Circuit source |
| --- | --- | --- |
| A2 Coldfoot ASIC HAT, 120 × 56 mm | [KiCad](boards/groundlark-hat/groundlark-hat.kicad_pcb) | [atopile](elec/hat.ato) |
| DAQHAT-01 Trenz FPGA HAT, 85 × 56 mm | [KiCad](boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb) | [atopile](elec/hat_trenz.ato) |
| [Burrowlark DAQUSB-01](../docs/usb-sensor-head.md) USB magnetometer/infrasound head, 70 × 45 mm | [KiCad](boards/groundlark-field-head/groundlark-field-head.kicad_pcb) | [atopile](elec/field_head.ato) |

`ato.yaml` owns the build targets. `elec/` owns connectivity; `layout*.json` owns
placement metadata. `boards/` contains routed deliverables, BOMs and rendered
previews. `libraries/` and `models/` are shared dependencies with relative CAD
references. Stack concept boards are visualization artifacts, not fabrication
boards.

Use the root portable lab for routine checks. See the [build guide](../docs/build.md),
[Trenz guide](../docs/trenz-hat.md) and [validation limits](../docs/validation.md)
before invoking the lower-level authoring tools.
