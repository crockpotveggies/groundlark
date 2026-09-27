# Hardware

Each product has its own directory. Existing model names and atopile targets
remain stable so board identity does not depend on its directory name.

| Product | Model / outline | Build target | Status |
| --- | --- | --- | --- |
| [Groundlark FPGA HAT](groundlark-fpga-hat/README.md) | DAQHAT-01, 85 × 56 mm | `trenz_hat` | Active prototype; physical qualification pending. |
| [Groundlark Coldfoot HAT](groundlark-coldfoot-hat/README.md) | A2 ASIC HAT, 120 × 56 mm | `hat` | Retained; integration deferred. |
| [Burrowlark USB](burrowlark-usb/README.md) | DAQUSB-01, 70 × 45 mm | `field_head` | Hardware design present; firmware pending. |
| [Skylark USB](skylark-usb/README.md) | Not assigned | None | Planned air-quality accessory; no implemented hardware yet. |

## Product contents

- `elec/`: authored circuit and product-specific part definitions.
- `layout/placement.json`: placement metadata for that board.
- `layout/<target>/`: atopile connectivity layout and local library tables.
- `boards/<board>/`: routed native CAD, review schematics, BOMs, previews and validation evidence.
- `mechanical/` and `simulation/`: product-specific artifacts where applicable.

Skylark currently contains only its status README. Add implementation directories
as their contents are created. Stack concept boards are visualization artifacts.

## Shared resources and tooling

[shared/](shared/README.md) holds common part definitions, KiCad libraries, models,
vendor/reference material and simulations used by multiple boards. Custom CAD
resource paths remain relative.

`tools/` and `tests/` retain the existing shared and cross-board checks.
`assembly/<product>/` holds procurement overrides; `releases/<product>/` is for
ignored local fabrication packages, which require explicit authorization to publish.
Disposable runs belong in `.lab/`; local dependencies belong in `.local/`.
Firmware and host software belong in `sw/`.

`ato.yaml` defines the three implemented targets. Direct atopile commands target
`hw/` from the repository root and write authoring outputs. Skylark has no build
target until its circuit is implemented.

Use the root portable lab for routine checks. See the [build guide](../docs/build.md),
[Trenz guide](../docs/trenz-hat.md) and [validation limits](../docs/validation.md)
before invoking the lower-level authoring tools.
