# Project organization

| Location | Purpose |
| --- | --- |
| [hw/groundlark-fpga-hat/](../hw/groundlark-fpga-hat/README.md) | DAQHAT-01 Trenz FPGA HAT; active prototype. |
| [hw/groundlark-coldfoot-hat/](../hw/groundlark-coldfoot-hat/README.md) | Separate A2 Coldfoot HAT; integration deferred. |
| [hw/burrowlark-usb/](../hw/burrowlark-usb/README.md) | DAQUSB-01 magnetometer/infrasound USB sensor head. |
| [hw/skylark-usb/](../hw/skylark-usb/README.md) | Rev A USB air-quality circuit, routed PCB and bell enclosure; physical qualification pending. |
| `hw/ato.yaml` | Shared build registry: `trenz_hat`, `hat`, `field_head` and `skylark`. |
| `hw/shared/elec/` | Common atomic parts and component assets. |
| `hw/assembly/<product>/` | Product-specific procurement and assembly overrides. |
| `hw/releases/<product>/` | Ignored local manufacturer review packages with explicit release status and hashes; not published without an explicit request. |
| `hw/shared/libraries/`, `hw/shared/models/` | Shared KiCad symbols/footprints and local 3D models. |
| `hw/tools/`, `hw/tests/`, `hw/shared/simulation/` | CAD tooling, electrical fault fixture, bounded SPICE models and recorded results. |
| `hw/shared/reference/`, `hw/shared/vendor/` | Component references and upstream board material. |
| `sw/interfaces/` | Versioned Protobuf, compatibility baseline, reference validation/framing. |
| `sw/tools/` | Offline schema and software check entrypoint. |
| `sw/pi/` | Pi drivers/configuration, acquisition, calibration and recording/replay. |
| [sw/skylark/](../sw/skylark/README.md) | Skylark STM32 firmware and native hardware-abstraction fault fixtures. |
| `sw/field-head/` | Planned Burrowlark DAQUSB-01 USB microcontroller firmware. |
| `sw/fpga/` | Trenz SPI echo bitstream, host-link checks and board constraints. |
| `sw/tests/` | Contract, acquisition, recording, recovery and FPGA-link tests. |
| `sw/ui/` | Python/NiceGUI workbench, locked optional dependencies and display assets. |
| `docs/` | Setup, hardware specifications, assembly, interface contracts and testing instructions. |
| `environment/` | Pinned portable toolchain, launcher implementation and safeguard tests. |
| `.lab/` | Ignored disposable reports, bounded by retention. |
| `.local/` | Ignored local dependencies and preserved legacy caches. |

Run the root `lab.ps1` / `lab.sh` commands from any working directory. Low-level
commands documented elsewhere assume the repository root as the working directory.
The atopile project itself is now `hw/`, so direct builds must target that directory.

Each implemented product owns its `elec/` circuit sources, `layout/placement.json`,
`layout/<target>/` compiled connectivity and `boards/<board>/` native CAD and
validation artifacts. Product-specific mechanical and simulation files stay with
the product. Shared tools resolve these locations through `hw/tools/project_paths.py`.
Native board names are retained to preserve model and build identities.
