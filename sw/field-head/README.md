# Burrowlark DAQUSB-01 firmware

Prototype STM32F042K6 firmware implements RM3100 magnetic and SHT45
temperature/humidity acquisition, USB CDC framing and reconnect handshakes.
The authoritative interface is the existing
[Burrowlark circuit and firmware contract](../../docs/usb-sensor-head.md), with
messages and framing in the [sensor data contract](../../docs/sensor-contract.md).
The bounded encoder uses no heap. The ARM build reserves two 1 KiB boot-journal
pages and at least 2 KiB of stack; the shared software profile checks the link.

Actual enumeration, sensor behavior, USB suspend current and physical validation are pending.
This firmware is separate from the Pi software that drives the accelerometer HAT.

The SHT45 profile uses address 0x44, heater-off high precision (0xFD), a 9 ms
conversion wait and one six-byte CRC-checked raw frame per second. Publish
sensor 17 under the USB-head identity using MCU timing. The Python injected-bus
reference is `sw/pi/groundlark/burrowlark.py`; the browser simulation exercises
it. Native C tests independently decode the target encoder's output and inject
I2C failures, CRC faults, DTR reconnects, suspend and backpressure.

Run `./lab.ps1 test -Profile software` (or `./lab.sh test --profile software`).
Firmware sources are in `firmware/`; binaries are retained in the bounded lab.
The default USB VID/PID is a private testing placeholder, not an allocated
product identity. Do not distribute it as a production USB device.

RM3100 uses cycle count 200, TMRC 0x96 and 10 Hz publication. Its physical
conversion loss remains unknown. Failed reads emit missing data; three consecutive
faults latch that sensor until the sensor supply is cycled. USB configuration
controls sensor power; suspend/reset turns it off. An independent watchdog
resets a stalled loop. Preserve the boot-journal pages when updating firmware.
