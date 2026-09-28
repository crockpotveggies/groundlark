"""Independent limiting cases, measured-design inputs and alias examples."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from signal_response import geophone, gas, db, phase, settling, folded, build_report


class ResponseTests(unittest.TestCase):
    def test_resonance_and_high_frequency_limits(self):
        m,e=geophone(4.5,2000,2e6,100.5e-9)
        self.assertAlmostEqual(abs(m),1/1.4)
        self.assertAlmostEqual(phase(m),90)
        self.assertAlmostEqual(db(geophone(1,2000,2e6,100.5e-9)[0]),-26.1305,places=4)
        self.assertLess(db(e),0)

    def test_double_pole_step_and_phase(self):
        h=gas(1/(2*math.pi*.01),100000,100e-9,10000,1e-6)
        self.assertAlmostEqual(abs(h),.5)
        self.assertAlmostEqual(phase(h),-90)
        self.assertAlmostEqual(settling(.01,.01),.06638352,places=7)
        self.assertGreater(settling(.01,.02),settling(.01,.01))

    def test_alias_is_not_nyquist_attenuation(self):
        self.assertAlmostEqual(folded(4.1,1/.24),1/15)
        self.assertAlmostEqual(folded(50,1/.24),0)
        self.assertAlmostEqual(folded(400,1024000/3116),71.3735558)
        with self.assertRaises(ValueError): folded(1,0)

    def test_native_design_keeps_unknowns_and_exposes_insufficient_filtering(self):
        report=build_report()
        self.assertFalse(report['physical_qualification'])
        g=report['groundlark'];s=report['skylark']
        self.assertIsNone(g['adc_phase_deg']);self.assertIsNone(s['gas_cell_transfer'])
        self.assertIsNone(s['enclosure_transfer'])
        self.assertLess(s['worst_slow_clock_single_shot_s'],s['minimum_slot_s'])
        self.assertGreater(s['adc_bandwidth_hz'],s['per_channel_nominal_rate_hz']/2)
        for channel in s['gas']:
            alias=next(r for r in channel['rows'] if abs(r['hz']-1/.24)<1e-6)
            self.assertGreater(alias['combined_electronics_estimate_db'],-1)
        self.assertEqual(len(g['imu_profiles']),4)


if __name__ == '__main__': unittest.main()
