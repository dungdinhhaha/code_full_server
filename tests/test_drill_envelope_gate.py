import os
import unittest
from datetime import datetime, timezone
from unittest import mock

from service import datadog_metrics as dm
from service import stage_envelopes as se

W7 = "smiot.crop.soil_moisture.review_required"
W8 = "smiot.crop.vpd_ec.review_required"
BANDS = {
    "soil_moisture_pct": {"unit": "%", "min": 40.0, "max": 70.0},
    "vpd_kpa": {"unit": "kPa", "min": 0.8, "max": 1.2},
    "soil_ec": {"unit": "mS/cm", "min": 1.2, "max": 2.0},
}
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def drill_doc():
    return {"crop_key": "melon", "stage_code": "fruiting", "cultivar": None, "version": 1,
            "approval_status": "drill", "status": "drill", "synthetic": True,
            "calibration_status": "drill_synthetic", "bands": BANDS,
            "source": {"citation": "synthetic drill"}, "effective_from": NOW, "effective_to": None}


def approved_doc():
    doc = drill_doc()
    doc.update(approval_status="approved", calibration_status="field_calibrated")
    doc.pop("synthetic")
    doc.pop("status")
    return doc


def fake_collection(docs):
    """Minimal collection stub that honours the drill gate in the query."""
    def find(query, projection=None):
        allow = "$and" in query
        out = []
        for doc in docs:
            ok_approved = doc["approval_status"] == "approved" and doc["calibration_status"] == "field_calibrated"
            ok_drill = (doc["approval_status"] == "drill" and doc.get("synthetic") is True
                        and doc["calibration_status"] == "drill_synthetic")
            if ok_approved or (allow and ok_drill):
                out.append(dict(doc))
        cursor = mock.Mock()
        cursor.sort.return_value.limit.return_value = out
        return cursor
    coll = mock.Mock()
    coll.find.side_effect = find
    return coll


class EnvelopeLookupTests(unittest.TestCase):
    def lookup(self, docs, **kw):
        with mock.patch.object(se, "collection", return_value=fake_collection(docs)):
            return se.get_effective_stage_envelope("melon", "fruiting", NOW, **kw)

    def test_drill_hidden_by_default(self):
        self.assertIsNone(self.lookup([drill_doc()]))

    def test_drill_visible_when_allowed(self):
        env = self.lookup([drill_doc()], allow_drill=True)
        self.assertTrue(env["drill"])
        self.assertEqual(env["calibration_status"], "drill_synthetic")

    def test_approved_unchanged(self):
        env = self.lookup([approved_doc()])
        self.assertNotIn("drill", env)
        self.assertEqual(env["calibration_status"], "field_calibrated")
        env2 = self.lookup([approved_doc()], allow_drill=True)
        self.assertNotIn("drill", env2)


def run_emit(source, node, envelope_for):
    cycle_coll = mock.Mock()
    cycle_coll.find_one.return_value = {"crop_name": "melon", "current_stage": "fruiting"}

    def fake_get(**kwargs):
        return envelope_for(kwargs.get("allow_drill", False))

    with mock.patch.dict(os.environ, {"DATADOG_METRICS_ENABLED": "true"}), \
            mock.patch("service.datadog_metrics._send_gauge") as send, \
            mock.patch("service.mongodb_store.collection", return_value=cycle_coll), \
            mock.patch("service.stage_envelopes.get_effective_stage_envelope", side_effect=fake_get), \
            mock.patch("service.mongodb_showcase.vpd_kpa", return_value=1.0), \
            mock.patch("service.datadog_metrics.emit_health_gauge") as emit:
        dm.emit_node_metrics("greenhouse_j", 1, node, source)
    return {c.args[0]: c for c in emit.call_args_list}, send


def drill_env(allow):
    return {"bands": BANDS, "drill": True, "calibration_status": "drill_synthetic"} if allow else None


class DrillEmitTests(unittest.TestCase):
    def test_drill_envelope_synthetic_data_emits_with_tag(self):
        for src in ("velxio_synthetic", "smiot_demo_stream"):
            calls, send = run_emit(src, {"sh": 20, "sec": 2.5}, drill_env)
            self.assertEqual(calls[W7].args[1], 1)
            self.assertEqual(calls[W8].args[1], 1)
            self.assertEqual(calls[W7].args[2], ["farm:greenhouse_j", "node:1", "source:synthetic_drill"])
            approved = [c for c in send.call_args_list if c.args[0] == "smiot.crop.envelope.approved"]
            self.assertEqual(approved[0].args[1], 0)

    def test_drill_envelope_real_data_does_not_emit(self):
        calls, _ = run_emit("device", {"sh": 20, "sec": 2.5}, drill_env)
        self.assertNotIn(W7, calls)
        self.assertNotIn(W8, calls)

    def test_drill_envelope_leaked_to_real_data_is_rejected(self):
        leaky = lambda allow: {"bands": BANDS, "drill": True}
        calls, _ = run_emit("device", {"sh": 20, "sec": 2.5}, leaky)
        self.assertNotIn(W7, calls)

    def test_approved_envelope_unchanged(self):
        approved = lambda allow: {"bands": BANDS, "calibration_status": "field_calibrated"}
        for src in ("device", "velxio_synthetic"):
            calls, _ = run_emit(src, {"sh": 20, "sec": 2.5}, approved)
            self.assertEqual(calls[W7].args[1], 1)
            self.assertEqual(calls[W7].args[2], ["farm:greenhouse_j", "node:1", f"source:{src}"])


if __name__ == "__main__":
    unittest.main()
