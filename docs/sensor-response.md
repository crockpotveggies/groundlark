# Sensor bandwidth and timing

These specifications cover the current Groundlark FPGA HAT and Skylark USB.
Raw recordings preserve sensor counts. They do not apply inverse response,
gas compensation, or a shared phase correction. Modeled response is not
physical qualification.

## Groundlark

The 4.5 Hz geophone measures ground velocity through its mechanical response,
coil/loading network, ADS122C04 PGA and digital filter. The nominal mechanical
response alone is down **26.13 dB at 1 Hz**. The PCB input network adds about
**0.011 dB at 10 Hz**. Sub-hertz velocity sensitivity cannot be recovered merely
by multiplying raw counts by the nominal 23.4 V/(m/s) sensitivity.

The ADC's nominal 330 SPS profile has an actual nominal period of 3116 clocks
at 1.024 MHz: **328.626 samples/s**, subject to oscillator tolerance. Its
digital filter has a **150.1 Hz −3 dB bandwidth**. Combined nominal estimates
from the mechanical model, routed component values and TI's response plot are:

| Input frequency | Combined attenuation relative to nominal velocity sensitivity |
| --- | --- |
| 1 Hz | approximately −26.1 dB |
| 10 Hz | approximately −0.2 dB |
| 100 Hz | approximately −1.4 dB |

Allow approximately 0.5 dB uncertainty for reading the ADC plot; this is not a
device tolerance. Coil resonance, damping, sensitivity and passive tolerances
add uncertainty. The digital filter is linear phase, but its coefficients and
exact delay are not provided by this analysis. Conversion duration is not a
measured group delay. See [TI SBAS751B, §§8.3.5–8.3.6](https://www.ti.com/lit/ds/symlink/ads122c04.pdf).

The IMU driver explicitly writes and verifies its high-performance filter
settings and records them in `register_config`. Accelerometer LPF2 and the
high-pass paths are disabled; gyro LPF1 is bypassed and LPF2 remains active.

| IMU output rate | Accelerometer LPF1 cutoff | Gyro LPF2 bandwidth |
| --- | --- | --- |
| 26 Hz (default) | 13 Hz | 8.3 Hz |
| 52 Hz | 26 Hz | 16.6 Hz |
| 104 Hz | 52 Hz | 33 Hz |
| 208 Hz | 104 Hz | 66.8 Hz |

At the default gyro setting, ST reports −36° phase at 2.5 Hz, equivalent to
40 ms phase delay **at that frequency**. Do not apply that as a constant delay
to every channel or frequency. FIFO timestamps identify sensor time slots;
they do not remove internal filtering delay. Bandwidth figures and this phase
point come from [ST AN5192, accelerometer and gyroscope bandwidth sections](https://www.st.com/resource/en/application_note/DM00517282-.pdf).

## Skylark

Both working and auxiliary electrode paths have nominal 15.9 Hz feedback and
output poles. Their cascaded electronics settle to within 1% of an ideal current
step in approximately **66 ms**. This excludes cell chemistry, potentiostat
loop dynamics, enclosure exchange and the ADC. Nominal conversion factors are
40 mV/ppm for SO₂ and 34 mV/ppm for H₂S; actual cells require calibration.

The 20 SPS single-shot ADC takes about 50.01 ms per conversion. At a 2% slow
oscillator it takes about 51.03 ms. Firmware permits at least **60 ms between
channel reads/starts**, with one sequential conversion at a time. Each gas
channel therefore has a nominal **240 ms period**, with longer intervals after
service delays. Sequence gaps expose missed nominal opportunities. Timestamps
refer to firmware service time, not the center of the ADC integration window.

**The present gas filters do not establish adequate broadband alias rejection.**
The per-channel Nyquist frequency is only 2.083 Hz, while the ADC bandwidth is
13.1 Hz. The analog electronics attenuate 4.167 Hz by only about 0.58 dB; noise
near that frequency can appear as slow baseline drift after channel sampling.
The converter's 50/60 Hz rejection does not cover every interference frequency.
Filtering already recorded samples cannot remove interference already aliased.

WE and AE are observed at least 60 ms apart. For identical sinusoidal pickup,
unadjusted subtraction leaves a fraction `2 × |sin(π × f × 0.060)|`: about
3.8% at 0.1 Hz and 37.5% at 1 Hz, before allowing for filter mismatch. Preserve
the raw streams; compensation must account for actual timestamps and qualified
cell behavior. Interpolation cannot repair prior aliasing.

Both selected SGX cells specify T90 below 60 seconds. That upper limit neither
defines their full transfer functions nor guarantees rejection of rapid inputs.
It also cannot suppress electrical noise introduced after the cell. References:
[SO₂ DS-0685](https://sgxsensortech.com/uploads/f_note/DS-0685-SGX-7SO2-AQ-20.pdf),
[H₂S DS-0681](https://sgxsensortech.com/uploads/f_note/DS-0681-SGX-7H2S-AQ-25.pdf).

SHT40 measurements and PMS5003 frames are published at 1 Hz; conversion time or
frame cadence does not establish their environmental response. BMP390 uses
pressure ×8 / temperature ×2 oversampling at 3.125 Hz, with IIR off, and publishes
the latest reading at 1 Hz. This pressure stream is intended for weather trends;
it is not a qualified infrasound channel. Its rate reduction has no added
anti-alias filter. See the [BMP390 datasheet](https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bmp390-ds002.pdf).

## Reproduction and qualification

`./lab.ps1 test` (or `./lab.sh test`) runs
[signal_response.py](../hw/tools/signal_response.py) and independent response
regressions. The bounded run retains
`results/hw/shared/simulation/signal-response/results.json`, including routed
PCB/source hashes, gain and phase calculations, passive corner scenarios,
ADC plot checkpoints, alias frequencies, timing and explicit unknowns. The
first-order gas examples are illustrative scenarios, not fitted sensor models.

Neither board has a qualified end-to-end noise floor or alias-rejection result.
Before interpreting field spectra, perform the sweeps and enclosure/cell step
tests in the [bench procedure](bench-procedure.md). Select a required signal
band, maximum interfering amplitude and allowable input-referred alias error
before passing the design. If it fails, reduce analog bandwidth or increase
acquisition rate with filtering before decimation; retain raw measurements and
requalify noise, timing, settling and firmware metadata for that configuration.
