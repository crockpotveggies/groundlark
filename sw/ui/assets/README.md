# Board visualization provenance

The workbench favicon uses a teal lark with a seismic waveform tail on dark
navy. `groundlark-icon.png` is the generated master; `groundlark-favicon.ico`
contains browser sizes from 16 to 256 pixels. See the
[generation prompt and export command](groundlark-icon-prompt.md).

`groundlark-wordmark.svg` combines the existing favicon's master PNG
(unchanged) with the name in Segoe UI Bold, matching the Windows system font
previously used in the workbench header. Text is stored as vector outlines so
the README and UI render identically without downloading or installing a font.
Both use this same self-contained image on a navy background. The PCB artwork
and browser favicon remain unchanged.
Regenerate with `python sw/ui/build_wordmark.py --font C:/Windows/Fonts/segoeuib.ttf`
using build-only `fonttools` (verified with 4.63.0). No font binary is distributed.

`daqhat-01.glb` is a display asset exported with KiCad 9.0.9 from the checked DAQHAT-01 PCB.
It includes the routed board's outline, holes, pads, mask, silkscreen and available
stock component models. It is not a manufacturing deliverable.

KiCad's exporter cannot convert the local VRML bodies. The Python scene adds
simplified envelopes for the Pi socket, Trenz connectors. Selection rings use `hw/groundlark-fpga-hat/layout/placement.json` XY values.
The remote head is a separate placement-based schematic 3D view; its optional
pressure sensor is shown even though the default assembly is DNP.

The external geophone is authored in Python in `../geophone_scene.py`, with a
25.4 mm diameter / 33 mm high Racotech body. Terminals and leads to J90 are
illustrative. Its selectable can and the ADC both map to sensor 9, and both
highlights follow the same selection. It adds no synthetic data stream or
mechanical motion to the acquisition models. Scene source is also hash-pinned.

Regenerate from the repository root on the Linux lab toolchain:

```sh
kicad-cli pcb export glb --force --no-dnp --include-pads --include-silkscreen \
  --include-soldermask --subst-models --output sw/ui/assets/daqhat-01.glb \
  hw/groundlark-fpga-hat/boards/groundlark-daqhat-01/groundlark-daqhat-01.kicad_pcb
```

The exporter reports missing local VRML models and may return nonzero despite creating
the GLB. Inspect the result and missing-model inventory before accepting it.
Do not ignore other export failures. The scene converts GLB metres/Y-up to
centimetres/Z-up, subtracts the CAD origin (50, 50 mm), then centres the 85 x 56 mm
board. The placement coordinates themselves are unchanged.

`provenance.json` pins the PCB, placements and display asset. Update its SHA-256
values only after re-export and alignment review. For a path-only relocation,
retain the previous hashes and verify unchanged normalized CAD, placement data,
model bytes and display assets before refreshing their bindings. The current
`source_relocation` record documents this exception. Startup fails on stale inputs.
Stock KiCad component geometry retains its upstream attribution/license; see
[KiCad's library licensing](https://www.kicad.org/libraries/license/).
