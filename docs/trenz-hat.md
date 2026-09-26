# Groundlark DAQHAT-01 — Pi-outline Trenz carrier

The front silkscreen carries a 7 mm monochrome Groundlark lark/waveform above
the model name. It is native KiCad polygon artwork, included in layout rebuilds
without adding BOM parts. See the [current 3D view](../hw/boards/groundlark-daqhat-01/3d.png).

**DAQHAT-01 revision:** six internal QSPI-reserved wires, retained UART and
switched Pi-driven JTAG replace external expansion connectors and ribbons.
See the [host-link circuit and bring-up guide](fpga-host-link.md). Pi 4 initially
uses SPI6; native quad transfers are not supported by its controller.

An external Racotech vertical geophone uses an ADS122C04 input; GNSS is not fitted.
See the [geophone circuit and acquisition](geophone-input.md).

DAQHAT-01 is an **85 × 56 mm, six-layer FR-4** alternative to the A2 Coldfoot ASIC HAT.
Electrical source: [`hw/elec/hat_trenz.ato`](../hw/elec/hat_trenz.ato).
CAD: [`groundlark-daqhat-01.kicad_pcb`](../hw/boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb).
The original ASIC HAT and [Burrowlark (DAQUSB-01) USB sensor head](usb-sensor-head.md)
remain separate builds.

## Stack and sensor placement

From bottom to top: Raspberry Pi, Groundlark DAQHAT-01, **TE0712-03-81I36-A**.
The FPGA stays on top for heatsink access. The HAT keeps the three LSM6DSO IMUs
and ADS122C04 geophone input; the dedicated inclinometer is removed. The magnetometer and optional infrasound
sensor stay on the separate USB head; they consume no HAT area.

The Trenz outline occupies HAT coordinates x=30–80, y=8–48 mm, measured from
the upper-left corner. Its mounting holes are (33,11), (77,11), (33,45), (77,45)
mm. Two 100-contact connectors and one 60-contact connector mate underneath it.
The selected 4 mm carrier and module connectors give an **8 mm surface gap**.
Use four matching M3 spacers. Components under the module are low-profile;
the tall service connectors are outside its outline.

The baseline CAD shows the Samtec ESQ-120-23-G-D bottom socket. Its body height is
16.129 mm. A **Samtec SSQ-120-02-G-D** 1:1 GPIO riser now adds 8.51 mm between
the Pi and J1, giving **27.18 mm nominal Pi-top to HAT-underside clearance** with
a 2.54 mm Pi header base. Its 4.93 mm square tails point into J1; the socket face
mates to the Pi. Use measured spacers/shims for actual seating, without forcing
the connector stack. The conceptual model and assembly BOM include this riser.

**The JLCPCB assembly selection for J1 is Megastar ZX-PM2.54-2-20PY / C7499354,
with an 8.5 mm body.** The baseline clearance above does not qualify that shorter
part. Confirm riser, pin engagement and spacer heights before assembly; see
[JLCPCB assembly](jlcpcb-assembly.md).

The three IMUs have matching XYZ axes and lie outside the FPGA outline:
U11 at (13,24), U12 at (24,24), and U13 at (13,36) mm. Their distance from the
FPGA outline is 17, 6 and 17 mm respectively. These planar distances do not
establish thermal or mechanical isolation. Local 100 nF bypass capacitors and
In1.Cu ground stitches are required. Connected-path limits checked by
`hw/tools/imu_layout.py` are 4 mm for VDDIO bypass, 2 mm for VDD bypass,
2 mm for capacitor ground and 2.5 mm for IMU ground-pin paths. These geometry
limits do not establish minimum noise; measure FPGA-off/idle/active coupling.

This compact stack increases thermal and electrical coupling compared with
placing the FPGA beside the Pi. Accelerometer/tilt drift and noise must be
measured with the FPGA idle and active, and cooling must avoid exciting the
motion sensors. Pi cooler compatibility needs a physical check.

## Power and interfaces

**J83 requires an external regulated 3.3 V-class supply, not 5 V.** Pin 1 is positive;
pin 2 is ground. It powers Trenz VIN and 3.3VIN through F80, a 5 A fast fuse.
The Pi continues to supply the sensor circuit. Grounds are common; positive
supplies are separate. There is no new USB connector on the HAT.

