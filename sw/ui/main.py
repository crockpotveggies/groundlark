"""Python-authored local workbench. Launch with ./ui.ps1 or ./ui.sh.

NiceGUI supplies the browser's Three.js/ECharts components; there is no custom
JavaScript application. Acquisition and all sample semantics live in sw/pi.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "sw/pi"), str(ROOT / "sw/interfaces/python")]


def build_descriptor():
    from grpc_tools import protoc
    target = ROOT / "sw/build/ui-schema.binpb"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = ROOT / "sw/interfaces/proto"
    result = protoc.main(["protoc", f"-I{source}", "--include_imports",
                          f"--descriptor_set_out={target}", str(source / "groundlark/sensor/v1/sensor.proto")])
    if result:
        raise RuntimeError("Could not build sensor descriptor")
    os.environ["GROUNDLARK_DESCRIPTOR"] = str(target)


build_descriptor()
from nicegui import app, run, ui  # noqa: E402
from groundlark.workbench import MAX_BYTES, NAMES, Workbench  # noqa: E402
from groundlark.hat_signals import run_bench  # noqa: E402
from geophone_scene import add_geophone  # noqa: E402

ASSETS = Path(__file__).parent / "assets"
for relative, expected in json.loads((ASSETS / "provenance.json").read_text())["sha256"].items():
    if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"Board visualization is stale: {relative}. See sw/ui/assets/README.md.")
app.add_static_files("/board-assets", ASSETS)
TEAL, MUTED = "#44d9c2", "#98aabd"
COLORS = [TEAL, "#a7a3ff", "#f3bd64"]
LABELS = {**{i: ("Acceleration · raw counts", "Angular rate · raw counts") for i in range(1, 5)},
          5: ("Acceleration · raw counts", "Inclination · raw counts"),
          9: ("Geophone ADC · raw counts", "Single vertical velocity-sensitive channel"),
          7: ("Magnetic field · raw counts", "XYZ samples • no calibration applied"),
          8: ("Differential pressure · raw counts", "Temperature · raw counts")}
MODELS = {**{i: "LSM6DSO" for i in range(1, 5)}, 5: "SCL3300", 9: "Racotech / ADS122C04", 7: "RM3100", 8: "DLVR · optional"}


def chart_options(title):
    return dict(backgroundColor="transparent", animation=False, color=COLORS,
        title=dict(text=title, textStyle=dict(color="#dce6ef", fontSize=12), left=8, top=8),
        tooltip=dict(trigger="axis"), legend=dict(bottom=0, right=10, textStyle=dict(color=MUTED)),
        grid=dict(left=65, right=20, top=40, bottom=50),
        xAxis=dict(type="value", name="s", axisLabel=dict(color=MUTED), splitLine=dict(show=False)),
        yAxis=dict(type="value", scale=True, axisLabel=dict(color=MUTED), splitLine=dict(lineStyle=dict(color="#283441"))),
        series=[dict(name=a, type="line", showSymbol=False, connectNulls=False,
                     lineStyle=dict(width=1.7), data=[]) for a in "XYZ"])


def board_scene(scene, select):
    """Real KiCad DAQHAT-01 geometry plus pick targets/custom envelopes at authored XY."""
    layout = json.loads((ROOT / "hw/groundlark-fpga-hat/layout/placement.json").read_text())["groundlark-daqhat-01"]
    remote = json.loads((ROOT / "hw/burrowlark-usb/layout/placement.json").read_text())["groundlark-field-head"]
    targets, rings = {}, {}
    with scene:
        with scene.group() as hat:
            scene.gltf("/board-assets/daqhat-01.glb").scale(100).rotate(math.pi / 2, 0, 0).move(-9.25, 7.8, 0)
            # Tall Pi socket envelope; the internal-link HAT has no FFC sockets.
            scene.box(5.08, .51, 1.61).move(-.999, 2.45, -.967).material("#252b34")
            # KiCad's GLB exporter omits these local VRML bodies. These are
            # intentionally simple visualization envelopes, not STEP substitutes.
            custom = {"J80": (3.9, .65, .4), "J81": (3.9, .65, .4), "J82": (.65, 2.6, .4)}
            for part in layout["parts"]:
                ref, (x, y) = part["ref"], part["xy"]
                x, y = (x - 42.5) / 10, (28 - y) / 10
                if ref in custom:
                    w, h, z = custom[ref]
                    scene.box(w, h, z).move(x, y, .16 + z / 2).material("#252b34")
                sid = {"U11": 1, "U12": 2, "U13": 3, "U22": 9}.get(ref)
                if sid:
                    radius = .29 if sid <= 4 else .72
                    target = scene.cylinder(radius, radius, .07).rotate(math.pi / 2, 0, 0).move(x, y, .63).material(TEAL, .28).with_name(f"sensor-{sid}")
                    targets[target.id] = sid
                    ring = scene.ring(radius, radius + .06, 48).move(x, y, .68).material(TEAL).with_name(f"sensor-{sid}")
                    rings.setdefault(sid, []).append(ring)
                    targets[ring.id] = sid
                    scene.text(NAMES[sid], "color:#e8f5ff;font-size:11px;background:#172534dc;padding:2px 5px;border-radius:4px;pointer-events:none").move(x, y, 1.12)
            scene.text("DAQHAT-01 SENSOR HAT  /  85 × 56 mm", "color:#a6bfcc;font-size:11px;pointer-events:none").move(0, -3.2, .1)
            connector = next(part for part in layout['parts'] if part['ref'] == 'J90')['xy']
            add_geophone(scene, ((connector[0]-42.5)/10, (28-connector[1])/10), targets, rings, TEAL)
        with scene.group() as head:
            scene.box(7, 4.5, .16).material("#165b51")
            for part in remote["parts"]:
                ref = part["ref"]
                if ref not in ("U1", "U2", "U3", "J1"):
                    continue
                x, y = (part["xy"][0] - 35) / 10, (22.5 - part["xy"][1]) / 10
                sid = {"U2": 7, "U3": 8}.get(ref)
                box = scene.box(1.6 if sid else .6, 1.5 if sid else .6, .5 if sid else .3).move(x, y, .35).material("#293544")
                if sid:
                    targets[box.id] = sid
                    ring = scene.ring(1, 1.08, 48).move(x, y, .64).material(TEAL)
                    rings.setdefault(sid, []).append(ring)
                    targets[ring.id] = sid
                    scene.text(NAMES[sid] + (" · optional" if sid == 8 else ""), "color:white;font-size:12px;pointer-events:none").move(x, y, 1)
            scene.text("REMOTE USB HEAD  /  70 × 45 mm", "color:#a6bfcc;font-size:11px;pointer-events:none").move(0, -2.8, .1)
        head.visible(False)
    def clicked(event):
        for hit in event.hits:
            if hit.object_id in targets:
                select(targets[hit.object_id])
                break
    scene.on_click(clicked)
    return hat, head, rings


@ui.page("/")
def page():
    engine = Workbench()
    selected = 1
    busy = False
    verified_capture, signal_report = None, None
    ui.dark_mode().enable()
    ui.colors(primary=TEAL, secondary="#a7a3ff", dark="#131c26", dark_page="#0d131c")
    ui.add_css((Path(__file__).parent / "style.css").read_text())

    def attempt(action):
        if busy:
            ui.notify("Please wait for the current operation")
            return
        try:
            action()
        except (ValueError, OSError, TypeError) as error:
            ui.notify(str(error), type="negative")

    def choose(sid):
        nonlocal selected
        selected = sid
        heading.set_text(f"{NAMES[sid]}  /  {MODELS[sid]}")
        board_label.set_text("DAQHAT-01 sensor HAT" if sid not in (7, 8) else "Remote USB sensor head")
        hat.visible(sid not in (7, 8))
        head.visible(sid in (7, 8))
        for sensor, highlights in rings.items():
            for ring in highlights:
                ring.material(TEAL if sensor == sid else "#60788a", 1 if sensor == sid else .25)
        for sensor, button in sensor_buttons.items():
            button.classes(replace="sensor-button selected" if sensor == sid else "sensor-button")
        update_charts()

    def camera(top=False):
        scene.move_camera(x=-1.4 if top else 4, y=-.01 if top else -8, z=14 if top else 10,
                          look_at_x=-1.4, look_at_y=0, look_at_z=.2, up_x=0, up_y=0, up_z=1)

    def fresh(document=None):
        nonlocal verified_capture, signal_report
        engine.reset(document, int(seed.value))
        verified_capture, signal_report = None, None
        verification_panel.set_visibility(False)
        ui.notify("New run ready. Press Start; save the recording before starting another run.")

    def save_recording():
        if engine.mode != "Simulate":
            raise ValueError("This is an imported recording")
        ui.download.content(engine.finish(), "groundlark-run.ssrec", "application/octet-stream")

    def save_scenario():
        ui.download.content(json.dumps(engine.scenario_json(), indent=2) + "\n", "groundlark-scenario.json", "application/json")

    async def upload_recording(event):
        nonlocal busy, verified_capture, signal_report
        if busy:
            return
        if event.file.size() > MAX_BYTES:
            ui.notify("Maximum recording size is 8 MiB", type="negative")
            return
        busy = True
        engine.pause()
        try:
            await run.io_bound(engine.load_recording, await event.file.read())
            verified_capture, signal_report = None, None
            verification_panel.set_visibility(False)
            ui.notify("Recording validated. Use Play or the replay timeline.")
        except (ValueError, OSError, TypeError, KeyError, RecursionError) as error:
            ui.notify(str(error), type="negative")
        finally:
            busy = False
            replay_upload.reset()

    async def upload_scenario(event):
        if busy:
            return
        if event.file.size() > 65536:
            ui.notify("Scenario file is too large", type="negative")
            return
        try:
            fresh(json.loads(await event.file.text()))
        except (ValueError, OSError, TypeError, KeyError, RecursionError) as error:
            ui.notify(str(error), type="negative")
        scenario_upload.reset()

    async def run_signal_test():
        nonlocal busy, verified_capture, signal_report
        if busy:
            return
        busy = True
        engine.pause()
        test_button.disable()
        test_button.set_text("Testing HAT signals…")
        verification_panel.set_visibility(False)
        try:
            data, report = await run.io_bound(run_bench)
            await run.io_bound(engine.load_recording, data)
            await run.io_bound(engine.seek, 8)
            verified_capture, signal_report = data, report
            choose(2)
            verification_title.set_text(f'{"PASS" if report["passed"] else "FAIL"} · {sum(c["passed"] for c in report["checks"])}/{len(report["checks"])} HAT signal checks')
            verification_scope.set_text(f'MODELED SPI / I²C BUSES → ACTUAL PI DRIVERS → ACQUISITION → CHECKED RECORDING · 8 simulated seconds · {report["samples"]:,} HAT samples')
            verification_title.style(f'color:{TEAL if report["passed"] else "#ff9a89"}')
            check_badges.clear()
            check_details.clear()
            with check_badges:
                for check in report["checks"]:
                    ui.badge(check["name"], color="positive" if check["passed"] else "negative").props("outline").tooltip(check["detail"])
            with check_details:
                for check in report["checks"]:
                    ui.label(f'{"PASS" if check["passed"] else "FAIL"} · {check["name"]}: {check["detail"]}').classes("small")
                ui.label(f'Recording SHA-256: {report["recording_sha256"]}').classes("fine-print break-all")
            verification_panel.set_visibility(True)
            ui.notify("HAT signal test passed; the checked capture is loaded below" if report["passed"] else "HAT signal test failed; inspect the report", type="positive" if report["passed"] else "negative")
        except (ValueError, OSError) as error:
            ui.notify(str(error), type="negative")
        finally:
            busy = False
            test_button.enable()
            test_button.set_text("Test HAT signals")

    with ui.row().classes("topbar"):
        with ui.column().classes("gap-0"):
            ui.element("img").props('src=/board-assets/groundlark-wordmark.svg alt=Groundlark').classes("brand-wordmark")
            ui.label("SENSOR WORKBENCH").classes("eyebrow brand-subtitle")
        ui.space()
        mode = ui.badge("SIMULATION", color="primary").props("outline")
        state_label = ui.label("Ready").classes("muted")
        test_button = ui.button("Test HAT signals", icon="fact_check", on_click=run_signal_test).props("outline no-caps").tooltip("Replaces this session with a fixed 8-second modeled-bus test; download any current run first")
        play = ui.button("Start", icon="play_arrow", on_click=lambda: attempt(engine.toggle)).props("unelevated no-caps")
        save = ui.button("Finish & save", icon="download", on_click=lambda: attempt(save_recording)).props("outline no-caps")

    with ui.column().classes("panel w-full") as verification_panel:
        with ui.row().classes("w-full items-center"):
            verification_title = ui.label().classes("section-title")
            ui.space()
            ui.button("Test recording", icon="download", on_click=lambda: ui.download.content(verified_capture, "hat-signals.ssrec", "application/octet-stream")).props("flat no-caps")
            ui.button("Report JSON", icon="download", on_click=lambda: ui.download.content(json.dumps(signal_report, indent=2), "hat-signals.json", "application/json")).props("flat no-caps")
        verification_scope = ui.label().classes("eyebrow")
        check_badges = ui.row().classes("gap-2")
        with ui.expansion("Measurements & tolerances").classes("w-full"):
            check_details = ui.column().classes("gap-1")
        ui.label("Bench inputs: 2 Hz / 0.300 m/s² vibration and 0.5 Hz / 5° rocking. No physical HAT connected; remote-head sensors are outside this test.").classes("small muted")
    verification_panel.set_visibility(False)

    with ui.element("div").classes("workspace"):
        with ui.column().classes("panel sensor-panel"):
            ui.label("DEVICES").classes("eyebrow")
            ui.label("Select a sensor").classes("section-title")
            sensor_buttons, statuses = {}, {}
            for sid in (1, 2, 3, 9, 7, 8):
                name = NAMES[sid]
                if sid in (1, 7):
                    ui.label("DAQHAT-01 HAT · PI / FPGA STACK" if sid == 1 else "REMOTE · USB-C HEAD").classes("group-label")
                with ui.button(on_click=lambda sid=sid: choose(sid)).props("flat no-caps align=left").classes("sensor-button") as b:
                    with ui.column().classes("gap-0 items-start"):
                        ui.label(name).classes("sensor-name")
                        statuses[sid] = ui.label(f"{MODELS[sid]} · waiting").classes("sensor-status")
                sensor_buttons[sid] = b
            ui.separator().classes("my-2")
            ui.label("MODELED DEVICES").classes("eyebrow")
            ui.label("No hardware connected. The FPGA is not required for sensor experiments.").classes("small muted")
            metrics = ui.label("0 samples · 0 missing").classes("small")
            ui.space()
            with ui.expansion("Recordings & scenarios", icon="folder_open").classes("w-full small"):
                replay_upload = ui.upload(label="Open .ssrec replay", auto_upload=True, max_file_size=MAX_BYTES,
                    max_files=1, on_upload=upload_recording, on_rejected=lambda: ui.notify("Recording exceeds 8 MiB", type="negative")).props('accept=".ssrec"').classes("w-full")
                scenario_upload = ui.upload(label="Load scenario JSON", auto_upload=True, max_file_size=65536,
                    max_files=1, on_upload=upload_scenario).props('accept=".json"').classes("w-full")
                ui.button("Export scenario", on_click=lambda: attempt(save_scenario)).props("flat no-caps")

        with ui.column().classes("center-column"):
            with ui.column().classes("panel board-panel"):
                with ui.row().classes("w-full items-center"):
                    with ui.column().classes("gap-0"):
                        ui.label("BOARD EXPLORER").classes("eyebrow")
                        board_label = ui.label("DAQHAT-01 sensor HAT").classes("section-title")
                    ui.space()
                    ui.button("Orbit", on_click=lambda: camera()).props("flat dense no-caps")
                    ui.button("Top", on_click=lambda: camera(True)).props("flat dense no-caps")
                scene = ui.scene(height=310, grid=False, camera=ui.scene.perspective_camera(fov=40), background_color="#111c28").classes("w-full rounded-lg")
                hat, head, rings = board_scene(scene, choose)
                camera()
                ui.label("Click a sensor to inspect · drag to orbit · scroll to zoom").classes("small muted")
                ui.label("HAT: KiCad geometry. Geophone: nominal 25.4 × 33 mm body; illustrative terminals/leads. Remote head: simplified geometry. Camera motion does not stimulate sensors.").classes("fine-print")
            with ui.column().classes("panel chart-panel"):
                heading = ui.label("IMU 1 / LSM6DSO").classes("section-title")
                detail = ui.label("Waiting for samples").classes("small muted")
                with ui.element("div").classes("chart-grid"):
                    primary = ui.echart(chart_options(LABELS[1][0])).classes("chart")
                    secondary = ui.echart(chart_options(LABELS[1][1])).classes("chart")
                ui.label("Raw counts preserved · gaps mean missing data · time axis is recording arrival time, not synchronized device clocks").classes("fine-print")

        with ui.column().classes("panel controls-panel"):
            ui.label("STIMULUS LAB").classes("eyebrow")
            ui.label("Shape the experiment").classes("section-title")
            ui.label("Controls apply when you press their Apply button. Changes are captured in the recording.").classes("small muted")
            with ui.row().classes("w-full items-center"):
                seed = ui.number("Seed", value=1, min=0, max=2**32-1, precision=0).props("dense outlined").classes("seed")
                ui.button("New run", icon="add", on_click=lambda: attempt(fresh)).props("flat no-caps").tooltip("Replaces the current run; save it first")
            ui.button("Load rocking + field demo", icon="waves", on_click=lambda: attempt(lambda: fresh(json.loads((ROOT / "sw/pi/profiles/stimulus-demo.json").read_text())))).props("outline no-caps").classes("w-full")
            with ui.column().classes("w-full gap-2") as stimuli:
                with ui.expansion("Pose & vibration", icon="screen_rotation", value=True).classes("w-full"):
                    pose_target = ui.select({"orientation_deg": "HAT pose", "head_orientation_deg": "Remote head pose"}, value="orientation_deg").props("dense outlined").classes("w-full")
                    pose = []
                    for axis in ("Roll", "Pitch", "Yaw"):
                        with ui.row().classes("w-full items-center gap-2"):
                            ui.label(axis).classes("small w-10")
                            slider = ui.slider(min=-180, max=180, step=1, value=0).props(f'label label-always aria-label="{axis} in degrees"').classes("flex-1")
                            pose.append(slider)
                    ui.button("Apply pose", on_click=lambda: attempt(lambda: engine.controls({pose_target.value: [s.value for s in pose]}))).props("flat no-caps")
                    amp = ui.number("Vertical amplitude (m/s²)", value=.3, min=0, max=20, step=.1).props("dense outlined").classes("w-full")
                    frequency = ui.number("Frequency (Hz)", value=2, min=0, max=12, step=.1).props("dense outlined").classes("w-full")
                    ui.button("Apply vibration", on_click=lambda: attempt(lambda: engine.controls({"acceleration_m_s2": [0, 0, {"amplitude": amp.value, "frequency_hz": frequency.value}]}))).props("flat no-caps")
                with ui.expansion("Magnetic field & infrasound", icon="sensors").classes("w-full"):
                    fields = [ui.number(f"Field {axis} (µT)", value=value, step=1).props("dense outlined").classes("w-full") for axis, value in zip("XYZ", (0, 20, -45))]
                    ui.button("Apply field", on_click=lambda: attempt(lambda: engine.controls({"magnetic_ut": [f.value for f in fields]}))).props("flat no-caps")
                    pressure = ui.number("Pressure amplitude (Pa)", value=20, min=0, max=500).props("dense outlined").classes("w-full")
                    pressure_hz = ui.number("Pressure frequency (Hz)", value=1, min=0, max=20, step=.1).props("dense outlined").classes("w-full")
                    ui.button("Apply pressure", on_click=lambda: attempt(lambda: engine.controls({"pressure_pa": {"amplitude": pressure.value, "frequency_hz": pressure_hz.value}}))).props("flat no-caps")
                with ui.expansion("Geophone stimulus", icon="waves").classes("w-full"):
                    geo_amp = ui.number("Vertical velocity amplitude (um/s)", value=100, min=0, max=10000)
                    geo_freq = ui.number("Frequency (Hz)", value=10, min=.1, max=100)
                    ui.button("Apply geophone tone", on_click=lambda: attempt(lambda: engine.controls({"geophone_velocity_m_s": {"amplitude": geo_amp.value/1e6, "frequency_hz": geo_freq.value}}))).props("flat no-caps")
                    ui.label("Steady-state response model; changes do not simulate settling.").classes("muted")
                with ui.expansion("Fault injection", icon="bug_report").classes("w-full"):
                    fault_sensor = ui.select({sid: name for sid, name in NAMES.items() if sid not in (4, 5)}, value=1, label="Sensor").props("dense outlined").classes("w-full")
                    fault = ui.select(["none", "timeout", "nack", "disconnect", "not_ready", "saturation", "short_read"], value="none", label="Fault").props("dense outlined").classes("w-full")
                    ui.label("Applies to one sensor; other active faults are preserved. Recovery follows the runtime retry budget.").classes("fine-print")
                    def apply_fault():
                        state, _ = engine.scenario.state_at(engine.now)
                        engine.controls({"sensor_faults": {**state["sensor_faults"], str(fault_sensor.value): fault.value}})
                    ui.button("Apply fault", on_click=lambda: attempt(apply_fault)).props("flat no-caps")

    with ui.column().classes("panel timeline-panel"):
        with ui.row().classes("w-full items-center"):
            time_label = ui.label("00:00.000").classes("time-label")
            ui.label("SESSION TIMELINE").classes("eyebrow")
            ui.space()
            capture_label = ui.label("Capture from start · up to 3 minutes / 8 MiB").classes("small muted")
        timeline = ui.slider(min=0, max=180, step=.01, value=0).props('label aria-label="Replay time in seconds"').classes("w-full")
        async def seek():
            nonlocal busy
            if engine.mode != "Replay":
                return
            busy = True
            try:
                await run.io_bound(engine.seek, timeline.value)
            except ValueError as error:
                ui.notify(str(error), type="negative")
            finally:
                busy = False
        timeline.on("change", seek)
        event_label = ui.label("Ready to start. Ideal sensor models; hardware qualification remains separate.").classes("small muted")
        error_label = ui.label().classes("small text-amber-300")

    def update_charts():
        snap = engine.snapshot(selected)
        for chart, field, label in ((primary, "primary", LABELS[selected][0]), (secondary, "secondary", LABELS[selected][1])):
            chart.options["title"]["text"] = label
            names = ["Counts", "", ""] if selected in (8, 9) else list("XYZ")
            chart.options["legend"]["show"] = selected not in (8, 9)
            for axis, series in enumerate(chart.options["series"]):
                series["name"] = names[axis]
                series["data"] = [[p["t"], p[field][axis]] for p in snap["points"]]
            chart.update()
        secondary.set_visibility(selected not in (7, 9))
        primary.style("grid-column:1 / -1" if selected in (7, 9) else "grid-column:auto")
        point = snap["latest"][selected]
        detail.set_text(f'{point["quality"]} · {point["detail"]}' if point else "Waiting for samples")
        heading.set_text(f"{NAMES[selected]}  /  {MODELS[selected]}")
        metrics.set_text(f'{snap["samples"]:,} samples · {snap["missing"]:,} missing')
        for sid, point in snap["latest"].items():
            if sid not in statuses: continue  # Legacy GNSS is retained in recordings, not displayed on DAQHAT-01.
            status = point["quality"] if point else "waiting"
            if point and snap["seconds"] - point["t"] > 2.5:
                status = "Stale"
            statuses[sid].set_text(f"{MODELS[sid]} · {status}")
            statuses[sid].style(f'color:{TEAL if status == "Valid" else "#f3bd64"}')
        mode.set_text(snap["mode"].upper())
        state_label.set_text("Running" if snap["running"] else "Finished" if snap["ended"] else "Paused")
        play.set_text("Pause" if snap["running"] else "Play" if snap["mode"] == "Replay" else "Start")
        play.set_enabled(not busy and not snap["ended"])
        play.props(f'icon={"pause" if snap["running"] else "play_arrow"}')
        save.set_enabled(snap["mode"] == "Simulate" and not busy)
        for element in stimuli.descendants():
            if hasattr(element, "set_enabled") and not isinstance(element, ui.expansion):
                element.set_enabled(snap["mode"] == "Simulate" and not snap["ended"])
        timeline.props(f'max={max(snap["duration"], .01)}')
        timeline.set_enabled(snap["mode"] == "Replay" and not busy)
        timeline.set_value(snap["seconds"])
        seconds = snap["seconds"]
        time_label.set_text(f"{int(seconds // 60):02d}:{seconds % 60:06.3f}")
        capture_label.set_text("Replay · drag timeline to seek" if snap["mode"] == "Replay" else "Capture from start · up to 3 minutes / 8 MiB")
        if snap["events"]:
            t, code, text = snap["events"][-1]
            event_label.set_text(f"{t:.3f}s · {code} · {text}")
        else:
            event_label.set_text("Ideal sensor models • raw recordings • no hardware connected")
        error_label.set_text(snap["error"])

    async def tick():
        if not busy:
            await run.io_bound(engine.advance, 50)

    choose(1)
    ui.timer(.05, tick)
    ui.timer(.25, update_charts)
    ui.context.client.on_disconnect(engine.pause)
    ui.context.client.on_delete(lambda: engine.acquisition.close())


if __name__ in {"__main__", "__mp_main__"}:
    parser = argparse.ArgumentParser(description="Local Groundlark sensor workbench")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    ui.run(host="127.0.0.1", port=args.port, title="Groundlark · Sensor Workbench",
           dark=True, reload=False, show=False, favicon=ASSETS / "groundlark-favicon.ico", reconnect_timeout=30)
