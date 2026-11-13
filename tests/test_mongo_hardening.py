"""Tests cho dot toi uu MongoDB: unique active incident, enum action, validator warn, TTL, index bo sung."""

import re
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pymongo.errors import DuplicateKeyError  # noqa: E402

from service import incident_blackbox as bb  # noqa: E402
from service import operational_evidence as oe  # noqa: E402


class _Inserted:
    pass


class UniqueScopeCollection:
    """Mo phong operational_incidents voi unique partial index (kind, farm_key, node_id) khi active."""

    def __init__(self, race=False):
        self.docs = []
        self.race = race  # find_one dau tien tra None du da co doc (gia lap dua tranh)
        self._first_find = True

    @staticmethod
    def _matches(doc, q):
        for k, v in q.items():
            if isinstance(v, dict) and "$in" in v:
                if doc.get(k) not in v["$in"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, q, projection=None, sort=None):
        if self.race and self._first_find:
            self._first_find = False
            return None
        rows = [d for d in self.docs if self._matches(d, q)]
        return rows[-1] if rows else None

    def insert_one(self, doc):
        for d in self.docs:
            if (d["kind"], d["farm_key"], d["node_id"]) == (doc["kind"], doc["farm_key"], doc["node_id"]) \
                    and d["status"] in bb.ACTIVE_STATUSES and doc["status"] in bb.ACTIVE_STATUSES:
                raise DuplicateKeyError("E11000 duplicate key")
        self.docs.append(doc)
        return _Inserted()

    def update_one(self, *a, **k):
        return mock.MagicMock(modified_count=0)


class OpenIncidentNoDuplicateTests(unittest.TestCase):
    def _il(self):
        from service import incident_lifecycle as il
        return il

    def test_two_opens_same_scope_leave_single_active_incident(self):
        il = self._il()
        coll = UniqueScopeCollection()
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value=None):
            first = il.open_incident("false_offline", "greenhouse_a", 1)
            second = il.open_incident("false_offline", "greenhouse_a", 1)
        self.assertEqual(first, second)
        self.assertEqual(len(coll.docs), 1)

    def test_race_duplicate_key_returns_existing_active_incident(self):
        il = self._il()
        coll = UniqueScopeCollection(race=True)
        existing = {"_id": "INC-EXISTING", "incident_id": "INC-EXISTING", "kind": "service_down",
                    "farm_key": "_system", "node_id": None, "status": "open", "opened_at": 1}
        coll.docs.append(existing)
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value=None):
            result = il.open_incident("service_down", "_system", None)
        self.assertEqual(result, "INC-EXISTING")
        self.assertEqual(len(coll.docs), 1)

    def test_duplicate_key_without_winner_is_not_swallowed(self):
        il = self._il()
        coll = mock.MagicMock()
        coll.find_one.return_value = None
        coll.insert_one.side_effect = DuplicateKeyError("dup")
        with mock.patch.object(il, "collection", return_value=coll), \
                mock.patch.object(il, "current_trace_id", return_value=None):
            with self.assertRaises(DuplicateKeyError):
                il.open_incident("false_offline", "greenhouse_a", 1)


class ActionEnumSyncTests(unittest.TestCase):
    RUNTIME_ACTIONS = {"HOLD", "CLEAR", "SAFE_STOP", "SET_OUTPUTS", "SET_VALVE", "SET_VENT", "SET_INVERTER"}

    def test_constant_has_all_runtime_actions(self):
        self.assertEqual(set(oe.LEDGER_ACTIONS), self.RUNTIME_ACTIONS)
        self.assertEqual(oe.LEDGER_ACTION_SET, frozenset(self.RUNTIME_ACTIONS))

    def test_validator_enum_matches_runtime_set(self):
        enum = bb.INCIDENT_VALIDATORS["action_ledger"]["$jsonSchema"]["properties"]["action"]["enum"]
        self.assertEqual(set(enum), set(oe.LEDGER_ACTIONS))

    def test_mqtt_runtime_literal_actions_are_in_set(self):
        text = (ROOT / "service" / "mqtt.py").read_text(encoding="utf-8")
        match = re.search(r'in \{("SET_OUTPUTS"[^}]*)\}', text)
        self.assertIsNotNone(match)
        literal = set(re.findall(r'"([A-Z_]+)"', match.group(1)))
        self.assertTrue(literal <= set(oe.LEDGER_ACTIONS))

    def test_record_action_event_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            oe.record_action_event({"command_id": "c1", "action": "DROP_TABLE"}, "requested")


