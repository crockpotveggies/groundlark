# Raspberry Pi software

Use `calibration-observe` and `calibration-fit` for measured static gain/offset. The [calibration guide](../../docs/calibration.md) covers fixtures, templates, evidence and instrument binding.

Executable acquisition, calibration, bounded recording/replay, Linux adapters
and deterministic simulation are in `groundlark/`. No configured FPGA is needed.
See the [run guide and recovery policy](../../docs/sensor-software.md).
Live HAT capture writes local [miniSEED 3 seismic files](../../docs/miniseed.md)
alongside SSREC diagnostics. Counts remain raw; Pi system timing is marked unverified.
Use the [stimulus guide](../../docs/stimulus-models.md) for motion/field/pressure
waveforms, GNSS trajectories and timed faults. Example: add
`--scenario sw/pi/profiles/stimulus-demo.json` to the simulation command.

Separate pure processing/protocol logic from Linux I2C/SPI/UART/USB adapters so
the same application can run against recorded samples and fault-injecting fakes.
Use the [DAQHAT-01 sensor/carrier design](../../docs/trenz-hat.md) and
[USB interface contract](../../docs/usb-sensor-head.md). Coldfoot integration is
deferred; if resumed, its host semantics remain owned by the current
`docs/runtime_contract.md` in the separate Coldfoot SoC repository.

Run `./lab.ps1 test -Profile software` for the complete portable demo and tests.
Live adapters cover LSM6DSO, SCL3300 and MAX-M10S. Bus logic has modeled-response
tests. [Pi 4 deployment](deploy/README.md), IRQ-assisted FIFO acquisition and PPS
edge recording are implemented. [UTC capture/correlation](../../docs/utc-timing.md)
and [bench report tools](../../docs/bench-procedure.md) are available; physical
timing bounds and validation remain bring-up work. USB ingestion expects a v1 producer;
the STM32 head still needs firmware.
