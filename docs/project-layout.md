# Project organization

| Location | Purpose |
| --- | --- |
| `hw/ato.yaml` | Three atopile build targets: ASIC HAT, Burrowlark DAQUSB-01 USB field head, Trenz HAT. |
| `hw/elec/` | Electrical source and atomic part definitions. |
| `hw/layout/`, `hw/layout*.json` | Compiled connectivity and mechanical placement inputs. |
| `hw/boards/` | Routed KiCad projects, review schematics, BOMs, 3D previews and recorded validation. |
| `hw/releases/` | Ignored local manufacturer review packages with explicit release status and hashes; not published without an explicit request. |
| `hw/libraries/`, `hw/models/` | Shared KiCad symbols/footprints and local 3D models. |
| `hw/tools/`, `hw/tests/`, `hw/simulation/` | CAD tooling, electrical fault fixture, bounded SPICE models and recorded results. |
| `hw/reference/`, `hw/vendor/` | Component references and upstream board material. |
| `sw/interfaces/` | Versioned Protobuf, compatibility baseline, reference validation/framing. |
| `sw/tools/` | Offline schema and software check entrypoint. |
| `sw/pi/` | Pi drivers/configuration, acquisition, calibration and recording/replay. |
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
