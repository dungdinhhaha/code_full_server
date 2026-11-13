"""RV1 fixes: AI HOLD for every non ok/no_water status; fault farm respected in reconcile."""

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import test_ai_failsafe  # noqa: E402,F401  (installs import stubs, imports ai_service)
import test_node_status  # noqa: E402,F401  (stubs datadog_metrics)
from service import ai_service as ai  # noqa: E402
from service import telemetry_health as th  # noqa: E402


class AiHoldTests(unittest.TestCase):
    def test_every_non_ok_status_holds(self):
        for payload in ({"ai_status": "timeout"}, {"ai_status": "timeout", "amount_ml": 50},
                        {"ai_status": "failed", "amount_ml": 50}, {"ai_status": "no_data", "amount_ml": 50},
                        {"ai_status": "ok"}, {}):
            with self.subTest(payload=payload):
                result = ai.classify_ai_payload(payload)
                self.assertTrue(result["hold"])
                self.assertIsNone(result["amount_ml"])
                self.assertTrue(result["reason"])

    def test_ok_and_no_water_do_not_hold(self):
        for payload in ({"ai_status": "ok", "amount_ml": 80}, {"ai_status": "no_water", "amount_ml": 0}):
            with self.subTest(payload=payload):
                self.assertFalse(ai.classify_ai_payload(payload)["hold"])


class ReconcileFaultFarmTests(unittest.TestCase):
    def _display(self, fault_farm):
        return {"node1_status": "ONLINE",
                "fault_stale_cache": {"node": 1, "farm": fault_farm, "label": "inj",
                                      "expires_at": time.time() + 60}}

    def test_fault_for_other_farm_is_ignored(self):
        display = self._display("greenhouse_b")
        computed = {"status": "OFFLINE", "reason": "r"}
        result = th.reconcile_display_status(display, 1, computed, "greenhouse_a")
        self.assertIsNone(result["injected"])
        self.assertEqual(display["node1_status"], "OFFLINE")  # corrected, fault not held

    def test_fault_for_same_farm_is_held(self):
        display = self._display("greenhouse_a")
        computed = {"status": "OFFLINE", "reason": "r"}
        result = th.reconcile_display_status(display, 1, computed, "greenhouse_a")
        self.assertEqual(result["injected"], "inj")
        self.assertEqual(display["node1_status"], "ONLINE")


if __name__ == "__main__":
    unittest.main()
