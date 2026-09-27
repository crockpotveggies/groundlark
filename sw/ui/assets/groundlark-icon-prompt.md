# Groundlark favicon

The PCB uses a monochrome trace of this mark, without the navy tile. Its native
KiCad artwork is `hw/shared/libraries/Groundlark.pretty/Logo_Groundlark_7mm.kicad_mod`.
The mark is 7 mm wide, centered at (94.5, 100.7) mm on F.SilkS; the model label
is centered below it at (94.5, 104.8) mm. `hw/tools/silkscreen.py` places the
artwork as board graphics, so it adds no BOM or assembly placement entries.
The trace uses the green channel at a 50% threshold and Potrace 1.16; cubic
curves are sampled and converted to native filled polygons with the eye, wing
and leg negative spaces preserved. The navy tile is omitted. The KiCad
footprint is the editable manufacturing artwork; no bitmap is embedded in the PCB.

Generated with the built-in image-generation tool. The source is
`groundlark-icon.png`; `groundlark-favicon.ico` contains 16, 24, 32, 48, 64,
128 and 256 pixel versions, preserving the source transparency.

Prompt:

Use case: logo-brand. Asset type: square browser favicon for Groundlark, an open-source seismic sensor research project. Create one bold, minimal symbol that fuses a small crested lark bird in side silhouette with a seismic seismogram: the bird's lower body/tail becomes a short angular ground-motion waveform. One coherent compact mark, recognizable bird first and seismic signal second. Flat vector-like graphic, solid mint teal (#64d9c3) on a solid very dark navy (#0d131c) rounded-square tile, transparent outside the tile. Thick geometric shapes, generous negative space, clear at 16 and 32 pixels. Centered, symbol fills about 75 percent of the square. No lettering, no words, no gradients, no texture, no shadows, no grid, no thin lines, no extra badges, no mockup or multiple alternatives. Favicon-ready original design.

Refinement prompt (built-in image edit, using the original generated icon):

Edit the supplied Groundlark favicon. Make only the seismic waveform tail a little more obvious: extend the oscillating portion slightly toward the left and give it three distinct alternating peaks and troughs with a short horizontal lead-in, like a compact seismogram. Keep its thick mint-teal stroke, smooth joins and natural connection into the bird. This is a subtle refinement, not a redesign. Preserve the crested lark's head, beak, eye, wing, body and legs, the overall scale and layout, the mint teal and very dark navy palette, rounded-square tile, and transparent exterior. Ensure the waveform reads clearly at favicon sizes; avoid adding fine detail, extra symbols, text or an ECG heart motif.

Export the browser sizes with ImageMagick:

```sh
magick sw/ui/assets/groundlark-icon.png -define icon:auto-resize=256,128,64,48,32,24,16 sw/ui/assets/groundlark-favicon.ico
```
