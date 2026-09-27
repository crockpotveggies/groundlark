# Skylark atomic component assets

`parts.ato` defines physical pin maps used by the Skylark circuit. The accompanying
symbols and custom footprints are authored for this project under its GPL-3.0
license, except for the KiCad-derived footprints listed below.

## KiCad library attribution

Footprints named `Library__Footprint.kicad_mod` are derived from the
[KiCad footprint libraries](https://gitlab.com/kicad/libraries/kicad-footprints),
using the installed KiCad 9 library snapshot on 2026-09-26. They retain the
[KiCad library license](LICENSE.KiCad.md): CC BY-SA 4.0 with the KiCad design
exception. Footprint names were normalized for the local library.

`SHT40.kicad_mod` is derived from
`Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad`.
The 1.27 mm debug header uses 0.75 mm finished holes to match the selected
Amphenol 20021111 part. USB non-plated hole layer declarations were normalized
to KiCad's all-copper notation without changing their dimensions.

## Custom footprints and models

- `BMP390.kicad_mod` follows the Bosch BMP390 land pattern.
- `SGX7_AQ_Socket.kicad_mod` mirrors SGX's bottom-view contact drawing for PCB
  top-view placement and uses the selected Mill-Max receptacle dimensions.
- `Fuse_1206.kicad_mod` is the project-authored resettable-fuse footprint.
- Portable 3D models under `hw/skylark-usb/models/` are project-authored simplified
  envelopes, not manufacturer models. Their dimensions and hashes are recorded
  in that directory's provenance file.

Manufacturer references and assembly limitations are in the
[Skylark guide](../../../skylark-usb/README.md).
