"""Kiem tra ham thuan cua giao dien 'Datadog dan dau' (khong can MongoDB, mang hay khoa Datadog that)."""
import json
import os
import socket
import sys
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from components.ui_kit import VN_TZ, dd_reason, dd_state, fmt_time  # noqa: E402
from pages import incident as inc_page  # noqa: E402
from service import datadog_reader as dr  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 11, 6, 4, 0, 0, tzinfo=UTC)
FAKE_KEY = "unit-test-secret-value"


def _incident(**extra):
    base = {"incident_id": "INC-X", "kind": "soil_humidity_flatline", "monitor_id": "111", "farm_key": "greenhouse_a",
            "node_id": 2, "opened_at": T0, "detected_at": T0 + timedelta(seconds=30), "recovered_at": T0 + timedelta(minutes=20)}
    base.update(extra)
    return base


class FakeGet:
    """Thay datadog_reader._get: tra du lieu theo path, hoac nem loi."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, path, params=None):
        self.calls.append(path)
        for prefix, value in self.routes.items():
            if path.startswith(prefix):
                if isinstance(value, BaseException):
                    raise value
                return value
        raise AssertionError(f"unexpected path {path}")


def _http(code):
    return urllib.error.HTTPError("https://x", code, "err", {}, None)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        dr._CACHE.clear()
        dr._OVERVIEW_CACHE.clear()

    def test_full_snapshot_reads_every_part(self):
        routes = {
            "/api/v1/monitor/111": {"overall_state": "OK", "name": "Flatline", "query": "avg(last_5m):x > 1",
                                    "options": {"thresholds": {"critical": 1}}, "overall_state_modified": "2026-11-06T04:26:30+00:00"},
            "/api/v1/query": {"series": [{"pointlist": [[1000.0 * 1000, 1.0], [1060.0 * 1000, 0.0]]}]},
            "/api/v2/events": {"data": [{"attributes": {"timestamp": "2026-11-06T04:14:20Z",
                                                        "attributes": {"title": "[Triggered] flatline"}}}]},
            "/api/v2/logs/events": {"data": [{"attributes": {"timestamp": "2026-11-06T04:15:00Z", "service": "smiot",
                                                             "message": "INC-X opened"}}], "meta": {"page": {"after": "c"}}},
        }
        with mock.patch.object(dr, "_get", FakeGet(routes)):
            snap = dr.read_incident_snapshot(_incident())
        self.assertTrue(snap["available"])
        self.assertEqual(snap["monitor_state"], "OK")
        self.assertEqual(snap["thresholds"], {"critical": 1})
        self.assertEqual(len(snap["events"]), 1)
        self.assertEqual(snap["logs"][0]["service"], "smiot")
        self.assertTrue(snap["logs_more"])
        self.assertEqual(len(snap["series"]), 2)

    def test_monitor_404_keeps_other_parts(self):
        routes = {"/api/v1/monitor/111": _http(404), "/api/v1/query": {"series": []},
                  "/api/v2/events": {"data": []}, "/api/v2/logs/events": {"data": []}}
        with mock.patch.object(dr, "_get", FakeGet(routes)):
            snap = dr.read_incident_snapshot(_incident())
        self.assertFalse(snap["available"])
        self.assertEqual(snap["reason"], "monitor_not_found")
        self.assertEqual(snap["logs"], [])
        self.assertEqual(snap["events"], [])

    def test_403_on_logs_does_not_hide_monitor(self):
        routes = {"/api/v1/monitor/111": {"overall_state": "Alert"}, "/api/v1/query": {"series": []},
                  "/api/v2/events": {"data": []}, "/api/v2/logs/events": _http(403)}
        with mock.patch.object(dr, "_get", FakeGet(routes)):
            snap = dr.read_incident_snapshot(_incident())
        self.assertTrue(snap["available"])
        self.assertEqual(snap["logs_error"], "http_403")
        self.assertNotIn("logs", snap)

    def test_timeout_reason(self):
        routes = {"/api/v1/monitor/111": socket.timeout(), "/api/v1/query": TimeoutError(),
                  "/api/v2/events": urllib.error.URLError(socket.timeout()), "/api/v2/logs/events": OSError("net")}
        with mock.patch.object(dr, "_get", FakeGet(routes)):
            snap = dr.read_incident_snapshot(_incident())
        self.assertEqual(snap["reason"], "timeout")
        self.assertEqual(snap["metric_error"], "timeout")
        self.assertEqual(snap["events_error"], "timeout")
        self.assertEqual(snap["logs_error"], "network")

    def test_keys_missing_is_distinct_and_leaks_nothing(self):
        env = {k: "" for k in ("DD_API_KEY", "DD_APP_KEY", "DATADOG_API_KEY", "DATADOG_APP_KEY")}
        with mock.patch.dict(os.environ, env):
            snap = dr.read_incident_snapshot(_incident())
            overview = dr.read_monitor_overview(["111"])
        self.assertEqual(snap["reason"], "keys_missing")
        self.assertEqual(overview["reason"], "keys_missing")
        self.assertFalse(overview["available"])

    def test_keys_never_in_result(self):
        env = {"DD_API_KEY": FAKE_KEY, "DD_APP_KEY": FAKE_KEY + "2"}
        routes = {"/api/v1/monitor": [{"id": 111, "name": "SMIOT x", "overall_state": "OK"}]}
        with mock.patch.dict(os.environ, env), mock.patch.object(dr, "_get", FakeGet(routes)):
            overview = dr.read_monitor_overview(["111"])
        self.assertNotIn(FAKE_KEY, json.dumps(overview, default=str))

    def test_missing_monitor_id_still_reads_metric_and_logs(self):
        routes = {"/api/v1/query": {"series": [{"pointlist": [[1000000.0, 2.0]]}]}, "/api/v2/logs/events": {"data": []}}
        fake = FakeGet(routes)
        with mock.patch.object(dr, "_get", fake):
            snap = dr.read_incident_snapshot(_incident(monitor_id=None))
        self.assertEqual(snap["reason"], "monitor_id_missing")
        self.assertIn("series", snap)
        self.assertEqual(snap["logs"], [])
        self.assertNotIn("/api/v1/monitor/", " ".join(fake.calls))

    def test_get_is_get_only(self):
        seen = {}

        class Res:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake_open(req, timeout=0):
            seen["method"], seen["timeout"] = req.get_method(), timeout
            return Res()

        with mock.patch.dict(os.environ, {"DD_API_KEY": "a", "DD_APP_KEY": "b"}), \
                mock.patch.object(dr.urllib.request, "urlopen", fake_open):
            dr._get("/api/v1/monitor")
        self.assertEqual(seen["method"], "GET")

    def test_overview_counts_and_missing(self):
        rows = [{"id": 1, "name": "A", "overall_state": "OK"}, {"id": 2, "name": "B", "overall_state": "Alert"},
                {"id": 9, "name": "smiot extra", "overall_state": "Warn"}, {"id": 8, "name": "other", "overall_state": "OK"}]
        out = dr.summarize_monitors(rows, ["1", "2", "3"])
        self.assertEqual(out["counts"]["OK"], 1)
        self.assertEqual(out["counts"]["Alert"], 1)
        self.assertEqual(out["counts"]["Warn"], 1)
        self.assertEqual(out["missing_ids"], ["3"])
        self.assertNotIn("8", out["monitors"])

    def test_parsers_tolerate_garbage(self):
        self.assertEqual(dr.parse_events({"data": [{}, {"attributes": {}}]}), [])
        self.assertEqual(dr.parse_logs(None), {"rows": [], "more": False})


class MessageTableTests(unittest.TestCase):
    def test_reasons_map_to_messages(self):
        for reason, word in (("keys_missing", "chưa cấu hình khóa"), ("monitor_not_found", "không có trong tổ chức"),
                             ("http_403", "không đủ quyền"), ("timeout", "hết thời gian chờ"),
                             ("monitor_id_missing", "chưa ghi")):
            self.assertIn(word, dd_state(reason)[0] + dd_state(reason)[1], reason)
        self.assertEqual(dd_reason("http_500"), "network")
        self.assertEqual(dd_reason("URLError"), "network")


class TimeTests(unittest.TestCase):
    def test_fmt_time_is_fixed_vietnam_time(self):
        self.assertEqual(fmt_time(datetime(2026, 11, 6, 4, 14, 20, tzinfo=UTC)), "11:14:20 06/11")
        self.assertEqual(fmt_time(datetime(2026, 11, 6, 4, 14, 20, tzinfo=UTC), with_date=False), "11:14:20")
        self.assertEqual(VN_TZ.utcoffset(None), timedelta(hours=7))

    def test_recovery_evidence_always_carries_time(self):
        ver = {"monitor_state": "OK", "sample_count": 12, "virtual_pump_outputs_off": True}
        text = inc_page.format_recovery_evidence(ver, "soil_humidity_flatline", T0 + timedelta(minutes=26))
        self.assertIn("Monitor OK lúc xác minh 11:26", text)
        none_time = inc_page.format_recovery_evidence(ver, "soil_humidity_flatline", None)
        self.assertIn("lúc xác minh (chưa ghi giờ)", none_time)


def _rec(values):
    return {"samples_after_clear": [{"differs_from_fault": v} for v in values]}


class VerdictTests(unittest.TestCase):
    def test_samples_contradict(self):
        self.assertTrue(inc_page.samples_contradict(_rec([False, False])))
        self.assertFalse(inc_page.samples_contradict(_rec([False, True])))
        self.assertFalse(inc_page.samples_contradict(_rec([False, None])))
        self.assertFalse(inc_page.samples_contradict(_rec([])))
        self.assertFalse(inc_page.samples_contradict(None))

    def test_cross_check_downgrades_only_ok(self):
        ok = ("ok", inc_page.V_RECOVERED, "x")
        self.assertEqual(inc_page.cross_check_verdict(ok, _rec([False]))[1], inc_page.V_UNVERIFIED)
        self.assertEqual(inc_page.cross_check_verdict(ok, _rec([True])), ok)
        watch = ("watch", inc_page.V_NO_PROOF, "x")
        self.assertEqual(inc_page.cross_check_verdict(watch, _rec([False])), watch)

    def test_case_file_state_downgrades_with_contradicting_samples(self):
        ver = {"verified": True, "monitor_state": "OK", "sample_count": 12, "virtual_pump_outputs_off": True,
               "sample_freshness_seconds": 5}
        inc = _incident(status="recovered", recovery_verification=ver)
        tl = {"incident": inc, "events": [], "recovery_evidence": _rec([False, False])}
        self.assertEqual(inc_page.case_file_state(tl)["verdict"][1], inc_page.V_UNVERIFIED)
        tl["recovery_evidence"] = _rec([True, False])
        self.assertEqual(inc_page.case_file_state(tl)["verdict"][1], inc_page.V_RECOVERED)


class PhaseTests(unittest.TestCase):
    def test_gaps_only_with_two_real_marks(self):
        inc = _incident(fault_started_at=T0 - timedelta(minutes=6, seconds=24), detected_at=T0)
        phases = inc_page.build_phases(inc, ("ok", "x", "y"), [], [], [], None)
        self.assertEqual(phases[0]["line2"], "Sau khi lỗi bắt đầu 6 phút 24 giây")
        self.assertEqual(phases[2]["line2"], "Phục hồi sau 20 phút")
        bare = {"incident_id": "I", "kind": "service_down"}
        phases = inc_page.build_phases(bare, ("watch", "x", "y"), [], [], [], None)
        self.assertIsNone(phases[0]["line2"])
        self.assertIsNone(phases[2]["line2"])
        self.assertIn("chưa ghi", phases[0]["line1"])

    def test_recovery_gap_needs_ok_verdict(self):
        phases = inc_page.build_phases(_incident(), ("stale", "x", "y"), [], [], [], None)
        self.assertIsNone(phases[2]["line2"])

    def test_disposition_label_keeps_unknown_code(self):
        self.assertEqual(inc_page.disposition_label("hold_already_latched_duplicate_suppressed")[1],
                         "hold_already_latched_duplicate_suppressed")
        self.assertEqual(inc_page.disposition_label("brand_new_code"), ("brand_new_code", None))
        self.assertEqual(inc_page.disposition_label(None), (None, None))

    def test_command_explanations(self):
        clear = {"origin": "action_ledger", "label": inc_page.ACTION_LABELS["CLEAR"],
                 "verified_at": T0, "sent_at": T0, "acked_at": T0}
        out = inc_page.command_explanations([clear], [], ("ok", "x", "y"))
        self.assertTrue(any("CLEAR đã xác minh" in line for line in out))
        blocked = [{"source_collection": "operational_decisions", "summary": "BLOCKED_HOLD"}]
        out = inc_page.command_explanations([], blocked, ("watch", "x", "y"))
        self.assertTrue(any("không có lệnh HOLD" in line for line in out))


class ChartTests(unittest.TestCase):
    def test_empty_gives_none_and_never_fake_points(self):
        self.assertIsNone(inc_page.measure_chart_options(_incident(), [], dd=None))
        self.assertIsNone(inc_page.dd_metric_options(_incident(), {"series": []}))

    def test_axis_is_vietnam_time_independent_of_browser(self):
        events = [{"kind": "telemetry_sample", "ts": T0, "value": 40.0}]
        option = inc_page.measure_chart_options(_incident(), events, now=T0 + timedelta(hours=1),
                                                dd={"soil_series": [[T0.timestamp(), 41.0]]})
        self.assertTrue(option["useUTC"])
        mongo, dd = option["series"]
        self.assertEqual(mongo["data"][0][0], int(T0.timestamp() * 1000) + 7 * 3600 * 1000)
        self.assertEqual(dd["data"][0][0], mongo["data"][0][0])
        self.assertEqual(len(option["series"]), 2)

    def test_threshold_line_only_when_api_returns_it(self):
        series = [[T0.timestamp(), 1.0]]
        with_thr = inc_page.dd_metric_options(_incident(), {"series": series, "thresholds": {"critical": 1}})
        names = [m["name"] for m in with_thr["series"][0]["markLine"]["data"]]
        self.assertIn("Ngưỡng critical", names)
        without = inc_page.dd_metric_options(_incident(), {"series": series, "thresholds": {}})
        self.assertNotIn("Ngưỡng critical", [m["name"] for m in without["series"][0]["markLine"]["data"]])


class ListTests(unittest.TestCase):
    def test_nothing_is_hidden(self):
        rows = [{"incident_id": "a", "status": "open"}, {"incident_id": "b", "status": "recovered"},
                {"incident_id": "c", "status": "holding"}, {"incident_id": "d", "status": "closed"}]
        active, closed = inc_page.split_rows(rows)
        self.assertEqual([r["incident_id"] for r in active], ["a", "c"])
        self.assertEqual(len(active) + len(closed), len(rows))

    def test_tabs_use_checked_flags(self):
        inc_page._FLAGS_CACHE.clear()
        now = __import__("time").time()
        inc_page._FLAGS_CACHE["ok"] = (now, {"known": True, "complete": True})
        inc_page._FLAGS_CACHE["gap"] = (now, {"known": True, "complete": False})
        rows = [{"incident_id": "ok"}, {"incident_id": "gap"}, {"incident_id": "new"}]
        self.assertEqual([r["incident_id"] for r in inc_page.tab_rows(rows, "complete")], ["ok"])
        self.assertEqual([r["incident_id"] for r in inc_page.tab_rows(rows, "incomplete")], ["gap"])
        self.assertEqual(len(inc_page.tab_rows(rows, "all")), 3)
        inc_page._FLAGS_CACHE.clear()

    def test_row_verdict_downgrade(self):
        row = {"status": "recovered", "kind": "soil_humidity_flatline",
               "recovery_verification": {"verified": True, "monitor_state": "OK", "sample_count": 12,
                                         "virtual_pump_outputs_off": True, "sample_freshness_seconds": 4}}
        self.assertEqual(inc_page.row_verdict(row)[1], inc_page.V_RECOVERED)
        self.assertEqual(inc_page.row_verdict(row, {"downgrade": True})[1], inc_page.V_UNVERIFIED)


class SourceHygieneTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parents[1]

    def test_no_invented_inverter_points(self):
        html = (self.ROOT / "static" / "test_inverter.html").read_text(encoding="utf-8")
        self.assertNotIn("set: 1.5", html)
        self.assertNotIn("initHistory", html)

    def test_no_hardcoded_datadog_purple_in_pages(self):
        for path in (self.ROOT / "pages").glob("*.py"):
            self.assertNotIn("#632CA6", path.read_text(encoding="utf-8"), path.name)

    def test_no_dict_props_in_changed_pages(self):
        import re
        for name in ("pages/incident.py", "pages/inverter.py", "components/ui_kit.py"):
            text = (self.ROOT / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\.props\(\s*\{", text), name)


if __name__ == "__main__":
    unittest.main()
