# Burrowlark USB — DAQUSB-01

Burrowlark is the separate 70 × 45 mm USB-C magnetometer and enclosure-climate
sensor head. It uses the PNI 14190 RM3100 XYZ module; U3/C5 and their pressure-sensor
branches are removed. The DLVR pressure sensor is on DAQHAT-01. USB-head firmware
and physical qualification remain pending.

![Burrowlark DAQUSB-01 Rev A2 with favicon, RM3100 and SHT45](boards/groundlark-field-head/3d.png)

Native PCB render with the Groundlark favicon, Burrowlark name and
`DAQUSB-01 / REV A2` front silkscreen. The existing A2 board revision is retained.
Module, fuse and SHT45 bodies are simplified envelopes; see
[render provenance](boards/groundlark-field-head/render-provenance.json).

- [Electrical source](elec/field_head.ato)
- [Placement inputs](layout/placement.json)
- [Routed KiCad project](boards/groundlark-field-head/groundlark-field-head.kicad_pro)
- [Assembly and interface guide](../../docs/usb-sensor-head.md)
- [Firmware directory](../../sw/field-head/)

Build target: `field_head` in [hw/ato.yaml](../ato.yaml). Existing CAD filenames
and the DAQUSB-01 model identifier are preserved.
