# Pi 4 deployment

## Unattended station software

The supported deployment baseline is **Raspberry Pi OS Lite 64-bit**, Pi 4,
systemd, NiceGUI and Caddy. The minimum medium is a nominal 32 GB SD card
(installer requires at least 30 billion addressable bytes). Alpine is an
unqualified alternative; Omarchy's desktop environment is outside this headless
station profile. Physical image boot and board qualification remain pending.

One NiceGUI application provides `/` for simulation/replay and `/station` for
the persistent station service. Closing a browser does not stop station capture.
Simulation sources are clearly identified and use the same recording/status path.
The default profile has simulated DAQHAT, Burrowlark and Skylark sources. A live
HAT source takes the existing profile path; each USB source needs a distinct
`/dev/serial/by-id/...` device. Set a unique `station_id` at provisioning.

Generate the current descriptor with the software profile and place the validated
`schema.binpb` in `sw/build/`. Package the runtime:

```sh
python sw/pi/deploy/package.py sw/build/groundlark-station.tar
```

On a freshly provisioned Pi OS Lite system, install uv **0.12.18**, extract the
bundle under `/opt/groundlark/releases/<release-id>`, then run its
`sw/pi/deploy/install.sh` as root. It verifies file checksums, checks card size,
creates separate acquisition/UI users, and installs a frozen Python 3.12.12
environment per release. It does not flash/repartition media or enable services.
OS packages still follow the configured Pi OS repositories; the bundle is not a
reproducible whole-disk OS image. Record the OS image checksum and installed
package versions when provisioning a real station.

Configure LAN DNS and a reserved LAN IP for the station. Copy `Caddyfile` to `/etc/caddy/Caddyfile`,
fill `/etc/groundlark/caddy.env` from `caddy.env.example`, and put
`caddy-groundlark.conf` in `/etc/systemd/system/caddy.service.d/groundlark.conf`.
Use `caddy hash-password` for the password hash; keep the environment file mode
0600. Set `GROUNDLARK_LAN_IP` to that reserved address; the listener binds there.
Validate the configuration with Caddy before starting it. `basic_auth`
requires Caddy 2.8 or newer. Trust Caddy's local CA certificate on authorized
clients; do not bypass certificate warnings. Bind/firewall HTTPS to the station
LAN, and do not forward it through an Internet router. The UI and acquisition
API bind to loopback only; the API token stays in server environments.

After GPIO bring-up below and editing `/var/lib/groundlark/station.json`, run:

```sh
sudo systemctl enable --now groundlark-station groundlark-ui
sudo systemctl daemon-reload
sudo systemctl restart caddy
```

Keep SSH disabled for normal local-UI operation. Use a local console for initial
provisioning/recovery. The provided journald drop-in bounds logs to 64 MiB.
Apply `groundlark-watchdog.conf` under `/etc/systemd/system.conf.d/` only during
Pi watchdog qualification; acquisition already uses a systemd service watchdog.
The supervisor boot/logind snippets belong to a separate supervised power test;
see [supervisor firmware](../../supervisor/README.md). They are not enabled by
the installer while the battery policy is disabled.

Updates interrupt capture: stop both services, install a new verified release,
then restart them. Retain the previous release for `rollback.sh <absolute-path>`.
The recording/configuration directory is shared across releases; preserve a
configuration backup before upgrades. Firmware updates must preserve the USB
heads' boot-journal pages. No remote updater or arbitrary command execution is
exposed by the UI.

### Storage and recovery

SSREC is authoritative. Segments close after 300 seconds or 8 MiB by default.
Each segment carries validated session ordering state and can replay independently.
The store reserves 2 GiB free space and uses at most 80% of the filesystem;
the smaller constraint wins. It removes the oldest completed/interrupted sets
before new writes. Active sets and unrelated files are preserved. Capacity,
free space, interruptions and deletion counts are visible in the UI. These
owned sets must not be edited by other programs while capture is running.

