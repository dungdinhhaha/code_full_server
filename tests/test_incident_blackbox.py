"""Test ham thuan cua hop den su co (service/incident_blackbox.py). Khong can Mongo.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -v
"""

import copy
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service import incident_blackbox as bb  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=UTC)
NOW = datetime(2026, 11, 6, 12, 0, 0, tzinfo=UTC)


class FakeCollection:
    """create_index gia lap: tu choi partial index de kiem tra duong fallback."""

    def __init__(self, reject_partial=False):
        self.reject_partial = reject_partial
        self.calls = []

    def create_index(self, keys, **options):
        self.calls.append((keys, dict(options)))
        if self.reject_partial and "partialFilterExpression" in options:
            raise RuntimeError("partial index not supported")
        return options.get("name") or "_".join(f"{k}_{v}" for k, v in keys)


class FakeDatabase:
    def __init__(self, reject_partial=False):
        self.reject_partial = reject_partial
        self.collections = {}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(self.reject_partial)
        return self.collections[name]


class PipelineTests(unittest.TestCase):
    @staticmethod
    def _union_collections(pipeline):
        return [stage["$unionWith"]["coll"] for stage in pipeline if "$unionWith" in stage]

    def test_pipeline_with_telemetry_branch_has_all_sources_and_window_stage(self):
        pipeline = bb.build_timeline_pipeline(
            "INC-X", farm_key="greenhouse_a", node_id=2,
            window_start=T0 - timedelta(minutes=15), window_end=NOW)
        text = json.dumps(pipeline, default=str)
        self.assertEqual(self._union_collections(pipeline), [
            "incident_telemetry_evidence", "operational_decisions", "findings",
            "action_ledger", "telemetry",
        ])
        self.assertIn("$setWindowFields", text)

    def test_pipeline_without_window_skips_telemetry_branch(self):
        pipeline = bb.build_timeline_pipeline("INC-X")
        text = json.dumps(pipeline, default=str)
        self.assertEqual(self._union_collections(pipeline), [
            "incident_telemetry_evidence", "operational_decisions", "findings", "action_ledger",
        ])
        self.assertNotIn("$setWindowFields", text)

    def test_scenario_ack_replay_requires_explicit_run_id(self):
        no_link = bb.build_timeline_pipeline("INC-X")
        linked = bb.build_timeline_pipeline("INC-X", scenario_run_id="run-1")
        no_link_collections = self._union_collections(no_link)
        linked_collections = self._union_collections(linked)
        self.assertNotIn("scenario_run_events", no_link_collections)
        self.assertNotIn("scenario_observations", no_link_collections)
        self.assertIn("scenario_run_events", linked_collections)
        self.assertIn("scenario_observations", linked_collections)
        self.assertEqual(len(linked_collections), len(no_link_collections) + 2)
        text = json.dumps(linked)
        self.assertIn("run-1", text)

    def test_pipeline_rejects_empty_incident_id(self):
        with self.assertRaises(ValueError):
            bb.build_timeline_pipeline("")

    def test_hot_queries_cover_five_queries_with_window(self):
        incident = {"_id": "INC-X", "kind": "service_down", "farm_key": "greenhouse_a", "node_id": None}
        queries = bb.hot_queries(incident, T0, NOW)
        self.assertEqual(len(queries), 7)
        self.assertEqual(queries[-1]["collection"], "telemetry")
        self.assertEqual(queries[3]["collection"], "scenario_run_events")


class IndexFallbackTests(unittest.TestCase):
    def test_partial_index_rejected_falls_back_without_partial(self):
        db = FakeDatabase(reject_partial=True)
        report = bb.ensure_incident_indexes(db)
        by_name = {r["index"]: r for r in report}
        self.assertEqual(by_name["active_incident_by_scope"]["status"], "ok_fallback")
        self.assertEqual(by_name["telemetry_by_incident_ts"]["status"], "ok_fallback")
        self.assertEqual(len(report), len(bb.INCIDENT_INDEX_SPECS))

    def test_index_specs_are_not_mutated_by_fallback(self):
        before = copy.deepcopy(bb.INCIDENT_INDEX_SPECS)
        bb.ensure_incident_indexes(FakeDatabase(reject_partial=True))
        self.assertEqual(before, bb.INCIDENT_INDEX_SPECS)


