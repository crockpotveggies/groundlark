"""Fault fixtures for the independent shared sensor pin contract."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from sensor_pin_checks import EXPECTED, verify

class SensorPins(unittest.TestCase):
    def test_reference_and_missing_or_crossed_contacts(self):
        pins={(ref,pin):net for ref,mapping in EXPECTED.items() for pin,net in mapping.items()}
        self.assertEqual(verify(pins),len(pins))
        for key in pins:
            with self.subTest(contact=key):
                missing=pins.copy(); del missing[key]
                with self.assertRaises(AssertionError): verify(missing)
                crossed=pins.copy(); crossed[key]='PI_5V'
                if pins[key]=='PI_5V': crossed[key]='GND'
                with self.assertRaises(AssertionError): verify(crossed)
