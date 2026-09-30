# GNSS pulse association and UTC recordings

**DAQHAT-01 GNSS revision:** MAX-M10S-00B uses Pi I2C1 at 0x42 and
BCM24 (header 18) for PPS. The Racotech/ADS122C04 geophone input remains on
I2C 0x40 with DRDY on BCM4. GNSS provides a clock reference; sample/filter
latency and multi-station millisecond alignment require physical measurement.
See [antenna setup and RF limits](gnss-hardware.md).

The Pi can now capture GNSS timepulse configuration, TIM-TP, NAV-TIMEUTC and PPS
edges with `live --fifo --utc`. Correlation is an **offline second pass** which
creates a new recording. The original counts, acquisition times, arrival order,
qualities and gaps are preserved. It neither sets the Pi clock nor runs a time
server. Use the GNSS revision of the PCB and its matching profile.

## Capture and correlate

Follow the [Pi deployment instructions](../sw/pi/deploy/README.md) first. The
commands below assume the normal sensor Python environment and generated schema.
Choose new filenames; these tools refuse to overwrite existing recordings.

```sh
python sw/tools/sensor.py live --fifo --utc \
  --profile sw/pi/profiles/daqhat-01.example.json --seconds 600 \
  --output sw/build/timing-001.ssrec
python sw/tools/sensor.py replay sw/build/timing-001.ssrec
python sw/tools/correlate_utc.py sw/build/timing-001.ssrec \
  --policy sw/build/timing-001-policy.json \
  --output sw/build/timing-001-utc.ssrec \
  --report sw/build/timing-001-utc.json
```

The [policy template](../sw/pi/profiles/utc-policy.template.json) deliberately
contains nulls. Copy it and fill it from the [timing bench procedure](bench-procedure.md).
Null, zero, mismatched or absent bounds cannot produce UTC labels. Policy fields:

| Field | Meaning and qualification |
| --- | --- |
| `recording_sha256` | Hash of the completed original recording; the policy is specific to that capture. |
| `scope` | `bench` for physical captures; `modeled` is accepted only for explicitly modeled timing fixtures. |
| `evidence` | Reference to the measured timing report and its assumptions; recorded with the output. |
| `transport_max_ns` | Upper bound from timing-message generation through complete I²C read, including receiver queuing, polling and fragmentation. Must be below 400 ms. This is **not** just SPI/I²C transaction duration. |
| `edge_error_ns` | Bound on physical PPS edge to kernel timestamp error, including interrupt latency, electrical propagation and reference-instrument error. |
| `pulse_error_ns` | GNSS pulse error against the UTC reference, including antenna/cable delays; quantization error and reported UTC accuracy are added separately. |
| `capture_age_max_ns` | Maximum acceptable delay before the process collects a kernel PPS event; at most 500 ms. |
| `clock_rate_ppm` | Bound on clock-rate deviation during qualified conditions, covering RAW interpolation and MONOTONIC/RAW conversion; 1–5000 ppm. |
| `sample_error_ns` | Per-local-sensor acquisition-time error bounds, in ns. Include device clock mapping, quantization, filter/conversion latency and sample age. Omit a sensor to leave its UTC absent. |

These are supplied engineering bounds, not confidence intervals invented by the
software. Requalify after changing the Pi, kernel, load envelope, receiver firmware,
sample/filter settings or mounting/cabling relevant to timing. A policy with a
false transport bound can still produce an integer-second error: the software
cannot observe a receiver's hidden generation time. Compare against an independent
UTC reference and retain margin under worst-case load. Without that evidence,
retain raw timing captures and use modeled tests; do not label them qualified.

## Receiver and capture behavior

The timed driver requires a 1 Hz GNSS navigation profile, enables UBX TIM-TP and
NAV-TIMEUTC on I²C, disables NMEA there, and sets a 1 Hz UTC-aligned rising pulse
with 100 ms width. Locked and unlocked periods match, but unlocked timing messages
are rejected by correlation. Antenna/user delay settings are zero; account for
their physical error in the policy. All keys are written to RAM, acknowledged
and read back. No flash configuration writes occur.