class WindowAndLotsTests(unittest.TestCase):
    def test_compute_window_uses_opened_at_and_pre_minutes(self):
        start, end = bb.compute_window({"kind": "false_offline", "opened_at": T0}, now=NOW)
        self.assertEqual(start, T0 - timedelta(minutes=15))
        self.assertEqual(end, NOW)

    def test_compute_window_none_without_any_fault_time(self):
        self.assertEqual(bb.compute_window({"kind": "service_down"}, now=NOW), (None, None))

    def test_expired_lot_assignment_is_not_matched(self):
        start, end = T0 - timedelta(minutes=15), NOW
        rows = [
            {"_id": "a1", "farm_key": "greenhouse_a", "node_id": 2, "lot_id": "LOT-A",
             "valid_from": T0 - timedelta(hours=1), "valid_to": None},
            {"_id": "a2", "farm_key": "greenhouse_a", "node_id": 2, "lot_id": "LOT-OLD",
             "valid_from": T0 - timedelta(hours=3), "valid_to": T0 - timedelta(minutes=30)},
            {"_id": "a3", "farm_key": "greenhouse_a", "node_id": 1, "lot_id": "LOT-NODE1",
             "valid_from": T0 - timedelta(hours=1), "valid_to": None},
        ]
        matched = bb.match_affected_lots(rows, "greenhouse_a", 2, start, end)
        self.assertEqual([m["lot_id"] for m in matched], ["LOT-A"])

    def test_match_returns_empty_when_scope_incomplete(self):
        rows = [{"farm_key": "greenhouse_a", "node_id": 2, "valid_from": T0, "valid_to": None}]
        self.assertEqual(bb.match_affected_lots(rows, None, 2, T0, NOW), [])
        self.assertEqual(bb.match_affected_lots(rows, "greenhouse_a", None, T0, NOW), [])


class ImpactTests(unittest.TestCase):
    def test_false_offline_unreliable_seconds_from_fault_to_recovery(self):
        incident = {"kind": "false_offline", "opened_at": T0,
                    "fault_started_at": T0, "recovered_at": T0 + timedelta(seconds=300)}
        impact = bb.compute_impact(incident, [], affected_lots=[], now=NOW)
        self.assertEqual(impact["unreliable_seconds"], 300.0)
        self.assertEqual(impact["recovery_seconds"], 300.0)
        self.assertEqual(impact["lots_to_review"], 0)

    def test_service_down_sums_telemetry_gaps(self):
        events = [{"kind": "telemetry_gap", "gap_seconds": 40},
                  {"kind": "telemetry_gap", "gap_seconds": 20},
                  {"kind": "telemetry_sample", "ts": T0}]
        impact = bb.compute_impact({"kind": "service_down", "opened_at": T0}, events, affected_lots=None, now=NOW)
        self.assertEqual(impact["unreliable_seconds"], 60.0)
        self.assertEqual(impact["missing_sample_gaps"], 2)
        self.assertIsNone(impact["lots_to_review"])

    def test_open_incident_has_no_recovery_or_fake_duration(self):
        impact = bb.compute_impact({"kind": "false_offline", "opened_at": T0, "fault_started_at": T0},
                                   [], affected_lots=None, now=NOW)
        self.assertIsNone(impact["recovered_at"])
        self.assertIsNone(impact["unreliable_seconds"])

    def test_all_kinds_do_not_raise(self):
        for kind in bb.INCIDENT_KINDS:
            with self.subTest(kind=kind):
                impact = bb.compute_impact({"kind": kind, "opened_at": T0}, [], affected_lots=[], now=NOW)
                self.assertIn("recovery_seconds", impact)
                self.assertIn("unreliable_basis", impact)


if __name__ == "__main__":
    unittest.main()
