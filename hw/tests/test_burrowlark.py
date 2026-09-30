"""Independent population and SHT45 pin/rail fault fixtures."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from burrowlark_checks import population, climate_pins


class BurrowlarkPopulationTests(unittest.TestCase):
    def test_magnetic_population(self):
        population({'U1', 'U2', 'C4', 'U4', 'U5', 'U6', 'C10'})

    def test_rejects_each_removed_part_even_without_connected_pads(self):
        for ref in ('U3', 'C5'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                population({'U1', 'U2', 'C4', 'U6', 'C10', ref})

    def test_rejects_removal_of_magnetic_module_or_bypass(self):
        for refs in ({'U1', 'C4', 'U6', 'C10'}, {'U1', 'U2', 'U6', 'C10'}):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                population(refs)

    def test_requires_each_climate_component(self):
        for removed in ('U6', 'C10'):
            with self.subTest(removed=removed), self.assertRaisesRegex(ValueError, 'SHT45'):
                population({'U2', 'C4', 'U6', 'C10'} - {removed})

    def test_rejects_wrong_sensor_supply_and_swapped_bus_pins(self):
        pins = {('U6','1'):'SDA', ('U6','2'):'SCL', ('U6','3'):'V3_SENSOR',
                ('U6','4'):'GND', ('C10','1'):'V3_SENSOR', ('C10','2'):'GND'}
        climate_pins(pins)
        for pin, wrong in [(('U6','1'),'SCL'), (('U6','2'),'SDA'),
                           (('U6','3'),'V3'), (('U6','4'),'SDA'),
                           (('C10','1'),'V3'), (('C10','2'),None)]:
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                climate_pins({**pins,pin:wrong})
