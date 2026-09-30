# Burrowlark DAQUSB-01 firmware

Planned firmware for the Burrowlark (DAQUSB-01) USB-C board's microcontroller:
RM3100 magnetic and SHT45 temperature/humidity acquisition, USB descriptors/transport,
and recovery from resets and disconnects. The authoritative interface is the existing
[Burrowlark circuit and firmware contract](../../docs/usb-sensor-head.md), with
messages and framing in the [sensor data contract](../../docs/sensor-contract.md).
Candidate Nanopb bounds exist; actual C/ARM/USB memory fit still needs validation.

Firmware implementation, enumeration tests and physical USB validation are pending.
This firmware is separate from the Pi software that drives the accelerometer HAT.

The SHT45 profile uses address 0x44, heater-off high precision (0xFD), a 9 ms
conversion wait and one six-byte CRC-checked raw frame per second. Publish
sensor 17 under the USB-head identity using MCU timing. The Python injected-bus
reference is `sw/pi/groundlark/burrowlark.py`; the browser simulation exercises
it, but this does not supply or validate the STM32 USB firmware.
