"""Focused receiver checks for additive virtual channels and scenario ACKs."""

import sys
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service import mqtt as mqtt_service  # noqa: E402
from pages.home import state  # noqa: E402


class FakeCollection:
    def __init__(self):
        self.documents = []

    def insert_one(self, document):
        self.documents.append(document)


class MqttVirtualReceiverTests(unittest.TestCase):
    def setUp(self):
        self.original_state = dict(state)

    def tearDown(self):
        state.clear()
        state.update(self.original_state)

    def test_id7_and_id8_are_stored_with_stable_timeseries_metadata(self):
        collection = FakeCollection()
        payload = {
            "farm_key": "greenhouse_a", "source": "smiot_demo_stream", "synthetic": True,
            "timestamp": "2026-11-09T10:00:00Z", "scenario_run_id": "run-7", "lot_id": "lot-7",
        }
        with patch("service.mongodb_store.collection", return_value=collection):
            self.assertTrue(mqtt_service._persist_virtual_sensor_channel(
                "greenhouse_a", payload,
                {"device_type": "drain_sensor", "measured_at": payload["timestamp"],
                 "scenario_run_id": "run-7"},
                {"drain_l": 0.4, "drain_ec_ms_cm": 1.2},
            ))
            self.assertTrue(mqtt_service._persist_virtual_sensor_channel(
                "greenhouse_a", payload,
                {"device_type": "ventilation_feedback", "measured_at": payload["timestamp"]},
                {"command": 1, "state": 1, "fan_rpm": 1450, "stuck": False},
            ))
        self.assertEqual(len(collection.documents), 2)
        self.assertEqual(collection.documents[0]["meta"]["measurement_type"], "drain_sensor")
        self.assertEqual(collection.documents[0]["readings"]["drain_l"], 0.4)
        self.assertEqual(collection.documents[1]["meta"]["measurement_type"], "ventilation_feedback")
        self.assertEqual(collection.documents[0]["source"]["scenario_run_id"], "run-7")
        # Scenario attribution is channel-local; the envelope's run ID alone
        # must not incorrectly associate every device stream with that run.
        self.assertNotIn("scenario_run_id", collection.documents[1]["source"])

    def test_status_receiver_exposes_virtual_plc_feedback(self):
        mqtt_service.process_farm_status({
            "device_name": "SMIOT Virtual PLC", "source": "smiot_demo_stream",
            "farm_key": "greenhouse_a", "bit0": 0, "bit1": 1,
            "safe_mode_active": True, "valve_state": 0, "vent_cmd": 1, "vent_state": 1,
            "fan_rpm": 1450, "fault": None, "timestamp": "2026-11-09T10:00:00Z",
        })
        feedback = state["virtual_plc_feedback"]
        self.assertEqual(feedback["virtual_output"]["bit1"], 1)
        self.assertTrue(feedback["safe_mode_active"])
        self.assertEqual(feedback["vent_state"], 1)

    def test_scenario_ack_updates_ui_and_calls_idempotent_persistence_api(self):
        state["demo_scenario_control"] = {
            "scenario_run_id": "run-1", "command_id": "cmd-1", "status": "pending_ack",
        }
        payload = {
            "event": "scenario_ack", "status": "started", "applied": True,
            "scenario_run_id": "run-1", "command_id": "cmd-1", "scenario_type": "water_overrun",
            "farm_key": "greenhouse_a", "timestamp": "2026-11-09T10:00:00Z",
        }
        with patch("service.mongodb_store.database", return_value=object()), \
                patch("service.scenario_evidence.record_scenario_ack", return_value=True) as record:
            mqtt_service._record_scenario_ack(payload)
        record.assert_called_once_with(payload, db=record.call_args.kwargs["db"])
        self.assertEqual(state["demo_scenario_control"]["status"], "started")
        self.assertTrue(state["demo_scenario_control"]["applied"])
        self.assertTrue(state["demo_scenario_control"]["ack_persisted"])
        self.assertEqual(state["demo_scenario_ack_by_run"]["run-1"]["command_id"], "cmd-1")

    def test_demo_status_topic_routes_only_scenario_ack(self):
        payload = {"event": "scenario_ack", "scenario_run_id": "run-2", "command_id": "cmd-2",
                   "status": "started", "applied": True}
        msg = SimpleNamespace(topic="farm/demo/status", payload=json.dumps(payload).encode())
        with patch.object(mqtt_service, "_record_scenario_ack") as record, \
                patch.object(mqtt_service, "trigger_ui_update"):
            mqtt_service.on_message(None, None, msg)
            legacy = SimpleNamespace(topic="farm/demo/status",
                                     payload=json.dumps({"demo_node2_fault": "normal"}).encode())
            mqtt_service.on_message(None, None, legacy)
        record.assert_called_once_with(payload)

    def test_w9_accepts_late_ack_only_for_exact_timed_out_command_and_farm(self):
        state["actuator_pending_by_command"] = {
            "cmd-9|q0": {
                "command_id": "cmd-9", "farm_key": "greenhouse_a", "actuator": "plc_pump",
                "channel": "q0", "target": 0, "status": "unacknowledged",
            }
        }
        state["actuator_current_by_scope"] = {"greenhouse_a|plc_pump|q0": "cmd-9|q0"}
        payload = {"command_id": "cmd-9", "farm_key": "greenhouse_a", "virtual_output": {"bit0": 0}}

        with patch("service.datadog_metrics.emit_count") as emit_count:
            self.assertFalse(mqtt_service._record_matching_actuator_ack(
                {**payload, "farm_key": "greenhouse_b"}, source="ack"
            ))
            self.assertTrue(mqtt_service._record_matching_actuator_ack(payload, source="ack"))

        record = state["actuator_pending_by_command"]["cmd-9|q0"]
        self.assertEqual(record["status"], "acknowledged")
        self.assertTrue(record["late_ack"])
        self.assertTrue(record["target_matches"])
        self.assertTrue(record["ack_verified"])
        self.assertNotIn("greenhouse_a|plc_pump|q0", state["actuator_current_by_scope"])
        metric_names = [call.args[0] for call in emit_count.call_args_list]
        self.assertIn("smiot.actuator.command_acknowledged", metric_names)
        self.assertIn("smiot.actuator.command_late_acknowledged", metric_names)


if __name__ == "__main__":
    unittest.main()
