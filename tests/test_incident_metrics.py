import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import pages.incident as incident_page
from pages.incident import METRIC_WINDOW_PAD, metric_links, metric_window

OPENED = datetime(2026, 11, 6, 3, 7, 19, tzinfo=timezone.utc)
RECOVERED = datetime(2026, 11, 6, 3, 13, 26, tzinfo=timezone.utc)

# Trang thai Metrics Explorer that Datadog tao ra (doc tu MCP Datadog) cho truy van
# min:systemd.unit.active{unit:smiot.service}; ban sinh lai phai trung tung ky tu.
DATADOG_EXPLORER_HASH = (
    "N4Ig7glgJg5gpgFxALlFOAzCA7CCID22KoATnAI4CucAzgrSgNpoS0AOANgIYCeA+gl7s4KEJxyiANCAwFSAWyo9GyFrPlKeY6nFK8ADCAC+AXRm7SEOszTcE3frQJVSAY1HIQCxFbeMZbG4fHRp9Iwsw3jEFHGRaXno4BSgAOipcBFTuN3wANzhgDLx42IIs2j08iA9jE3MQcg4iSv45RXsxfB9KqxsZel5OT1AJbDhBYU8QZwkoEBkxicgoBAALMWxNbk4FkHYdxARpqAIYfjcVWhqTMxkhES6IHr1rRmNFvhckVBA1uAgMDWPwAjDIVusUGCQAAPKEyaLIEHGD4zLh4ADCRCwMBQ2GUnGMQA"
)


def _ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


class MetricLinksTests(unittest.TestCase):
    def test_each_case_lists_its_own_metrics(self):
        expected = {
            "false_offline": "smiot.telemetry.status_mismatch",
            "soil_humidity_flatline": "smiot.telemetry.sensor_flatline",
            "service_down": "systemd.unit.active",
        }
        for kind, metric in expected.items():
            links = metric_links({"kind": kind, "opened_at": OPENED, "recovered_at": RECOVERED})
            self.assertIn(metric, [label for label, _, _ in links], kind)

    def test_window_pads_open_and_recovery(self):
        start, end = metric_window({"opened_at": OPENED, "recovered_at": RECOVERED})
        self.assertEqual(start, OPENED - METRIC_WINDOW_PAD)
        self.assertEqual(end, RECOVERED + METRIC_WINDOW_PAD)

    def test_explorer_urls_carry_the_incident_time_range(self):
        links = metric_links({"kind": "service_down", "opened_at": OPENED, "recovered_at": RECOVERED})
        start, end = _ms(OPENED - METRIC_WINDOW_PAD), _ms(RECOVERED + METRIC_WINDOW_PAD)
        for _, url, _ in links[:-1]:
            self.assertTrue(url.startswith("https://app.datadoghq.com/metric/explorer?"), url)
            self.assertIn(f"start={start}", url)
            self.assertIn(f"end={end}", url)
            self.assertIn("paused=true", url)
            self.assertIn("#", url)

    def test_explorer_state_matches_what_datadog_generates(self):
        query = "min:systemd.unit.active{unit:smiot.service}"
        generated = incident_page._LZ.compressToEncodedURIComponent(incident_page._explorer_state(query))
        self.assertEqual(generated, DATADOG_EXPLORER_HASH)

    def test_state_in_url_decodes_to_the_metric_query(self):
        links = metric_links({"kind": "false_offline", "opened_at": OPENED, "recovered_at": RECOVERED})
        _, url, _ = links[0]
        state = json.loads(incident_page._LZ.decompressFromEncodedURIComponent(url.split("#", 1)[1]))
        query = state["widget"]["definition"]["requests"][0]["queries"][0]["query"]
        self.assertEqual(query, "max:smiot.telemetry.status_mismatch{*} by {farm,node}")

    def test_falls_back_to_metrics_summary_without_lzstring(self):
        with mock.patch.object(incident_page, "_LZ", None):
            links = metric_links({"kind": "service_down", "opened_at": OPENED, "recovered_at": RECOVERED})
        self.assertEqual(links[0][1], "https://app.datadoghq.com/metric/summary?metric=systemd.unit.active")

    def test_dashboard_link_uses_dashboard_time_params(self):
        links = metric_links({"kind": "false_offline", "opened_at": OPENED, "recovered_at": RECOVERED})
        url = links[-1][1]
        self.assertIn("/dashboard/rzf-su8-zgf", url)
        self.assertIn(f"from_ts={_ms(OPENED - METRIC_WINDOW_PAD)}", url)
        self.assertIn(f"to_ts={_ms(RECOVERED + METRIC_WINDOW_PAD)}", url)
        self.assertIn("live=false", url)

    def test_open_incident_ends_at_now(self):
        now = OPENED + timedelta(minutes=5)
        _, end = metric_window({"opened_at": OPENED}, now=now)
        self.assertEqual(end, now + METRIC_WINDOW_PAD)

    def test_naive_datetimes_are_treated_as_utc(self):
        start, _ = metric_window({"opened_at": OPENED.replace(tzinfo=None), "recovered_at": RECOVERED})
        self.assertEqual(start, OPENED - METRIC_WINDOW_PAD)

    def test_no_links_without_kind_or_open_time(self):
        self.assertEqual(metric_links({"kind": "unknown_kind", "opened_at": OPENED}), [])
        self.assertEqual(metric_links({"kind": "service_down"}), [])
        self.assertEqual(metric_links(None), [])
        self.assertIsNone(metric_window({}))


if __name__ == "__main__":
    unittest.main()
