"""Fault fixtures for the electrical bench probe interface."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from calibration_checks import verify


class CalibrationProbeTests(unittest.TestCase):
    def fixture(self):
        return {ref: dict(net=net, source_net=net, back=True, bare_copper=True, pads=1,
                          size_mm=(1.5,1.5), xy=(1.,1.), source_xy=(1.,2.), through_via=True)
                for ref, net in [('TP90','GND'), ('TP91','GEO_VCM'),
                                 ('TP92','GEO_AVDD'), ('TP93','GEO_DRDY_N')]}

    def test_passive_interface(self):
        self.assertEqual(verify(self.fixture())['additional_gpio'], 0)

    def test_independent_faults_rejected(self):
        for ref in self.fixture():
            for key, value in [('net','PI_5V'), ('source_net','GEO_P'), ('back',False),
                               ('bare_copper',False), ('pads',2), ('size_mm',(1.,1.)),
                               ('xy',(10.,20.)), ('through_via',False)]:
                with self.subTest(ref=ref, fault=key):
                    rows = deepcopy(self.fixture()); rows[ref][key] = value
                    with self.assertRaises(ValueError): verify(rows)
        rows = self.fixture(); del rows['TP91']
        with self.assertRaises(ValueError): verify(rows)
