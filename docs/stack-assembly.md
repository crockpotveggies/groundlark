# DAQHAT-01 bench assembly

Bottom to top: Pi 4, 85 x 56 mm DAQHAT-01 sensor HAT, TE0712-03-81I36-A.
Four straight Pi supports replace the previous ribbon guide and offset spacer.
J84-J89 and all external FPGA ribbon cables are removed. Programming and data
travel through J1 and the Trenz mezzanine connectors; see the
[host-link guide](fpga-host-link.md).

## Selected hardware

| Item | Selection | Fit rule |
| --- | --- | --- |
| Host | Raspberry Pi 4 Model B | Pi 5/cooler not covered. |
| Pi cooling | Official Pi 4 Case Fan kit 18 x 18 x 10 mm heatsink | Allow 0.5 mm adhesive; fan omitted. |
| Pi riser | SSQ-120-02-G-D plus existing ESQ-120-23-G-D | 27.179 mm nominal Pi top to HAT underside. |
| Pi supports | Four straight M2.5 supports, <=4.8 mm outside diameter | Match seated riser/socket height with measured spacers/shims. |
| FPGA | TE0712-03-81I36-A with standard connectors | Four M3 spacers; 8 mm HAT-to-module surface gap. |
| Geophone plug | Phoenix Contact 1803581 | J90: GEO+, GEO-, shield/GND. |

The geophone plug has 9.20 mm calculated lateral clearance to the module after
0.5 mm allowance. Keep a vertical withdrawal column above J90, route its shielded
twisted pair toward the lower-left edge, and clamp the cable outside the PCB.
The geophone remains external, vertical and mechanically coupled to the ground.

**J1 procurement caveat:** the JLCPCB BOM selects the shorter 8.5 mm-body
Megastar ZX-PM2.54-2-20PY / C7499354. The 27.179 mm gap in the baseline table
does not apply automatically. Confirm mating depth, riser/spacer height and
cooler clearance for the ordered socket before assembly.

## Checks and limits

`assembly_fit.py` checks four support envelopes against the actual underside
components, socket, modeled Pi ports and selected heatsink. It reserves 0.5 mm
for support clearance and 1 mm for component/port seating uncertainty.
The [generated report](../hw/groundlark-fpga-hat/boards/groundlark-daqhat-01/prefab-review.json)
records margins. Use supports at (3.5,3.5), (61.5,3.5), (3.5,52.5), (61.5,52.5)
mm. Trim through-hole tails to <=2 mm below the HAT; the model allows 0.2 mm extra.

Keep the existing riser height. Removing cables does not qualify a shorter stack.
Actual mating, screws, cooler capacity, strain relief and sensor noise still need
a first-article check. The Pi and service envelopes are conceptual; the Trenz
model is the vendor's generic revision-03 STEP.

C95/C96 and D90 are underside geophone components; C90 is on the front.
ADC supply-pad and U101.4 link through-vias require epoxy-filled/copper-capped processing, as do the other
through-vias in this six-layer revision. Tenting alone does not meet this requirement.

See the [bench procedure](bench-procedure.md),
[Pi Case Fan brief](https://datasheets.raspberrypi.com/case-fan/case-fan-product-brief.pdf),
and [geophone plug](https://www.phoenixcontact.com/en-us/products/pcb-plug-mc-15-3-st-381-1803581).
