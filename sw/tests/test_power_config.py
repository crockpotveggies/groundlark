"""Battery policy placeholders must never silently enable automatic power."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pi"))
from groundlark.power_config import load_policy


class PowerConfigTests(unittest.TestCase):
    def valid(self):
        # Synthetic validation fixture, not a recommended battery profile.
        return dict(enabled=True, battery_description="test source",
                    shutdown_v=11, restart_v=12, shutdown_confirm_s=5,
                    restart_confirm_s=60, shutdown_timeout_s=60, minimum_off_s=30)

    def test_shipped_placeholder_is_disabled(self):
        path = Path(__file__).resolve().parents[1] / "pi/deploy/power-policy.example.json"
        config = json.loads(path.read_text())
        self.assertIsNone(load_policy(config))
        config["enabled"] = True
        with self.assertRaises(ValueError):
            load_policy(config)

    def test_valid_policy(self):
        self.assertEqual(load_policy(self.valid()).restart_v, 12)

    def test_invalid_numbers_thresholds_and_timeouts(self):
        for key, value in [("enabled", "false"), ("shutdown_v", None),
                           ("shutdown_v", float("nan")), ("restart_v", float("inf")),
                           ("shutdown_v", True), ("shutdown_v", 8),
                           ("restart_v", 11.1), ("restart_v", 19),
                           ("minimum_off_s", 0), ("shutdown_timeout_s", 0),
                           ("restart_confirm_s", -1), ("battery_description", "")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                load_policy({**self.valid(), key: value})


if __name__ == "__main__":
    unittest.main()
