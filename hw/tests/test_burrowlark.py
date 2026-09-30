"""Fault fixtures for removed pressure hardware and retained magnetic hardware."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from burrowlark_checks import magnetometer_only


class BurrowlarkPopulationTests(unittest.TestCase):
    def test_magnetic_population(self):
        magnetometer_only({'U1', 'U2', 'C4', 'U4', 'U5'})

    def test_rejects_each_removed_part_even_without_connected_pads(self):
        for ref in ('U3', 'C5'):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                magnetometer_only({'U1', 'U2', 'C4', ref})

    def test_rejects_removal_of_magnetic_module_or_bypass(self):
        for refs in ({'U1', 'C4'}, {'U1', 'U2'}):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                magnetometer_only(refs)
