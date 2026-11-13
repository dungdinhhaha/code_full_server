"""Test ham thuan dieu huong cua trang su co (pages/incident.py): tom tat, link Datadog, bang 6 cau hoi.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -v
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pages.incident import (  # noqa: E402
    build_six_questions,
    incident_headline,
    incident_summary,
    mongo_only_events,
    _link_groups,
    SRC_DATADOG,
    SRC_MONGO,
)
from service.incident_blackbox import UNKNOWN  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=UTC)
BITS_UUID = "11111111-2222-3333-4444-555555555555"


class SummaryByKindTest(unittest.TestCase):
    def test_flatline_summary_matches_expected_text_for_node_2(self):
        self.assertEqual(
            incident_summary("soil_humidity_flatline", 2),
            "Cảm biến độ ẩm Node 2 báo một giá trị đứng yên. "
            "Hệ thống đã giữ chế độ an toàn, không tưới, cho đến khi dữ liệu trở lại bình thường.")

    def test_each_known_kind_has_vietnamese_summary(self):
        for kind in ("soil_humidity_flatline", "false_offline", "service_down"):
            text = incident_summary(kind)
            self.assertTrue(text.startswith(incident_headline(kind)))
            self.assertIn("Hệ thống", text)

    def test_unknown_kind_falls_back(self):
        self.assertEqual(incident_headline(None), UNKNOWN)
        self.assertIn("Datadog", incident_summary("unrelated"))


class InvestigationLinksTest(unittest.TestCase):
    """Phan dieu tra tren trang chi dung Monitor, Workflow, Logs, Trace (khong co Bits AI)."""

    def test_page_exposes_no_bits_helpers(self):
        import pages.incident as incident_module
        for name in ("pick_bits_link", "BITS_LIST_URL", "BITS_NO_INVESTIGATION_NOTE"):
            self.assertFalse(hasattr(incident_module, name), name)

    def test_link_groups_only_have_logs_in_investigation_group(self):
        groups = _link_groups({"kind": "service_down", "incident_id": "INC-3", "bits_investigation_id": BITS_UUID})
        labels = [item[0] for item in groups["Nhật ký & điều tra"]]
        self.assertEqual(labels, ["Logs của sự cố"])
        for items in groups.values():
            for _, url, _ in items:
                self.assertNotIn("bits-ai", url)


class SixQuestionsTest(unittest.TestCase):
    def setUp(self):
        self.incident = {"incident_id": "INC-2", "kind": "soil_humidity_flatline", "farm_key": "farm-a",
                         "node_id": 2, "monitor_id": "339977691", "workflow_id": "wf-1",
                         "last_workflow_execution_id": "exec-123456789012345",
                         "detected_at": T0, "evidence": {"trace_ids": ["abcdef1234567890"]}}
        self.timeline = {"events": [], "affected_lots": [{"lot_id": "LOT-A"}], "affected_lots_status": "khớp",
                         "recovery_evidence": {"clear_ts": T0, "samples_after_clear": [{"value": 3.1}],
                                               "verification": "ok"}}

    def test_returns_six_rows_with_four_fields(self):
        rows = build_six_questions(self.incident, self.timeline)
        self.assertEqual(len(rows), 6)
        for row in rows:
            self.assertEqual(set(row), {"question", "answer", "sources", "links"})

    def test_question_one_is_datadog_with_monitor_link(self):
        row = build_six_questions(self.incident, self.timeline)[0]
        self.assertEqual(row["sources"], [SRC_DATADOG])
        self.assertIn("/monitors/339977691", row["links"][0][1])

    def test_question_two_states_monitor_from_datadog(self):
        row = build_six_questions(self.incident, self.timeline)[1]
        self.assertIn("monitor 339977691 (Datadog)", row["answer"])
        self.assertEqual(row["sources"], [SRC_MONGO, SRC_DATADOG])

    def test_question_three_only_links_logs_and_traces(self):
        row = build_six_questions(self.incident, self.timeline)[2]
        self.assertIn("/logs?query=", row["links"][0][1])
        self.assertIn("/apm/trace/", row["links"][1][1])
        self.assertEqual(len(row["links"]), 2)

    def test_question_four_from_mongo_lots(self):
        row = build_six_questions(self.incident, self.timeline)[3]
        self.assertEqual(row["answer"], "LOT-A")
        self.assertEqual(row["sources"], [SRC_MONGO])

    def test_question_five_links_execution(self):
        row = build_six_questions(self.incident, self.timeline)[4]
        self.assertIn("?instance=exec-123456789012345", row["links"][0][1])
        self.assertIn("giữ HOLD", row["answer"])

    def test_missing_data_is_marked_unknown_not_invented(self):
        bare = {"incident_id": "INC-X", "kind": "false_offline"}
        rows = build_six_questions(bare, {"events": [], "affected_lots": [], "affected_lots_status": UNKNOWN,
                                          "recovery_evidence": {}})
        self.assertTrue(rows[1]["answer"].startswith(UNKNOWN))  # chua co detected_at, monitor tu ca 1
        self.assertEqual(rows[3]["answer"], UNKNOWN)
        self.assertEqual(rows[5]["answer"], UNKNOWN)
        self.assertEqual(rows[4]["links"], [])
        self.assertIn("Chưa có trace_id", rows[2]["answer"])


class MongoOnlyEventsTest(unittest.TestCase):
    def test_monitor_detection_milestone_is_hidden(self):
        events = [{"kind": "detected", "ts": T0}, {"kind": "telemetry_sample", "ts": T0},
                  {"kind": "decision", "ts": T0}, {"kind": "action_clear_verified", "ts": T0}]
        kept = [e["kind"] for e in mongo_only_events(events)]
        self.assertEqual(kept, ["telemetry_sample", "decision", "action_clear_verified"])

    def test_none_is_empty(self):
        self.assertEqual(mongo_only_events(None), [])


if __name__ == "__main__":
    unittest.main()