GNSS service uses the same bounded worker/recovery mechanism as buffered sensors,
with a 20 ms service target, at most eight 256-byte reads and 32 timing events per
call. Configuration-era backlog is drained, parser state is reset, and every
successful configuration is recorded. Parser/checksum or bus failures create
status records. Multiple NAV-PVT results with indistinguishable read timestamps
fail the drain's monotonicity check instead of inventing separate capture times.
The process remains subject to Linux scheduling and physical bus behavior.

`gnss_timing_config` records effective key values; `gnss_tim_tp` and `gnss_timeutc`
retain payload bytes and RAW read brackets. `pps_edge` retains the kernel
MONOTONIC edge, the MONOTONIC/RAW bridge bracket and the bridge observation time.
The current GPIO owner remains the application: do not also enable `pps-gpio`.
Old captures lacking this evidence cannot be retroactively qualified.

## Association rules

TIM-TP labels the **next** pulse. A candidate must have exactly one valid TIM-TP
and one valid NAV-TIMEUTC between the preceding and following PPS edges. The
generation-to-read bound must place the message wholly after the previous edge;
its read must finish before the following edge, including timing margins. Late,
duplicate, invalid, incomplete and boundary-crossing candidates are rejected.
UTC calendar, whole-second pulse grid, known UTC standard and GNSS lock flags
must agree. NAV-TIMEUTC accuracy estimates above 100 ms are rejected.

Only adjacent accepted pulse anchors separated by one UTC second form a usable
interval. RAW cadence must fit the clock/error budget. Interpolation uses integer
arithmetic and adds anchor error, per-sensor acquisition error and conservative
between-anchor clock variation. It never extrapolates through a missing pulse,
startup, receiver fault or loss of lock. Configuration/fault events conservatively
exclude nearby intervals. The report lists accepted intervals and rejection counts.

Samples must fit entirely inside an accepted interval after their acquisition
error allowance. Only VALID/SATURATED local samples with supplied bounds receive
both `utc_unix_ns` and `utc_uncertainty_ns`. USB-head clocks are unrelated and
remain unlabelled. An existing larger acquisition uncertainty is retained in the
calculation; the original acquisition timestamp/uncertainty is never rewritten.

POSIX cannot uniquely represent a leap second. Version 1 deliberately suppresses
UTC for five seconds on either side of **every UTC midnight**, rejects second 60,
and reacquires after consecutive valid anchors. Raw samples continue throughout.
Week rollover is decoded explicitly. This conservative daily gap is an announced
availability tradeoff, not loss of sensor data or a claim of leap-second smearing.

The correlator retains at most 32,768 timing/status events and streams samples in
two passes. Output uses the existing 64 MiB recording budget. A failed output
write may leave an incomplete file; it must not be used as a successful result.
Only operate on completed, immutable input recordings.

## Tests and source

Run `./lab.ps1 test -Profile software`. Tests cover independent calendar/wire
vectors, actual timed-driver configuration/readback, fragmented UBX and checksum
errors, driver-to-recording integration, delayed/duplicate messages, missing or
stale PPS, resets, lock loss, policy mismatches, midnight/leap rejection, week
rollover and correlated-copy replay with unchanged raw data. They exercise modeled
buses and clocks, not physical UTC accuracy.

Recorded checkpoint: portable software run `20260925T040959Z-8ae6ce16` passed
**140 tests** without skips, Buf compatibility checks, deliberate incompatible
change rejection and acquisition/replay demos. The 19 newly added tests comprise
15 UTC/timed-driver cases and four bench-report cases. Ten containment tests also
passed; the Windows junction case was skipped inside Linux. Repository structure
and whitespace checks passed. Hardware CAD is unchanged from `e379fce`.

Protocol reference: [u-blox M10 SPG 5.10 interface description, UBX-21035062 R03](https://content.u-blox.com/sites/default/files/u-blox-M10-SPG-5.10_InterfaceDescription_UBX-21035062.pdf),
sections 3.15.24, 3.18.2 and 4.9.25. Unsupported keys or readback differences on
another firmware revision fail startup; identify the receiver firmware during
bench work. [Linux GPIO event ABI](https://docs.kernel.org/userspace-api/gpio/gpio-get-lineevent-ioctl.html)
defines the event clock used by the capture path.
