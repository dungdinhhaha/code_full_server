"""Focused tests for the authenticated Datadog-to-SMIOT notification route.

The route is extracted from ``main.py`` instead of importing the full app,
which starts MQTT/Mongo initialization. All persistence and app state are fakes;
these tests never contact Datadog, AWS, MongoDB, or the EC2 service.
"""

import ast
import asyncio
import hashlib
import json
import os
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from service.datadog_notifications import (
    NotificationValidationError,
    normalize_datadog_notification,
)
from service.farm_registry import FARM_KEYS


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"


class Response:
    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content


class FakeApp:
    def post(self, _path):
        return lambda fn: fn


class FakeRequest:
    def __init__(self, body=b"", headers=None):
        self._body = body
        self.headers = headers or {}

    async def body(self):
        return self._body


class FakeCollection:
    def __init__(self):
        self.documents = {}
        self.calls = []
        self.incident_documents = {}
        self.incident_updates = []

    def find_one(self, query, projection=None):
        return self.incident_documents.get(query["_id"])

    def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))
        if "$setOnInsert" not in update:
            self.incident_updates.append((query, update))
            return types.SimpleNamespace(upserted_id=None)
        key = query["_id"]
        if key in self.documents:
            return types.SimpleNamespace(upserted_id=None)
        self.documents[key] = update["$setOnInsert"]
        return types.SimpleNamespace(upserted_id=key)


class DatadogNotificationNormalizationTests(unittest.TestCase):
    def test_normalizes_required_and_optional_fields(self):
        result = normalize_datadog_notification({
            "event_id": " run-123 ",
            "message": " Workflow completed ",
            "category": "DATADOG",
            "severity": "ERROR",
            "farm_key": "greenhouse_a",
            "incident_id": "inc-1",
            "workflow_name": "W1",
            "workflow_id": "wf-1",
        })
        self.assertEqual(result["event_id"], "run-123")
        self.assertEqual(result["message"], "Workflow completed")
        self.assertEqual(result["category"], "datadog")
        self.assertEqual(result["severity"], "error")
        self.assertEqual(result["farm_key"], "greenhouse_a")

    def test_unknown_category_and_severity_use_bounded_fallbacks(self):
        result = normalize_datadog_notification({"event_id": "r", "message": "m", "category": "custom", "severity": "critical"})
        self.assertEqual(result["category"], "datadog")
        self.assertEqual(result["severity"], "warning")

    def test_normalizes_incident_run_device_and_provenance_context(self):
        result = normalize_datadog_notification({
            "event_id": "event-1", "message": "W9 ACK timeout",
            "scenario_run_id": "scenario-17", "command_id": "cmd-9",
            "device_id": "pump-1", "node_id": "2", "scenario_code": "W9_NO_ACK",
            "event_time": "2026-11-10T10:00:00Z", "synthetic": True,
        })
        self.assertEqual(result["scenario_run_id"], "scenario-17")
        self.assertEqual(result["command_id"], "cmd-9")
        self.assertEqual(result["device_id"], "pump-1")
        self.assertEqual(result["node_id"], "2")
        self.assertEqual(result["scenario_code"], "W9_NO_ACK")
        self.assertTrue(result["synthetic"])

    def test_synthetic_must_be_a_boolean(self):
        with self.assertRaises(NotificationValidationError) as ctx:
            normalize_datadog_notification({
                "event_id": "event-1", "message": "test", "synthetic": "true"
            })
        self.assertEqual(ctx.exception.result, "invalid_synthetic")

    def test_recovery_status_requires_positive_verification(self):
        for status in ("recovered", "already_healthy"):
            with self.subTest(status=status), self.assertRaises(NotificationValidationError) as ctx:
                normalize_datadog_notification({"event_id": "r", "message": "m", "status": status})
            self.assertEqual(ctx.exception.result, "recovery_requires_verification")
        result = normalize_datadog_notification({
            "event_id": "r", "message": "m", "status": "recovered", "verification_status": "passed"
        })
        self.assertEqual(result["status"], "recovered")

    def test_rejects_non_object_and_missing_required_fields(self):
        cases = [([], "invalid_payload", 400), ({"event_id": "r"}, "event_id_and_message_required", 422)]
        for payload, code, status in cases:
            with self.subTest(code=code), self.assertRaises(NotificationValidationError) as ctx:
                normalize_datadog_notification(payload)
            self.assertEqual((ctx.exception.result, ctx.exception.status_code), (code, status))

    def test_rejects_invalid_event_ids_messages_and_farm_keys(self):
        cases = [
            ({"event_id": "x" * 161, "message": "m"}, "invalid_event_id"),
            ({"event_id": "r\n2", "message": "m"}, "invalid_event_id"),
            ({"event_id": "r", "message": " "}, "invalid_message"),
            ({"event_id": "r", "message": "m" * 501}, "invalid_message"),
            ({"event_id": "r", "message": "m", "farm_key": "unknown"}, "invalid_farm_key"),
        ]
        for payload, code in cases:
            with self.subTest(code=code), self.assertRaises(NotificationValidationError) as ctx:
                normalize_datadog_notification(payload)
            self.assertEqual(ctx.exception.result, code)

    def test_all_local_workflow_notification_bodies_match_app_contract(self):
        drafts = ROOT / "outputs" / "workflow_imports" / "level5_drafts"
        notifications = 0
        for path in sorted(drafts.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            spec = data.get("spec") or data.get("data", {}).get("attributes", {}).get("spec") or {}
            for step in spec.get("steps", []):
                if step.get("actionId") != "com.datadoghq.http.request":
                    continue
                parameters = {item["name"]: item.get("value") for item in step.get("parameters", [])}
                body = json.loads(parameters["body"])
                for key, value in (("InstanceId", "run-test"), ("WorkflowName", "W-test"),
                                   ("WorkflowId", "wf-test")):
                    body = {
                        name: field.replace("{{" + key + "}}", value) if isinstance(field, str) else field
                        for name, field in body.items()
                    }
                with self.subTest(file=path.name, step=step["name"]):
                    normalized = normalize_datadog_notification(body)
                    self.assertTrue(normalized["event_id"])
                    self.assertTrue(normalized["message"])
                    self.assertTrue(normalized["farm_key"] is None or normalized["farm_key"] in FARM_KEYS)
                    self.assertNotIn("{{Trigger.farm_key}}", json.dumps(body))
                notifications += 1
        self.assertGreaterEqual(notifications, 10)


def _load_notification_route():
    """Compile only the route, injecting app/runtime dependencies."""
    tree = ast.parse(MAIN.read_text(encoding="utf-8"), filename=str(MAIN))
    route = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "receive_datadog_notification"
    )
    namespace = {
        "app": FakeApp(),
        "Request": object,
        "JSONResponse": Response,
        "os": os,
        "secrets": __import__("secrets"),
        "json": json,
        "datetime": datetime,
        "timezone": timezone,
        "collection": lambda _name: _load_notification_route.collection,
        "system_logger": types.SimpleNamespace(exception=lambda *_args, **_kwargs: None),
    }
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(MAIN), "exec"), namespace)
    return namespace["receive_datadog_notification"]


