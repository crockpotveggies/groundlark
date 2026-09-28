# DAQHAT-01 prototype enclosure

The vented indoor enclosure has a 104 × 118 × 75 mm body, 3 mm walls and roof,
and a 5 mm base. Its roof has a 20 mm tall bird recessed 0.6 mm, centered between
the two vent groups. The bird reuses the shared `Logo_Groundlark_7mm.kicad_mod`
favicon outline, including the eye, wing and leg openings.

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

The renderer preserves planar mesh faces to avoid wavy shading and produces
closed, open, lid-top and lid-interior views. Electronics and wires include
reference envelopes and illustrative geometry. Checks establish CAD clearances
and mesh validity; first-print fit, thermal behavior and noise remain unqualified.
