"""Independent recording boundaries, storage pressure, service and API faults."""
import copy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
from threading import Thread, Event
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from groundlark import messages
from groundlark.cli import replay
from groundlark.recording import Reader
from groundlark.session import Sessions
from groundlark.storage import Store, SegmentedWriter, MiB
from groundlark.station import Station, api, configuration
from groundlark.telemetry import Summaries
from groundlark.geophone import SETTINGS

ROOT=Path(__file__).resolve().parents[2]
META=dict(format='groundlark-acquisition-v1',source='simulation',calibrations=[])


class StationTests(unittest.TestCase):
    def test_continuous_capture_crosses_hour_and_week_without_session_restart(self):
        from groundlark.cli import run
        cfg=json.loads((ROOT/'sw/pi/profiles/station-simulation.json').read_text())
        for board in ('hat','burrowlark','skylark'):
            with self.subTest(board=board), tempfile.TemporaryDirectory() as tmp:
                config=copy.deepcopy(cfg)
                config['sources']=[dict(name='test',board=board,mode='simulation')]
                station=Station(config,tmp,'x'*32)
                station.store.disk_usage=lambda _:SimpleNamespace(total=32_000_000_000,free=30_000_000_000)
                source=station.sources[0];stop=Event()
                # Exercise the real continuous CLI across boundaries without claiming elapsed soak time.
                times=iter([0,3_599_999_999_999,3_600_000_000_001,169*3600*10**9])
                def clock():
                    try:return next(times)
                    except StopIteration:stop.set();return 169*3600*10**9+1
                args=SimpleNamespace(command='simulate',board=board,output=Path(tmp)/'unused',seconds=3600,
                    no_miniseed=True,utc=False,fifo=True,faults=None,calibrations=None,drain_every=1,
                    remote=False,seed=1,scenario=None,max_mib=64,queue=64,writer_factory=source.writer,
                    stop_event=stop,station_device='test-station:'+board,station_boot=42)
                with patch('groundlark.cli.time.perf_counter_ns',side_effect=clock), patch('groundlark.cli.time.sleep'):
                    run(args)
                self.assertGreater(source.samples,0)
                self.assertTrue(all(v['boot']=='42' for v in source.latest.values()))
                self.assertTrue(all(int(v['acquisition_ns'])==169*3600*10**9 for v in source.latest.values()))
                for path in Path(tmp).glob('*.closed/data.ssrec'):self.assertTrue(replay(path)['completed'])

    def test_exhausted_sensor_retries_enter_source_backoff(self):
        from groundlark.simulation import Simulated
        class BrokenSensor(Simulated):
            def read(self): raise OSError('injected permanent bus fault')
        cfg=json.loads((ROOT/'sw/pi/profiles/station-simulation.json').read_text())
        cfg['sources']=cfg['sources'][:1]
        with tempfile.TemporaryDirectory() as tmp, patch('groundlark.cli.Simulated',BrokenSensor):
            station=Station(cfg,tmp,'x'*32)
            station.store.disk_usage=lambda _:SimpleNamespace(total=32_000_000_000,free=30_000_000_000)
            source=station.sources[0];source.thread.start()
            try:
                deadline=time.monotonic()+5
                while source.restarts==0 and time.monotonic()<deadline: time.sleep(.02)
                self.assertEqual(source.state,'recovering')
                self.assertGreater(source.restarts,0)
                self.assertIn('retry budget exhausted',source.error)
                self.assertTrue(any(e.get('code')=='source_recovery' for e in source.events))
                recordings=list(Path(tmp).glob('*.interrupted/data.ssrec'))
                self.assertTrue(recordings)
                self.assertFalse(replay(recordings[-1])['completed'])
            finally: station.shutdown()

    def store(self, path, free=100*MiB):
        return Store(path,reserve_bytes=MiB,disk_usage=lambda _:SimpleNamespace(total=100*MiB,free=free))

    def test_rotation_keeps_exact_samples_and_known_zero_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer=SegmentedWriter(self.store(tmp),META,segment_seconds=1)
            writer.message(messages.identity('sensor',123,1,[9]),0)
            writer.message(messages.configuration('sensor',123,[SETTINGS]),0)
            expected=[]
            for i in range(4):
                m=messages.batch('sensor',123,9,i,i*1_000_000_000,dict(counts=i-2,conversion_counter=i))
                expected.append(m.SerializeToString())
                writer.message(m,i*1_000_000_000)
            writer.close()
            actual=[]
            files=sorted(Path(tmp).glob('*.closed/data.ssrec'))
            self.assertEqual(len(files),4)
            for path in files:
                self.assertTrue(replay(path)['completed'])
                with path.open('rb') as stream:
                    actual += [m.SerializeToString() for _,m in Reader(stream)
                               if not isinstance(m,dict) and m.WhichOneof('body')=='batch']
            self.assertEqual(actual,expected)

    def test_checkpoint_rejects_regression_and_bad_sensor(self):
        s=Sessions();s.accept(messages.identity('sensor',1,1,[9]))
        s.accept(messages.configuration('sensor',1,[SETTINGS]))
        m=messages.batch('sensor',1,9,0,1,dict(counts=0,conversion_counter=0))
        s.accept(m);checkpoint=s.checkpoint()
        with self.assertRaises(ValueError): Sessions(checkpoint=checkpoint).accept(m)
        checkpoint[0]['last']['17']=[0,0]
        with self.assertRaises(ValueError): Sessions(checkpoint=checkpoint)

    def test_accelerated_week_retention_keeps_latest_valid_segments(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.store(tmp);store.max_bytes=MiB
            writer=SegmentedWriter(store,META,segment_seconds=3600)
            writer.message(messages.identity('sensor',123,1,[9]),0)
            writer.message(messages.configuration('sensor',123,[SETTINGS]),0)
            seq=0
            for hour in range(169):
                for sample in range(128):
                    at=hour*3600*1_000_000_000+sample*3_030_303
                    writer.message(messages.batch('sensor',123,9,seq,at,
                        dict(counts=seq,conversion_counter=seq%256)),at)
                    seq+=1
            writer.close()
            self.assertGreater(store.deleted,0)
            self.assertLessEqual(store.status()['recording_bytes'],MiB)
            newest=sorted(Path(tmp).glob('*.closed/data.ssrec'))[-1]
            self.assertTrue(replay(newest)['completed'])
            with newest.open('rb') as stream:
                last=[m for _,m in Reader(stream) if not isinstance(m,dict) and m.WhichOneof('body')=='batch'][-1]
            self.assertEqual(last.batch.samples[-1].sequence,seq-1)

    def test_process_kill_preserves_flushed_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            code='''import sys,time
from groundlark.storage import Store,SegmentedWriter,MiB
from groundlark import messages
w=SegmentedWriter(Store(sys.argv[1],reserve_bytes=MiB),dict(format="groundlark-acquisition-v1",calibrations=[]))
w.message(messages.identity("killed",1,1,[9]),0)
w.flush(True)
print("ready",flush=True)
time.sleep(30)
'''
            child=subprocess.Popen([sys.executable,'-c',code,tmp],stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(),'ready')
                path=next(Path(tmp).glob('*.open/data.ssrec'));original=path.read_bytes()
            finally:child.kill();child.wait(timeout=5);child.stdout.close()
            self.store(tmp).recover()
            path=next(Path(tmp).glob('*.interrupted/data.ssrec'))
            self.assertEqual(path.read_bytes(),original)
            self.assertFalse(replay(path)['completed'])

    def test_interrupted_bytes_preserved_and_not_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.store(tmp)
            writer=SegmentedWriter(store,META)
            writer.message(messages.identity('sensor',1,1,[9]),0)
            writer.flush(True)
            path=writer.path
            writer.stream.close();writer.stream=None;store.active.clear()
            original=(path/'data.ssrec').read_bytes()
            store.recover()
            recovered=path.with_suffix('.interrupted')/'data.ssrec'
            self.assertEqual(original,recovered.read_bytes())
            self.assertFalse(replay(recovered)['completed'])

    def test_retention_preserves_active_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=self.store(tmp)
            protected=Path(tmp)/'notes.txt';protected.write_text('preserve')
            closed=store.create();(closed/'data.ssrec').write_bytes(b'x'*4096)
            store.active.remove(closed);closed=closed.rename(closed.with_suffix('.closed'))
            active=store.create();(active/'data.ssrec').write_bytes(b'x'*4096)
            store.disk_usage=lambda _:SimpleNamespace(total=100*MiB,free=MiB)
            store.make_room(2048)
            self.assertFalse(closed.exists());self.assertTrue(active.exists());self.assertTrue(protected.exists())
            with self.assertRaises(OSError):store.make_room(8192)

    def test_all_sources_rotate_and_survive_browser_independence(self):
        cfg=json.loads((ROOT/'sw/pi/profiles/station-simulation.json').read_text())
        cfg['storage']['segment_seconds']=1
        # A coarse/frozen platform monotonic_ns must not pace simulated samples.
        with tempfile.TemporaryDirectory() as tmp, patch('groundlark.cli.time.monotonic_ns',return_value=0):
            station=Station(cfg,tmp,'x'*32)
            # The portable lab uses a 512 MiB tmpfs; model the deployed card.
            station.store.disk_usage=lambda _:SimpleNamespace(total=32_000_000_000,free=30_000_000_000)
            for source in station.sources:source.thread.start()
            try:
                time.sleep(2.2)
                status=station.snapshot()
                self.assertTrue(all(s['samples']>0 and not s['error'] for s in status['sources']),status)
                self.assertGreater(status['sources'][0]['samples'],200)
                station.control('air',False)
                time.sleep(.1)
                self.assertGreater(station.sources[0].samples,0)
            finally:station.shutdown()
            for path in Path(tmp).glob('*.closed/data.ssrec'):self.assertTrue(replay(path)['completed'])

    def test_api_authentication_and_strict_control(self):
        cfg=json.loads((ROOT/'sw/pi/profiles/station-simulation.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            station=Station(cfg,tmp,'x'*32);server=api(station,0)
            thread=Thread(target=server.serve_forever);thread.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with self.assertRaises(HTTPError) as e:urlopen(base+'/status')
                self.assertEqual(e.exception.code,401)
                req=Request(base+'/status',headers={'Authorization':'Bearer '+'x'*32})
                with urlopen(req) as response:self.assertEqual(json.load(response)['station_id'],'bench-001')
                req=Request(base+'/control',data=b'{"source":"hat","enabled":"false"}',headers={'Authorization':'Bearer '+'x'*32})
                with self.assertRaises(HTTPError) as e:urlopen(req)
                self.assertEqual(e.exception.code,400)
                station.store=self.store(tmp)
                writer=SegmentedWriter(station.store,META)
                writer.message(messages.identity('download',1,1,[9]),0);writer.close()
                path=next(Path(tmp).glob('*.closed/data.ssrec'))
                req=Request(base+'/recordings/'+path.parent.name+'/data.ssrec',headers={'Authorization':'Bearer '+'x'*32})
                with urlopen(req) as response:self.assertEqual(response.read(),path.read_bytes())
                req=Request(base+'/recordings/../controls.json',headers={'Authorization':'Bearer '+'x'*32})
                with self.assertRaises(HTTPError) as e:urlopen(req)
                self.assertEqual(e.exception.code,400)
            finally:server.shutdown();server.server_close();thread.join()

    def test_reject_duplicate_hardware_owners(self):
        cfg=json.loads((ROOT/'sw/pi/profiles/station-simulation.json').read_text())
        cfg['sources']=[dict(name='a',board='hat',mode='live',profile='a.json'),dict(name='b',board='hat',mode='live',profile='b.json')]
        with self.assertRaises(ValueError):configuration(cfg)

    def test_torn_record_recovery_copies_prefix_without_forging_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer=SegmentedWriter(self.store(tmp),META)
            writer.message(messages.identity('torn',1,1,[9]),0);writer.close(False)
            source=next(Path(tmp).glob('*.interrupted/data.ssrec'))
            valid=source.read_bytes();source.write_bytes(valid+b'\x01\x00')
            original=source.read_bytes();target=Path(tmp)/'recovered.ssrec'
            result=subprocess.run([sys.executable,str(ROOT/'sw/tools/recover_recording.py'),str(source),str(target)],
                                  capture_output=True,text=True,check=True,timeout=10)
            self.assertEqual(json.loads(result.stdout)['valid_prefix_bytes'],len(valid))
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(target.read_bytes(),valid)
            self.assertFalse(replay(target)['completed'])

    def test_summary_never_turns_missing_into_zero(self):
        summary=Summaries(1)
        for i,value in enumerate([-2,4,None,0]):
            m=messages.batch('s',1,9,i,i*500_000_000,
                None if value is None else dict(counts=value,conversion_counter=i), dropped=None if i==2 else 0)
            summary.observe(m,500_000_000)
        summary.interrupt()
        self.assertEqual(summary.results[0]['mean_absolute_counts'],3)
        self.assertTrue(summary.results[0]['complete'])
        self.assertFalse(summary.results[1]['complete'])
        self.assertTrue(summary.results[1]['loss_unknown'])

    def test_summary_coverage_respects_fractional_rate_and_boundary_loss(self):
        summary=Summaries(1)
        for i in range(4):
            at=100_000_000+i*333_333_333
            summary.observe(messages.batch('s',1,9,i,at,dict(counts=2,conversion_counter=i)),333_333_333)
        self.assertEqual(summary.results[0]['expected_samples'],3)
        self.assertTrue(summary.results[0]['complete'])
        changed=messages.batch('s',1,9,4,1_500_000_000,dict(counts=10,conversion_counter=4))
        changed.batch.configuration_revision=2
        summary.observe(changed,333_333_333)
        self.assertEqual(summary.results[-1]['configuration_revision'],1)
        self.assertEqual(summary.results[-1]['mean_absolute_counts'],2)
        summary.interrupt()
        self.assertEqual(summary.results[-1]['configuration_revision'],2)
        self.assertEqual(summary.results[-1]['mean_absolute_counts'],10)


if __name__=='__main__':unittest.main()
