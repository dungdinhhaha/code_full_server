"""Focused acceptance checks for the specialized W6/W9 incident contract."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service import mqtt as mqtt_service  # noqa: E402
from pages.home import state  # noqa: E402


class FakeCollection:
    def __init__(self):
        self.rows = {}

    def find_one(self, query, projection=None, sort=None):
        if "_id" in query:
            row = self.rows.get(query["_id"])
            if row and ("farm_key" not in query or row.get("farm_key") == query["farm_key"]):
                return row
            return None
        active = [row for row in self.rows.values()
                  if all(row.get(k) == v for k, v in query.items() if k not in {"status"})
                  and row.get("status") in {"open", "holding", "recovering"}]
        return active[-1] if active else None

    def insert_one(self, document):
        self.rows[document["_id"]] = document

    def update_one(self, query, update):
        row = self.rows.get(query.get("_id"))
        if not row or ("farm_key" in query and row.get("farm_key") != query["farm_key"]):
            return type("R", (), {"modified_count": 0})()
        for key, value in update.get("$set", {}).items():
            row[key] = value
        for key, value in update.get("$push", {}).items():
            row.setdefault(key, []).append(value)
        return type("R", (), {"modified_count": 1})()


class W6W9CorrelationTests(unittest.TestCase):
    def setUp(self):
        self.original_state = dict(state)

    def tearDown(self):
        state.clear()
        state.update(self.original_state)

    def test_w9_timeout_carries_incident_id_to_metric_and_event(self):
        state["actuator_pending_by_command"] = {
            "w9-cmd|q0": {"command_id": "w9-cmd", "farm_key": "greenhouse_j",
                           "actuator": "plc_pump", "channel": "q0", "target": 0,
                           "status": "pending", "synthetic": True,
                           "incident_id": "INC-SMIOT-W9-test"}
        }
        with patch("service.datadog_metrics.emit_count") as emit, \
                patch("service.special_incident_correlation.record_special_event") as event:
            self.assertTrue(mqtt_service._emit_actuator_command_unacknowledged(
                "plc_pump", 0, 10, channel="q0", farm_key="greenhouse_j", command_id="w9-cmd"
            ))
        self.assertIn("incident_id:INC-SMIOT-W9-test", emit.call_args.args[1])
        event.assert_called_once()
        self.assertEqual(event.call_args.args[0], "INC-SMIOT-W9-test")
        self.assertEqual(event.call_args.args[1], "actuator_command_unacknowledged")

    def test_matching_late_ack_preserves_incident_id(self):
        state["actuator_pending_by_command"] = {
            "w9-cmd|q0": {"command_id": "w9-cmd", "farm_key": "greenhouse_j",
                           "actuator": "plc_pump", "channel": "q0", "target": 0,
                           "status": "unacknowledged", "incident_id": "INC-SMIOT-W9-test"}
        }
        state["actuator_current_by_scope"] = {"greenhouse_j|plc_pump|q0": "w9-cmd|q0"}
        with patch("service.datadog_metrics.emit_count"):
            self.assertTrue(mqtt_service._record_matching_actuator_ack(
                {"command_id": "w9-cmd", "farm_key": "greenhouse_j",
                 "virtual_output": {"bit0": 0}}, source="ack"
            ))
        record = state["actuator_pending_by_command"]["w9-cmd|q0"]
        self.assertEqual(record["incident_id"], "INC-SMIOT-W9-test")
        self.assertTrue(record["late_ack"])
        self.assertTrue(record["ack_verified"])

    def test_special_incident_is_created_and_closed_for_w6(self):
        from service import special_incident_correlation as correlation
        fake = FakeCollection()
        with patch.object(correlation, "collection", return_value=fake), \
                patch.object(correlation, "trace_span"):
            incident_id = correlation.ensure_special_incident(
                "detector_heartbeat_missing", "greenhouse_b", monitor_id="343029221"
            )
            self.assertEqual(fake.rows[incident_id]["status"], "open")
            self.assertTrue(correlation.recover_special_incident(
                incident_id, farm_key="greenhouse_b",
                verification={"fresh_evaluation": True}
            ))
        self.assertEqual(fake.rows[incident_id]["status"], "recovered")


if __name__ == "__main__":
    unittest.main()
