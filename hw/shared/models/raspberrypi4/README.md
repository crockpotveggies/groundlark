# Raspberry Pi 4B display model

Detailed component CAD by **integrated-circuit**, from the
[FreeCAD community library](https://github.com/FreeCAD/FreeCAD-library/tree/13b72b471f641f4a665644718a4b223ad572edda/Electronics%20Parts/Boards/Raspberry/Raspberry%20Pi%204B),
licensed [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
The original license is retained in `LICENSE-Assets`; the pinned source URL,
revision and SHA-256 are in `provenance.json`.

`raspberry-pi-4b.step.gz` is losslessly compressed source CAD. The derived GLB
contains 89 component solids with detailed connector shells, contacts and IC
bodies. Groundlark rotates and tessellates this geometry, and applies approximate
presentation colors/materials. No source geometry is reflected.

The source axes are X along the board, Y above it and Z across it. Conversion to
physical Z-up is `(x, -z-56, y)`. The GLB uses millimetres and glTF Y-up axes.
The enclosure renderer seats the model's PCB underside on the supports. Its
1.8 mm modeled thickness is retained conservatively; the nominal Pi board is
1.6 mm. Some header geometry in this community model is approximate.

This is display/reference CAD, not Raspberry Pi certified mating CAD. The
[official mechanical drawing](https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-mechanical-drawing.pdf)
and independent numbered-pad fixtures control the enclosure/PCB orientation.
`prepare_components.py` in the enclosure directory rebuilds the mesh;
`check_components.py` checks physical landmarks and printed-part intersections.
