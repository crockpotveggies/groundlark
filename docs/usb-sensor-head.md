# Burrowlark DAQUSB-01 — USB sensor head

**Burrowlark** (model **DAQUSB-01**) is Groundlark's 70 × 45 mm remote USB-C
sensor board, carrying an RM3100 magnetometer and SHT45 temperature/humidity sensor. The DLVR infrasound sensor and
its bypass capacitor have moved to Groundlark DAQHAT-01 as U23/C24. Its circuit source is [`hw/burrowlark-usb/elec/field_head.ato`](../hw/burrowlark-usb/elec/field_head.ato),
its native CAD is in [`hw/burrowlark-usb/boards/groundlark-field-head/`](../hw/burrowlark-usb/boards/groundlark-field-head),
and its firmware belongs in [`sw/field-head/`](../sw/field-head/README.md).

Prototype target firmware now implements the fixed RM3100/SHT45 profile, USB
framing and boot journal. Native fault fixtures and ARM linking are software
evidence; real enumeration, suspend current, sensors and timing remain unqualified.

Connect Burrowlark directly to an existing Raspberry Pi USB host port with a
USB data cable. The HAT communicates with the Pi over its 40-pin header; the
A2 ASIC HAT retains the run-1 Coldfoot module. There is no USB connector, cable
power output or PCA9615 transceiver on the HAT.

## Circuit

- J1: GCT USB4105-GF-A USB 2.0 receptacle; both D+ contacts are joined, as are
  both D− contacts. CC1 and CC2 each have their own 5.1 kohm, 1% pull-down.
  SBU is unused. The shield joins board ground. No PD negotiation is required.
- D1/D2: USBLC6-2SC6 protection on D+/D− and CC1/CC2, referenced to VBUS/GND.
- F1: MF-MSMF050-2, 500 mA-hold resettable fuse, followed by AP2112K-3.3TRG1.
  The LDO has 2.2 uF input and 4.7 uF output capacitors; its enable follows input.
- U1: STM32F042K6T6, native full-speed USB with internal pull-up and HSI48/CRS.
  Each supply has local 100 nF bypass. NRST has 10 kohm/100 nF; BOOT0 has a
  10 kohm pull-down and a boot jumper. SWD provides debug/programming access.
- U5: TPS22919DCKR switches the sensor rail; PA0 enables it, a 100 kohm pull-down
  defaults it off. QOD joins output for discharge through the internal resistor.
- PB6/PB7 read RM3100 (0x20) and SHT45 (0x44) over local I2C. Pull-ups connect to the switched
  rail. PB0 reads RM3100 data-ready. U3/C5 and their pressure-sensor branches
  are removed; the USB board remains 70 × 45 mm.

- U6: Sensirion SHT45-AD1B-R2, DFN-4 1.5 x 1.5 mm. Pins 1/2 are SDA/SCL,
  pin 3 is switched V3_SENSOR, pin 4 is GND. C10 provides local 100 nF bypass.
  This shares the existing switched-rail pull-ups; its heater remains off.

J2 SWD pins: 1 = 3.3 V reference, 2 = SWDIO, 3 = GND, 4 = SWCLK, 5 = NRST.
Use its 3.3 V pin as a probe reference; do not power it externally while USB is
connected. J3 connects BOOT0 to 3.3 V when fitted. Keep it open for normal boot.

## Firmware contract

The PCB alone will not enumerate: the prototype USB firmware must be flashed.
Configure HSI48 and CRS according to ST's USB clock requirements. Implement a
full-speed USB CDC interface with a maximum 100 mA descriptor (bMaxPower = 50).
Use a properly assigned VID/PID before distribution. Do not invent an identity.

Keep sensors off before USB configuration and during suspend; place SDA, SCL
and DRDY in high impedance without internal pull-ups while their power is off.
Disable USB clocks/peripherals as required to meet suspend current, then restore
clock synchronization, sensor power and acquisition on resume. Measure current
in every USB state; component budgets and a PTC are not compliance evidence.

