"""GNSS cross-wiring and unintended power-path fault fixtures."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gnss_checks import PINS,NC,verify


class GNSSTests(unittest.TestCase):
    def fixture(self):
        return {**PINS,**{key:'NC_'+str(key) for key in NC}}

    def test_nominal(self):
        self.assertEqual(verify(self.fixture()),len(PINS))

    def test_every_pin_fault(self):
        for key in PINS:
            with self.subTest(key=key):
                pins=self.fixture();pins[key]='wrong'
                with self.assertRaises(ValueError):verify(pins)

    def test_backup_and_unused_pins_cannot_backfeed(self):
        for key in NC:
            with self.subTest(key=key):
                pins=self.fixture();pins[key]='PI_3V3'
                with self.assertRaisesRegex(ValueError,'no-connect'):verify(pins)

    def test_pps_shared_with_other_function_rejected(self):
        pins=self.fixture();pins['J1','7']='GNSS_PPS'
        with self.assertRaisesRegex(ValueError,'only'):verify(pins)
