# Skylark assembly inputs

`jlcpcb-parts.json` binds all 119 PCB assembly placements to exact manufacturers,
orderable MPNs and JLCPCB catalog codes. It also records manual cells, sockets
and the external PMS5003 module. Stock observations are dated and are not
reservations. No fabrication order is authorized by these files.

## Export

With KiCad 9 CLI, its `pcbnew` Python module and `sexpdata` available:

```sh
python3 hw/tools/skylark_package.py --out hw/releases/skylark-usb-review
```

Use a new or empty output directory. The exporter checks native DRC and stock
construction without rewriting or refilling CAD. It emits four-layer Gerbers,
separate plated/non-plated Excellon files with routed USB slots, a review BOM/CPL,
top/bottom assembly drawings, procurement evidence and a source-hash manifest.
Quantities in the BOM describe one board; order quantities are chosen separately.
Generated packages remain ignored and local under `hw/releases/`.

For independent plot and hole comparison, install `gerbonara==1.5.0` in a local
environment that can import `pcbnew`, then run:

```sh
python3 hw/tools/skylark_inspect.py hw/releases/skylark-usb-review
```

This checks all eleven Gerber layers, native outline segments, 177 round plated
holes, four plated USB slots and six non-plated holes. It does not establish
physical signal quality or supplier acceptance.

## Construction and placement

- 90 × 100 mm, 1.6 mm stock four-layer FR-4, JLC04161H-7628;
  outer 1 oz / inner 0.5 oz copper. Through-vias are at least 0.6/0.3 mm.
  No filled/capped vias, via-in-SMT-pad or custom lamination is required.
- `jlcpcb-placement.json` freezes numbered public JLCPCB/EasyEDA pad geometry
  and its source hash. The exporter fits identities and pad envelopes, including
  deliberate contact aliases, instead of assigning reference-specific rotations.
- CPL coordinates are absolute mm, X right and Y up. Bottom parts reflect local
  supplier X before CCW rotation; absolute placement coordinates are never mirrored.
  The bottom assembly SVG is mirrored for physical inspection.
- J3 is a through-hole SWD header. Confirm THT assembly service or fit it manually.
  J1 has SMT contacts and plated shell slots; confirm both processes.
- U11's centre die pad is deliberately unsoldered. Sensirion SHT4x v7.3,
  sections 5.4–5.5, says this pad is unconnected and recommends not soldering it.
  Only the four numbered signal/supply terminals enter the pad fit. The open
  [Adafruit SHT40 PCB](https://github.com/adafruit/Adafruit-SHT40-PCB/blob/40fe2b3aca1aaa3b2185d3d138e77d5b043a56e1/Adafruit%20SHT40.brd)
  independently uses the same four pad centres and omits the centre pad.
- Fit the eight Mill-Max sockets before inserting either SGX cell. Do not reflow
  gas cells or coat their gas openings, the SHT40 membrane or the pressure port.
  Preserve cleaning, guard and coating requirements in the product README.

## Sourcing and remaining qualification

The registry enforces positive available stock, no preorder and minimum order
quantity one for every assembled part. The 2026-09-28 replacements are:

| Reference | Manufacturer / MPN | JLCPCB | Available order quantity |
| --- | --- | --- | ---: |
| J1 | HRO TYPE-C-31-M-12 | C165948 | 438,598 |
| R3 | Yageo RC0603FR-0782KL, 82 kΩ | C137678 | 147,794 |
| U12 | Bosch BMP388 | C779278 | 5,868 |

These are dated observations, not reservations. The exporter rejects a registry
entry with an unavailable quantity, preorder status or a larger minimum.
All 119 placements pass the frozen supplier-pad fit. The HRO drawing dated
2020-12-08 defines 8.65 mm shell spacing, 4.18 mm row spacing and shared power
lands. Supplier shell pads 1–4 map explicitly to grounded S1; data/CC pin names
remain unchanged. The fit checks every physical pad.

Review every component on both sides in JLCPCB's actual order preview. Its
private assembly library can differ from the public catalog. Exact AQ-cell bias,
electrochemical loop stability, physical socket/enclosure fit and operation below
800 mbar remain unqualified. The user owns fabrication approval.

## Gas-cell requirements

`sensor-requirements.json` records exact datasheet revisions, hashes, operating
limits and source comparisons. DS-0685 omits SO₂ bias; DS-0681 prints ppb units in
its H₂S bias row. The circuit maintains WE, AE and RE near the same 1.25 V reference,
giving nominal zero differential bias.

[Soldered Electronics' implementation](https://github.com/SolderedElectronics/Soldered-Electrochemical-Gas-Sensor-Arduino-Library/blob/c4df54b9dbff26c6e6f8dd814ed0133e900030ba/src/sensorConfigData.h)
uses zero bias for SGX-4SO2 and SGX-4H2S-100. The open
[Smart Citizen four-electrode hardware](https://github.com/fablabbcn/smartcitizen-kit-gases-pro-board/tree/ffdb0bc9b76d6bd9d8732966f34968b3d14020a8/hardware/SCK_2.0_GASES_PRO_BOARD_rev3)
uses Alphasense cells and a shared reference. These support the circuit approach,
but neither establishes bias or pressure limits for the exact SGX AQ models.
Do not copy their gain, load or calibration constants into Skylark.

Run the existing hardware regressions after changing these inputs. Offline tests
check identity, geometry, holds and reproducible exports; they never establish
current inventory or measured sensor performance.
