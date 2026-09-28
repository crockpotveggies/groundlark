# DAQHAT-01 prototype enclosure

The vented indoor enclosure has a 104 × 118 × 75 mm body, 3 mm walls and roof,
and a 5 mm base. Its roof has a 20 mm tall bird recessed 0.6 mm, centered between
the two vent groups. The bird reuses the shared `Logo_Groundlark_7mm.kicad_mod`
favicon outline, including the eye, wing and leg openings.

The Pi/HAT/Trenz stack is rotated 180° about its board center, putting the J90
geophone input beside the geophone bay. Board-space hole coordinates remain
native; the base supports, stack reference solids and port openings use the
enclosure rotation. USB/Ethernet move to the left wall, microSD and FPGA power
to the right wall. Pi power/HDMI/audio face the geophone bay: connect these with
the lid removed and route leads through the front cable opening. Straight plug
access through that bay is obstructed by the geophone; cable and plug selection
and physical fit still need qualification.

J90 is the horizontal Phoenix 1803280 header with a 1803581 cable plug.
The model reserves the full 16.1 mm plug length beyond the header mouth, without
crediting insertion overlap, plus a 12 mm withdrawal stroke. The raised clamp
beside this corridor holds the lead at connector height; release its cap before
unplugging. The Pi-to-HAT gap is 28.06 mm, matching the selected two-riser stack.
Actual mated dimensions, cable bend radius and clamp retention need a first fit.

Install `requirements.txt` in a separate CAD environment. From the repository root:

```sh
python hw/mechanical/daqhat-01-case/case.py
python hw/mechanical/daqhat-01-case/check.py
python -m unittest discover -s hw/mechanical/daqhat-01-case -p 'test_*.py'
```

STL, STEP, renders and fit evidence stay local in ignored
`hw/releases/groundlark-case-r1/`. Geometry used by the renderer is cached in
`.local/case/reference/`.

With Blender 4.0.2 and the existing DAQHAT UI model, prepare the Trenz reference
from its vendor STEP and render with:

```sh
python hw/mechanical/daqhat-01-case/prepare_preview.py
blender --background --python hw/mechanical/daqhat-01-case/render.py
```

Use `-- --view assembly-open --material clear-petg` for an approximate clear PETG
material view. The renderer supports an `assembly-top` view for inspecting the
rotated stack. Material previews do not predict the transparency of a printed part.

The README image uses the same open assembly at 4000 x 2933 pixels, with 384
Cycles samples, adaptive sampling and denoising. To reproduce it:

```sh
blender --background --python hw/mechanical/daqhat-01-case/render.py -- \
  --view assembly-open --material clear-petg --quality high --device CUDA --skip-glb
```

Use `--device CPU` when CUDA is unavailable. The high-quality output is
`preview/assembly-open-clear-petg-4k.png`, with a JSON sidecar recording input
hashes, camera, material and render settings. Copy both files to
`docs/images/groundlark-enclosure.png` and `.json` when updating the README.
Plug screw wells, wire entries and fastener recesses are illustrative render
details inside the reference envelopes; the fit checks use the conservative
solid envelopes. Planar enclosure faces retain flat normals.

The renderer preserves planar mesh faces to avoid wavy shading and produces
closed, open, lid-top and lid-interior views. Electronics and wires include
reference envelopes and illustrative geometry. Checks establish CAD clearances
and mesh validity; first-print fit, thermal behavior and noise remain unqualified.
