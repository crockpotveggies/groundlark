# Pi 4 deployment

The supplied overlay targets the current Pi 4 / BCM2711 design. Do not assume
the same GPIO chip or controller configuration on a Pi 5. This is an explicit
bring-up procedure; no workstation boot configuration is changed by the lab.

1. Build `groundlark-daqhat-01.dtbo` with `dtc -@ -I dts -O dtb -o
   groundlark-daqhat-01.dtbo groundlark-daqhat-01-overlay.dts` on the Pi. Install the result
   under `/boot/firmware/overlays/` and add `dtoverlay=groundlark-daqhat-01` to the
   `[pi4]` section of `/boot/firmware/config.txt`. Ensure the following settings
   are not unintentionally restricted by that section.
2. Remove conflicting SPI chip-select overlays. Do not enable `w1-gpio` or
   `pps-gpio` on BCM4: it is now the geophone DRDY signal. Do not
   enable a kernel IMU driver on the same SPI devices.
3. Reboot. Load `spidev` and `i2c-dev` with `sudo modprobe spidev` and
   `sudo modprobe i2c-dev`. Run `python3 bind_spi.py` to verify all five device
   identities, then `sudo python3 bind_spi.py --apply`. The script will not
   detach a different driver. Repeat binding after a reboot.
4. Verify `/dev/spidev0.0` through `.4`, `/dev/i2c-1`, and the GPIO line mapping
   with `gpioinfo`. Grant the acquisition user access using the Pi's spi/i2c/gpio
   groups. Check the example JSON against the actual chip before using it.
5. From the repository, run `python sw/tools/sensor.py live --fifo --profile
   sw/pi/profiles/daqhat-01.example.json --seconds 60 --output sw/build/bench-001.ssrec`.
   Use a new output filename each time. Start with the FPGA supply off.
   Capture also creates `bench-001.mseed` locally; keep it with the SSREC file.
   Check/synchronize the Pi's date first. Absolute timing is marked unverified;
   see the [miniSEED guide](../../../docs/miniseed.md) for station codes and limits.

Chip-select order is BCM8,7,5. IRQ order is BCM27,22,23. Sensor OE is
BCM26; geophone DRDY is BCM4 (currently polled over I2C). IRQs are rising-edge hints, backed by a 20 ms periodic drain
so an event missed while servicing the FIFO does not strand data. The application
requests GPIO inputs without a bias; the board drives them through U42.

DAQHAT-01 uses ADS122C04 at I2C address 0x40 and MAX-M10S at 0x42. The updated profile assigns PPS to BCM24 (header 18). Use `live --fifo --utc` for timing capture; do not also enable the kernel `pps-gpio` overlay. Geophone conversion counters
report gaps, but polling timestamps do not establish exact sample times.
Conversion gaps do not reset a healthy ADC; real bus faults still trigger bounded
recovery. Modeled independent-clock tests show that current polling does not
preserve every conversion under load.
Dedicated falling-edge DRDY acquisition is the next software step; do not enable
400 kHz merely to claim lossless capture. That speed also needs electrical testing.
Physical qualification follows the [bench procedure](../../../docs/bench-procedure.md).

Build/merge checks run against a small controller fixture. They establish overlay
structure, not a boot test of Raspberry Pi OS or the connected devices.

References: [Pi overlays](https://www.raspberrypi.com/documentation/computers/configuration.html),
[Linux spidev binding](https://docs.kernel.org/spi/spidev.html),
[GPIO v1 event ABI](https://docs.kernel.org/userspace-api/gpio/gpio-get-lineevent-ioctl.html).
