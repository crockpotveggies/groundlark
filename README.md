<img src="sw/ui/assets/groundlark-wordmark.svg" alt="Groundlark — lark and seismic waveform" width="440">

# Groundlark — an open source seismic acquisition platform with support for FPGAs and BISCUT AI chips

Groundlark is an open hardware seismic acquisition platform combining a
Raspberry Pi, a three-IMU DAQHAT-01 sensor HAT, a Trenz Artix-7 200T FPGA module,
and a passive geophone.

![Groundlark: Raspberry Pi, DAQHAT-01 and Trenz FPGA stack with Racotech geophone](docs/images/groundlark-stack-geophone.png)

The image uses current HAT CAD and the vendor Trenz model. The Pi, baseline
socket and geophone are conceptual geometry; lead routing is illustrative.
The J1 procurement substitute needs a physical stack-height check.

## Hardware

The [DAQHAT-01](docs/trenz-hat.md) is an 85 × 56 mm, six-layer FR-4 carrier with
three XYZ LSM6DSO IMUs and one ADS122C04 input for an external Racotech geophone.
The stack is **Pi → HAT → Trenz FPGA**. It requires a separate regulated
3.3 V-class FPGA supply; follow the guide's voltage and power limits.

The [internal FPGA link](docs/fpga-host-link.md) reserves six QSPI wires and
supports UART, reset and switched Pi-driven JTAG without external ribbon cables.
Pi 4 initially uses SPI6; native quad transfers require a different host solution.
An SPI echo bitstream is implemented; accelerated sensor processing remains future work.

The [Burrowlark (DAQUSB-01) USB-C sensor head](docs/usb-sensor-head.md) carries
an RM3100 magnetometer and optional DLVR infrasound sensor. It connects to the Pi for power and data;
its MCU firmware is still pending. These sensors are separate from the HAT.
The [A2 ASIC HAT](docs/design-a0.md) and [Coldfoot integration](docs/coldfoot-integration.md)
are retained as a separate design; current hardware work focuses on the FPGA stack.

Use the [stack assembly guide](docs/stack-assembly.md) and
[JLCPCB instructions](docs/jlcpcb-assembly.md) for mechanical and manufacturing details.
The JLCPCB package targets **one assembled HAT**. Upload the corrected BOM and
CPL together. Supplier quantity, sourcing, placement and J1 fit checks remain open.
Fabrication packages stay local under ignored `hw/releases/`.

Physical power, fit, timing, noise and thermal qualification remain pending.
The [bench procedure](docs/bench-procedure.md) describes the required measurements.

## Sensor workbench

The dark-mode Python UI includes a selectable 3D HAT and geophone, six virtual
sensor streams, raw-data charts, stimulus/fault controls and recording/replay.
No hardware or Docker is required. Follow the
[beginner walkthrough](docs/sensor-workbench.md) to create your first signal.

```powershell
# Windows: set up once, then launch
./setup-ui.ps1 -Check
./ui.ps1
```

On Linux/macOS, use `sh ./setup-ui.sh --check`, then `sh ./ui.sh`.
Open **http://127.0.0.1:8080**. Tools and dependencies stay in ignored `.local/`.

![Groundlark sensor workbench showing the external geophone and a simulated 2 Hz signal](docs/images/sensor-workbench.png)

This is an actual browser screenshot with simulated data. Select the geophone
can or its HAT input to highlight both and inspect the same ADC stream.
**Test HAT signals** runs eight simulated seconds through production Pi drivers
on modeled buses, with signal checks and downloadable recordings/results.
The UI simulates and replays; physical acquisition uses the [Pi software](docs/sensor-software.md).

## Project files and tests

| Directory | Contents |
| --- | --- |
| [hw/](hw/README.md) | Atopile circuits, KiCad boards, models, hardware checks and SPICE. |
| [sw/](sw/README.md) | Pi acquisition, contracts, simulator, FPGA and remote firmware interfaces. |
| [docs/](docs/README.md) | Setup, hardware specifications, assembly, interfaces and testing instructions. |
| [environment/](docs/portable-lab.md) | Pinned Docker test environment and bounded cleanup tooling. |

For the full test environment, run `./lab.ps1 build` once, then `./lab.ps1 test`.
Use `./lab.ps1 test -Profile software` for sensor contracts, acquisition,
recording/replay and recovery. See the [portable lab guide](docs/portable-lab.md)
for Linux commands, test scope, five-run retention and cleanup.

Hardware sources: [DAQHAT-01 circuit](hw/elec/hat_trenz.ato),
[KiCad PCB](hw/boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb),
[A2 HAT](hw/boards/groundlark-hat/groundlark-hat.kicad_pcb), and
[Burrowlark DAQUSB-01](hw/boards/groundlark-field-head/groundlark-field-head.kicad_pcb).
See [build instructions](docs/build.md) and [source references](docs/sources.md).
