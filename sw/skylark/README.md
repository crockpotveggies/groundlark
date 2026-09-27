# Skylark USB firmware

Prototype firmware for the **STM32F072CBT6** on the current Skylark Rev A PCB.
The ARM image builds and the production C sensor drivers, encoder and boot
journal run in native fault tests. Physical USB enumeration, suspend current,
sensor timing, analog settling and calibration still require a populated board.

## Build and test

From the repository root:

```powershell
./lab.ps1 build
./lab.ps1 unit
./lab.ps1 test -Profile software
```

Linux/macOS: use `sh ./lab.sh build`, `sh ./lab.sh unit`, and
`sh ./lab.sh test --profile software`. The shared software profile builds the
firmware, checks wire compatibility, and compiles/runs the actual C drivers with
injected I²C/UART failures. It also exercises queue overflow, reconnects, warmup,
conversion-counter loss, and interrupted flash writes/erases.

The lab uses Debian ARM GCC 12.2.1 and libopencm3 commit
`2da12dc96e0b9e42a3332348dd9b02a0a17981f8`, fetched and SHA-256 verified by
[install_skylark.py](../../environment/install_skylark.py). Complete upstream
sources and licenses remain under `/opt/skylark/libopencm3` in the image.
The application is GPL-3.0-only; libopencm3 retains its LGPL-3.0-or-later license.
Preserve corresponding sources and license notices when distributing firmware.

For a direct Linux build with that library and an ARM GCC toolchain:

```sh
make -C sw/skylark/firmware LIBOPENCM3=/absolute/path/to/libopencm3 \
  EXTRA_CFLAGS=-isystem/usr/include/newlib
```

Outputs are ignored `sw/skylark/build/skylark.elf` and `skylark.bin`.
The portable profile instead builds under `sw/build/skylark-arm/` in its
disposable workspace and retains ELF/BIN/map plus size and SHA-256 metadata in
`.lab/runs/<run-id>/results/sw/build/skylark-arm/`. The link reserves at least 4 KiB for stack; no heap or
RTOS is used. Physical stack watermarking remains part of bring-up.

## Program a prototype

Use J3 SWD with a 3.3 V compatible ST-Link and the STM32F0 target profile.
The image starts at `0x08000000`; the last **4 KiB at 0x0801F000–0x0801FFFF**
store a two-page boot counter. Program/verify only image pages. **Do not mass
erase or overwrite the journal during updates:** reusing a device/boot identity
breaks recording ordering. A failed or exhausted counter stops acquisition.
SW1 resets the MCU; SW2 selects the STM32 ROM bootloader when held during reset.
The normal acquisition path needs neither button.

Default USB **1209:0001** is the pid.codes identifier reserved for
[private in-house testing](https://pid.codes/1209/0001/). Before distributing
devices, build with an allocated VID/PID via
`EXTRA_CFLAGS='-DSK_USB_VID=... -DSK_USB_PID=... -isystem/usr/include/newlib'`.
The serial string is the MCU's 96-bit unique ID. The USB device requests 500 mA.

## Acquisition

USB configuration starts sensor power and acquisition. CDC DTR opens the data
session; closing the port leaves the cells conditioned and continues acquisition
without buffering disconnected samples. Reopening announces a new configuration
revision with sequence continuity and does not restart conditioning.
USB reset, unconfiguration or suspend clamps the electrodes and removes
analog/PMS power. Restoring USB power authorization repeats sensor setup and warmup.
The MCU reduces its clock in suspend and disables the ADC/UART/I²C peripherals;
the actual total suspend current and USB compliance are **not measured**.

| Sensor | Firmware behavior |
| --- | --- |
| ADS122C04, I²C 0x40 | AIN0/1 = SO₂ working/auxiliary; AIN2/3 = H₂S working/auxiliary. Gain 1, PGA bypass, external 2.5 V reference, normal 20 SPS single-shot conversions. Four slots, 60 ms apart; 240 ms per channel. Readback, inverted-data integrity and conversion counter checked. |
| SHT40, I²C 0x44 | Serial probe, high-precision measurement every second, CRC on both raw words; heater off. |
| BMP390, I²C 0x76 | Chip ID/readback, pressure ×8 and temperature ×2 oversampling, 3.125 Hz normal mode; latest ready sample every second. Six raw bytes plus 21 factory trim bytes retained. |
| PMS5003, USART2 | 9600 8N1; complete 32-byte active-mode frames with checksum/error-byte checking. Latest fresh frame published every second. Rail-fault/low-VBUS detection disables power. |

On startup, analog rails settle for 150 ms while electrodes remain clamped.
Gas samples are **missing for 60 seconds**, PMS samples for **30 seconds**.
These are prototype policies, not measured cell stabilization guarantees.
Keep raw working and auxiliary values separate. ADC volts = counts × 2.5 / 2²³;
ppm conversion, zero/temperature compensation and detection thresholds require
cell-specific calibration, polarity checks and environmental qualification.

Three I/O failures latch the affected sensor until USB power is reset. Closing
and reopening the serial port does not clear the latch or disturb electrode bias.
All four gas streams share the ADC's fault state; other sensors continue.
Not-ready, invalid checksum, stale PMS data, warmup and unknown conversion loss
never become zero measurements. The eight-frame transmit queue drops newest
data under backpressure. Sequence gaps remain visible; loss counts are unknown.
The firmware never resets the ADC solely because its counter skipped.

## Capture and replay

The firmware uses the existing [v1 sensor contract](../../docs/sensor-contract.md):
COBS, CRC-32, protobuf identity/configuration/batches/status, board ID 3.
No ASCII console, command protocol or calibrated gas values are emitted.
Generate the current descriptor as described in the
[software guide](../../docs/sensor-software.md), then on Linux:

```sh
python sw/tools/sensor.py usb --board skylark --usb /dev/ttyACM0 \
  --seconds 120 --output sw/build/skylark-field.ssrec
python sw/tools/sensor.py replay sw/build/skylark-field.ssrec
python sw/tools/sensor.py simulate --board skylark --seconds 8 \
  --output sw/build/skylark-sim.ssrec
```

Prefer the actual `/dev/serial/by-id/...` path when several USB devices exist.
The same bounded receiver, validation and recording format serve both USB boards.
Open captures in the existing workbench; choose **Skylark USB** for simulation,
or **Test selected board** for an ideal-stimulus acquisition/replay check.
That UI test does not run MCU instructions. Native C driver tests and ARM linking
are in the portable software profile. Burrowlark firmware remains separate.

## Source references

- [TI ADS122C04 datasheet](https://www.ti.com/lit/ds/symlink/ads122c04.pdf), register map and data integrity.
- [Sensirion SHT4x datasheet](https://sensirion.com/resource/datasheet/sht4x), commands and CRC.
- [Bosch BMP390 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp390-ds002.pdf), register profile and compensation.
- [libopencm3](https://github.com/libopencm3/libopencm3), STM32 peripherals and USB CDC support.
- [Hardware pin/power requirements](../../hw/skylark-usb/README.md), including the SGX bias assumption and outstanding physical checks.
