# JLCPCB assembled DAQHAT-01 HAT

The package targets **one fabricated PCB and one assembled HAT**, the same
physical board. The HAT is 85 × 56 mm with 117 placements and 38 BOM lines.
The Pi, Trenz module, geophone, riser, supply and mounting hardware are separate
purchases. The remote sensor head and A2 ASIC HAT are not included.

## Files to upload

| File | Local package |
| --- | --- |
| `DAQHAT-01-Gerbers-REVIEW.zip` | `hw/releases/groundlark-daqhat-01-jlcpcb-review-20260926-one-hat/` |
| `BOM-review.csv` and `CPL-review.csv` together | `hw/releases/groundlark-daqhat-01-jlcpcb-placement-20260926-c91-c92/` |

Use the BOM and CPL from the same overlay. Do not reuse the base package's BOM/CPL
or previous manual rotation overrides. Gerbers contain one closed outline;
BOM quantities are per HAT. Set the supplier's PCB and assembly quantities
separately: the CSV cannot control the website's quantity selector.

Packages remain local and Git-ignored. They include checksums and validation
records; source CAD, part, side or process changes require a fresh export.
The package retains manufacturing holds and is not a fabrication approval.

## Fabrication and assembly requirements

- Six-layer FR-4, nominal 1.6 mm, TG135, ENIG, 1 oz outer / 0.5 oz inner copper.
  Use the stock JLC06161H-3313 stack, with no HDI or custom lamination.
  Its 1.5384 mm copper/dielectric sum is ordered as nominal 1.6 mm, ±10%.
- Through-vias only, 0.30 mm drill, epoxy-filled and copper-capped (POFV),
  including vias in solder pads. Tenting alone is insufficient.
  Do not fill component plated holes or non-plated mounting holes.
- Double-sided assembly: 107 SMT-only placements, seven THT-only placements and
  three mixed SMT/THT connectors. J80/J81/J82 have SMT contacts and plated mounts.
  J1 is the bottom Pi socket.
- Confirm the supplier's one-piece assembly acceptance, handling frame,
  fiducials, part allocation and process requirements. Recorded Standard PCBA
  rules require a two-piece minimum and a 70 mm minimum dimension; the 85 × 56 mm
  HAT therefore needs a supplier-agreed quantity exception and handling frame.
  Do not change the requested quantity without the owner's agreement.
- Verify the supplier placement preview and final proposed production data.
  CAD, modeled tests and catalog pad fits do not establish physical fit or DFM approval.

## BOM mapping and selected parts

The [exact-part registry](../hw/assembly/groundlark-fpga-hat/daqhat-01-jlcpcb-parts.json) binds each
reference to its source value/footprint and approved manufacturer, MPN and C-code.
Catalog listing does not reserve stock or guarantee assembly eligibility.
Recheck allocation at ordering; do not accept automatic substitutes.

| Upload field | CSV column |
| --- | --- |
| Comment / manufacturer part number | `Comment` (full orderable MPN) |
| Designator | `Designator` |
| Footprint / package | `Footprint` |
| JLCPCB / LCSC part number | `JLCPCB Part #` |

Do not use `Description` as the ordering code. Confirm all 38 nonblank catalog
identities and all 117 placements survive import.

| References | Assembly selection | Required specification |
| --- | --- | --- |
| J1 | Megastar ZX-PM2.54-2-20PY / C7499354 | Bottom-mounted 2×20 female socket, 8.5 mm body; stack fit remains open. |
| C42, C80–C82 | Samsung CL31A226KAHNNNE / C12891 | 22 µF, ±10%, X5R, 25 V, 1206. |
| C84, C85 | Murata GRM21BR71C475KE51L / C408144 | 4.7 µF, ±10%, X7R, 16 V, 0805. |
| C90 | Murata GRM31C5C1H104JA01L / C97946 | 100 nF, ±5%, C0G, 50 V, 1206. |
| C91, C92 | KEMET C0603C102J5GAC7867 / C140950 | 1 nF, ±5%, C0G, 50 V, 0603. |
| F80 | Littelfuse 0466005.NRHF / C57525 | 5 A fast fuse, 32 V, 1206. |

F80 must use the 1206 assembly selection; the 0603 source-schematic MPN is not
an approved assembly part. Its nominal cold resistance is 11 mΩ, which is
included in the **30 mΩ total hot power-loop budget**, not an allowance in
addition to it. Check hot voltage drop, startup and fuse behavior on hardware.
Signal capacitors C90–C92 must retain C0G dielectric, tolerance and voltage rating.

