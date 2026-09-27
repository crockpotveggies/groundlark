# Sensor interfaces

[Sensor contract v1](../../docs/sensor-contract.md) defines units, time, bounds,
loss and USB framing. Protobuf lives under `proto/`; `buf.yaml` enables STANDARD
lint and FILE compatibility checks. `baseline.binpb` is the frozen initial
descriptor, intentionally tracked as a compatibility fixture. Do not regenerate
it just to make a breaking check pass. Change it only for an explicitly reviewed
new contract version, with migration fixtures.

From the repository root, build the updated portable image once with
`./lab.ps1 build`, then run `./lab.ps1 test -Profile software`.
The full and quick profiles also run these checks. On Linux use
`sh ./lab.sh test --profile software`.

Buf 1.73.0 is SHA-256 pinned in `environment/install_buf.py`; the reference
Python codec uses Protobuf 5.29.6 from the existing locked environment. Tests
need no network or hardware. The descriptor and verification output are built
inside the disposable workspace at `sw/build/`, never added to source control.
The lab retains a small report with its usual five-run retention/cleanup.

`python/` contains the reference validator and incremental framing decoder.
`sensor.options` records candidate Nanopb bounds; it is not generated firmware.
The [Pi application](../pi/README.md) uses these contracts for modeled/Linux
adapters, recording/replay and USB input. Real sensor and firmware qualification
remain separate from software checks.

Skylark adds board ID 3 and sensor IDs 10–16 without changing prior field numbers
or the frozen baseline. Its firmware emits v1 through a bounded C encoder;
native tests decode that output with the Python reference runtime. Raw gas
channels, complete PM/SHT frames, and BMP raw/factory trim remain in recordings.
