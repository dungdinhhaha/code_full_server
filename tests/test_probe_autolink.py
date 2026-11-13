"""Unit tests for the workflow/monitor link added to scripts/smiot_external_probe.py.

No MongoDB, no Datadog, no network: pymongo is replaced in sys.modules and urllib is mocked.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -p "test_*.py"
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

PROBE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smiot_external_probe.py"
_spec = importlib.util.spec_from_file_location("smiot_external_probe", PROBE_PATH)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

DD_KEYS = ("DD_API_KEY", "DD_APP_KEY", "DD_SITE")


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_pymongo(incidents):
    """Return a fake pymongo module whose client exposes operational_incidents as `incidents`."""
    db = mock.MagicMock()
    db.__getitem__.return_value = incidents
    client = mock.MagicMock()
    client.__getitem__.return_value = db
    module = mock.MagicMock()
    module.MongoClient.return_value = client
    return module


class ServiceDownDocumentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_path = os.path.join(self._tmp.name, "state.json")
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump({"app_fail_streak": 1}, fh)  # next failed run is the 2nd -> open
        self.env = {
            "SMIOT_PROBE_RECORD_INCIDENT": "1",
            "SMIOT_PROBE_MONGODB_URI_WRITE": "mongodb://fake",
            "SMIOT_PROBE_STATE_FILE": self.state_path,
            "SMIOT_PROBE_MONITOR_ID": "monitor-test",
            "SMIOT_PROBE_WORKFLOW_ID": "workflow-test",
        }
        self.incidents = mock.MagicMock()
        self.incidents.find_one.return_value = None

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, app_up, newest_age=None):
        clean = {k: "" for k in DD_KEYS}
        with mock.patch.dict(os.environ, {**clean, **self.env}), \
                mock.patch.dict(sys.modules, {"pymongo": _fake_pymongo(self.incidents)}):
            return probe.update_service_down_incident(app_up, 0, "/login", newest_age, "_system")

    def test_opened_document_carries_monitor_and_workflow(self):
        out = self._run(app_up=0)
        self.assertEqual(out["incident_action"], "opened")
        self.incidents.insert_one.assert_called_once()
        doc = self.incidents.insert_one.call_args[0][0]
        self.assertEqual(doc["kind"], "service_down")
        self.assertEqual(doc["farm_key"], "_system")
        self.assertEqual(doc["monitor_id"], "monitor-test")
        self.assertEqual(doc["workflow_id"], "workflow-test")

    def test_recovery_keeps_monitor_and_workflow_fields(self):
        # Open incident already in state; close it with a fresh sample.
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump({"app_fail_streak": 0, "service_down_incident_id": "INC-1"}, fh)
        opened_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.incidents.find_one.return_value = {"_id": "INC-1", "opened_at": opened_at.replace(tzinfo=None)}
        self.incidents.update_one.return_value = mock.Mock(modified_count=1)
        out = self._run(app_up=1, newest_age=10.0)
        self.assertEqual(out["incident_action"], "recovered")
        self.assertNotIn("incident_error", out)
        set_fields = self.incidents.update_one.call_args[0][1]["$set"]
        self.assertEqual(set_fields["status"], "recovered")
        # Only the status/verification fields are $set; monitor_id/workflow_id are not touched.
        self.assertNotIn("monitor_id", set_fields)
        self.assertNotIn("workflow_id", set_fields)


class WorkflowLookupTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_path = os.path.join(self._tmp.name, "state.json")
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump({"app_fail_streak": 0, "service_down_incident_id": "INC-1"}, fh)
        self.env = {
            "SMIOT_PROBE_RECORD_INCIDENT": "1",
            "SMIOT_PROBE_MONGODB_URI_WRITE": "mongodb://fake",
            "SMIOT_PROBE_STATE_FILE": self.state_path,
            "SMIOT_PROBE_WORKFLOW_ID": "workflow-test",
        }
        self.incidents = mock.MagicMock()
        self.opened_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        self.incidents.find_one.return_value = {"_id": "INC-1", "opened_at": self.opened_at.replace(tzinfo=None)}
        self.incidents.update_one.return_value = mock.Mock(modified_count=1)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, extra_env, urlopen=None):
        clean = {k: "" for k in DD_KEYS}
        env = {**clean, **self.env, **extra_env}
        patches = [
            mock.patch.dict(os.environ, env),
            mock.patch.dict(sys.modules, {"pymongo": _fake_pymongo(self.incidents)}),
        ]
        if urlopen is not None:
            patches.append(mock.patch.object(probe.urllib.request, "urlopen", side_effect=urlopen))
        for p in patches:
            p.start()
        try:
            return probe.update_service_down_incident(1, 200, "/healthz", 10.0, "_system")
        finally:
            for p in reversed(patches):
                p.stop()

    def test_lookup_error_does_not_break_probe(self):
        err = urllib.error.URLError("network down")
        with mock.patch("sys.stderr", new=io.StringIO()):
            out = self._run({"DD_API_KEY": "k", "DD_APP_KEY": "a"}, urlopen=err)
        self.assertEqual(out["incident_action"], "recovered")
        self.assertNotIn("incident_error", out)
        self.assertNotIn("state_error", out)
        self.incidents.update_one.assert_called_once()
        set_fields = self.incidents.update_one.call_args[0][1]["$set"]
        self.assertNotIn("last_workflow_execution_id", set_fields)

    def test_http_error_does_not_break_probe(self):
        err = urllib.error.HTTPError("https://api.datadoghq.com/x", 403, "Forbidden", {}, None)
        with mock.patch("sys.stderr", new=io.StringIO()):
            out = self._run({"DD_API_KEY": "k", "DD_APP_KEY": "a"}, urlopen=err)
        self.assertEqual(out["incident_action"], "recovered")
        self.assertNotIn("incident_error", out)

    def test_latest_execution_in_window_is_saved(self):
        started = (datetime.now(timezone.utc) - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        older = (datetime.now(timezone.utc) - timedelta(minutes=4)).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {"data": [
            {"id": "exec-old", "attributes": {"startTime": older}},
            {"id": "exec-new", "attributes": {"startTime": started}},
        ]}
        resp = _FakeResponse(json.dumps(body).encode("utf-8"))
        with mock.patch("sys.stderr", new=io.StringIO()):
            out = self._run({"DD_API_KEY": "k", "DD_APP_KEY": "a"}, urlopen=lambda *a, **k: resp)
        self.assertEqual(out["incident_action"], "recovered")
        set_fields = self.incidents.update_one.call_args[0][1]["$set"]
        self.assertEqual(set_fields["last_workflow_execution_id"], "exec-new")

    def test_no_api_key_probe_still_closes_incident(self):
        urlopen = mock.Mock(side_effect=AssertionError("must not call Datadog without a key"))
        with mock.patch("sys.stderr", new=io.StringIO()) as err:
            out = self._run({}, urlopen=urlopen)
        urlopen.assert_not_called()
        self.assertEqual(out["incident_action"], "recovered")
        self.assertNotIn("incident_error", out)
        self.assertIn("no_api_key", err.getvalue())
        set_fields = self.incidents.update_one.call_args[0][1]["$set"]
        self.assertNotIn("last_workflow_execution_id", set_fields)

    def test_no_api_key_helper_returns_reason(self):
        clean = {k: "" for k in DD_KEYS}
        with mock.patch.dict(os.environ, clean):
            exec_id, reason = probe.latest_workflow_execution_id(datetime.now(timezone.utc))
        self.assertIsNone(exec_id)
        self.assertEqual(reason, "no_api_key")

    def test_workflow_lookup_skips_when_org_workflow_id_not_configured(self):
        clean = {k: "" for k in DD_KEYS}
        with mock.patch.dict(os.environ, {**clean, "DD_API_KEY": "k", "DD_APP_KEY": "a",
                                          "SMIOT_PROBE_WORKFLOW_ID": ""}):
            exec_id, reason = probe.latest_workflow_execution_id(datetime.now(timezone.utc))
        self.assertIsNone(exec_id)
        self.assertEqual(reason, "no_workflow_id")


if __name__ == "__main__":
    unittest.main()
