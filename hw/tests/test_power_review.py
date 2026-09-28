"""Source-budget failures and independent loop-analysis limiting cases."""
import cmath
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import power_review as power
from skylark_spice import phase_margin


class PowerTests(unittest.TestCase):
    def test_current_limit_voltage_drop_and_ramp(self):
        limits=power.pm_limit(80600)
        self.assertAlmostEqual(limits['maximum'],.37454,places=5)
        self.assertLess(limits['minimum'],limits['nominal'])
        self.assertLess(limits['nominal'],limits['maximum'])
        self.assertAlmostEqual(power.load_voltage(5,.5,.4),4.8)
        self.assertAlmostEqual(power.charge_current(10e-6,5,.001),.05)
        self.assertGreater(power.ldo_heat(5,3.3,.1,.0005,200,85)['scenario_junction_C'],119)
        with self.assertRaises(ValueError):power.charge_current(10e-6,5,0)
        with self.assertRaises(ValueError):power.pm_limit(100)

    def test_native_power_topology_and_rejected_cable(self):
        r=power.build_report();s=r['skylark'];g=r['groundlark']
        self.assertFalse(r['physical_qualification'])
        self.assertIsNone(s['suspend_measured_A'])
        self.assertFalse(g['powered_from_pi_header_only'])
        self.assertLess(s['configured_A'],.5)
        self.assertLess(s['attach_charge_C'],50e-6)
        self.assertTrue(any(c['pms_4p5V_met'] for c in s['cable_scenarios']))
        self.assertTrue(any(not c['pms_4p5V_met'] for c in s['cable_scenarios']))
        self.assertGreater(g['startup_scenarios'][0]['pi_5V_A'],2)

    def test_overcurrent_and_cross_power_faults_rejected(self):
        original=power.native
        for fault in ('ilim','fpga','charge'):
            def mutated(name):
                parts,pins,cap,sha=original(name)
                if fault=='ilim' and name=='skylark-usb':parts['R3']='40000R'
                if fault=='fpga' and name=='groundlark-daqhat-01':pins['J83','1']='PI_3V3'
                if fault=='charge' and name=='skylark-usb':
                    old=cap
                    cap=lambda net:old(net)+(100e-6 if net=='USB_5V' else 0)
                return parts,pins,cap,sha
            with self.subTest(fault=fault),patch.object(power,'native',mutated):
                with self.assertRaises(AssertionError):power.build_report()

    def test_phase_margin_against_known_single_and_double_poles(self):
        frequencies=[10**(i/100) for i in range(901)]
        one=[(f,1e5/(1+1j*f/10)) for f in frequencies]
        two=[(f,1e5/(1+1j*f/10)/(1+1j*f/1e6)) for f in frequencies]
        self.assertAlmostEqual(phase_margin(one)[0]['phase_margin_deg'],90,places=2)
        self.assertAlmostEqual(phase_margin(two)[0]['phase_margin_deg'],51.83,places=1)
        with self.assertRaises(ValueError):phase_margin([(1,complex(.5)),(2,complex(.1))])


if __name__=='__main__':unittest.main()
