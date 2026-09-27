# Burrowlark USB — DAQUSB-01

Burrowlark is the separate 70 × 45 mm USB-C magnetometer and optional infrasound
sensor head. It uses an RM3100 and optional DLVR sensor. USB-head firmware and
physical qualification remain pending.

- [Electrical source](elec/field_head.ato)
- [Placement inputs](layout/placement.json)
- [Routed KiCad project](boards/groundlark-field-head/groundlark-field-head.kicad_pro)
- [Assembly and interface guide](../../docs/usb-sensor-head.md)
- [Firmware directory](../../sw/field-head/)

Build target: `field_head` in [hw/ato.yaml](../ato.yaml). Existing CAD filenames
and the DAQUSB-01 model identifier are preserved.
