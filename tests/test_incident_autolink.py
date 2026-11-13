"""Unit tests: watchdog-opened incidents carry monitor_id/workflow_id (no real Mongo)."""

import sys
import types
import unittest
from unittest import mock

sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

import service  # noqa: E402

il = None
th = None
_LIFECYCLE_PRESENT_BEFORE = "service.incident_lifecycle" in sys.modules


def setUpModule():
    # Imported here (not at module load) so that test_flatline_* keep patching
    # sys.modules["service.incident_lifecycle"] with fakes without interference.
    global il, th
    from service import incident_lifecycle as _il  # noqa: E402
    from service import telemetry_health as _th  # noqa: E402
    il, th = _il, _th


def tearDownModule():
    # Undo the import so `from service import incident_lifecycle` in other tests
    # resolves through sys.modules patches again.
    if not _LIFECYCLE_PRESENT_BEFORE:
        if hasattr(service, "incident_lifecycle"):
            delattr(service, "incident_lifecycle")
        sys.modules.pop("service.incident_lifecycle", None)


FALSE_OFFLINE_MONITOR = "342585836"
FALSE_OFFLINE_WORKFLOW = "ffd62026-6b63-40e4-9b46-6ac18d2d584f"
FLATLINE_MONITOR = "342585819"
FLATLINE_WORKFLOW = "2f9a3c1d-5292-4bc3-b4b9-cc03d4172724"


def _coll(find_one=None):
    coll = mock.MagicMock()
    coll.find_one.return_value = find_one
    return coll


def _mismatch_result():
    return {"mismatch": True, "injected": None, "display": "ONLINE",
            "computed": "OFFLINE", "reason": "display_status_ONLINE_but_mongo_status_OFFLINE"}


class OpenIncidentLinkTests(unittest.TestCase):
    def test_open_incident_writes_monitor_and_workflow(self):
        coll = _coll(find_one=None)
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value=None):
            incident_id = il.open_incident("false_offline", "greenhouse_a", 1,
                                           monitor_id=FALSE_OFFLINE_MONITOR,
                                           workflow_id=FALSE_OFFLINE_WORKFLOW)
        doc = coll.insert_one.call_args[0][0]
        self.assertEqual(doc["_id"], incident_id)
        self.assertEqual(doc["monitor_id"], FALSE_OFFLINE_MONITOR)
        self.assertEqual(doc["workflow_id"], FALSE_OFFLINE_WORKFLOW)

    def test_open_incident_without_ids_keeps_old_document_shape(self):
        coll = _coll(find_one=None)
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value=None):
            il.open_incident("service_down", "greenhouse_b", 1)
        doc = coll.insert_one.call_args[0][0]
        self.assertNotIn("monitor_id", doc)
        self.assertNotIn("workflow_id", doc)

    def test_reused_incident_backfills_missing_ids(self):
        coll = _coll(find_one={"_id": "INC-OLD"})
        with mock.patch.object(il, "collection", return_value=coll):
            incident_id = il.open_incident("false_offline", "greenhouse_a", 1,
                                           monitor_id=FALSE_OFFLINE_MONITOR,
                                           workflow_id=FALSE_OFFLINE_WORKFLOW)
        self.assertEqual(incident_id, "INC-OLD")
        coll.insert_one.assert_not_called()
        set_fields = [c[0][1]["$set"] for c in coll.update_one.call_args_list]
        self.assertTrue(any(s.get("monitor_id") == FALSE_OFFLINE_MONITOR for s in set_fields))
        self.assertTrue(any(s.get("workflow_id") == FALSE_OFFLINE_WORKFLOW for s in set_fields))

    def test_flatline_constants_match_required_ids(self):
        self.assertEqual(il.MONITOR_ID, FLATLINE_MONITOR)
        self.assertEqual(il.WORKFLOW_ID, FLATLINE_WORKFLOW)

    def test_start_flatline_incident_document_has_ids(self):
        coll = _coll(find_one=None)
        assignment = {"_id": "a", "zone_id": "greenhouse_a_zone_2", "lot_id": "lot",
                      "mapping_source": "explicit_demo_fixture"}
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "ensure_demo_lot_assignment", return_value=assignment), \
                mock.patch.object(il, "current_trace_id", return_value=None):
            il.start_flatline_incident("greenhouse_a", 2)
        doc = coll.insert_one.call_args[0][0]
        self.assertEqual(doc["monitor_id"], FLATLINE_MONITOR)
        self.assertEqual(doc["workflow_id"], FLATLINE_WORKFLOW)


