"""Population changes must not shift sensor identity or open removed sensor devices."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from groundlark.cli import run
from groundlark.simulation import Simulated, defaults
from groundlark.workbench import Workbench

ROOT = Path(__file__).resolve().parents[2]


class ThreeImuTests(unittest.TestCase):
    def test_current_inventory_and_legacy_imu_identity(self):
        self.assertEqual([c['sensor_id'] for c in defaults()], [1,2,3,9,6])
        self.assertEqual([c['sensor_id'] for c in defaults(legacy_gnss=True)], [1,2,3,4,5,6])
        self.assertIn('acceleration', Simulated(4).read().raw)
        self.assertIn('angle', Simulated(5).read().raw)

    def test_legacy_inclinometer_recording_still_replays(self):
        legacy_tilt = next(c for c in defaults(legacy_gnss=True) if c['sensor_id'] == 5)
        with patch('groundlark.workbench.defaults', side_effect=lambda remote=False: [] if remote else [legacy_tilt]):
            legacy = Workbench()
        legacy.toggle()
        legacy.advance(200)
        data = legacy.finish()
        current = Workbench()
        self.assertNotIn(5, current.snapshot(1)['latest'])
        current.load_recording(data)
        current.seek(.2)
        self.assertEqual(current.snapshot(5)['latest'][5]['secondary'], [0, 0, 16384])
        current.reset()
        self.assertNotIn(5, current.snapshot(1)['latest'])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux live acquisition')
    def test_live_inventory_opens_only_three_imus_geophone_and_gnss(self):
        profile=ROOT/'sw/pi/profiles/daqhat-01.example.json'
        opened=[]
        def factory(sid,path,fifo,utc):
            opened.append((sid,path,fifo,utc))
            return Simulated(sid)
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(command='live',utc=False,fifo=False,calibrations=None,
                seconds=.01,drain_every=1,profile=str(profile),output=Path(tmp)/'live.ssrec',
                max_mib=1,queue=64,usb=None,mseed_time='system',mseed_station='GL001',mseed_network='XX')
            with patch('groundlark.live.Factory',side_effect=factory), \
                 patch('groundlark.worker.Worker',side_effect=lambda device,cfg:device), \
                 patch('groundlark.linux_io.SensorEnable'):
                result=run(args)
            self.assertTrue(result['completed'])
            waveform = Path(tmp)/'live.mseed'
            self.assertEqual(waveform.read_bytes()[:4], b'MS\x03\x02')
            self.assertGreater(result['miniseed']['channel_samples'],0)
            self.assertEqual(result['miniseed']['omitted_without_calendar_time'],0)
        self.assertEqual(opened,[(1,'/dev/spidev0.0',False,False),
            (2,'/dev/spidev0.1',False,False),(3,'/dev/spidev0.2',False,False),
            (9,'/dev/i2c-1',False,False),(6,'/dev/i2c-1',False,False)])

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux live acquisition')
    def test_old_four_device_profile_fails_before_opening_hardware(self):
        profile=json.loads((ROOT/'sw/pi/profiles/daqhat-01.example.json').read_text())
        profile['spi'].append('/dev/spidev0.3')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'old.json';path.write_text(json.dumps(profile))
            args=SimpleNamespace(command='live',utc=False,calibrations=None,
                seconds=1,drain_every=1,profile=str(path),output=Path(tmp)/'old.ssrec',mseed_time='system')
            with patch('groundlark.live.Factory') as factory:
                with self.assertRaisesRegex(ValueError,'three explicit SPI'):
                    run(args)
                factory.assert_not_called()

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux live acquisition')
    def test_legacy_pps_pin_rejected_before_opening_hardware(self):
        profile=json.loads((ROOT/'sw/pi/profiles/daqhat-01.example.json').read_text())
        profile['pps']['line']=4  # Now geophone DRDY, not TIMEPULSE.
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wrong-pps.json';path.write_text(json.dumps(profile))
            args=SimpleNamespace(command='live',utc=True,fifo=True,calibrations=None,
                seconds=1,drain_every=1,profile=str(path),output=Path(tmp)/'wrong.ssrec',mseed_time='system')
            with patch('groundlark.live.Factory') as factory:
                with self.assertRaisesRegex(ValueError,'BCM24'):
                    run(args)
                factory.assert_not_called()
