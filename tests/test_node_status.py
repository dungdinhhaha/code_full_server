"""Unit tests for pure node-status logic in service/telemetry_health.py (no Mongo/MQTT)."""

import sys
import time
import types
import unittest
from datetime import datetime, timedelta, timezone

if "service.datadog_metrics" not in sys.modules:
    try:
        import service.datadog_metrics  # noqa: F401
    except Exception:
        stub = types.ModuleType("service.datadog_metrics")
        stub.emit_health_gauge = lambda *a, **k: None
        stub.metric_tags = lambda *a, **k: []
        sys.modules["service.datadog_metrics"] = stub

from service import telemetry_health as th  # noqa: E402

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _status(age_s):
    return th.compute_node_status(NOW - timedelta(seconds=age_s), NOW, stale_after_s=90, offline_after_s=300)


class ComputeNodeStatusTest(unittest.TestCase):
    def test_unknown_when_no_sample(self):
        self.assertEqual(th.compute_node_status(None, NOW)["status"], "UNKNOWN")

    def test_online(self):
        self.assertEqual(_status(10)["status"], "ONLINE")

    def test_stale(self):
        self.assertEqual(_status(120)["status"], "STALE")

    def test_offline(self):
        self.assertEqual(_status(400)["status"], "OFFLINE")


class ReconcileTest(unittest.TestCase):
    def test_active_fault_keeps_display_and_flags_mismatch(self):
        display = {"node1_status": "OFFLINE", "fault_stale_cache": {
            "node": 1, "label": "synthetic_injected_stale_cache", "expires_at": time.time() + 300}}
        r = th.reconcile_display_status(display, 1, _status(10))
        self.assertTrue(r["mismatch"])
        self.assertEqual(display["node1_status"], "OFFLINE")
        self.assertEqual(r["injected"], "synthetic_injected_stale_cache")
        self.assertIn("fault_stale_cache", display)

    def test_expired_fault_is_cleared_and_display_corrected(self):
        display = {"node1_status": "OFFLINE", "fault_stale_cache": {
            "node": 1, "expires_at": time.time() - 1}}
        th.reconcile_display_status(display, 1, _status(10))
        self.assertEqual(display["node1_status"], "ONLINE")
        self.assertNotIn("fault_stale_cache", display)

    def test_unknown_display_is_not_mismatch(self):
        display = {"node1_status": "UNKNOWN"}
        r = th.reconcile_display_status(display, 1, _status(10))
        self.assertFalse(r["mismatch"])
        self.assertEqual(display["node1_status"], "ONLINE")

    def test_fault_for_other_node_does_not_hold(self):
        display = {"node1_status": "OFFLINE", "fault_stale_cache": {
            "node": 2, "expires_at": time.time() + 300}}
        r = th.reconcile_display_status(display, 1, _status(10))
        self.assertEqual(display["node1_status"], "ONLINE")
        self.assertIsNone(r["injected"])


class FailureDomainTest(unittest.TestCase):
    def test_four_branches(self):
        f = th.classify_failure_domain
        self.assertEqual(f(mongo_ok=False, mqtt_connected=True, sample_status="OFFLINE")["domain"], "mongo")
        self.assertEqual(f(mongo_ok=True, mqtt_connected=False, sample_status="OFFLINE")["domain"], "broker")
        self.assertEqual(f(mongo_ok=True, mqtt_connected=True, sample_status="OFFLINE",
                           broker_msg_age_s=5, stale_after_s=90)["domain"], "app_ingest")
        self.assertEqual(f(mongo_ok=True, mqtt_connected=True, sample_status="OFFLINE",
                           broker_msg_age_s=None, stale_after_s=90)["domain"], "producer")
        self.assertIsNone(f(mongo_ok=True, mqtt_connected=True, sample_status="ONLINE"))


if __name__ == "__main__":
    unittest.main()