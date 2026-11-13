"""Test ham thuan cho buoc hoan thien trang su co: format_recovery_evidence va chon trace dau tien.

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
    RECOVERY_GENERIC,
    _first_trace_link,
    _trace_links,
    build_six_questions,
    format_recovery_evidence,
)
from service.incident_blackbox import UNKNOWN  # noqa: E402

UTC = timezone.utc
T0 = datetime(2026, 11, 6, 10, 0, 0, tzinfo=UTC)
EXAMPLE = "Monitor OK; 12 mẫu mới, độ ẩm 38,9–40,9%; mẫu mới nhất cách 8 giây; pump ảo đều OFF."
TRACES = [f"trace{i:02d}abcdef0123" for i in range(1, 7)]


class FormatRecoveryEvidenceTest(unittest.TestCase):
    def test_form_a_nested_verifier_dict(self):
        verification = {
            "method": "verified_by_recovery_verifier",
            "verifier": {"monitor_state": "OK", "sample_count": 12,
                         "soil_humidity_range_pct": [38.9, 40.9], "sample_freshness_seconds": 8.1,
                         "virtual_pump_outputs_off": True},
        }
        self.assertEqual(format_recovery_evidence(verification, "soil_humidity_flatline"), EXAMPLE)

    def test_form_b_auto_flatline_method(self):
        verification = {"method": "auto_flatline_recovery_verified", "sample_count": 7,
                        "soil_humidity_range_pct": [39.3, 41.0], "newest_sample_age_seconds": 23.4}
        self.assertEqual(format_recovery_evidence(verification, "soil_humidity_flatline"),
                         "7 mẫu mới, độ ẩm 39,3–41%; mẫu mới nhất cách 23 giây.")

    def test_form_c_false_offline_shows_time_age_and_states(self):
        verification = {"mongo_newest_received_at": "2026-11-06T10:00:05+00:00", "age_s": 3.2,
                        "display_now": "ONLINE", "computed_now": "ONLINE"}
        self.assertEqual(format_recovery_evidence(verification, "false_offline"),
                         "mẫu mới nhất cách 3 giây (17:00:05); UI hiện ONLINE, tính lại ONLINE.")

    def test_form_c_display_states_only_for_false_offline(self):
        verification = {"age_s": 3.2, "display_now": "ONLINE", "computed_now": "ONLINE"}
        self.assertEqual(format_recovery_evidence(verification, "service_down"),
                         "mẫu mới nhất cách 3 giây.")

    def test_form_c_accepts_datetime_value(self):
        verification = {"mongo_newest_received_at": T0, "age_s": 1}
        self.assertEqual(format_recovery_evidence(verification, "false_offline"),
                         "mẫu mới nhất cách 1 giây (17:00:00).")

    def test_form_d_service_down_healthz(self):
        verification = {"http_status": 200, "newest_sample_age_s": 8.1}
        self.assertEqual(format_recovery_evidence(verification, "service_down"),
                         "mẫu mới nhất cách 8 giây; healthz HTTP 200.")

    def test_form_e_direct_verifier(self):
        verification = {"monitor_state": "OK", "sample_count": 12, "soil_humidity_range_pct": [38.9, 40.9],
                        "sample_freshness_seconds": 8, "virtual_pump_outputs_off": True}
        self.assertEqual(format_recovery_evidence(verification, "soil_humidity_flatline"), EXAMPLE)

    def test_pump_not_off_is_stated_plainly(self):
        text = format_recovery_evidence({"sample_count": 2, "virtual_pump_outputs_off": False}, None)
        self.assertEqual(text, "2 mẫu mới; pump ảo chưa đều OFF.")

    def test_range_without_count_and_invalid_range_is_skipped(self):
        self.assertEqual(format_recovery_evidence({"soil_humidity_range_pct": [38.9, 40]}, None),
                         "độ ẩm 38,9–40%.")
        self.assertEqual(format_recovery_evidence({"sample_count": 3, "soil_humidity_range_pct": ["x", 2]}, None),
                         "3 mẫu mới.")
        self.assertEqual(format_recovery_evidence({"sample_count": 3,
                                                   "soil_humidity_range_pct": [float("nan"), 2]}, None),
                         "3 mẫu mới.")

    def test_unknown_shape_gives_generic_text_never_raw_dict(self):
        for verification in ({"foo": 1}, {}, {"verifier": {"unrelated": True}}, "ok", ["x"], 42):
            text = format_recovery_evidence(verification, "soil_humidity_flatline")
            self.assertEqual(text, RECOVERY_GENERIC)
            self.assertNotIn("{", text)
            self.assertNotIn("'", text)

    def test_missing_value_is_unknown(self):
        self.assertEqual(format_recovery_evidence(None, None), UNKNOWN)
        self.assertEqual(format_recovery_evidence("", None), UNKNOWN)

    def test_no_invented_numbers_for_missing_fields(self):
        text = format_recovery_evidence({"monitor_state": "OK"}, "soil_humidity_flatline")
        self.assertEqual(text, "Monitor OK.")
        self.assertNotIn("mẫu", text)
        self.assertNotIn("%", text)

    def test_bool_is_not_a_count(self):
        self.assertEqual(format_recovery_evidence({"sample_count": True}, None), RECOVERY_GENERIC)

    def test_six_questions_row_six_uses_formatted_text(self):
        incident = {"incident_id": "INC-2", "kind": "soil_humidity_flatline", "detected_at": T0}
        timeline = {"events": [], "affected_lots": [], "affected_lots_status": UNKNOWN,
                    "recovery_evidence": {"clear_ts": T0, "samples_after_clear": [],
                                          "verification": {"monitor_state": "OK", "sample_count": 12,
                                                           "soil_humidity_range_pct": [38.9, 40.9],
                                                           "sample_freshness_seconds": 8,
                                                           "virtual_pump_outputs_off": True}}}
        answer = build_six_questions(incident, timeline)[5]["answer"]
        self.assertIn(EXAMPLE, answer)
        self.assertNotIn("{", answer)


class FirstTraceTest(unittest.TestCase):
    def setUp(self):
        self.incident = {"incident_id": "INC-2", "kind": "soil_humidity_flatline",
                         "evidence": {"trace_ids": TRACES}}

    def test_first_trace_is_the_only_trace_button(self):
        links = _first_trace_link(self.incident)
        self.assertEqual(len(links), 1)
        label, url, tip = links[0]
        self.assertEqual(label, "Trace")
        self.assertEqual(tip, TRACES[0])
        self.assertTrue(url.endswith(f"/apm/trace/{TRACES[0]}"))

    def test_no_trace_gives_no_link(self):
        self.assertEqual(_first_trace_link({"evidence": {"trace_ids": []}}), [])
        self.assertEqual(_first_trace_link({}), [])

    def test_full_trace_list_is_kept_for_expansion(self):
        links = _trace_links(self.incident)
        self.assertEqual(len(links), 6)
        self.assertEqual([tip for _, _, tip in links], TRACES)

    def test_question_three_has_logs_and_first_trace_only(self):
        incident = {"incident_id": "INC-2", "kind": "soil_humidity_flatline", "evidence": {"trace_ids": TRACES}}
        timeline = {"events": [], "affected_lots": [], "affected_lots_status": UNKNOWN, "recovery_evidence": {}}
        links = build_six_questions(incident, timeline)[2]["links"]
        self.assertEqual(len(links), 2)
        self.assertIn("/logs?query=", links[0][1])
        self.assertTrue(links[1][1].endswith(f"/apm/trace/{TRACES[0]}"))


if __name__ == "__main__":
    unittest.main()
