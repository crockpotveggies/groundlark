# Power supplies and operating limits

These are prototype design allocations. Measure startup, steady load, cable
drop, regulator temperature and suspend current before deployment. A passed
calculation is not a USB compliance or physical power qualification result.

## Groundlark FPGA HAT (DAQHAT-01)

| Input | Required allocation | Loads |
| --- | --- | --- |
| Pi header 5 V, pins 2/4 | Reserve 50 mA steady state | LDL1117, three IMUs, ADC and sensor-side interfaces |
| Pi header 3.3 V, pins 1/17 | Reserve 50 mA steady state | Pi-side interfaces, EEPROM, GPIO expander, logic and pull-ups |
| J83 external supply | 3.35 V ±0.5%, 3 A design envelope | Trenz module and FPGA-side circuitry |

**The complete FPGA stack cannot run from the Pi header alone.** Keep J83's
positive supply separate from both Pi rails. Never apply 5 V to J83. See the
[Trenz power and protection requirements](trenz-hat.md#power-and-interfaces).
The 3 A allowance depends on the bitstream and is not a measured module load.

The two 50 mA allowances include interface switching and reserve; they are not
the GPIO signal-pin drive rating. The Pi's supply must also support its own
workload, cooling, USB devices and other accessories. Do not hot-plug the HAT.
At an assumed 1 ms supply ramp, the PCB capacitor charge adds about 220 mA on
5 V and 43 mA on 3.3 V with 20% high capacitance. A 0.1 ms ramp is much more
demanding. This C·dV/dt calculation omits regulator current limiting and source
control loops; verify startup on the intended Pi and power supply.

At 50 mA output, 5.25 V input and 85 °C ambient, the LDL1117 dissipates about
103 mW. Assuming 150 °C/W gives about 101 °C junction temperature. This is a
thermal sensitivity scenario; the actual copper, enclosure and FPGA heating
determine the operating temperature. C42 must retain at least 4.7 µF effective
capacitance for regulator stability.

## Skylark USB

Use a USB data port that grants the board's **500 mA configuration**. The PMS
and gas analog rail remain off until configuration. A power-only charger does
not start acquisition. USB-C pull-down resistors alone do not authorize a
1.5 A or 3 A load; there is no USB-PD negotiation.

The TPS2553's 80.6 kΩ setting gives approximately 289–375 mA current-limit
bounds. A further 50 mA allocation covers the MCU/USB, gas analog rail,
temperature/pressure sensors, digital ADC supply, pull-ups and reserve.
The resulting configured envelope is **425 mA**, leaving about 75 mA below
the descriptor allocation. The SHT40 heater stays off. Current-limit response
and fan startup overshoot still require measurements.

Before configuration the 50 mA allocation is below USB 2.0's 100 mA unit load.
Estimated capacitor charging is about **38 µC**, including downstream digital
capacitors and 20% high capacitance, below the 50 µC screening limit. This
charge calculation does not predict peak inrush or establish compliance.

**The PMS5003 needs at least 4.5 V at J2.** Skylark has no boost converter.
A USB source/cable can satisfy the digital electronics while failing this
sensor requirement. Use a short, low-resistance cable and verify voltage under
fan startup and steady load. For example, 5.0 V at the source, 0.5 Ω total
source/cable/fuse loop resistance and a further 0.25 Ω switch/PM-lead allowance
give about 4.69 V at the 425 mA envelope. The same assumptions with 4.75 V at
the source give about 4.44 V and fail. These resistance values are scenarios,
not extracted PCB or measured cable resistances.

Firmware checks the post-fuse supply through the calibrated MCU ADC, using
a nominal 4.65 V threshold, and checks the switch fault input. A failed or
unavailable voltage measurement disables PM power and reports missing PM
samples; gas and climate acquisition can continue. The ADC monitors upstream
of the switch and lead, so it cannot certify J2 voltage. Divider/ADC error and
the downstream drop must be measured against that threshold.

AP2112 dissipation at a 50 mA output allocation is about 101 mW at 5.25 V input.
An assumed 250 °C/W and 85 °C ambient give about 110 °C junction temperature.
Verify the actual enclosure temperature and capacitor effective values.

During suspend/reset the firmware clamps the cells, holds the gas ADC in
reset, and cuts analog/PMS power. Suspend reduces the MCU/APB clock to 12 MHz
so the polled USB peripheral remains above its 10 MHz erratum limit; ADC,
UART and I²C are disabled. **Total suspend current is unmeasured and must meet
the applicable 2.5 mA USB limit.** The always-on regulator, MCU, digital sensors
and pull-ups remain loads. A compliant lower-power USB suspend/wakeup design
may require further firmware or hardware changes after measurement.

Pi downstream USB limits are shared by all attached devices. Raspberry Pi 4
allows 1.2 A total; Pi 5 normally limits this to 600 mA with a 3 A source,
or 1.6 A with a detected 5 A source. Reserve Skylark's full 500 mA allocation
when planning other peripherals. See [Raspberry Pi power documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#power-supply).

## Reproducible checks

`hw/tools/power_review.py` reads native PCB values and verifies source-domain
connections, the configured USB envelope, attached capacitance and reference
divider settling. Full lab runs retain `power-review/results.json` under the
shared simulation results. Fault fixtures reject an excessive current-limit
setting, added input bulk capacitance and an FPGA input tied to the Pi rail.

For bench qualification, record Pi-model/PSU/cable identities, both header
currents, J83 current, USB attach/configured/suspend currents, J2 minimum
voltage during startup, rail minima/maxima and regulator temperatures. Repeat
with FPGA inactive/active, fan starting/running, minimum source voltage and
the intended temperature range. Missing measurements do not pass a report.

Manufacturer references: [TPS2553](https://www.ti.com/lit/ds/symlink/tps2553.pdf),
[AP2112](https://www.diodes.com/datasheet/download/AP2112.pdf),
[LDL1117](https://www.st.com/resource/en/datasheet/ldl1117.pdf),
[STM32F072 errata ES0223](https://www.st.com/resource/en/errata_sheet/es0223-stm32f072x8xb-device-errata-stmicroelectronics.pdf).
