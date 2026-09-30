from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pi_power_checks import PINS,NC,verify,budget

class PiPowerTests(unittest.TestCase):
 def fixture(self):return {**PINS,**{key:'NC_'+key[0]+'_'+key[1] for key in NC}}
 def test_manufacturer_pin_faults(self):
  verify(self.fixture())
  for key in [('U130','32'),('U131','5'),('U133','3'),('Q130','3'),('Q131','1'),('J130','1'),('J1','31')]:
   with self.subTest(key=key),self.assertRaises(ValueError):verify({**self.fixture(),key:'PI_3V3'})
 def test_unused_pins_and_core_load(self):
  for key in NC:
   with self.subTest(key=key),self.assertRaises(ValueError):verify({**self.fixture(),key:'GND'})
  with self.assertRaises(ValueError):verify({**self.fixture(),('FAULT','1'):'SUP_CORE'})
 def test_pi_envelope(self):
  b=budget();self.assertGreater(b['minimum_V'],4.75);self.assertLess(b['maximum_V'],5.25)
  self.assertLess(b['adc_at_18V'],2.5);self.assertLess(b['input_scenario_A'],3)
  with self.assertRaises(ValueError):budget(3.1)
  self.assertLess(budget(copper_ohm=.15)['minimum_V'],4.75)

if __name__=='__main__':unittest.main()
