import os
import unittest
from unittest import mock

from service import datadog_metrics as dm

W7 = "smiot.crop.soil_moisture.review_required"
W8 = "smiot.crop.vpd_ec.review_required"
BANDS = {
    "soil_moisture_pct": {"unit": "%", "min": 30.0, "max": 60.0},
    "vpd_kpa": {"unit": "kPa", "min": 0.8, "max": 1.4},
    "soil_ec": {"unit": "mS/cm", "min": 1.5, "max": 3.0},
}


def run_emit(node, vpd=1.0, bands=BANDS):
    """Drive emit_node_metrics with a mocked envelope; capture review gauges."""
    cycle_coll = mock.Mock()
    cycle_coll.find_one.return_value = {"crop_name": "melon", "current_stage": "fruiting"}
    envelope = {"bands": bands} if bands is not None else None
    with mock.patch.dict(os.environ, {"DATADOG_METRICS_ENABLED": "true"}), \
            mock.patch("service.datadog_metrics._send_gauge"), \
            mock.patch("service.mongodb_store.collection", return_value=cycle_coll), \
            mock.patch("service.stage_envelopes.get_effective_stage_envelope", return_value=envelope), \
            mock.patch("service.mongodb_showcase.vpd_kpa", return_value=vpd), \
            mock.patch("service.datadog_metrics.emit_health_gauge") as emit:
        dm.emit_node_metrics("greenhouse_j", 2, node, "device")
    return {c.args[0]: c for c in emit.call_args_list}


class RealReviewMetricTests(unittest.TestCase):
    def test_within_band_does_not_emit_one(self):
        calls = run_emit({"at": 25, "ah": 70, "sh": 45, "sec": 2.0}, vpd=1.0)
        self.assertEqual(calls[W7].args[1], 0)
        self.assertEqual(calls[W8].args[1], 0)

    def test_soil_moisture_out_of_band_emits_one_with_tags(self):
        calls = run_emit({"sh": 20, "sec": 2.0}, vpd=1.0)
        self.assertEqual(calls[W7].args[1], 1)
        self.assertEqual(calls[W8].args[1], 0)
        self.assertEqual(calls[W7].args[2], ["farm:greenhouse_j", "node:2", "source:device"])

    def test_vpd_out_of_band_emits_w8(self):
        calls = run_emit({"sh": 45, "sec": 2.0}, vpd=2.0)
        self.assertEqual(calls[W8].args[1], 1)
        self.assertEqual(calls[W8].args[2], ["farm:greenhouse_j", "node:2", "source:device"])

    def test_ec_out_of_band_emits_w8(self):
        calls = run_emit({"sh": 45, "sec": 4.5}, vpd=1.0)
        self.assertEqual(calls[W8].args[1], 1)

    def test_no_approved_envelope_emits_nothing(self):
        calls = run_emit({"sh": 5, "sec": 9}, vpd=3.0, bands=None)
        self.assertNotIn(W7, calls)
        self.assertNotIn(W8, calls)

    def test_missing_reading_or_band_emits_nothing(self):
        calls = run_emit({"sec": 2.0}, vpd=None, bands={"soil_moisture_pct": BANDS["soil_moisture_pct"]})
        self.assertNotIn(W7, calls)
        self.assertNotIn(W8, calls)

    def test_flags_helper_ignores_bool_and_nan(self):
        self.assertEqual(dm.review_flags_from_bands(BANDS, {"sh": True, "sec": float("nan")}, None), {})


if __name__ == "__main__":
    unittest.main()
