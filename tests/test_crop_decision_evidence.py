"""Safe decision evidence for crop scenarios; no actuator or Datadog calls."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.scenario_domain_crops import evaluate_crop_scenario  # noqa: E402


class CropDecisionEvidenceTests(unittest.TestCase):
    def evaluate(self, code, *, payload=None, context=None):
        return evaluate_crop_scenario(
            {"code": code, "farm_key": "greenhouse_a", "scenario_run_id": "run-7"},
            payload or {"timestamp": "2026-11-10T08:00:00+07:00", "source": "sensor"},
            context=context or {},
        )

    def test_missing_approved_context_emits_review_event_without_recommendation(self):
        # Irrigation/rain policy, VPD envelope, EC policy, pollination window,
        # and disease-risk policy are deliberately absent.
        for code in ("C1", "C2", "C6", "C7", "C8", "C9"):
            with self.subTest(code=code):
                result = self.evaluate(code)
                event = result["decision_event"]
                self.assertEqual(result["status"], "unknown")
                self.assertEqual(event["event"], "crop_decision_evidence")
                self.assertTrue(event["requires_human_review"])
                self.assertIsNone(event["automatic_recommendation"])
                self.assertEqual(event["response"], "HOLD")
                self.assertTrue(event["reason"])

    def test_configured_rain_signal_only_proposes_human_review_of_future_schedule(self):
        result = self.evaluate("C9", payload={"timestamp": "2026-11-10T08:00:00+07:00",
            "id6": {"node1": {"sh": 42}}}, context={
                "rainfall": {"observed_mm": 8, "source": "rain_gauge", "observed_at": "2026-11-10T07:50:00+07:00"},
                "irrigation_schedule": {"schedule_id": "sched-1"},
                "rain_irrigation_policy": {"rain_mm_min": 5},
            })
        event = result["decision_event"]
        self.assertEqual(result["status"], "triggered")
        self.assertIsNone(event["automatic_recommendation"])
        self.assertFalse(event["requires_human_review"])
        self.assertTrue(result["evidence"]["active_irrigation_untouched"])

    def test_pollination_reminder_does_not_claim_biological_failure(self):
        result = self.evaluate("C7", context={
            "now": "2026-11-10T08:00:00+07:00",
            "pollination_window": {"start": "2026-11-10T07:00:00+07:00", "end": "2026-11-10T09:00:00+07:00"},
            "pollination_events": [],
        })
        self.assertEqual(result["status"], "triggered")
        self.assertIn("not proof", result["reason"])
        self.assertIsNone(result["decision_event"]["automatic_recommendation"])

    def test_soil_moisture_uses_only_explicitly_approved_calibrated_envelope(self):
        result = self.evaluate("C1", payload={
            "timestamp": "2026-11-10T08:00:00+07:00", "farm_key": "greenhouse_a",
            "id6": {"node1": {"sh": 32, "measured_at": "2026-11-10T08:00:00+07:00"}},
        }, context={
            "now": "2026-11-10T08:00:30+07:00", "sensor_freshness_limit_seconds": 120,
            "stage": "fruit_growth", "lot_id": "lot-verified-1",
            "stage_envelope": {
                "effective_from": "2026-11-01T00:00:00+00:00", "version": 1,
                "calibration_status": "field_calibrated",
                "source": {"citation": "approved field calibration"},
                "bands": {"sh": {"min": 40, "max": 70}},
            },
        })
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["response"], "HOLD")
        self.assertIn("No approved, field-calibrated", result["reason"])

    def test_fresh_calibrated_soil_reading_is_lot_correlated_and_stale_is_hold(self):
        context = {
            "now": "2026-11-10T08:00:30+07:00", "sensor_freshness_limit_seconds": 120,
            "stage": "fruit_growth", "crop_cycle": {"lot_id": "lot-verified-1"},
            "stage_envelope": {
                "approval_status": "approved", "effective_from": "2026-11-01T00:00:00+00:00",
                "version": 3, "calibration_status": "field_calibrated",
                "source": {"citation": "approved field calibration"},
                "bands": {"sh": {"min": 40, "max": 70}},
            },
        }
        fresh_payload = {"timestamp": "2026-11-10T08:00:00+07:00", "farm_key": "greenhouse_a",
                         "id6": {"node1": {"sh": 32, "measured_at": "2026-11-10T08:00:00+07:00"}}}
        fresh = self.evaluate("C1", payload=fresh_payload, context=context)
        self.assertEqual(fresh["status"], "triggered")
        self.assertEqual(fresh["response"], "HOLD")
        self.assertEqual(fresh["finding"]["lot_id"], "lot-verified-1")
        self.assertEqual(fresh["evidence"]["envelope_version"], "3")

        stale_context = {**context, "now": "2026-11-10T08:05:00+07:00"}
        stale = self.evaluate("C1", payload=fresh_payload, context=stale_context)
        self.assertEqual(stale["status"], "unknown")
        self.assertEqual(stale["response"], "HOLD")
        self.assertEqual(stale["evidence"]["freshness_status"], "sample_stale")

    def test_vpd_does_not_join_temperature_and_humidity_from_different_nodes(self):
        result = self.evaluate("C2", payload={
            "timestamp": "2026-11-10T08:00:00+07:00",
            "id6": {
                "node1": {"at": 30, "measured_at": "2026-11-10T08:00:00+07:00"},
                "node2": {"ah": 60, "measured_at": "2026-11-10T08:00:00+07:00"},
            },
        }, context={
            "now": "2026-11-10T08:00:30+07:00", "sensor_freshness_limit_seconds": 120,
            "stage_envelope": {
                "approval_status": "approved", "effective_from": "2026-11-01T00:00:00+00:00",
                "version": 1, "calibration_status": "field_calibrated",
                "source": {"citation": "approved field calibration"},
                "bands": {"vpd_kpa": {"min": 0.3, "max": 1.6}},
            },
        })
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["response"], "HOLD")


if __name__ == "__main__":
    unittest.main()