class TraceEvidenceTests(unittest.TestCase):
    def test_trace_id_attached_when_available(self):
        coll = _coll(find_one=None)
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value="12345"), \
                mock.patch.object(il, "add_incident_trace_evidence") as add_trace:
            incident_id = il.open_incident("false_offline", "greenhouse_a", 1)
        add_trace.assert_called_once_with(incident_id, trace_id="12345")

    def test_no_trace_attached_when_ddtrace_missing(self):
        coll = _coll(find_one=None)
        with mock.patch.dict(sys.modules, {"ddtrace": None}), \
                mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "add_incident_trace_evidence") as add_trace:
            self.assertIsNone(il.current_trace_id())
            incident_id = il.open_incident("false_offline", "greenhouse_a", 1)
        add_trace.assert_not_called()
        self.assertTrue(incident_id.startswith("INC-SMIOT-"))

    def test_trace_evidence_error_is_swallowed(self):
        coll = _coll(find_one=None)
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value="999"), \
                mock.patch.object(il, "add_incident_trace_evidence", side_effect=RuntimeError("mongo down")):
            incident_id = il.open_incident("false_offline", "greenhouse_a", 1)
        self.assertTrue(incident_id.startswith("INC-SMIOT-"))


class WatchdogLinkTests(unittest.TestCase):
    def setUp(self):
        th._open_false_offline.clear()

    def tearDown(self):
        th._open_false_offline.clear()

    def test_watchdog_false_offline_passes_monitor_and_workflow(self):
        with mock.patch.object(il, "open_incident", return_value="INC-FO-1") as open_inc:
            result = th._track_false_offline("greenhouse_a", 1, _mismatch_result(),
                                             {"status": "OFFLINE"}, None, False)
        self.assertEqual(result, "INC-FO-1")
        open_inc.assert_called_once()
        args, kwargs = open_inc.call_args
        self.assertEqual(args[:3], ("false_offline", "greenhouse_a", 1))
        self.assertEqual(kwargs["monitor_id"], FALSE_OFFLINE_MONITOR)
        self.assertEqual(kwargs["workflow_id"], FALSE_OFFLINE_WORKFLOW)
        self.assertEqual(kwargs["monitor_id"], "342585836")
        self.assertEqual(kwargs["workflow_id"], "ffd62026-6b63-40e4-9b46-6ac18d2d584f")

    def test_mongo_error_in_open_does_not_break_watchdog(self):
        with mock.patch.object(il, "open_incident", side_effect=RuntimeError("mongo down")):
            result = th._track_false_offline("greenhouse_a", 1, _mismatch_result(),
                                             {"status": "OFFLINE"}, None, False)
        self.assertIsNone(result)
        self.assertNotIn(("greenhouse_a", 1), th._open_false_offline)

    def test_mongo_error_in_collection_does_not_break_watchdog(self):
        with mock.patch.object(il, "collection", side_effect=RuntimeError("mongo down")):
            result = th._track_false_offline("greenhouse_a", 1, _mismatch_result(),
                                             {"status": "OFFLINE"}, None, False)
        self.assertIsNone(result)

    def test_mongo_error_in_flatline_does_not_break_watchdog(self):
        with mock.patch.object(il, "collection", side_effect=RuntimeError("mongo down")):
            result = th._track_flatline_incident("greenhouse_a", 2, True, 10)
        self.assertIsNone(result)

    def test_backfill_error_is_swallowed(self):
        coll = _coll(find_one={"_id": "INC-OLD"})
        coll.update_one.side_effect = RuntimeError("mongo down")
        with mock.patch.object(il, "collection", return_value=coll):
            incident_id = il.open_incident("false_offline", "greenhouse_a", 1,
                                           monitor_id=FALSE_OFFLINE_MONITOR,
                                           workflow_id=FALSE_OFFLINE_WORKFLOW)
        self.assertEqual(incident_id, "INC-OLD")


if __name__ == "__main__":
    unittest.main()
