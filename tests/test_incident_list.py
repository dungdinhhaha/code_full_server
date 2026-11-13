"""Test ham thuan cua trang danh sach su co: gom theo ca, thoi gian xu ly, bo loc."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pages.incident import (  # noqa: E402
    STATE_DONE,
    STATE_OPEN,
    build_list_rows,
    case_runs,
    case_summary_text,
    format_duration,
    run_state,
    scope_label,
)

T0 = datetime(2026, 11, 6, 4, 48, 17, tzinfo=timezone.utc)


def _row(kind, status="recovered", node=2, farm="greenhouse_a", incident_id="INC-SMIOT-20261106T044817-ABCD1234",
         opened=T0, recovered=T0 + timedelta(minutes=6, seconds=39)):
    return {"kind": kind, "status": status, "node_id": node, "farm_key": farm, "incident_id": incident_id,
            "opened_at": opened, "recovered_at": recovered if status == "recovered" else None}


class FormatDurationTests(unittest.TestCase):
    def test_seconds_minutes_hours(self):
        self.assertEqual(format_duration(T0, T0 + timedelta(seconds=45)), "45 giây")
        self.assertEqual(format_duration(T0, T0 + timedelta(minutes=6, seconds=39)), "6 phút 39 giây")
        self.assertEqual(format_duration(T0, T0 + timedelta(minutes=21)), "21 phút")
        self.assertEqual(format_duration(T0, T0 + timedelta(hours=1, minutes=56)), "1 giờ 56 phút")

    def test_missing_or_reversed_is_unknown_not_zero(self):
        self.assertEqual(format_duration(T0, None), "—")
        self.assertEqual(format_duration(None, T0), "—")
        self.assertEqual(format_duration(T0, T0 - timedelta(seconds=1)), "—")


class CaseGroupingTests(unittest.TestCase):
    def test_groups_rows_by_case_keeping_order(self):
        rows = [_row("false_offline"), _row("soil_humidity_flatline", incident_id="A"),
                _row("soil_humidity_flatline", incident_id="B"), _row("service_down", node=None, farm="_system")]
        runs = case_runs(rows)
        self.assertEqual([r["incident_id"] for r in runs[2]], ["A", "B"])
        self.assertEqual(len(runs[1]), 1)
        self.assertEqual(len(runs[3]), 1)

    def test_unknown_kind_is_ignored_and_empty_input_ok(self):
        self.assertEqual(sum(len(v) for v in case_runs([_row("something_else")]).values()), 0)
        self.assertEqual(sum(len(v) for v in case_runs(None).values()), 0)

    def test_summary_text(self):
        self.assertEqual(case_summary_text([]), "Chưa diễn tập")
        runs = [_row("soil_humidity_flatline"), _row("soil_humidity_flatline", status="open")]
        self.assertEqual(case_summary_text(runs), "2 lần diễn tập, 1 đã phục hồi")


class RowTests(unittest.TestCase):
    def test_state_labels(self):
        self.assertEqual(run_state(_row("false_offline")), STATE_DONE)
        for status in ("open", "holding", "recovering"):
            self.assertEqual(run_state(_row("false_offline", status=status)), STATE_OPEN)

    def test_scope_label(self):
        self.assertEqual(scope_label(_row("soil_humidity_flatline")), "greenhouse_a, node 2")
        self.assertEqual(scope_label(_row("service_down", node=None, farm="_system")), "Toàn hệ thống")
        self.assertEqual(scope_label(_row("false_offline", node=None)), "greenhouse_a")

    def test_filter_by_case(self):
        rows = [_row("false_offline", incident_id="X1"), _row("soil_humidity_flatline", incident_id="X2"),
                _row("service_down", incident_id="X3", node=None, farm="_system")]
        self.assertEqual(len(build_list_rows(rows, 0)), 3)
        only2 = build_list_rows(rows, 2)
        self.assertEqual([r["id"] for r in only2], ["X2"])
        self.assertEqual(only2[0]["case"], "Ca 2")
        self.assertEqual(build_list_rows(rows, 9), [])

    def test_row_fields_for_table(self):
        row = build_list_rows([_row("false_offline")], 0)[0]
        self.assertTrue(row["id_short"].startswith("…"))
        self.assertEqual(row["duration"], "6 phút 39 giây")
        self.assertTrue(row["state_ok"])

    def test_open_row_has_no_fake_duration(self):
        row = build_list_rows([_row("false_offline", status="open")], 0)[0]
        self.assertEqual(row["duration"], "—")
        self.assertFalse(row["state_ok"])


if __name__ == "__main__":
    unittest.main()
