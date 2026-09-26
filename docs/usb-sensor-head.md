# Burrowlark DAQUSB-01 — USB sensor head

**Burrowlark** (model **DAQUSB-01**) is Groundlark's 70 × 45 mm remote USB-C
sensor board, carrying an RM3100 magnetometer and an optional DLVR infrasound
sensor. Its circuit source is [`hw/elec/field_head.ato`](../hw/elec/field_head.ato),
its native CAD is in [`hw/boards/groundlark-field-head/`](../hw/boards/groundlark-field-head/),
and its firmware belongs in [`sw/field-head/`](../sw/field-head/README.md).

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
- PB6/PB7 read RM3100 (0x20) and optional DLVR (0x28) over local I2C. Pull-ups
  connect to the switched rail. PB0 reads RM3100 data-ready. The DLVR remains DNP
  by default and needs pneumatic hardware for infrasound measurements.

J2 SWD pins: 1 = 3.3 V reference, 2 = SWDIO, 3 = GND, 4 = SWCLK, 5 = NRST.
Use its 3.3 V pin as a probe reference; do not power it externally while USB is
connected. J3 connects BOOT0 to 3.3 V when fitted. Keep it open for normal boot.

## Firmware contract — implementation pending

The PCB alone will not enumerate: USB firmware must be written and flashed.
Configure HSI48 and CRS according to ST's USB clock requirements. Implement a
full-speed USB CDC interface with a maximum 100 mA descriptor (bMaxPower = 50).
Use a properly assigned VID/PID before distribution. Do not invent an identity.

Keep sensors off before USB configuration and during suspend; place SDA, SCL
and DRDY in high impedance without internal pull-ups while their power is off.
Disable USB clocks/peripherals as required to meet suspend current, then restore
clock synchronization, sensor power and acquisition on resume. Measure current
in every USB state; component budgets and a PTC are not compliance evidence.

Start with a 100 kHz local sensor bus. Preserve signed 24-bit magnetic samples,
pressure status bits, sequence numbers and MCU acquisition timestamps. Report
sensor identity, configuration, overruns and reset reasons. The Pi correlates
timestamps and calibrates/stores readings; Coldfoot integration is deferred.
Use the [sensor v1 contract](sensor-contract.md) for Protobuf messages, explicit
timestamp domains, loss reporting and bounded COBS/CRC framing. Its reference
codec is tested; MCU implementation and enumeration are still pending.
USB arrival time must not be represented as exact sensor acquisition time.

Target operating envelope: 25 mA controller plus 25 mA sensors = 50 mA; verify
against real modes, temperature and module variants. Startup capacitance is
2.2 + 4.7 + 0.4 = 7.3 uF nominal on the unswitched rails, plus NRST charge and
parasitics. Sensor capacitors/module load are behind the initially off switch.
Capacitor tolerance, inrush and USB suspend behavior require measurement.

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
