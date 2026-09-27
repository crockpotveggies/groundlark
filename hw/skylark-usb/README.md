# Skylark USB

Skylark is the planned outdoor air-quality USB accessory in the Groundlark
project. Its scope includes particulate matter, SO2, H2S, temperature, humidity
and barometric pressure. It is a USB accessory; no camera or Pi HAT is included.

No electrical design, PCB, firmware implementation, build target or fabrication
package exists yet. This directory reserves the product's home without implying
hardware readiness.

As the design is implemented, circuit definitions belong in `elec/`, placement
inputs in `layout/`, native KiCad projects in `boards/`, and enclosure sources in
`mechanical/`. Reuse [shared hardware resources](../shared/README.md) and the
existing portable lab. Firmware belongs under `sw/`.