Start with a 100 kHz local sensor bus. Preserve signed 24-bit magnetic samples,
sequence numbers and MCU acquisition timestamps. Legacy recordings may retain
pressure status bits from the former optional DLVR population. Report
sensor identity, configuration, overruns and reset reasons. The Pi correlates
timestamps and calibrates/stores readings; Coldfoot integration is deferred.
Use the [sensor v1 contract](sensor-contract.md) for Protobuf messages, explicit
timestamp domains, loss reporting and bounded COBS/CRC framing. Its reference
codec and prototype MCU implementation are tested in software; physical enumeration remains pending.
USB arrival time must not be represented as exact sensor acquisition time.

Target operating envelope: 25 mA controller plus 25 mA sensors = 50 mA; verify
against real modes, temperature and module variants. Startup capacitance is
2.2 + 4.7 + 0.4 = 7.3 uF nominal on the unswitched rails, plus NRST charge and
parasitics. Sensor capacitors/module load are behind the initially off switch.
Capacitor tolerance, inrush and USB suspend behavior require measurement.

## CAD and previews

The routed PCB, compiled layout, review schematic and BOM contain the RM3100
and its C4 bypass capacitor, plus SHT45 U6/C10, with no U3/C5 pressure-sensor population. The
70 × 45 mm outline, USB interface and native SES routing snapshot are retained.
[PCB render](../hw/burrowlark-usb/boards/groundlark-field-head/3d.png) and
[schematic/assembly previews](../hw/burrowlark-usb/boards/groundlark-field-head/preview/)
show this population; [rebuild commands](build.md) regenerate them from native CAD.
The circuit and CAD checks reject removed pressure parts in both compiled and
routed boards, placement metadata and review schematics.

## Layout and validation limits

Keep the complete head away from the Pi, fan and Coldfoot. Its own USB MCU and
cable current can still contaminate magnetics; compare quiet and active USB
conditions, calibrate the installed orientation and use nonferrous hardware.
The 27 SPICE cases include bounded USB cable/PTC loss, ideal LDO headroom,
sensor-switch on resistance and CC pull-down corners. They do not simulate USB
enumeration, signal integrity, regulator stability, ESD or firmware behavior.

Select a fabrication stackup and review USB impedance/return paths before
manufacturing. Native KiCad checks establish geometry and connectivity only.

## Manufacturer references

- [STM32F042 family datasheet](https://www.st.com/resource/en/datasheet/stm32f042t6.pdf)
- [TPS22919 datasheet](https://www.ti.com/lit/ds/symlink/tps22919.pdf)
- [AP2112 datasheet](https://www.diodes.com/datasheet/download/AP2112.pdf)
- [USB4105 drawing](https://gct.co/files/drawings/usb4105.pdf)

## SHT45 acquisition and installation

Use high-precision command `0xFD` at address `0x44`, with a STOP followed by
at least 8.3 ms before reading six bytes (the reference driver waits 9 ms).
Check the CRC of each two-byte word: polynomial 0x31, initial value 0xFF.
Publish both original words and CRCs as sensor 17 `ClimateRaw`, once per second,
with MCU acquisition timing. A failed read produces missing data and bounded
recovery; it never becomes a zero-temperature or zero-humidity reading.
The fixed profile exposes no heater command. See the
[Sensirion SHT4x datasheet](https://sensirion.com/resource/datasheet/sht4x).

Temperature is `-45 + 175 * raw / 65535` degrees Celsius. Relative humidity is
`-6 + 125 * raw / 65535` percent; clip the display to 0-100% while retaining
unchanged raw bytes. Keep the sensing opening free of solder flux, coating and
potting. Inside a sealed buried enclosure, this measures enclosure air and
helps detect condensation/leaks; it does not measure soil water content.
Board heat and the enclosure's equilibration delay require characterization.

The browser workbench runs the command-aware reference driver against a modeled
bus, including both CRCs, independent magnetic/climate faults, recovery and raw
record/replay. It is not USB enumeration or STM32 firmware qualification.
The selected assembly identity is recorded under
[`hw/assembly/burrowlark-usb/`](../hw/assembly/burrowlark-usb/).
