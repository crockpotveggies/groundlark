import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from infrasound_checks import PINS, MPN, verify


class InfrasoundTests(unittest.TestCase):
    def setUp(self):
        self.pins={**PINS, **{('J1',str(n)):f'NC_{n}' for n in (18,31,33)}}
        self.pads={'1':(1.5,26), '2':(1.5,28.54), '3':(1.5,31.08), '4':(1.5,33.62)}

    def check(self, **changes):
        args=dict(pins=self.pins,pads=self.pads,pose=(270,False),mpn=MPN,dnp=False)
        args.update(changes)
        return verify(**args)

    def test_rejects_wrong_supply_and_swapped_bus(self):
        self.assertEqual(self.check()['additional_pi_pins'],0)
        for key in PINS:
            for net in ('PI_5V','FPGA_3V3','PI_I2C_SDA','WRONG'):
                with self.subTest(key=key,net=net),self.assertRaises(ValueError):
                    self.check(pins={**self.pins,key:net})

    def test_rejects_reversed_package_and_wrong_variant(self):
        for pose in ((90,False),(270,True),(0,False)):
            with self.assertRaises(ValueError):self.check(pose=pose)
        with self.assertRaises(ValueError):self.check(pads={**self.pads,'1':self.pads['4'],'4':self.pads['1']})
        with self.assertRaises(ValueError):self.check(mpn=MPN.replace('NI3F','NI5F'))
        with self.assertRaises(ValueError):self.check(dnp=True)

    def test_rejects_consumed_power_control_pin(self):
        for pin in ('18',):
            with self.assertRaises(ValueError):self.check(pins={**self.pins,('J1',pin):'I2C_SDA'})
