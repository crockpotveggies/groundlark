"""Reject unsafe rail joins, polarity errors, DNC ties and regulator budgets."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from fpga_power_checks import PINS,verify,budget

class FPGAPowerTests(unittest.TestCase):
 def fixture(self):
  p=dict(PINS);p.update({('J1','1'):'PI_3V3',('J1','2'):'PI_5V'})
  for key in [('U80','4'),('U80','5'),('U80','13'),('J83','3'),('SW80','3')]:p[key]='NC_'+key[0]+'_'+key[1]
  return p
 def test_supply_and_connector_faults(self):
  verify(self.fixture())
  for key,net in [(('J83','1'),'GND'),(('D80','1'),'FUSED_12V'),(('U80','7'),'PI_3V3'),(('J80','14'),'PI_5V'),(('U80','6'),'PI_3V3')]:
   with self.subTest(key=key):
    p=self.fixture();p[key]=net
    with self.assertRaises(AssertionError):verify(p)
 def test_dnc_and_switch_contact_faults(self):
  for key in [('U80','4'),('U80','5'),('J83','3'),('SW80','3')]:
   p=self.fixture();p[key]='GND'
   with self.assertRaises(AssertionError):verify(p)
 def test_converter_budget_and_negative_cases(self):
  b=budget();self.assertAlmostEqual(b['setpoint_V'],3.3255813953)
  self.assertGreater(b['minimum_V'],3.201);self.assertLess(b['maximum_V'],3.399)
  self.assertLess(b['adapter_scenario_A'],1.1)
  self.assertLess(budget(loop_ohm=.03)['minimum_V'],3.201)
  self.assertGreater(budget(bottom=3900)['maximum_V'],3.399)
  self.assertGreater(budget(resistor_tolerance=.01)['maximum_V'],3.399)
  with self.assertRaises(ValueError):budget(current_a=3.1)

if __name__=='__main__':unittest.main()
