import unittest
from datetime import datetime, timezone

from pages import farm_overview_component as overview


def at(hour, minute):
    return datetime(2026, 11, 10, hour, minute, tzinfo=timezone.utc)


WORKFLOW = "Datadog workflow needs operator review because the verification result is still pending " * 3


class NoticeGroupingTests(unittest.TestCase):
    def test_identical_notices_collapse_with_count_and_latest_time(self):
        entries = [("Toàn hệ thống", None, {"message": WORKFLOW, "created_at": at(3, 0)}),
                   ("Toàn hệ thống", None, {"message": WORKFLOW + " ", "created_at": at(7, 5)}),
                   ("Toàn hệ thống", None, {"message": WORKFLOW.upper(), "created_at": at(5, 0)}),
                   ("Nhà màng A", None, {"message": WORKFLOW, "created_at": at(6, 0)}),
                   ("Toàn hệ thống", None, {"message": "Khác", "created_at": at(1, 0)})]
        groups = overview.group_notices(entries)
        self.assertEqual(len(groups), 3)
        top = groups[0]
        self.assertEqual((top["scope"], top["count"]), ("Toàn hệ thống", 3))
        self.assertEqual(top["last_at"], at(7, 5))
        # 07:05 UTC is 14:05 in Vietnam.
        self.assertEqual(overview._repeat_line(top), "x 3 lần, gần nhất 14:05")
        self.assertEqual(groups[1]["scope"], "Nhà màng A")  # same text, other scope stays separate

    def test_single_notice_shows_plain_time(self):
        groups = overview.group_notices([("Nhà màng A", None, {"message": "Một lần", "created_at": at(0, 30)})])
        self.assertEqual(groups[0]["count"], 1)
        self.assertIn("07:30:00", overview._repeat_line(groups[0]))

    def test_pending_groups_by_status_and_does_not_mutate_input(self):
        base = {"farm_key": None, "message": WORKFLOW, "workflow_status": "escalated", "verification_status": "pending"}
        rows = [{**base, "created_at": at(2, 0)}, {**base, "created_at": at(4, 0)},
                {**base, "workflow_status": "pending_verification", "created_at": at(3, 0)}]
        snapshot = [dict(r) for r in rows]
        groups = overview.group_pending(rows)
        self.assertEqual(sorted(g["count"] for g in groups), [1, 2])
        self.assertEqual(rows, snapshot)

    def test_clip_cuts_long_text_and_keeps_short(self):
        self.assertEqual(overview._clip("ngắn"), "ngắn")
        clipped = overview._clip(WORKFLOW, 60)
        self.assertEqual(len(clipped), 60)
        self.assertTrue(clipped.endswith("…"))

    def test_tooltip_formatter_escapes_html_and_breaks_lines(self):
        self.assertIn("&lt;", overview._TIP_FN)
        self.assertIn("split('\\n').join('<br/>')", overview._TIP_FN)
        rows = overview._matrix_rows({
            "level": "ok", "causes": [], "nodes": [{"status": {"status": "ONLINE"}, "sample": None},
                                                    {"status": {"status": "STALE"}, "sample": None}],
            "channels": {k: {"sample": None, "status": {"status": "UNKNOWN"}}
                         for k in ("water", "flow", "drain_sensor", "ventilation_feedback")}})
        self.assertEqual(len(rows), len(overview.MATRIX_COLUMNS))
        self.assertEqual(rows[1][0], "1/2 mới")
        self.assertNotIn("<br", "".join(r[2] for r in rows))


if __name__ == "__main__":
    unittest.main()