class ValidatorWarnOnlyTests(unittest.TestCase):
    class _DB:
        def __init__(self, existing):
            self.existing = existing
            self.commands, self.created = [], []

        def list_collection_names(self):
            return list(self.existing)

        def command(self, *args, **kwargs):
            self.commands.append((args, kwargs))

        def create_collection(self, name, **kwargs):
            self.created.append((name, kwargs))

    def test_target_collections_have_validators(self):
        for name in ("action_ledger", "operational_incidents", "notifications"):
            self.assertIn(name, bb.INCIDENT_VALIDATORS)
        for name in ("telemetry", "system.buckets.telemetry"):
            self.assertNotIn(name, bb.INCIDENT_VALIDATORS)

    def test_apply_uses_moderate_and_warn_never_error(self):
        db = self._DB({"action_ledger", "operational_incidents"})  # notifications duoc tao moi
        bb.apply_incident_validators(db)
        self.assertTrue(db.commands and db.created)
        for _args, kwargs in db.commands + [((), kw) for _n, kw in db.created]:
            self.assertEqual(kwargs["validationLevel"], "moderate")
            self.assertEqual(kwargs["validationAction"], "warn")
        self.assertIn("notifications", [n for n, _ in db.created])

    def test_no_error_action_in_source(self):
        text = (ROOT / "service" / "incident_blackbox.py").read_text(encoding="utf-8")
        self.assertNotIn('validationAction="error"', text)


class _IdxColl:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def create_index(self, keys, **options):
        self.store.append((self.name, list(keys), dict(options)))
        return options.get("name")


class _IdxDB:
    def __init__(self):
        self.store = []

    def __getitem__(self, name):
        return _IdxColl(self.store, name)


class HardeningIndexTests(unittest.TestCase):
    def setUp(self):
        self.by_name = {o["name"]: (c, k, o) for c, k, o in bb.HARDENING_INDEX_SPECS}

    def test_ttl_indexes_have_expected_names_and_seconds(self):
        coll, keys, opts = self.by_name["scenario_api_idempotency_ttl_created_at"]
        self.assertEqual((coll, keys, opts["expireAfterSeconds"]), ("scenario_api_idempotency", [("created_at", 1)], 7 * 86400))
        coll, keys, opts = self.by_name["scenario_api_rate_limits_ttl_updated_at"]
        self.assertEqual((coll, keys), ("scenario_api_rate_limits", [("updated_at", 1)]))
        self.assertGreater(opts["expireAfterSeconds"], 0)

    def test_no_ttl_on_business_collections(self):
        ttl_colls = {c for c, _k, o in bb.HARDENING_INDEX_SPECS + bb.INCIDENT_INDEX_SPECS if "expireAfterSeconds" in o}
        self.assertEqual(ttl_colls, {"scenario_api_idempotency", "scenario_api_rate_limits"})

    def test_unique_index_new_name_partial_and_scoped_to_generic_kinds(self):
        coll, keys, opts = self.by_name["active_incident_by_scope_unique"]
        self.assertTrue(opts["unique"])
        self.assertEqual(keys, [("kind", 1), ("farm_key", 1), ("node_id", 1)])
        pfe = opts["partialFilterExpression"]
        self.assertEqual(pfe["status"]["$in"], bb.ACTIVE_STATUSES)
        self.assertEqual(set(pfe["kind"]["$in"]), {"false_offline", "service_down"})
        self.assertNotIn("soil_humidity_flatline", pfe["kind"]["$in"])
        self.assertNotIn("_fallback_drop", opts)  # khong bao gio bo partial -> khong thanh unique toan bang
        # index cu giu nguyen trong danh sach, khong bi thay the
        self.assertIn("active_incident_by_scope", [o.get("name") for _c, _k, o in bb.INCIDENT_INDEX_SPECS])

    def test_additive_indexes_present(self):
        self.assertEqual(self.by_name["findings_by_incident_detected"][:2], ("findings", [("incident_id", 1), ("detected_at", 1)]))
        self.assertEqual(self.by_name["action_ledger_by_farm_updated"][:2], ("action_ledger", [("farm_key", 1), ("updated_at", -1)]))
        self.assertEqual(self.by_name["schedule_logs_by_schedule_start"][:2], ("schedule_logs", [("schedule_id", 1), ("start_at", 1)]))

    def test_ensure_incident_indexes_creates_hardening_but_keeps_report_length(self):
        db = _IdxDB()
        report = bb.ensure_incident_indexes(db)
        self.assertEqual(len(report), len(bb.INCIDENT_INDEX_SPECS))
        created = {opts.get("name") for _c, _k, opts in db.store}
        for name in self.by_name:
            self.assertIn(name, created)

    def test_hardening_failure_never_raises(self):
        class Boom:
            def __getitem__(self, name):
                raise RuntimeError("boom")
        self.assertIsInstance(bb.ensure_incident_indexes(Boom()), list)


if __name__ == "__main__":
    unittest.main()
