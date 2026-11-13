"""Khoang thieu mau chi thuoc ve su co khi bat dau truoc luc phuc hoi."""
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from service import incident_blackbox as bb  # noqa: E402

T0 = datetime(2026, 11, 6, 2, 36, 40, tzinfo=timezone.utc)
RECOVERED = T0 + timedelta(minutes=21)


def _gap(start, seconds=420):
    return {"kind": "telemetry_gap", "ts": start, "gap_start": start,
            "gap_end": start + timedelta(seconds=seconds), "gap_seconds": float(seconds)}


def _incident(kind="soil_humidity_flatline"):
    return {"kind": kind, "opened_at": T0, "fault_started_at": T0, "recovered_at": RECOVERED}


class GapScopeTests(unittest.TestCase):
    def test_gap_after_recovery_is_not_counted(self):
        events = [_gap(RECOVERED + timedelta(minutes=9))]  # vi du: ca khac xay ra sau
        impact = bb.compute_impact(_incident(), events, [])
        self.assertEqual(impact["missing_sample_gaps"], 0)

    def test_gap_during_incident_is_counted(self):
        events = [_gap(T0 + timedelta(minutes=5))]
        impact = bb.compute_impact(_incident(), events, [])
        self.assertEqual(impact["missing_sample_gaps"], 1)

    def test_open_incident_counts_all_gaps(self):
        inc = {"kind": "service_down", "opened_at": T0, "fault_started_at": T0}
        events = [_gap(T0 + timedelta(minutes=1)), _gap(T0 + timedelta(minutes=30))]
        impact = bb.compute_impact(inc, events, [])
        self.assertEqual(impact["missing_sample_gaps"], 2)

    def test_service_down_unreliable_seconds_ignore_later_gap(self):
        inc = _incident("service_down")
        events = [_gap(T0 + timedelta(minutes=2), 300), _gap(RECOVERED + timedelta(minutes=5), 400)]
        impact = bb.compute_impact(inc, events, [])
        self.assertEqual(impact["unreliable_seconds"], 300.0)


if __name__ == "__main__":
    unittest.main()