**J1 fit remains unresolved:** its 8.5 mm body is shorter than the Samtec socket
in the baseline CAD and stack render. Riser/spacer height, pin engagement and
bottom-side orientation need confirmation. The previous tall-socket geometry
does not qualify this part. See [stack assembly](stack-assembly.md).

## Placement conventions

The exporter fits supplier numbered pads to native footprints using the frozen
[catalog geometry](../hw/assembly/groundlark-fpga-hat/daqhat-01-jlcpcb-placement.json). It accounts
for bottom-side projection and preserves absolute component positions.
Use its CPL rather than raw KiCad angles or manual per-reference offsets.

| References | Supplier CPL rotation |
| --- | --- |
| J1 (Bottom) | 0° |
| J4 | 270° |
| JP1, JP80, JP81 | 0° |
| J80, J81 | 180° |
| J82, J83 | 270° |
| J90 | 180° |
| U1, U22, U41, U42 | 270° |
| U100–U103 (Bottom) | 270° |
| Q1, U40, U51, U52 | 180° |
| D90 (Bottom), C91, C92 (Top) | 0° |

Check J1's underside model and pin-1 direction in the supplier preview. Its
front-layer land pattern requires a bottom-mounted socket. Confirm mixed
SMT/THT assembly, reflow/cleaning limits and sensor handling with the supplier.
Each placement must have a part-bound catalog mapping
or explicit exception. Changed MPNs or footprints invalidate those mappings.
The full exporter and overlay use the same solver; repeated export does not
apply an extra rotation. This checks registration, not solder-joint reliability.

## Reproduce exports without changing CAD

Use KiCad 9.0.9 and a Python that imports `pcbnew` (WSL or the portable lab).
The exporter rejects source CAD/BOM hashes that differ from recorded validation,
checks all native DRC severities, validates the layer/drill inventory, and verifies
that BOM and CPL references agree. It refuses to overwrite a populated directory.

```bash
python3 hw/tools/jlcpcb_package.py --quantity 1 --output .local/jlcpcb/new-review
python3 -m unittest discover -s hw/tests -p 'test_jlcpcb*.py' -v
```

For optional independent plot inspection and PDF production, keep dependencies
inside the repo rather than installing into the atopile environment. The review
renderer uses rsvg-convert for luminance masks so silkscreen cutouts preserve
underlying copper, and draws the silkscreen above copper:

```bash

# Also requires rsvg-convert (librsvg2-bin on Debian/Ubuntu).
python3 -m venv --system-site-packages .local/fab-venv
.local/fab-venv/bin/pip install gerbonara==1.5.0 reportlab==4.4.10
.local/fab-venv/bin/python hw/tools/jlcpcb_inspect.py .local/jlcpcb/new-review
.local/fab-venv/bin/python hw/tools/jlcpcb_drawings.py .local/jlcpcb/new-review
```

The independent parser compares every exported hole location, diameter and
span to CAD (1 micrometre coordinate quantization), and parses all 13 plot layers.
The package report gives actual drill counts; no blind-drill files are accepted.
It emits benign parser warnings about KiCad's G90 header position and unused
RoundRect macro parameters; these are retained rather than suppressed. Render
the PDF with `pdftoppm` and inspect each page. Gerber parsing does not establish
DFM approval or validate solder-paste apertures against supplier process limits.

After adding the package README and reviewing the PDF, run
`python3 hw/tools/jlcpcb_seal.py .local/jlcpcb/new-review` to write checksums
and the complete review ZIP. This retains all manufacturing holds; it does not
promote the package to an approved release.

## Sources reviewed 2026-09-25

- [JLCPCB assembly capabilities](https://jlcpcb.com/capabilities/pcb-assembly-capabilities):
  Standard service, two-piece minimum, panel dimensions, rails and fiducials.
- [PCB capabilities](https://jlcpcb.com/capabilities/Capab) and
  [six-layer POFV](https://jlcpcb.com/news/free-via-in-pad-6-20-layer-pcbs-pofv).
- [KiCad 9 export guide](https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9).
- [BOM format](https://jlcpcb.com/help/article/bill-of-materials-for-pcb-assembly)
  and [CPL format](https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly).
- [Parts sourcing](https://jlcpcb.com/help/article/pcba-parts-sourcing-instruction).
- [LSM6DSOTR catalog](https://jlcpcb.com/partdetail/LSM6DSOTR/C2655100)
  and [TCA9534PWR catalog](https://jlcpcb.com/partdetail/TexasInstruments-TCA9534PWR/C783615).