The rolling strategy is informed by [Raspberry Shake's local archive](https://manual.raspberryshake.org/download.html).
Retention is capacity-based here: seven days of uptime does not guarantee seven
days of raw-data retention. Measure the actual write rate and size the SD card
for the desired history. Files are flushed and fsynced at most every two seconds
and at boundaries; this is not proof of SD/controller power-loss durability.

On restart, abandoned `.open` sets become `.interrupted` without changing their
contents. A torn record remains an error. To recover the validated prefix into
a new file, preserving the original:

```sh
python sw/tools/recover_recording.py interrupted/data.ssrec recovered.ssrec
```

Recovery never invents missing bytes or marks an incomplete acquisition complete.
The station currently records SSREC; use the existing miniSEED export commands
with recorded timing evidence. No UTC or calibration is fabricated for an export.

### Summaries, tests and limits

The station exposes bounded recent alerts and 60-second raw-count RSAM summaries
locally. Each summary reports its clock domain, boot, coverage and unknown loss.
It is `mean(abs(raw ADC counts))`, without DC removal/filtering or a velocity
calibration. Missing data never becomes zero. Local summaries prepare a narrow
interface for later transport; no LoRa driver, radio choice, Internet forwarding
or SensorThings adapter is enabled.

Run `./lab.ps1 test -Profile software` and the UI smoke/controller/browser checks.
For a real-time **software** soak, using the UI Python environment and a built
descriptor, run `python environment/soak.py --hours 168`. The runner limits
recordings to 256 MiB and writes status/results into the normal five-run lab
storage. Active soaks count toward those five and cannot be pruned. Ctrl+C stops
the run and records it as interrupted. For a background run, create an empty
`stop.request` file in its reported run directory to stop it cleanly.
An unexpected host/process death may leave
an active marker; confirm the recorded PID has stopped before clearing that flag.
A pass requires the requested wall-clock duration and no recorded source errors.
Accelerated tests and ARM links do not establish a seven-day physical bench pass.

## GPIO and sensor bring-up

The supplied overlay targets the current Pi 4 / BCM2711 design. Do not assume
the same GPIO chip or controller configuration on a Pi 5. This is an explicit
bring-up procedure; no workstation boot configuration is changed by the lab.

1. Build `groundlark-daqhat-01.dtbo` with `dtc -@ -I dts -O dtb -o
   groundlark-daqhat-01.dtbo groundlark-daqhat-01-overlay.dts` on the Pi. Install the result
   under `/boot/firmware/overlays/` and add `dtoverlay=groundlark-daqhat-01` to the
   `[pi4]` section of `/boot/firmware/config.txt`. Ensure the following settings
   are not unintentionally restricted by that section.
2. Remove conflicting SPI chip-select overlays. Do not enable `w1-gpio` or
   `pps-gpio` on BCM4: it is now the geophone DRDY signal. Do not
   enable a kernel IMU driver on the same SPI devices.
3. Reboot. Load `spidev` and `i2c-dev` with `sudo modprobe spidev` and
   `sudo modprobe i2c-dev`. Run `python3 bind_spi.py` to verify all five device
   identities, then `sudo python3 bind_spi.py --apply`. The script will not
   detach a different driver. Repeat binding after a reboot.
4. Verify `/dev/spidev0.0` through `.4`, `/dev/i2c-1`, and the GPIO line mapping
   with `gpioinfo`. Grant the acquisition user access using the Pi's spi/i2c/gpio
   groups. Check the example JSON against the actual chip before using it.
5. From the repository, run `python sw/tools/sensor.py live --fifo --profile
   sw/pi/profiles/daqhat-01.example.json --seconds 60 --output sw/build/bench-001.ssrec`.
   Use a new output filename each time. Start with the FPGA supply off.
   Capture also creates `bench-001.mseed` locally; keep it with the SSREC file.
   Check/synchronize the Pi's date first. Absolute timing is marked unverified;
   see the [miniSEED guide](../../../docs/miniseed.md) for station codes and limits.

Chip-select order is BCM8,7,5. IRQ order is BCM27,22,23. Sensor OE is
BCM26; geophone DRDY is BCM4. IMU IRQs are rising-edge hints, backed by a 20 ms periodic drain
so an event missed while servicing the FIFO does not strand data. The application
requests GPIO inputs without a bias; the board drives them through U42.

DAQHAT-01 uses ADS122C04 at I2C address 0x40 and MAX-M10S at 0x42. The updated profile assigns PPS to BCM24 (header 18). Use `live --fifo --utc` for timing capture; do not also enable the kernel `pps-gpio` overlay. Geophone conversion counters
report gaps, but read-completion timestamps do not establish exact sample times.
Conversion gaps do not reset a healthy ADC; real bus faults still trigger bounded
recovery. The `geophone_drdy` profile entry enables a dedicated falling-edge reader
inside the ADC worker, independently of the recording loop. Delivery buffers
256 readings plus one unknown-loss marker, with 32 readings per drain. A missed
edge gets a readiness check within 20 ms; a stuck reader fails after 250 ms.
The legacy polling path (omit this entry) still has documented conversion loss
under modeled load. Neither path establishes physical lossless capture; shared
I2C traffic and Linux scheduling still need measurement. Do not enable 400 kHz
merely to claim lossless capture. That speed also needs electrical testing.
Physical qualification follows the [bench procedure](../../../docs/bench-procedure.md).

Build/merge checks run against a small controller fixture. They establish overlay
structure, not a boot test of Raspberry Pi OS or the connected devices.

References: [Pi overlays](https://www.raspberrypi.com/documentation/computers/configuration.html),
[Linux spidev binding](https://docs.kernel.org/spi/spidev.html),
[GPIO v1 event ABI](https://docs.kernel.org/userspace-api/gpio/gpio-get-lineevent-ioctl.html).
