"""The same acquisition, validation and recording path for sim and Linux."""
import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import time
from .calibration import Calibrations, canonical
from .messages import configuration
from .recording import Reader, Writer, is_acquisition_metadata
from .runtime import Acquisition, Channel
from .session import Sessions
from .simulation import Simulated, defaults
from .stimulus import Scenario


def load_json(path, limit=16384):
    with open(path, "rb") as stream: data = stream.read(limit + 1)
    if len(data) > limit: raise ValueError("JSON input byte limit")
    return json.loads(data, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def replay(path):
    counts, digest = Counter(), hashlib.sha256()
    completed = False
    with open(path, "rb") as stream:
        reader = Reader(stream)
        if not is_acquisition_metadata(reader.metadata):
            raise ValueError("recording application metadata")
        calibrations = Calibrations(reader.metadata.get("calibrations", []))
        sessions = Sessions(calibrations)
        for arrived, item in reader:
            completed = isinstance(item, dict) and item.get("code") == "acquisition_summary"
            if isinstance(item, dict):
                counts["events"] += 1
                if item.get("code") == "usb_disconnected" and item.get("device") is not None:
                    sessions.disconnect(item["device"])
            else:
                kind = sessions.accept(item)
                counts[kind] += 1
                digest.update(item.SerializeToString(deterministic=True))
                if kind == "batch":
                    for sample in item.batch.samples:
                        counts["samples"] += 1
                        counts[{1: "valid", 2: "missing", 3: "saturated", 4: "fault"}[sample.quality]] += 1
    return dict(counts, completed=completed, message_sha256=digest.hexdigest())


def export_scenario(recording, output):
    """Recover scheduled and interactive changes from a validated recording."""
    replay(recording)
    with open(recording, "rb") as stream:
        reader = Reader(stream)
        if reader.metadata.get("stimulus_model") != "ideal-v1": raise ValueError("recording has no supported stimulus model")
        document = Scenario(reader.metadata["scenario"]).export()
        pending, applied = document["events"][:], []
        for arrived, item in reader:
            if not isinstance(item, dict) or item.get("code") != "stimulus_change": continue
            event = {"at_ns": item["at_ns"], "set": item["set"]}
            if type(event["at_ns"]) is not int or not 0 <= event["at_ns"] <= arrived:
                raise ValueError("invalid recorded control time")
            if event in pending: pending.remove(event)
            applied.append(event)
            if len(applied) > 256: raise ValueError("recorded control limit")
        document["events"] = sorted(applied + pending, key=lambda e: e["at_ns"])
        document = Scenario(document).export()
    with open(output, "x", encoding="utf-8") as stream:
        stream.write(json.dumps(document, indent=2, allow_nan=False) + "\n")
    return dict(scenario=str(output), events=len(document["events"]), seed=reader.metadata["seed"], remote=reader.metadata["remote"])


def run(args):
    simulated = args.command == "simulate"
    mseed_path = getattr(args, 'miniseed', None)
    if not simulated and not getattr(args, 'no_miniseed', False):
        mseed_path = mseed_path or args.output.with_suffix('.mseed')
    if getattr(args, 'no_miniseed', False) and mseed_path:
        raise ValueError('--no-miniseed conflicts with --miniseed')
    simulation_origin = getattr(args, 'mseed_start_utc', None)
    if simulation_origin and (not simulated or not mseed_path):
        raise ValueError('--mseed-start-utc requires simulate --miniseed')
    if mseed_path and simulated and not simulation_origin:
        raise ValueError('simulation miniSEED requires --mseed-start-utc (synthetic calendar origin)')
    if mseed_path and mseed_path.resolve() == args.output.resolve():
        raise ValueError('miniSEED and SSREC need different output paths')
    if mseed_path and simulated and getattr(args, 'board', 'hat') != 'hat':
        raise ValueError('miniSEED output currently supports HAT seismic channels')
    if mseed_path and not simulated and args.mseed_time == 'recorded':
        raise ValueError('DAQHAT-01 live acquisition has no qualified UTC; system mode marks timing unverified')
    for path in (args.output, mseed_path):
        if path is not None and path.exists(): raise FileExistsError(f'Output already exists: {path}')
    utc = getattr(args, 'utc', False)
    if utc and not args.fifo: raise ValueError('--utc requires --fifo and PPS profile')
    faults = load_json(args.faults) if getattr(args, "faults", None) else []
    records = load_json(args.calibrations) if args.calibrations else []
    calibrations = Calibrations(records)
    ids = {}
    for ident, record in calibrations.records.items():
        if record["sensor_id"] in ids: raise ValueError("one active calibration per sensor")
        ids[record["sensor_id"]] = ident
    if not 0 < args.seconds <= 3600 or not 1 <= args.drain_every <= 10000: raise ValueError("run bounds")
    board = getattr(args, 'board', 'hat')
    if simulated and board != 'hat' and args.remote:
        raise ValueError('--remote applies to the HAT simulation; select the USB board directly')
    if simulated and board != 'hat':
        from .workbench import board_configs
        settings = board_configs(board)
    else: settings = defaults()
    channels, enable, usb, pps = [], None, None, None
    if simulated:
        # Human-readable JSON may exceed its bounded canonical representation.
        scenario = Scenario(load_json(args.scenario, 65536) if args.scenario else None)
        current = 0
        clock = lambda: current
        for cfg in settings:
            channels.append(Channel('sim-skylark' if board=='skylark' else 'sim-head' if board=='burrowlark' else 'sim-pi',
                                    1, cfg, Simulated(cfg["sensor_id"], args.seed, faults, scenario, clock)))
        if args.remote:
            for cfg in defaults(True):
                channels.append(Channel("sim-head", 2, cfg, Simulated(cfg["sensor_id"], args.seed, faults, scenario, clock)))
    else:
        if not sys.platform.startswith("linux"): raise ValueError("live acquisition requires Linux")
        from .live import Factory, USB
        from .linux_io import SensorEnable, RisingEdges
        from .worker import Worker
        from .transport import Receiver
        profile = load_json(args.profile)
        if set(profile) - {"device_id", "spi", "i2c", "sensor_enable", "imu_irq", "pps"} or len(profile["spi"]) != 3:
            raise ValueError("live profile requires three explicit SPI paths and sensor OE")
        if len(set(profile["spi"])) != 3: raise ValueError("each sensor needs a separate chip select")
        if utc and (not profile.get('pps') or profile['pps'].get('line') != 24):
            raise ValueError('DAQHAT-01 GNSS PPS requires BCM24; BCM4 is geophone DRDY')
        boot = secrets.randbits(64) or 1
        # Validate all identity/configuration fields before opening devices.
        configuration(profile["device_id"], boot, settings)
        for cfg in settings:
            sid = cfg["sensor_id"]
            path = profile["spi"][(1, 2, 3).index(sid)] if sid in (1, 2, 3) else profile["i2c"]
            channels.append(Channel(profile["device_id"], boot, cfg, Worker(Factory(sid, path, args.fifo and sid in (1, 2, 3), utc and sid == 6), cfg)))
        clock = lambda: time.clock_gettime_ns(time.CLOCK_MONOTONIC_RAW)
    sessions = Sessions(calibrations)
    metadata = dict(format="groundlark-acquisition-v1", source="simulation" if simulated else "linux-polling",
                    calibrations=list(calibrations.records.values()), timing="poll completion; uncertainty unknown")
    if simulated: metadata.update(seed=args.seed, faults=faults, remote=args.remote, board=board, stimulus_model="ideal-v1", scenario=scenario.export())
    else:
        metadata["profile"] = profile
        if utc: metadata['utc_capture'] = 'm10-tim-tp-v1'
        if args.fifo:
            metadata.update(source='linux-fifo', timing='IMU device timestamp mapped to RAW; absolute uncertainty unknown; geophone poll completion')
    seismic = None
    if mseed_path:
        metadata['miniseed'] = dict(format_version=3, station=args.mseed_station,
            network=args.mseed_network, raw_counts=True,
            timing='synthetic-origin' if simulated else args.mseed_time,
            simulation_start_utc=simulation_origin)
    try:
        # Exclusive create prevents accidentally replacing a prior recording.
        with ExitStack() as files:
            stream = files.enter_context(open(args.output, "xb"))
            writer = Writer(stream, metadata, max_bytes=args.max_mib * 1024 * 1024)
            if mseed_path:
                from .miniseed import SeismicWriter, Mirror
                target = files.enter_context(open(mseed_path, 'xb'))
                seismic = SeismicWriter(target, metadata, station=args.mseed_station,
                    network=args.mseed_network, max_bytes=args.max_mib * 1024 * 1024,
                    simulation_start=simulation_origin)
                def observe_system_clock():
                    before = clock()
                    unix = time.time_ns()
                    after = clock()
                    return dict(raw_ns=(before + after)//2, unix_ns=unix, bracket_ns=after-before)
                writer = Mirror(writer, seismic,
                    observe_system_clock if not simulated and args.mseed_time == 'system' else None)
            app = Acquisition(writer, sessions, channels, args.queue, ids)
            if not simulated:
                enable = SensorEnable(**profile["sensor_enable"])
                if utc and not profile.get('pps'): raise ValueError('--utc requires PPS line')
                if args.fifo:
                    irqs = profile.get('imu_irq')
                    if irqs is None or len(irqs) != 3: raise ValueError('FIFO profile needs three IMU IRQ lines')
                    pins = [(x['chip'], x['line']) for x in irqs] + [(profile['sensor_enable']['chip'], profile['sensor_enable']['line'])]
                    if profile.get('pps'): pins.append((profile['pps']['chip'], profile['pps']['line']))
                    if len(set(pins)) != len(pins): raise ValueError('duplicate GPIO role')
                    for channel, mapping in zip(channels[:3], irqs): channel.adapter.irq = RisingEdges(**mapping)
                    if utc: pps = RisingEdges(**profile['pps'])
                enable.enabled(True)
                if args.usb:
                    # Independent USB session state prevents peers replacing local identities.
                    usb = USB(args.usb, Receiver(Sessions(calibrations), board=2, forbidden_devices=[profile["device_id"]]))
            start = clock()
            app.start(start)
            end, tick = clock() + int(args.seconds * 1e9), 0
            while clock() < end:
                if simulated:
                    for change in scenario.advance(current):
                        app.event("stimulus_change", "simulation controls changed", current, **change)
                app.tick(clock)
                if pps:
                    raw_before = clock()
                    mono = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
                    raw_after = clock()
                    for edge in pps.read():
                        app.event('pps_edge', 'kernel MONOTONIC edge; UTC association not established', clock(),
                                  monotonic_ns=edge, estimated_raw_ns=edge + (raw_before + raw_after)//2 - mono,
                                  mapping_bracket_ns=raw_after - raw_before, mapping_monotonic_ns=mono)
                if usb:
                    app.drain()
                    usb.poll(clock(), lambda m, t: app.emit(m, t), app.event)
                tick += 1
                if tick % args.drain_every == 0: app.drain()
                if simulated: current += 1_000_000
                else: time.sleep(.001)
            app.finish(clock())
            if seismic:
                seismic.flush()
                os.fsync(target.fileno())
                if not seismic.samples:
                    raise ValueError('No timed seismic samples were written to miniSEED')
                stream.flush()
                os.fsync(stream.fileno())
    finally:
        # Close every independent resource even if one worker cannot be reaped.
        errors = []
        for obj in [usb, pps, *[c.adapter for c in channels], enable]:
            if obj is not None:
                try: obj.close()
                except Exception as error: errors.append(error)
        if errors: raise errors[0]
    result = replay(args.output)
    if seismic: result['miniseed'] = dict(path=str(mseed_path), **seismic.summary())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Groundlark sensor acquisition (no FPGA required)")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("simulate", "live"):
        p = commands.add_parser(name)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--seconds", type=float, default=2)
        p.add_argument("--queue", type=int, default=64)
        p.add_argument("--drain-every", type=int, default=1)
        p.add_argument("--max-mib", type=int, default=64)
        p.add_argument("--calibrations", type=Path)
        p.add_argument('--miniseed', type=Path, help='local miniSEED 3 file; live defaults to OUTPUT.mseed')
        p.add_argument('--mseed-station', default='GL001')
        p.add_argument('--mseed-network', default='XX')
        p.add_argument('--mseed-start-utc', help='simulation only: explicit synthetic YYYY-MM-DDTHH:MM:SSZ origin')
        p.add_argument('--mseed-time', choices=['system','recorded'], default='system',
                       help='live: unverified Pi system time, or only sample timestamps with recorded UTC')
        p.add_argument('--no-miniseed', action='store_true', help='retain SSREC-only capture')
        if name == "simulate":
            p.add_argument('--board', choices=['hat','burrowlark','skylark'], default='hat')
            p.add_argument("--seed", type=int, default=1)
            p.add_argument("--faults", type=Path)
            p.add_argument("--scenario", type=Path, help="versioned SI stimulus scenario JSON")
            p.add_argument("--remote", action="store_true")
        else:
            p.add_argument("--profile", type=Path, required=True)
            p.add_argument("--usb")
            p.add_argument('--fifo', action='store_true', help='buffered IMUs with hardware timestamps and IRQ hints; explicit profile required')
            p.add_argument('--utc', action='store_true', help='capture MAX-M10S timing evidence and BCM24 PPS; offline correlation requires measured bounds')
    p = commands.add_parser('usb', help='capture a standalone USB board without Pi GPIO or an FPGA')
    p.add_argument('--board',choices=['skylark','burrowlark'],required=True)
    p.add_argument('--usb',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=120)
    p.add_argument('--max-mib',type=int,default=8)
    p = commands.add_parser("replay")
    p.add_argument("recording", type=Path)
    p = commands.add_parser('calibration-fit', help='fit static SI gain/offset from measured SSREC reference intervals')
    p.add_argument('specification', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-simulation', action='store_true', help='permit explicitly identified synthetic bench fixtures')
    p = commands.add_parser('calibration-observe', help='inspect the raw mean and scatter of a calibration interval')
    p.add_argument('recording', type=Path)
    p.add_argument('--device', required=True)
    p.add_argument('--sensor', type=int, choices=[1,2,3,9], required=True)
    p.add_argument('--field', choices=['acceleration_m_s2','angular_rate_rad_s','temperature_k','geophone_input_v'], required=True)
    p.add_argument('--first', type=int, required=True)
    p.add_argument('--last', type=int, required=True)
    p.add_argument('--allow-simulation', action='store_true')
    p = commands.add_parser("export-scenario", help="recover controls for another deterministic simulation")
    p.add_argument("recording", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser('export-miniseed', help='export raw HAT seismic channels from SSREC')
    p.add_argument('recording', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--station', default='GL001')
    p.add_argument('--network', default='XX')
    p.add_argument('--simulation-start-utc', help='explicit synthetic origin; simulation recordings only')
    p.add_argument('--max-mib', type=int, default=64)
    args = parser.parse_args(argv)
    try:
        if args.command == "replay": result = replay(args.recording)
        elif args.command == 'calibration-fit':
            from .calibration_fit import write_fit
            result = write_fit(args.specification, args.output, args.allow_simulation)
        elif args.command == 'calibration-observe':
            from .calibration_fit import observe, SUPPORTED
            if args.field not in SUPPORTED[args.sensor]: raise ValueError('field incompatible with sensor')
            result = observe(args.recording, args.device, args.sensor, args.field,
                             args.first, args.last, args.allow_simulation)
        elif args.command == 'usb':
            from .usb_capture import capture
            result = capture(args)
        elif args.command == 'export-miniseed':
            from .miniseed import export
            result = export(args.recording, args.output, station=args.station, network=args.network,
                simulation_start=args.simulation_start_utc, max_bytes=args.max_mib*1024*1024)
        elif args.command == "export-scenario": result = export_scenario(args.recording, args.output)
        else: result = run(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"groundlark: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__": main()
