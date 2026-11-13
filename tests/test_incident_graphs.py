"""Test ham thuan du lieu khoi Tac dong / chat luong du lieu cua trang su co (pages/incident.py). Khong can Mongo.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -v
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pages.incident import build_impact_chart_data  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=UTC)
FALSE_OFFLINE_NOTE = "Dữ liệu vẫn vào MongoDB trong lúc UI báo offline"


def sample(ts: datetime, value, node_id: int = 2) -> dict:
    return {"ts": ts, "kind": "telemetry_sample", "source_collection": "telemetry",
            "summary": "Mẫu", "value": value, "node_id": node_id}


def gap(start: datetime, end: datetime) -> dict:
    return {"ts": start, "kind": "telemetry_gap", "source_collection": "telemetry",
            "gap_start": start, "gap_end": end, "gap_seconds": (end - start).total_seconds(), "missing": True}


def decision(ts: datetime, summary: str) -> dict:
    return {"ts": ts, "kind": "decision", "source_collection": "operational_decisions", "summary": summary}


def cards_by_label(data: dict) -> dict:
    return {c["label"]: c["value"] for c in data["cards"]}


class QualitySeriesTest(unittest.TestCase):
    def setUp(self):
        self.flatline = {"incident_id": "INC-2", "kind": "soil_humidity_flatline", "farm_key": "farm-a",
                         "node_id": 2, "opened_at": T0, "fault_started_at": T0,
                         "observed_fault": {"value": 2.4}}
        self.impact = {"lots_to_review": 2, "missing_sample_gaps": 1, "unreliable_hours": 0.5}

    def test_abnormal_split_by_fault_value_per_minute(self):
        events = [
            sample(T0 + timedelta(seconds=10), 2.4),   # bat thuong: bang gia tri loi
            sample(T0 + timedelta(seconds=40), 3.1),   # hop le
            sample(T0 + timedelta(minutes=1, seconds=5), 3.3),  # hop le, phut ke tiep
        ]
        q = build_impact_chart_data(self.flatline, events, self.impact)["quality"]
        self.assertTrue(q["known"])
        self.assertTrue(q["split_known"])
        self.assertEqual(q["labels"], ["10:00", "10:01"])
        self.assertEqual(q["series"]["abnormal"], [1, 0])
        self.assertEqual(q["series"]["valid"], [1, 1])
        self.assertEqual(q["totals"]["abnormal"], 1)
        self.assertEqual(q["totals"]["valid"], 2)

    def test_unknown_fault_value_gives_none_not_zero(self):
        incident = dict(self.flatline, observed_fault=None)
        q = build_impact_chart_data(incident, [sample(T0, 2.4), gap(T0 + timedelta(minutes=2),
                                                                  T0 + timedelta(minutes=4))],
                                    self.impact)["quality"]
        self.assertFalse(q["split_known"])
        self.assertTrue(all(v is None for v in q["series"]["valid"]))
        self.assertTrue(all(v is None for v in q["series"]["abnormal"]))
        self.assertIsNone(q["totals"]["valid"])
        self.assertIsNone(q["totals"]["abnormal"])
        self.assertEqual(q["totals"]["missing"], 2)  # thieu mau van dem duoc
        self.assertIn("không vẽ số 0 giả", q["note"])

    def test_false_offline_all_samples_valid_with_note(self):
        incident = {"incident_id": "INC-1", "kind": "false_offline", "farm_key": "farm-a", "node_id": 1,
                    "opened_at": T0}
        events = [sample(T0 + timedelta(seconds=30), 2.2), sample(T0 + timedelta(seconds=60), 2.2)]
        q = build_impact_chart_data(incident, events, {})["quality"]
        self.assertTrue(q["split_known"])
        self.assertEqual(q["totals"]["valid"], 2)
        self.assertEqual(q["totals"]["abnormal"], 0)
        self.assertIn(FALSE_OFFLINE_NOTE, q["note"])

    def test_samples_without_value_are_skipped(self):
        events = [sample(T0, None), sample(T0 + timedelta(seconds=5), "abc"), sample(T0 + timedelta(seconds=9), True)]
        q = build_impact_chart_data(self.flatline, events, self.impact)["quality"]
        self.assertEqual(q["labels"], [])
        self.assertEqual(q["totals"]["valid"], 0)

    def test_gap_minutes_counted_and_sorted(self):
        events = [gap(T0 + timedelta(seconds=30), T0 + timedelta(minutes=3)),
                  sample(T0 + timedelta(seconds=10), 3.0)]
        q = build_impact_chart_data(self.flatline, events, self.impact)["quality"]
        # Khoang 10:00:30 -> 10:03:00 cham cac phut 10:00, 10:01, 10:02
        self.assertEqual(q["labels"], ["10:00", "10:01", "10:02"])
        self.assertEqual(q["series"]["missing"], [1, 1, 1])
        self.assertEqual(q["totals"]["missing"], 3)

    def test_unknown_when_no_farm_key(self):
        incident = dict(self.flatline, farm_key=None)
        q = build_impact_chart_data(incident, [sample(T0, 2.4)], self.impact)["quality"]
        self.assertFalse(q["known"])
        self.assertEqual(q["labels"], [])
        self.assertTrue(all(v is None for v in q["totals"].values()))

    def test_handles_none_inputs(self):
        data = build_impact_chart_data(None, None, None)
        self.assertFalse(data["quality"]["known"])
        labels = cards_by_label(data)
        self.assertIsNone(labels["Lô ảnh hưởng"])
        self.assertIsNone(labels["Giờ dữ liệu không đáng tin"])
        self.assertIsNone(labels["Số khoảng thiếu mẫu"])
        self.assertEqual(labels["Đề xuất tưới bị chặn"], 0)


class ImpactCardsTest(unittest.TestCase):
    def setUp(self):
        self.incident = {"incident_id": "INC-2", "kind": "soil_humidity_flatline", "farm_key": "farm-a",
                         "node_id": 2, "opened_at": T0}

    def test_blocked_counts_only_blocked_decisions(self):
        events = [
            decision(T0, "hold: đề xuất HOLD → áp dụng BLOCKED_HOLD"),
            decision(T0 + timedelta(seconds=5), "hold: đề xuất HOLD → áp dụng HOLD"),
            decision(T0 + timedelta(seconds=9), "hold: đề xuất HOLD → áp dụng BLOCKED_HOLD"),
        ]
        data = build_impact_chart_data(self.incident, events, {})
        self.assertEqual(cards_by_label(data)["Đề xuất tưới bị chặn"], 2)

    def test_zero_lots_is_real_zero_and_none_is_unknown(self):
        self.assertEqual(cards_by_label(build_impact_chart_data(self.incident, [], {"lots_to_review": 0}))
                         ["Lô ảnh hưởng"], 0)
        self.assertIsNone(cards_by_label(build_impact_chart_data(self.incident, [], {"lots_to_review": None}))
                          ["Lô ảnh hưởng"])

    def test_hours_and_gaps_from_impact(self):
        impact = {"unreliable_hours": 1.234, "unreliable_basis": "từ lúc đứng số", "unreliable_ongoing": True,
                  "missing_sample_gaps": 3}
        data = build_impact_chart_data(self.incident, [], impact)
        values = cards_by_label(data)
        self.assertEqual(values["Giờ dữ liệu không đáng tin"], 1.23)
        self.assertEqual(values["Số khoảng thiếu mẫu"], 3)
        hours_card = next(c for c in data["cards"] if c["label"] == "Giờ dữ liệu không đáng tin")
        self.assertIn("đang tiếp diễn", hours_card["note"])

    def test_removed_soil_and_milestone_keys(self):
        data = build_impact_chart_data(self.incident, [], {})
        self.assertNotIn("soil_points", data)
        self.assertNotIn("markers", data)
        self.assertNotIn("milestones", data)


if __name__ == "__main__":
    unittest.main()
