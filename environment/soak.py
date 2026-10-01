"""Bounded real-time three-board software soak; results use the normal lab retention."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import sys
from threading import Thread
import time
import uuid
from lab import lab_lock, clean, MARKER

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'sw/pi'),str(ROOT/'sw/interfaces/python')]
from groundlark.station import Station, api
from groundlark.storage import atomic_json, MiB


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hours',type=float,default=168);p.add_argument('--port',type=int,default=8765)
    args=p.parse_args()
    if not 0<args.hours<=168:p.error('duration must be greater than zero and at most 168 hours')
    ident=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+uuid.uuid4().hex[:8]
    root=ROOT/'.lab'
    with lab_lock(root):
        clean(root,keep=4,apply=True)
        folder=root/'runs'/ident;folder.mkdir(parents=True)
        record=dict(owner=MARKER,id=ident,profile='station-soak',status='running',active_soak=True,
                    pid=os.getpid(),requested_hours=args.hours,started_utc=datetime.now(timezone.utc).isoformat(),
                    scope='real-time software simulation; no physical qualification')
        inputs=[Path(__file__),ROOT/'sw/pi/profiles/station-simulation.json']
        for path in (ROOT/'sw/pi/groundlark',ROOT/'sw/interfaces/python'):
            inputs.extend(path.rglob('*.py'))
        record['source_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
        atomic_json(folder/'run.json',record)
    print(folder,flush=True)
    station=server=None;server_started=False
    errors=set();began=time.monotonic();finished=False;previous=began
    def stop(*_):
        if station:station.stop.set()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
    try:
        config=json.loads((ROOT/'sw/pi/profiles/station-simulation.json').read_text())
        station=Station(config,folder/'recordings',os.environ.get('GROUNDLARK_STATION_TOKEN') or secrets.token_hex(32))
        station.store.max_bytes=256*MiB
        server=api(station,args.port)
        with station.store.exclusive():
            Thread(target=server.serve_forever,daemon=True).start()
            server_started=True
            for source in station.sources:source.thread.start()
            while not station.stop.wait(1):
                if (folder/'stop.request').exists():break
                now=time.monotonic();elapsed=now-began
                if now-previous>5:errors.add('monitor missed its 5-second deadline (host sleep or stall)')
                previous=now
                status=station.snapshot()
                for source in status['sources']:
                    if source['error']:errors.add(source['name']+': '+source['error'])
                    if source['restarts']:errors.add(source['name']+': source restarted during soak')
                    if not source['enabled']:errors.add(source['name']+': paused during soak')
                    if source['heartbeat_age']>30:raise TimeoutError('source heartbeat stalled')
                if int(elapsed)%30==0:
                    atomic_json(folder/'status.json',status)
                    record.update(elapsed_seconds=elapsed,errors=sorted(errors))
                    atomic_json(folder/'run.json',record)
                if elapsed>=args.hours*3600:finished=True;break
    except BaseException as error:
        errors.add(str(error)[:256]);raise
    finally:
        try:
            if station:station.shutdown()
            if server_started:server.shutdown()
            if server:server.server_close()
        except BaseException as error:
            errors.add('shutdown: '+str(error)[:200]);raise
        finally:
            record.update(active_soak=False,elapsed_seconds=time.monotonic()-began,
                status='passed' if finished and not errors else 'failed' if errors else 'interrupted',
                errors=sorted(errors),finished_utc=datetime.now(timezone.utc).isoformat())
            if station:atomic_json(folder/'status.json',station.snapshot())
            atomic_json(folder/'run.json',record)
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