class DatadogNotificationRouteTests(unittest.TestCase):
    def setUp(self):
        self.route = _load_notification_route()
        self.collection = FakeCollection()
        _load_notification_route.collection = self.collection
        self.state = {"notifications": [], "_update_counter": 0}
        self.home_module = types.ModuleType("pages.home")
        self.home_module.state = self.state
        self.module_patch = mock.patch.dict(sys.modules, {"pages.home": self.home_module})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.env_patch = mock.patch.dict(os.environ, {"DATADOG_APP_NOTIFICATION_TOKEN": "unit-test-token"})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def run_route(self, request):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.route(request))
        finally:
            loop.close()

    def request(self, payload, token="unit-test-token", headers=None):
        encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        actual_headers = {"authorization": f"Bearer {token}", "content-length": str(len(encoded))}
        actual_headers.update(headers or {})
        return FakeRequest(encoded, actual_headers)

    def test_missing_server_token_and_bad_bearer_are_rejected(self):
        with mock.patch.dict(os.environ, {"DATADOG_APP_NOTIFICATION_TOKEN": ""}):
            response = self.run_route(self.request({}))
        self.assertEqual((response.status_code, response.content["result"]), (503, "disabled"))
        response = self.run_route(self.request({}, token="wrong"))
        self.assertEqual((response.status_code, response.content["result"]), (401, "unauthorized"))

    def test_malformed_and_oversized_requests_are_rejected(self):
        response = self.run_route(self.request(b"{not-json"))
        self.assertEqual((response.status_code, response.content["result"]), (400, "invalid_json"))
        response = self.run_route(self.request(b"x" * 8193))
        self.assertEqual((response.status_code, response.content["result"]), (413, "payload_too_large"))

    def test_notification_is_persisted_idempotently_and_updates_bell_once(self):
        payload = {"event_id": "run-7", "message": "W5 dependency alert", "farm_key": "greenhouse_a", "workflow_name": "W5", "workflow_id": "wf-5", "severity": "warning"}
        first = self.run_route(self.request(payload))
        duplicate = self.run_route(self.request(payload))
        expected_id = "datadog:" + hashlib.sha256(b"run-7").hexdigest()
        self.assertEqual((first.status_code, first.content["result"]), (202, "received"))
        self.assertEqual((duplicate.status_code, duplicate.content["result"]), (200, "duplicate"))
        self.assertEqual(len(self.collection.documents), 1)
        self.assertIn(expected_id, self.collection.documents)
        self.assertEqual(self.collection.documents[expected_id]["source"], "datadog_workflow")
        self.assertEqual(self.state["_update_counter"], 1)
        self.assertEqual(len(self.state["notifications"]), 1)

    def test_invalid_farm_does_not_write_to_mongo(self):
        response = self.run_route(self.request({"event_id": "r", "message": "m", "farm_key": "not-a-farm"}))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.collection.documents, {})

    def test_workflow_metadata_is_bounded_and_stored(self):
        payload = {"event_id": "run-8", "message": "ok", "workflow_name": "N" * 161}
        response = self.run_route(self.request(payload))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.collection.documents, {})

    def test_workflow_event_links_only_to_matching_incident_and_never_closes_it(self):
        self.collection.incident_documents["INC-1"] = {
            "_id": "INC-1", "farm_key": "greenhouse_a", "status": "open"
        }
        payload = {
            "event_id": "run-9:branch-refused",
            "workflow_run_id": "run-9",
            "scenario_run_id": "scenario-9",
            "command_id": "cmd-9",
            "node_id": "2",
            "scenario_code": "W4_STATUS_MISMATCH",
            "synthetic": True,
            "workflow_id": "wf-1",
            "monitor_id": "mon-1",
            "incident_id": "INC-1",
            "farm_key": "greenhouse_a",
            "status": "refused",
            "decision_code": "RESTART_REFUSED_HEALTHY",
            "action_code": "NO_RESTART",
            "verification_status": "passed",
            "evidence_refs": ["trace-1", "log-1"],
            "message": "Safe refusal confirmed",
        }
        response = self.run_route(self.request(payload))
        expected_id = "datadog:" + hashlib.sha256(payload["event_id"].encode()).hexdigest()
        self.assertEqual((response.status_code, response.content["result"]), (202, "received"))
        notification = self.collection.documents[expected_id]
        self.assertEqual(notification["incident_id"], "INC-1")
        self.assertEqual(notification["correlation_status"], "verified")
        self.assertEqual(notification["workflow_status"], "refused")
        self.assertEqual(notification["scenario_run_id"], "scenario-9")
        self.assertEqual(notification["command_id"], "cmd-9")
        self.assertEqual(notification["node_id"], "2")
        self.assertTrue(notification["synthetic"])
        self.assertEqual(len(self.collection.incident_updates), 1)
        incident_query, incident_update = self.collection.incident_updates[0]
        self.assertEqual(incident_query, {"_id": "INC-1", "farm_key": "greenhouse_a"})
        self.assertNotIn("status", incident_update["$set"])

    def test_workflow_event_with_wrong_farm_is_stored_unlinked(self):
        self.collection.incident_documents["INC-2"] = {
            "_id": "INC-2", "farm_key": "greenhouse_b", "status": "open"
        }
        response = self.run_route(self.request({
            "event_id": "run-10", "incident_id": "INC-2", "farm_key": "greenhouse_a",
            "message": "Unmatched candidate",
        }))
        self.assertEqual(response.status_code, 202)
        document = next(iter(self.collection.documents.values()))
        self.assertIsNone(document["incident_id"])
        self.assertEqual(document["correlation_status"], "unlinked")
        self.assertEqual(self.collection.incident_updates, [])

    def test_workflow_event_with_incident_missing_farm_is_stored_unlinked(self):
        self.collection.incident_documents["INC-3"] = {
            "_id": "INC-3", "status": "open"
        }
        response = self.run_route(self.request({
            "event_id": "run-11", "incident_id": "INC-3", "farm_key": "greenhouse_a",
            "message": "Cannot prove farm match",
        }))
        self.assertEqual(response.status_code, 202)
        document = next(iter(self.collection.documents.values()))
        self.assertIsNone(document["incident_id"])
        self.assertEqual(document["correlation_status"], "unlinked")
        self.assertEqual(self.collection.incident_updates, [])

    def test_recovered_workflow_notification_never_closes_incident(self):
        self.collection.incident_documents["INC-4"] = {
            "_id": "INC-4", "farm_key": "greenhouse_a", "status": "open"
        }
        response = self.run_route(self.request({
            "event_id": "run-12:recovered",
            "workflow_run_id": "run-12",
            "incident_id": "INC-4",
            "farm_key": "greenhouse_a",
            "status": "recovered",
            "verification_status": "passed",
            "message": "Workflow reports recovered; app verifier still owns closure",
        }))
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.collection.incident_documents["INC-4"]["status"], "open")
        _query, incident_update = self.collection.incident_updates[0]
        self.assertNotIn("status", incident_update.get("$set", {}))


if __name__ == "__main__":
    unittest.main()
