"""Board-specific experiments through the shared acquisition/recording path."""
from hashlib import sha256
from .workbench import Workbench


def run_bench(board="hat"):
    if board == "hat":
        from .hat_signals import run_bench as hat_bench
        data, report = hat_bench()
        report["scope"] = "Modeled SPI/I2C buses through actual Pi drivers; no physical HAT connected"
        return data, report
    if board not in ("burrowlark", "skylark"):
        raise ValueError("Board test is unavailable")
    e = Workbench(board=board)
    initial = ({"so2_ppm": 1, "h2s_ppm": 2, "pm25_ug_m3": 37,
                "temperature_c": 25, "humidity_percent": 50, "ambient_pressure_pa": 101325}
               if board == "skylark" else {"magnetic_ut": [-10, 0, 20]})
    e.controls(initial)
    def advance(ms):
        e.running = True
        for _ in range(ms // 100): e.advance(100)
        e.pause()
    checks = []
    def check(name, passed, detail): checks.append(dict(name=name, passed=bool(passed), detail=detail))
    advance(2000)
    sid = 10 if board == "skylark" else 7
    snap = e.snapshot(sid)
    check("Inventory", all(snap["latest"].values()) and not e.error, f"{len(snap['latest'])} active streams")
    if board == "skylark":
        values = snap["latest"]
        check("Gas channels", values[10]["primary"][0] == 4328522 and values[11]["primary"][0] == 4194304
              and values[12]["primary"][0] == 4422474 and values[13]["primary"][0] == 4194304,
              "Independent 2.5 V ADC expectation for nominal stimulus; no cell calibration")
        check("Particulate", values[14]["primary"] == [22, 37, 48], "Atmospheric PM1/2.5/10: 22 / 37 / 48 ug/m3")
        check("Climate", abs(values[15]["primary"][0]-25)<.003 and abs(values[15]["secondary"][0]-50)<.003,
              "SHT40 inverse transfer, CRC-preserved frame")
        check("Barometer", values[16]["primary"][0] == 101325 and values[16]["secondary"][0] == 25,
              "Factory compensation of synthetic trim: 101325 Pa, 25 C")
    else:
        check("Magnetometer", snap["latest"][7]["primary"] == [-750, 0, 1500], "Nominal 75 counts/uT, signed axes")
    e.controls({"sensor_faults": {str(sid): "timeout"}})
    advance(1000)
    snap = e.snapshot(sid)
    check("Fault isolation", snap["latest"][sid]["quality"] == "Missing" and
          (board != "skylark" or snap["latest"][14]["quality"] == "Valid"), "Missing stays distinct from zero; independent Skylark streams continue")
    e.controls({"sensor_faults": {str(sid): "none"}})
    advance(5000)
    data = e.finish()
    before = e.snapshot(sid)["latest"]
    e.load_recording(data);e.seek(8)
    check("Replay", e.snapshot(sid)["latest"] == before, "Checked recording reproduces final raw values, gaps and timestamps")
    return data, dict(passed=all(c["passed"] for c in checks), checks=checks,
                     samples=e.samples, recording_sha256=sha256(data).hexdigest(),
                     scope="Ideal sensor stimulus through shared acquisition and replay; " +
                     ("Skylark C firmware fault tests run separately in the portable suite" if board=='skylark'
                      else "Burrowlark firmware remains pending"))
