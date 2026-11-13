"""Unit tests for acknowledged virtual scenario persistence (no Mongo connection)."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.scenario_evidence import record_scenario_ack  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 11, 9, 10, 0, tzinfo=UTC)


def _matches(doc, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, branch) for branch in expected):
                return False
            continue
        actual = doc.get(key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$in" and actual not in value:
                    return False
                if op == "$lte" and (actual is None or actual > value):
                    return False
                if op == "$gte" and (actual is None or actual < value):
                    return False
                if op == "$exists" and ((key in doc) != bool(value)):
                    return False
        elif actual != expected:
            return False
    return True


class FakeResult:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


class FakeCollection:
    def __init__(self):
        self.rows = {}

    def find_one(self, query, projection=None):
        return next((row.copy() for row in self.rows.values() if _matches(row, query)), None)

    def update_one(self, query, update, upsert=False):
        row = next((row for row in self.rows.values() if _matches(row, query)), None)
        inserted_id = None
        if row is None:
            if not upsert:
                return FakeResult()
            row = {key: value for key, value in query.items() if not key.startswith("$") and not isinstance(value, dict)}
            row.update(update.get("$setOnInsert", {}))
            row_id = row.get("_id")
            if row_id is not None:
                self.rows[row_id] = row
                inserted_id = row_id
        if "$setOnInsert" not in update or inserted_id is None:
            row.update(update.get("$set", {}))
            for key, value in update.get("$addToSet", {}).items():
                row.setdefault(key, [])
                if value not in row[key]:
                    row[key].append(value)
        return FakeResult(inserted_id)


class FakeDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


class ScenarioEvidenceTests(unittest.TestCase):
    def ack(self, state, command_id, timestamp):
        return {"event": "scenario_ack", "status": state, "applied": True,
                "command_id": command_id, "scenario_run_id": "run-1",
                "scenario_type": "water_overrun", "farm_key": "greenhouse_a",
                "node_id": 1, "timestamp": timestamp.isoformat(), "source": "smiot_demo_stream"}

    def test_start_stop_is_idempotent_and_monotonic(self):
        db = FakeDatabase()
        start = self.ack("started", "cmd-start", T0)
        stop = self.ack("stopped", "cmd-stop", T0 + timedelta(seconds=30))
        self.assertTrue(record_scenario_ack(start, db=db))
        self.assertFalse(record_scenario_ack(start, db=db))
        self.assertTrue(record_scenario_ack(stop, db=db))
        late_start = {**start, "command_id": "cmd-start-late"}
        self.assertTrue(record_scenario_ack(late_start, db=db))
        run = db["scenario_runs"].rows["run-1"]
        self.assertEqual(run["status"], "stopped")
        self.assertEqual(run["started_at"], T0)
        self.assertEqual(run["ended_at"], T0 + timedelta(seconds=30))
        self.assertEqual(len(db["scenario_run_events"].rows), 3)

    def test_lot_is_not_linked_without_a_valid_assignment(self):
        db = FakeDatabase()
        ack = self.ack("started", "cmd-start", T0)
        ack["lot_id"] = "lot-claimed-by-ack"
        record_scenario_ack(ack, db=db)
        event = db["scenario_run_events"].rows["run-1:cmd-start"]
        self.assertIsNone(event["lot_id"])

    def test_invalid_ack_is_rejected(self):
        with self.assertRaises(ValueError):
            record_scenario_ack({"event": "scenario_ack", "status": "applied"}, db=FakeDatabase())


if __name__ == "__main__":
    unittest.main()
