"""Persistent station service with isolated acquisition sources and a loopback API."""
import argparse
from collections import deque
from contextlib import ExitStack
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
from threading import Event, RLock, Thread, BoundedSemaphore
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

from .cli import load_json, run
from .storage import Store, SegmentedWriter, atomic_json, MiB
from .storage import SET_NAME
from .telemetry import Summaries
from .workbench import project_sample


def configuration(document):
    if not isinstance(document, dict) or set(document) != {'version', 'station_id', 'sources', 'storage'}:
        raise ValueError('station configuration fields')
    if type(document['version']) is not int or document['version'] != 1 or not isinstance(document['station_id'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,24}', document['station_id']):
        raise ValueError('station identity/version')
    storage = document['storage']
    if not isinstance(storage, dict) or set(storage) != {'reserve_mib', 'fraction', 'segment_mib', 'segment_seconds'}:
        raise ValueError('storage configuration fields')
    for field, lo, hi in [('reserve_mib', 1024, 65536), ('segment_mib', 1, 64), ('segment_seconds', 1, 3600)]:
        if type(storage[field]) is not int or not lo <= storage[field] <= hi: raise ValueError(field)
    if type(storage['fraction']) not in (float, int) or not .1 <= storage['fraction'] <= .9: raise ValueError('storage fraction')
    sources = document['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= 4: raise ValueError('source count')
    names, ports, hats = set(), set(), 0
    for source in sources:
        if not isinstance(source, dict) or set(source) - {'name', 'board', 'mode', 'profile', 'usb'} or not {'name','board','mode'} <= set(source):
            raise ValueError('source fields')
        if not isinstance(source['name'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,7}', source['name']) or source['name'] in names: raise ValueError('unique source name')
        names.add(source['name'])
        if source['board'] not in ('hat', 'burrowlark', 'skylark') or source['mode'] not in ('simulation', 'live'): raise ValueError('source board/mode')
        if source['mode'] == 'simulation' and ('profile' in source or 'usb' in source): raise ValueError('simulation has no device paths')
        if source['mode'] == 'live':
            if source['board'] == 'hat':
                hats += 1
                if not isinstance(source.get('profile'), str) or 'usb' in source: raise ValueError('HAT profile')
            else:
                port = source.get('usb', '')
                if not isinstance(port,str) or not re.fullmatch(r'/dev/serial/by-id/[A-Za-z0-9_.:+-]+', port) or port in ports or 'profile' in source:
                    raise ValueError('USB sources require distinct stable by-id paths')
                ports.add(port)
    if hats > 1: raise ValueError('one physical HAT owner')
    return json.loads(json.dumps(document, allow_nan=False))


class Source:
    def __init__(self, station, spec):
        self.station, self.spec = station, spec
        self.stop = Event()
        self.enabled = True
        self.lock = RLock()
        self.state = 'starting'
        self.error = ''
        self.restarts = self.samples = self.missing = 0
        self.known_dropped = self.unknown_loss_batches = 0
        self.last_tick = time.monotonic()
        self.latest, self.periods = {}, {}
        self.events = deque(maxlen=40)
        self.summaries = Summaries()
        self.thread = Thread(target=self.loop, name='capture-'+spec['name'], daemon=True)

    def observe(self, item, at):
        with self.lock:
            if isinstance(item, dict):
                self.events.append(dict(at_ns=str(at), **item)); return
            kind = item.WhichOneof('body')
            if kind == 'configuration':
                self.periods = {s.sensor_id: s.period_ns for s in item.configuration.sensors}
            if kind == 'batch':
                if item.batch.HasField('dropped_before'): self.known_dropped += item.batch.dropped_before
                else: self.unknown_loss_batches += 1
                self.summaries.observe(item, self.periods.get(9, 3_030_303))
                for s in item.batch.samples:
                    self.samples += 1; self.missing += s.quality == 2
                    self.latest[str(item.batch.sensor_id)] = dict(project_sample(item.batch.sensor_id, s),
                        device=item.device_id, boot=str(item.boot_id), sequence=str(s.sequence),
                        acquisition_ns=str(s.time.acquisition_ns), clock_domain=s.time.domain,
                        utc_ns=str(s.time.utc_unix_ns) if s.time.HasField('utc_unix_ns') else None,
                        observed_monotonic=time.monotonic())
            elif kind == 'status':
                self.events.append(dict(at_ns=str(at), code=item.status.code, sensor=item.status.sensor_id, detail=item.status.detail))

    def heartbeat(self):
        with self.lock: self.last_tick = time.monotonic()

    def writer(self, metadata):
        options = self.station.config['storage']
        metadata = dict(metadata, station_id=self.station.config['station_id'], station_source=self.spec['name'])
        writer = SegmentedWriter(self.station.store, metadata, segment_bytes=options['segment_mib']*MiB,
                                 segment_seconds=options['segment_seconds'], observer=self.observe)
        writer.heartbeat = self.heartbeat
        return writer

    def loop(self):
        failures = 0
        while not self.station.stop.is_set():
            if not self.enabled:
                self.state = 'paused'; self.heartbeat(); self.station.stop.wait(.2); continue
            self.stop.clear()
            began = time.monotonic()
            self.state, self.error = 'acquiring', ''
            self.heartbeat()
            spec = self.spec
            args = SimpleNamespace(command='simulate' if spec['mode']=='simulation' else 'live',
                board=spec['board'], output=self.station.store.root/'unused', seconds=3600,
                miniseed=None, no_miniseed=True, mseed_start_utc=None, utc=False, fifo=True,
                faults=None, calibrations=None, drain_every=1, remote=False, seed=1,
                scenario=None, profile=spec.get('profile'), usb=spec.get('usb'), max_mib=64, queue=64,
                writer_factory=self.writer, stop_event=self.stop,
                station_device=self.station.config['station_id']+':'+spec['name'], station_boot=secrets.randbits(64) or 1)
            try:
                if spec['mode']=='live' and spec['board']!='hat':
                    from .usb_capture import capture
                    capture(args)
                else: run(args)
            except Exception as error:
                with self.lock:
                    self.error, self.state = str(error)[:256], 'recovering'
                    self.events.append(dict(code='source_failure', detail=self.error))
            finally:
                with self.lock: self.summaries.interrupt()
            if self.station.stop.is_set(): break
            if not self.enabled: continue
            failures = 0 if time.monotonic()-began >= 60 else min(failures+1, 8)
            self.restarts += 1
            deadline = time.monotonic()+min(300, 2**failures)
            while time.monotonic()<deadline and self.enabled and not self.station.stop.is_set():
                self.heartbeat(); self.station.stop.wait(.2)
        self.state = 'stopped'

    def snapshot(self):
        with self.lock:
            now = time.monotonic()
            latest = {k: dict(v, age_seconds=now-v['observed_monotonic']) for k,v in self.latest.items()}
            return dict(name=self.spec['name'], board=self.spec['board'], mode=self.spec['mode'],
                enabled=self.enabled, state=self.state, error=self.error, restarts=self.restarts,
                samples=self.samples, missing=self.missing, heartbeat_age=now-self.last_tick,
                known_dropped=self.known_dropped, unknown_loss_batches=self.unknown_loss_batches,
                latest=latest, events=list(self.events), summaries=list(self.summaries.results))


class Station:
    def __init__(self, config, root, token, config_path=None):
        self.config = configuration(config)
        self.config_path = config_path
        if not isinstance(token, str) or len(token) < 32: raise ValueError('API token requires at least 32 characters')
        self.token, self.stop = token, Event()
        self.control_lock = RLock()
        options = self.config['storage']
        self.store = Store(root, reserve_bytes=options['reserve_mib']*MiB, fraction=options['fraction'])
        self.sources = [Source(self, spec) for spec in self.config['sources']]
        self.started = time.monotonic()
        controls = self.store.root/'controls.json'
        if controls.exists():
            saved = load_json(controls)
            if not isinstance(saved,dict) or any(type(v) is not bool for v in saved.values()): raise ValueError('saved controls')
            for source in self.sources: source.enabled = saved.get(source.spec['name'], True)

    def snapshot(self):
        return dict(station_id=self.config['station_id'], uptime_seconds=time.monotonic()-self.started,
                    sources=[s.snapshot() for s in self.sources], storage=self.store.status(),
                    physical_qualification=False)

    def control(self, name, enabled):
        if type(enabled) is not bool: raise ValueError('enabled must be boolean')
        source = next((s for s in self.sources if s.spec['name']==name), None)
        if source is None: raise ValueError('unknown source')
        with self.control_lock:
            saved={s.spec['name']:s.enabled for s in self.sources}
            saved[name]=enabled
            atomic_json(self.store.root/'controls.json',saved)
            source.enabled = enabled
            if not enabled: source.stop.set()

    def shutdown(self):
        self.stop.set()
        for source in self.sources: source.stop.set()
        for source in self.sources:
            if source.thread.ident: source.thread.join(8)
        if any(s.thread.is_alive() for s in self.sources): raise TimeoutError('acquisition shutdown deadline')


def api(station, port):
    class Server(ThreadingHTTPServer):
        # Bound clients before allocating threads or buffering downloads.
        slots = BoundedSemaphore(4)
        def process_request(self, request, address):
            if not self.slots.acquire(blocking=False):
                self.shutdown_request(request); return
            try: super().process_request(request,address)
            except BaseException:
                self.slots.release(); raise
        def process_request_thread(self, request, address):
            try: super().process_request_thread(request,address)
            finally: self.slots.release()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup(); self.connection.settimeout(5)

        def log_message(self, *_): pass

        def send(self, value, status=200):
            data = json.dumps(value, allow_nan=False).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data))); self.send_header('Cache-Control', 'no-store')
            self.end_headers(); self.wfile.write(data)

        def authorized(self):
            if not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+station.token):
                self.send(dict(error='authentication required'),401); return False
            return True

        def do_GET(self):
            if not self.authorized(): return
            route = urlsplit(self.path).path
            if route=='/status': self.send(station.snapshot())
            elif route=='/recordings': self.send(station.store.listing())
            elif route=='/configuration': self.send(station.config)
            elif route.startswith('/recordings/'):
                parts=route.split('/')
                if len(parts)!=4 or not SET_NAME.fullmatch(parts[2]) or not parts[2].endswith('.closed') or parts[3]!='data.ssrec':
                    self.send(dict(error='completed recording required'),400); return
                with station.store.lock:
                    path=station.store.root/parts[2]/parts[3]
                    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
                        self.send(dict(error='not found'),404); return
                    if path.stat().st_size>64*MiB: self.send(dict(error='recording exceeds download bound'),413); return
                    data=path.read_bytes()
                self.send_response(200); self.send_header('Content-Type','application/octet-stream')
                self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            else: self.send(dict(error='not found'),404)

        def do_POST(self):
            if not self.authorized(): return
            if self.path not in ('/control','/configuration'): self.send(dict(error='not found'),404); return
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 1<=length<=16384: raise ValueError('request size')
                value = json.loads(self.rfile.read(length))
                if self.path=='/configuration':
                    value=configuration(value)
                    if station.config_path is None: raise ValueError('configuration persistence unavailable')
                    atomic_json(station.config_path,value)
                    station.stop.set()
                    for source in station.sources: source.stop.set()
                else:
                    if not isinstance(value,dict) or set(value)!={'source','enabled'}: raise ValueError('control fields')
                    station.control(value['source'], value['enabled'])
                self.send(dict(accepted=True))
            except (ValueError, TypeError, KeyError) as error: self.send(dict(error=str(error)),400)
            except OSError: self.send(dict(error='configuration could not be persisted'),503)
    server = Server(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def notify(message):
    address = os.environ.get('NOTIFY_SOCKET')
    if not address or not hasattr(socket,'AF_UNIX'): return
    if address.startswith('@'): address='\0'+address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.connect(address); sock.sendall(message.encode())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--seconds', type=float, help='bounded software soak duration; omit for continuous service')
    parser.add_argument('--storage-cap-mib', type=int, help='additional recording cap for developer soak runs')
    args=parser.parse_args(argv)
    if args.seconds is not None and not 0<args.seconds<=31*86400: parser.error('duration 0..31 days')
    station=Station(load_json(args.config), args.data, os.environ.get('GROUNDLARK_STATION_TOKEN',''), args.config)
    if args.storage_cap_mib is not None:
        if not 16 <= args.storage_cap_mib <= 4096: parser.error('soak storage cap 16..4096 MiB')
        station.store.max_bytes=args.storage_cap_mib*MiB
    server=api(station,args.port)
    def stop(*_):
        station.stop.set()
        for source in station.sources: source.stop.set()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,stop)
    with station.store.exclusive():
        station.store.recover()
        Thread(target=server.serve_forever,daemon=True).start()
        for source in station.sources: source.thread.start()
        notify('READY=1')
        try:
            while not station.stop.wait(1):
                if any(time.monotonic()-s.last_tick>30 for s in station.sources):
                    raise TimeoutError('acquisition heartbeat stalled')
                notify('WATCHDOG=1')
                if args.seconds and time.monotonic()-station.started>=args.seconds: break
        finally:
            station.shutdown(); server.shutdown(); server.server_close()
            atomic_json(args.data/'last-run.json',station.snapshot())


if __name__=='__main__': main()
