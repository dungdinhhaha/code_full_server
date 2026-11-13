from pathlib import Path
import unittest

SKETCH = (Path(__file__).resolve().parents[1] / "velxio" / "node1_environment" / "sketch.ino").read_text(encoding="utf-8")


class Node1SketchContract(unittest.TestCase):
    def test_identity_and_pins_unchanged(self):
        for token in ('DEVICE_ID = "velxio-node1"', '\\"node_id\\":\\"node1\\"', "DHT_PIN = 4",
                      "SOIL_PIN = 34", "ALERT_LED_PIN = 23", "BUZZER_PIN = 22"):
            self.assertIn(token, SKETCH)

    def test_fault_values(self):
        self.assertIn('activeScenario == "S2"', SKETCH)
        self.assertIn("sh = 95.0f", SKETCH)
        self.assertIn("sh = 0.0f", SKETCH)
        self.assertIn('activeScenario == "C2"', SKETCH)
        self.assertIn("at = 39.0f; ah = 88.0f; sec = 3.8f", SKETCH)
        self.assertNotIn('"W8"', SKETCH)

    def test_serial_markers(self):
        self.assertIn("DRILL ALERT profile=fault scenario_code=%s scenario_run_id=%s", SKETCH)
        self.assertIn("DRILL RESTORED scenario_run_id=%s", SKETCH)
        self.assertIn("DRILL AUTO_REVERT scenario_run_id=%s", SKETCH)

    def test_auto_revert(self):
        self.assertIn("FAULT_AUTO_REVERT_MS = 120000UL", SKETCH)
        self.assertIn("faultStartedMs = millis()", SKETCH)


if __name__ == "__main__":
    unittest.main()
