"""Independent limiting cases and negative design envelopes."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from daqhat_01_engineering import microstrip, width_for, supply_range, clearance, power_interfaces, POWER_PINS


class EngineeringTests(unittest.TestCase):
    def test_air_dielectric_and_scale_invariance(self):
        z, er = microstrip(2, 1, 0, 1)
        self.assertEqual(er, 1)
        # Wheeler air-line expression, independent approximation (within 0.5%).
        reference = 120 * math.pi / (2 + 1.393 + .667 * math.log(2 + 1.444))
        self.assertAlmostEqual(z, reference, delta=.45)
        self.assertEqual(microstrip(2, 1, .1, 4), microstrip(20, 10, 1, 4))

    def test_width_solver_and_old_route(self):
        self.assertAlmostEqual(width_for(50, .215, .035, 4.3), .388, delta=.001)
        self.assertGreater(microstrip(.3, .215, .035, 4.3)[0], 55)
        self.assertAlmostEqual(microstrip(.388, .215, .035, 4.3)[0], 50, delta=.1)

    def test_supply_rejects_old_optimistic_budget(self):
        self.assertLess(supply_range(3.3, .01, .03, 3)[0], 3.201)
        lo, hi = supply_range(3.35, .005, .03, 3)
        self.assertGreater(lo, 3.201)
        self.assertLess(hi, 3.399)
        self.assertLess(supply_range(3.35, .005, .05, 3)[0], 3.201)

    def test_old_stack_fails_component_tolerance_margin(self):
        self.assertLess(clearance(18.669), 0)
        self.assertLess(clearance(19.55), 3)  # Short J1 plus only one riser.
        from assembly_fit import PI_GAP, RISER_COUNT
        self.assertEqual(RISER_COUNT, 2)
        self.assertAlmostEqual(PI_GAP, 28.06)
        self.assertGreater(clearance(PI_GAP), 3)

    def test_power_domain_and_default_enable_faults_rejected(self):
        self.assertEqual(power_interfaces(POWER_PINS),31)
        for key, unsafe in [(('U51','7'),'PI_3V3'), (('R50','2'),'GND'),
                            (('R62','2'),'PI_3V3'), (('Q1','2'),'FPGA_3V3'),
                            (('R64','2'),'PI_3V3'), (('U41','23'),'PI_5V')]:
            pins = dict(POWER_PINS); pins[key] = unsafe
            with self.assertRaises(ValueError): power_interfaces(pins)


if __name__ == '__main__': unittest.main()