Start with a current-limited supply capable of module startup. The initial
operating budget is 3 A; this is a design envelope, not a measured FPGA load.
Set **3.35 V ±0.5% at J83** and keep **3.201–3.399 V at the module management
supply under load**. The revised hot loop resistance budget is **30 mΩ total**,
including positive and ground paths, fuse, PCB and mating contacts. At 3 A this
leaves a calculated DC range of 3.243–3.367 V, before transients. This limit must
be verified by differential voltage measurements; no extracted or measured
resistance is claimed. Current-limit first startup and check inrush before raising
the limit. This prototype input still has no reverse-polarity or overvoltage
protection; those protections must be supplied by the external bench source.

The module's sequenced 3.3 V output powers the exposed FPGA banks and the B
side of the TXU0202 UART isolator. Pi GPIO25 enables that interface, with a
pull-down keeping it disabled at startup. GPIO17 asserts application reset
through an open-drain transistor; the supervisor also holds reset during a
low FPGA I/O supply. FPGA configuration reset is separate on JP81.

| Function | Module pin | Carrier pad |
| --- | --- | --- |
| Pi TX → FPGA UART RX | JM2-11, B14_L8_N | J81-12 |
| FPGA UART TX → Pi RX | JM2-13, B14_L8_P | J81-14 |
| Application reset, active low | JM2-14, B14_L10_N | J81-13 |
| Configuration reset | JM2-18 | J81-17 |
| JTAG TMS / TDI / TDO / TCK | JM2-93 / 95 / 97 / 99 | J81-94 / 96 / 98 / 100 |

Carrier/module connector numbering swaps odd and even pins. See the complete
[`trenz-pin-map.json`](trenz-pin-map.json). Dedicated JTAG now reaches the Pi
through U100. R80 keeps JTAGEN low for the Trenz CPLD's FPGA path. JP80 disables
module power sequencing when shunted; JP81 asserts configuration reset.
NOSEQ has a defined low bias; its behavior depends on the module CPLD firmware.

## Internal GPIO allocation

Nine of the 158 ordinary module I/Os are connected: six SPI/QSPI signals plus
UART RX/TX and application reset. The remaining 149 ordinary I/Os are deliberate
no-connects. J84-J89, their fanout and the four flex cables are removed. Ethernet,
GTP, dedicated connector clock inputs and unused management contacts remain
unconnected. The UART service header J4 is retained.

The [GPIO contract](trenz-gpio-breakout.csv) records every ordinary module I/O.
Independent [module](trenz-gpio-module.csv) and [ground](trenz-ground-module.csv)
fixtures retain their vendor schematic transcription. The audit checks all 260
module contacts, including no-connects; JM1.12 is Ethernet RD_N, not ground.
Bank supplies remain at 3.3 V. There are no externally exposed raw FPGA GPIOs.

## Fabrication stack

The cost-reduced revision uses conventional **six-layer FR-4**, nominal 1.6 mm,
with through-vias only. Ground references are In1.Cu and In4.Cu. Signal layers
are F.Cu, In2.Cu, In3.Cu and B.Cu. Minimum signal width/clearance is
0.125/0.10 mm; vias have 0.30 mm drills and at least 0.45 mm pads.
Native custom rules additionally enforce via copper, SMD pad and hole clearances.
All through-vias are epoxy filled and copper capped, including solder-pad sites.

The recorded stock reference is JLC06161H-3313: 1 oz outer / 0.5 oz inner copper.
Its published copper/dielectric sum is 1.5384 mm; 1.6 mm is the nominal ordering
and mechanical-model thickness (+/-10% supplier tolerance). CAD mask thickness
and dielectric electrical constants are illustrative. Do not request custom
lamination to force the stock values to sum to 1.600 mm. No controlled impedance
is claimed. See [JLCPCB assembly](jlcpcb-assembly.md) for upload and process requirements.

## Verification and release limits

Current results are recorded in [validation.json](../hw/boards/groundlark-daqhat-01/validation.json),
[engineering.json](../hw/boards/groundlark-daqhat-01/engineering.json), and
[prefab-review.json](../hw/boards/groundlark-daqhat-01/prefab-review.json).
The portable lab checks circuit compilation, independent pin fixtures, ERC/DRC,
route connectivity, sensor regressions, power/geophone models and stack envelopes.
These checks do not establish physical power, timing, noise or thermal performance.
Follow the [bench procedure](bench-procedure.md) for first-article qualification.
