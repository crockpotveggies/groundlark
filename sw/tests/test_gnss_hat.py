"""Current HAT timing path: production M10 driver, PPS, replay and miniSEED."""
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from groundlark.workbench import Workbench
from groundlark.recording import Reader
from groundlark.gnss_sim import EPOCH, modeled_policy
from groundlark.utc import correlate
from groundlark.miniseed import export


def advance(engine, milliseconds):
    engine.running=True
    while milliseconds:
        step=min(milliseconds,200);engine.advance(step);milliseconds-=step
    engine.running=False
    if engine.error:raise AssertionError(engine.error)


class GNSShatTests(unittest.TestCase):
    def test_startup_then_lock_and_separate_pps_loss(self):
        engine=Workbench(board='hat')
        self.assertFalse(engine.snapshot(6)['timing']['locked'])
        advance(engine,2200)
        state=engine.snapshot(6)['timing']
        self.assertTrue(state['locked']);self.assertTrue(state['pps_recent'])
        self.assertEqual(state['pps_count'],2);self.assertFalse(state['qualified'])
        engine.controls({'gnss_pps':False});advance(engine,2100)
        state=engine.snapshot(6)['timing']
        self.assertTrue(state['locked']);self.assertFalse(state['pps_recent'])
        self.assertEqual(state['pps_count'],2)
        engine.controls({'gnss_pps':True,'gnss_fix':False});advance(engine,1200)
        state=engine.snapshot(6)['timing']
        self.assertFalse(state['locked']);self.assertTrue(state['pps_recent'])
        self.assertEqual(engine.snapshot(1)['latest'][1]['quality'],'Valid')

    def test_fault_clears_lock_without_stopping_acquisition(self):
        engine=Workbench(board='hat');advance(engine,2200)
        engine.controls({'sensor_faults':{'6':'disconnect'}});advance(engine,1800)
        self.assertFalse(engine.snapshot(6)['timing']['locked'])
        self.assertEqual(engine.snapshot(9)['latest'][9]['quality'],'Valid')

    def test_record_correlate_raw_preservation_replay_and_miniseed(self):
        engine=Workbench(board='hat');advance(engine,8000);raw=engine.finish()
        with tempfile.TemporaryDirectory() as directory:
            src=Path(directory)/'raw.ssrec';dst=Path(directory)/'utc.ssrec'
            src.write_bytes(raw)
            policy=modeled_policy(hashlib.sha256(raw).hexdigest())
            report=correlate(src,dst,policy)
            self.assertGreater(report['samples_correlated'],1000)
            self.assertEqual(report['scope'],'modeled')
            original=list(Reader(BytesIO(raw)));annotated=list(Reader(BytesIO(dst.read_bytes())))
            self.assertEqual(len(original),len(annotated))
            for (arrival,a),(other,b) in zip(original,annotated):
                self.assertEqual(arrival,other)
                if not isinstance(b,dict) and b.WhichOneof('body')=='batch':
                    for sample in b.batch.samples:
                        if sample.time.HasField('utc_unix_ns'):
                            self.assertEqual(sample.time.utc_unix_ns,EPOCH*10**9+sample.time.acquisition_ns)
                            self.assertLess(sample.time.utc_uncertainty_ns,1_000_000)
                        sample.time.ClearField('utc_unix_ns');sample.time.ClearField('utc_uncertainty_ns')
                self.assertEqual(a,b)
            summary=export(dst,Path(directory)/'waveforms.mseed')
            self.assertGreater(summary['records'],0)
            engine.load_recording(dst.read_bytes());engine.seek(7)
            self.assertTrue(engine.snapshot(6)['timing']['locked'])
            self.assertGreater(engine.snapshot(6)['timing']['pps_count'],0)

    def test_missing_pps_never_manufactures_utc(self):
        engine=Workbench({'version':1,'initial':{'gnss_pps':False}},board='hat')
        advance(engine,6000);raw=engine.finish()
        with tempfile.TemporaryDirectory() as directory:
            src=Path(directory)/'raw.ssrec';src.write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'no unambiguous'):
                correlate(src,Path(directory)/'utc.ssrec',modeled_policy(hashlib.sha256(raw).hexdigest()))

    def test_burrowlark_has_no_gnss_or_pi_time_reference(self):
        engine=Workbench(board='burrowlark');advance(engine,3000)
        self.assertNotIn(6,engine.sensor_ids)
        self.assertEqual(engine.snapshot(7)['timing']['pps_count'],0)
        self.assertEqual(engine.snapshot(7)['latest'][7]['clock_domain'],2)
