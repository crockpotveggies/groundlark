# Local seismic recordings

DAQHAT-01 live acquisition writes **miniSEED 3** beside its `.ssrec` recording.
miniSEED contains uncalibrated integer counts for the geophone and all three
IMUs. The companion SSREC contains full sensor messages, configuration,
diagnostics, explicit missing/unknown-loss records and timing observations.
Keep both files together.

## Capture

Run in the configured [Pi software environment](sensor-software.md):

```sh
python sw/tools/sensor.py live --profile sw/pi/profiles/daqhat-01.example.json \
  --seconds 60 --output sw/build/field-001.ssrec --mseed-station GL001
```

This creates `field-001.ssrec` and `field-001.mseed` locally. Use
`--miniseed PATH` to choose the waveform path, `--mseed-network XX` to set the
network, or `--no-miniseed` for SSREC-only acquisition. Existing files are never
overwritten. Network and station codes use uppercase letters/digits, with
maximum lengths of two and five characters respectively. `XX` is a test network;
use your assigned network code when applicable, and give each deployed unit a
distinct station code.

The current live default, `--mseed-time system`, maps the Pi's raw monotonic
sample clock to system calendar time using a fresh, bracketed observation for
each batch. Check the Pi's date and synchronize its clock before capture.
**This is unverified absolute timing:** records set the miniSEED questionable-time
flag, do not set clock-locked, and do not invent an uncertainty bound. The raw
acquisition timestamps and system-clock observations remain in SSREC; miniSEED
extra headers identify the timing source. This does not qualify timing for
multi-station correlation. A backward calendar step stops the capture rather
than writing overlapping samples; start a new file after correcting the clock.

`--mseed-time recorded` requires sample UTC timestamps. Current DAQHAT-01 live
acquisition has no qualified UTC source, so that mode fails before acquisition.
An offline export can use UTC already present in validated sample messages.
The existing [recording-bound UTC correlation rules](utc-timing.md) still apply.

Simulation requires an explicit synthetic date:

```sh
python sw/tools/sensor.py simulate --seconds 2 --output sw/build/sim-001.ssrec \
  --miniseed sw/build/sim-001.mseed --mseed-start-utc 2026-09-30T00:00:00Z
```

The supplied date is the origin of the simulation clock, never a measured UTC
timestamp. Its records also carry questionable timing. USB magnetometer and
Skylark capture remain SSREC-only; they are outside this seismic export.

## Export an existing recording

```sh
python sw/tools/sensor.py export-miniseed sw/build/field-001.ssrec \
  --output sw/build/field-export.mseed --station GL001 --network XX
```

The exporter validates the SSREC checksum, message contract, configuration,
calibration references and sample order. It uses sample UTC when available,
otherwise the recorded system-clock observation for that specific batch.
Older monotonic-only captures cannot acquire real UTC after the fact: samples
without calendar evidence are omitted and counted, and an export containing no
timed seismic samples fails. For simulation recordings only, supply
`--simulation-start-utc 2026-09-30T00:00:00Z` explicitly. Use the same station,
network and synthetic origin to reproduce an original simulation export.

The JSON result reports record count, channel sample count, bytes, omitted
missing/fault samples and samples lacking calendar time. Omission counts are
sensor samples (one IMU sample contains six channel values). `source_completed`
reports whether the SSREC ended with its normal acquisition summary. A complete
prefix can be exported with `source_completed: false`; a corrupt or truncated
record fails validation. A failed write/export can leave a partial output file;
do not treat that file as a completed capture.

## Channels and raw data

Default FDSN source identifiers are:

| Sensor | Identifiers | Values |
| --- | --- | --- |
| IMU U11, sensor 1 | `FDSN:XX_GL001_01_I_N_1` through `_N_3` | Acceleration X/Y/Z counts |
| IMU U11, sensor 1 | `FDSN:XX_GL001_01_I_J_1` through `_J_3` | Angular-rate X/Y/Z counts |
| IMUs U12/U13, sensors 2/3 | Same codes, locations `02` and `03` | Six channels per IMU |
| Geophone, sensor 9 | `FDSN:XX_GL001_09_I_H_3` | Signed ADS122C04 counts |

There are 19 channels. Axes `1/2/3` are package axes, not surveyed geographic
directions. The geophone uses axis `3`; this does not certify installation
orientation. Temperature, infrasound and other non-seismic payloads stay in
SSREC. `I` denotes irregular sampling. Each record uses the configured nominal
sample period, but only samples whose actual timestamps and sequences match
that period exactly can share a record. Polling jitter therefore often produces
one-sample records. Consumers must retain record start times and gaps; forcing
these onto a regular trace would be a separate resampling operation.

The encoding is little-endian INT32 with CRC32C. Signed IMU and 24-bit geophone
values are preserved exactly, including valid zero and saturation. No unit
conversion, interpolation, axis rotation or response correction is applied,
even when the SSREC also includes calibrated values. Missing/fault samples
produce no waveform values. Gaps, resets, configuration changes and timing or
quality changes end records. Unknown loss remains distinct from known zero.

The `Groundlark` extra-header object records device/boot/sensor identity,
first sequence and acquisition time, configuration hash, quality, loss before
the record, timing provenance and available uncertainty. `calibration_applied`
is false. Full configuration and calibration artifacts remain in SSREC.
Use a miniSEED 3 reader such as EarthScope libmseed/pymseed; software supporting
only miniSEED 2 cannot read these files.

## Storage and limits

Both outputs are bounded independently by `--max-mib` (64 MiB each by default,
up to 1024). Reaching either limit stops capture with an error. There is no
automatic rollover or overwrite. Record buffers hold at most 128 counts per
channel; jitter and event boundaries can make records much shorter. Allow for
header overhead when sizing storage: this is uncompressed raw output, and
irregular acquisition can cost hundreds of bytes per channel sample.

Normal completion flushes and synchronizes both files to local storage.
There is no power-loss durability guarantee: an interrupted capture can lose
pending records or end with a partial record. Orderly Pi shutdown remains
necessary. The miniSEED file has no capture-complete marker; use the SSREC
summary and successful command result to establish normal completion.

## Verification and calibration

The portable software profile runs waveform/count, timing, loss, byte-limit,
short-write and CLI round-trip fixtures in `sw/tests/test_miniseed.py`. A frozen
record generated by EarthScope pymseed 1.0.1 independently checks the wire
format, CRC, signed values and nanosecond date. These tests do not qualify the
physical sensor response or absolute clock accuracy.

Calibration coefficients and measured instrument response have not been added
by the miniSEED exporter. Preserve these raw recordings for subsequent response
calibration and instrument metadata work.

Format references: [FDSN miniSEED 3](https://docs.fdsn.org/projects/miniseed3/en/latest/definition.html),
[FDSN channel codes](https://docs.fdsn.org/projects/source-identifiers/en/latest/channel-codes.html),
and [EarthScope pymseed](https://github.com/EarthScope/pymseed).
