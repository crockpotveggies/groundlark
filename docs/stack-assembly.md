# DAQHAT-01 bench assembly

Bottom to top: Pi 4, 140 x 56 mm DAQHAT-01 sensor HAT, TE0712-03-81I36-A.
Four straight Pi supports replace the previous ribbon guide and offset spacer.
J84-J89 and all external FPGA ribbon cables are removed. Programming and data
travel through J1 and the Trenz mezzanine connectors; see the
[host-link guide](fpga-host-link.md).

## Selected hardware

| Item | Selection | Fit rule |
| --- | --- | --- |
| Host | Raspberry Pi 4 Model B | Pi 5/cooler not covered. |
| Pi cooling | Official Pi 4 Case Fan kit 18 x 18 x 10 mm heatsink | Allow 0.5 mm adhesive; fan omitted. |
| Pi riser | Two SSQ-120-02-G-D risers plus Megastar ZX-PM2.54-2-20PY J1 | 28.06 mm nominal Pi top to HAT underside. |
| Pi supports | Four straight M2.5 supports, <=4.8 mm outside diameter | Match seated riser/socket height with measured spacers/shims. |
| FPGA | TE0712-03-81I36-A with standard connectors | Four M3 spacers; 8 mm HAT-to-module surface gap. |
| Geophone header / plug | Phoenix Contact 1803280 / 1803581 | Horizontal J90: 1 GEO+, 2 GEO-, 3 shield/GND. |

The geophone plug has 9.20 mm calculated lateral clearance to the module after
0.5 mm allowance. J90 opens parallel to the PCB toward native +Y. Reserve a
12 mm withdrawal stroke beyond the plug and clamp its shielded twisted pair
beside that corridor. The enclosure rotates the stack 180° so entry faces the
adjacent geophone. Release the cable clamp before unplugging.
Use the [R3 enclosure](../hw/mechanical/daqhat-01-case/README.md). Its Pi USB-C
and HDMI side faces the geophone bay, opposite GPIO; the adjacent wall admits
USB-A plugs. R1 printable geometry is superseded because it was mirrored.
The geophone is off-board and vertical; the enclosure holds its bare element in
the adjacent clamp. Mechanical coupling to the ground still needs qualification.

J1 uses the JLCPCB-selected 8.5 mm-body socket. Two external SSQ risers restore
clearance: 8.5 + 2 × 8.51 + 2.54 = **28.06 mm**. The risers are self-nesting;
4.93 mm tails satisfy the intermediate SSQ's 3.68–6.35 mm insertion range.
Check the upper riser's engagement in Megastar J1 and the lower riser's engagement
on the actual Pi, continuity of all 40 pins, retention and seated height before
fitting supports. These checks cannot be established from the enclosure render.
[Samtec dimensions](https://suddendocs.samtec.com/catalog_english/ssw_th.pdf).

The external riser was listed with quantity-one pricing and 591 units in stock
at [DigiKey](https://www.digikey.com/en/products/detail/samtec-inc/SSQ-120-02-G-D/1110847)
on 2026-09-27. It is separately purchased assembly hardware, not part of JLCPCB's
117-placement PCB BOM. Recheck stock before purchase.

## Checks and limits

`assembly_fit.py` checks four support envelopes against the actual underside
components, socket, modeled Pi ports and selected heatsink. It reserves 0.5 mm
for support clearance and 1 mm for component/port seating uncertainty.
The [generated report](../hw/groundlark-fpga-hat/boards/groundlark-daqhat-01/prefab-review.json)
records margins. Use supports at (3.5,3.5), (61.5,3.5), (3.5,52.5), (61.5,52.5)
mm. Trim through-hole tails to <=2 mm below the HAT; the model allows 0.2 mm extra.

Keep both risers and match the measured seated height. Removing cables does not qualify a shorter stack.
Actual mating, screws, cooler capacity, strain relief and sensor noise still need
a first-article check. The Pi and service envelopes are conceptual; the Trenz
model is the vendor's generic revision-03 STEP.

C95/C96 and D90 are underside geophone components; C90 is on the front.
ADC supply-pad and U101.4 link through-vias require epoxy-filled/copper-capped processing, as do the other
through-vias in this six-layer revision. Tenting alone does not meet this requirement.

See the [bench procedure](bench-procedure.md),
[Pi Case Fan brief](https://datasheets.raspberrypi.com/case-fan/case-fan-product-brief.pdf),
and [geophone plug](https://www.phoenixcontact.com/en-us/products/pcb-plug-mc-15-3-st-381-1803581).

## FPGA supply and enclosure clearance

Allow 140 × 56 mm for the revised carrier. Its original Pi and Trenz mounting
coordinates are unchanged. The R3 enclosure supports the power extension with four underside saddles and
board-edge stops. Their stiffness and printed fit remain unqualified.
J83 is at (95, 14.1) mm with its mouth facing -Y, opposite the geophone's +Y
exit. Its 9 × 14.4 × 11 mm body and the actual adapter plug/cable need clearance.
The R3 case is 159 × 118 × 75 mm. Its rear opening reserves up to 14 mm for
an adapter body, subject to the PCB-edge clearance in the enclosure guide.
A roof opening gives access to SW80. Updated illustrations show the wider board.
CAD clearance does not establish printed fit or thermal performance. Apply only
12 V ±5%, center-positive at J83. J130 separately accepts 8–18 V DC for the
TI-controlled Pi supply. Leave Pi USB-C power disconnected when using J130.
Remove the JP130 bench shunt before automatic supervision; MCU firmware and
battery configuration must first be implemented and qualified.
