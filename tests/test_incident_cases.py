import unittest
from datetime import datetime, timezone

from service.incident_blackbox import CASES, case_for_kind, latest_by_case
from pages.incident import _link_groups


class IncidentCasesTests(unittest.TestCase):
    def test_known_and_unknown_kinds(self):
        for number, case in CASES.items():
            self.assertEqual(case_for_kind(case["kind"]), number)
        self.assertIsNone(case_for_kind("unrelated"))

    def test_latest_by_case_uses_time_not_input_order(self):
        old = {"kind": "service_down", "opened_at": datetime(2026, 11, 1, tzinfo=timezone.utc)}
        new = {"kind": "service_down", "opened_at": datetime(2026, 11, 2, tzinfo=timezone.utc)}
        self.assertIs(latest_by_case([new, old, {"kind": "unknown"}])[3], new)
        self.assertNotIn(1, latest_by_case([new, old]))

    def test_default_links_follow_case(self):
        for number, case in CASES.items():
            groups = _link_groups({"kind": case["kind"]})
            # Keep links evidence-based: candidate incident kinds may not have
            # a real Datadog monitor yet, so the UI omits this group.
            if case.get("monitor_id"):
                self.assertIn("Phát hiện", groups)
                self.assertIn(f"/monitors/{case['monitor_id']}", groups["Phát hiện"][0][1])
            else:
                self.assertNotIn("Phát hiện", groups)
            self.assertIn("/dashboard/rzf-su8-zgf", groups["Hạ tầng"][0][1])
            if case.get("workflow_id"):
                self.assertIn(case["workflow_id"], groups["Hành động"][0][1])


if __name__ == "__main__":
    unittest.main()
