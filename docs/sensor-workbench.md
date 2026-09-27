# Run your first Groundlark sensor experiment

The sensor workbench is a local browser app for trying virtual sensors and
replaying recordings. Choose a board, click a sensor in its 3D view, change an input, and watch
its signal. **No Raspberry Pi or sensor hardware is required.**
The header uses the same lark-and-waveform wordmark as the project README.

You need internet access for setup, a modern browser with WebGL, and Windows
PowerShell or a Linux/macOS terminal. The scripts install the needed Python
tools locally. Docker, KiCad, Node.js and an FPGA are not prerequisites.

![Workbench showing the geophone and a simulated 2 Hz signal](images/sensor-workbench.png)

## 1. Get the project

If you already have the project folder, use it. Otherwise visit the
[Groundlark repository](https://github.com/crockpotveggies/groundlark), choose
**Code → Download ZIP**, and extract it to a folder you can write to.
Git users can instead run `git clone https://github.com/crockpotveggies/groundlark.git`.

Open a terminal in that folder. You should see `README.md`, `setup-ui.ps1` and
`setup-ui.sh`. On Windows, right-click the folder and choose **Open in Terminal**,
using a PowerShell tab. On macOS/Linux, use `cd` followed by your folder's path;
quote paths that contain spaces.

## 2. Set up once, then start

**Windows — PowerShell:**

```powershell
./setup-ui.ps1 -Check
./ui.ps1
```

**Linux/macOS — Terminal:**

```sh
sh ./setup-ui.sh --check
sh ./ui.sh
```

Setup downloads a pinned uv tool from its official source and installs the
locked Python dependencies. The check option starts a temporary server,
checks the page and assets, and tests the geophone scene. Wait for the checks
to pass; the first download may take a few minutes. Rerunning setup is safe.

Once the launch command reports the server is ready, open
**[http://127.0.0.1:8080](http://127.0.0.1:8080)**. Keep the terminal open while
using the app. **Ctrl+C** in that terminal stops it.
Next time, just run `./ui.ps1` or `sh ./ui.sh` again.

If PowerShell blocks scripts, follow your computer's approved process for
running local development scripts. On a managed computer, ask your administrator.
The project does not need administrator privileges or a permanent policy change.

## 3. Make a geophone signal

1. Click **Geophone** in the device list or the gold can in the 3D view. The can
   and its HAT input highlight together: they represent one signal.
2. Expand **Geophone stimulus** on the right (below the charts on a narrow screen).
3. Set **Vertical velocity amplitude** to **100** µm/s and **Frequency** to **2** Hz.
4. Press **Apply geophone tone**, then **Start** in the top bar.
5. After a few seconds, press **Pause**. Look for a repeating wave in
   **Geophone ADC · raw counts** and a **Valid** status.

Changing a box alone does not change the experiment: press its **Apply** button.
The geophone has one vertical channel. The chart shows ADC counts, not velocity
units. Zero motion produces a flat ideal trace. The model includes nominal
geophone response, but not real noise or settling. The chart retains recent
points; the recording contains the whole run.

## 4. Try the other sensors

Choose **HAT + Burrowlark** in the **Board** menu, then click
**Load rocking + field demo** and **Start** to explore IMU and remote-head
signals. This replaces the current run, so save first if needed.

| Control | What to look for |
| --- | --- |
| **Pose & vibration** | Select an IMU; tilt moves gravity between XYZ axes, and vibration adds an oscillation. A stationary IMU still measures gravity. |
| **Magnetic field & infrasound** | Select Magnetometer or Infrasound to view the separate Burrowlark (DAQUSB-01) USB head and its modeled signals. |
| **Fault injection** | Apply a sensor fault and inspect status, events and missing-data gaps. Start a new run to return to a clean baseline. |
| **Top / Orbit**, drag, scroll | Change the camera only. These gestures do not stimulate sensors or change recorded samples. |

Choose **Skylark USB** to inspect its PCB and gas cells. **Air quality stimulus**
controls nominal SO₂/H₂S, PM2.5, temperature, humidity and pressure. Press
**Apply air stimulus**, then **Start**. Gas plots show independent raw working
and auxiliary counts; the ppm controls are ideal model inputs, not a calibration.
PM plots show the atmospheric PM1/PM2.5/PM10 fields. Climate/barometer displays
apply the manufacturer's conversion equations while retaining original bytes.
The PMS5003 is shown beside the PCB for inspection, not in its mounted bell pose.

![Skylark board test, gas-cell model and recorded missing-data gap](images/skylark-workbench.png)

Changing boards starts a new run, so save the current recording first. The menu
supports the FPGA HAT, Burrowlark, their combined simulation, and Skylark.
Coldfoot remains deferred. Choose an individual board to enable its test button.
Imported recordings select their board automatically.

The HAT has three IMUs and one geophone input. The optional remote head adds
magnetometer and pressure streams: six sensor streams altogether.

## 5. Save and replay

- **Finish & save** ends the capture and downloads a `.ssrec` recording to your
  browser's download location. It includes samples and applied input changes.
- Under **Recordings & scenarios**, upload that recording. Press **Play** or
  move the timeline slider to inspect it.
- In replay mode, stimulus controls are disabled because the samples already
  exist. Use **New run** to create a new experiment.
- **Export scenario** saves inputs as JSON. Import it with the same seed to
  repeat the experiment. See [advanced scenarios](stimulus-models.md).

**Save before refreshing, closing the tab or starting a new run.** Experiments
live in memory, independently in each tab. There is no automatic save database.
A capture stops at three simulated minutes or its 8 MiB limit.

## 6. Run a board check

Save your experiment, then press **Test selected board**. With **Groundlark FPGA HAT** selected, the app runs eight seconds
of modeled input through the production HAT drivers and opens the capture in
replay. Expect **nine passing checks** covering **3,264 samples** from the three
IMUs and geophone input. Expand the results for measurements and tolerances;
download the recording and JSON report from that panel.

With **Skylark USB** selected, expect seven checks: inventory, gas channels,
particulate, climate, pressure, isolated failure and replay. Burrowlark has five
checks. These two USB-board UI tests use ideal sensor stimuli through the shared
acquisition/controller; the portable software profile separately compiles and
runs Skylark's actual C drivers/encoder with injected register/UART faults and
builds the ARM firmware. The report states each test's scope.

The HAT check tests driver and recording behavior on modeled buses. It does not prove
physical power, fit, timing, noise, sensor accuracy or FPGA operation. The browser
currently simulates and replays; it does not connect to a real HAT. For real Pi
acquisition, use the [Linux software guide](sensor-software.md).

## Troubleshooting

| Symptom | What to do |
| --- | --- |
| Setup cannot download packages | Check your internet/proxy settings and retry setup. Keep TLS verification enabled. |
| `uv` or Python is missing | Run setup; no separate Python install is needed. |
| Browser cannot connect | Keep the launcher terminal open, wait for the ready message, and check errors printed there. |
| Port 8080 is already in use | Run `./ui.ps1 -Port 8081` or `sh ./ui.sh --port 8081`, then open `http://127.0.0.1:8081`. |
| 3D area is blank | Enable WebGL/hardware acceleration or try another current browser. Run `./ui.ps1 -Check` / `sh ./ui.sh --check` to check asset delivery separately. |
| Flat or empty chart | Select the intended sensor, press **Apply**, then **Start**. Check status and faults. Paused or unexcited sensors may correctly stay flat. |
| Changes seem ineffective | Press **Apply**. Stimulus controls are unavailable during replay. Camera gestures never stimulate sensors. |
| Recording will not open | Keep the original file. The app rejects corrupt data; an incomplete recording may show a completion warning, while a corrupt one is rejected. |
| Board visualization is stale | Use matching code/CAD/assets from the same checkout. Contributors should follow [asset provenance](../sw/ui/assets/README.md). |

## Storage and cleanup

Setup stores its tools under ignored `.local/`: uv, Python when needed, virtual
environments and the package cache. It leaves your persistent PATH and circuit
design environment unchanged. Windows and Unix use separate environments.
Startup generates the schema in ignored `sw/build/ui-schema.binpb`.
Experiments create no run folders; browser downloads remain separate.

To reclaim only the package download cache, stop the app and run:

```powershell
# Windows
./.local/tools/uv-windows/uv.exe cache clean --cache-dir .local/uv-cache
```

```sh
# Linux/macOS
./.local/tools/uv-unix/uv cache clean --cache-dir .local/uv-cache
```

Dependencies may need downloading again afterward. Keep other `.local/` files:
they can include project tools and manually saved results.
After updating the repository, rerun setup with its check option.

## For contributors

See [sensor software](sensor-software.md) for data and timing semantics and
[UI source notes](../sw/ui/README.md) for checks and asset provenance.

The scene reads the FPGA HAT and Burrowlark placement files from their respective
product directories under `hw/`. Moving these files requires updating the scene's
paths and asset provenance together; see the [project map](project-layout.md).
The [portable lab](portable-lab.md) is the separate Docker-based full regression
environment; it is optional for using this UI.
Setup uses the official [uv installer options](https://docs.astral.sh/uv/reference/installer/)
with an unmanaged local install and the checked `sw/ui/uv.lock`.
