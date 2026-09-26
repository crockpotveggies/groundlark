# Documentation

## Getting started

- [Sensor workbench](sensor-workbench.md): installation, first experiment, recordings and replay.
- [Sensor software](sensor-software.md): command-line simulation and Pi acquisition.
- [Stimulus scenarios](stimulus-models.md): saved inputs, waveforms and sensor-model limits.
- [Project layout](project-layout.md): where to find hardware, software and generated files.

## Hardware and assembly

- [DAQHAT-01 hardware](trenz-hat.md): sensors, Trenz module, power, connectors and fabrication stack.
- [Pi/FPGA host link](fpga-host-link.md): SPI/QSPI pins, UART, JTAG and bring-up.
- [Geophone input](geophone-input.md): Racotech connection, analog circuit and accelerometer axes.
- [Stack assembly](stack-assembly.md): Pi, HAT, FPGA, cooling, supports and geophone lead.
- [JLCPCB assembly](jlcpcb-assembly.md): upload files, selected parts, placement and manufacturing requirements.
- [Physical bench procedure](bench-procedure.md): power, fit, timing and noise measurements.
- [A2 ASIC HAT](design-a0.md), [Coldfoot module](coldfoot-integration.md) and [A2 validation limits](validation.md).
- [Burrowlark DAQUSB-01 USB sensor head](usb-sensor-head.md): magnetometer, optional infrasound and firmware interface.

## Interfaces and reproducible builds

- [Sensor data contract](sensor-contract.md) and [schema tools](../sw/interfaces/README.md).
- [GNSS timing](utc-timing.md): legacy hardware/recording support; GNSS is absent from DAQHAT-01.
- [Hardware build](build.md), [portable tests](portable-lab.md) and [SPICE scope](../hw/simulation/README.md).
- [Component and vendor references](sources.md).

The hardware is an engineering prototype. Modeled tests do not replace physical
power, fit, timing, thermal or noise qualification.
