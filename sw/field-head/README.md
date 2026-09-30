# Burrowlark DAQUSB-01 firmware

Planned firmware for the Burrowlark (DAQUSB-01) USB-C board's microcontroller:
magnetometer acquisition, USB descriptors/transport,
and recovery from resets and disconnects. The authoritative interface is the existing
[Burrowlark circuit and firmware contract](../../docs/usb-sensor-head.md), with
messages and framing in the [sensor data contract](../../docs/sensor-contract.md).
Candidate Nanopb bounds exist; actual C/ARM/USB memory fit still needs validation.

Firmware implementation, enumeration tests and physical USB validation are pending.
This firmware is separate from the Pi software that drives the accelerometer HAT.
