"""Phuc hoi su co flatline: watchdog chi dong khi verifier (cung cong recovery-clear) dat."""
import json
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, ".")

from service import telemetry_health  # noqa: E402


def _completed(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class FlatlineRecoveryTests(unittest.TestCase):
    def setUp(self):
        telemetry_health._last_recovery_attempt.clear()

    def test_rejects_unstructured_verifier_success_without_correlated_proof(self):
        fake = mock.MagicMock()
        fake.close_flatline_incident.return_value = True
        verifier_out = json.dumps({"result": "cleared", "fresh_normal_samples": 10})
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}), \
                mock.patch.object(telemetry_health.subprocess, "run", return_value=_completed(0, verifier_out)):
            ok = telemetry_health._track_flatline_recovery(
                "greenhouse_a", 2, "smiot_demo_stream", [38.7, 41.3, 39.4], 21.0)
        self.assertFalse(ok)
        fake.close_flatline_incident.assert_not_called()

    def test_accepts_cadence_derived_six_samples_for_five_minute_recovery(self):
        details = {
            "result": "verified_and_cleared",
            "incident_id": "INC-SMIOT-20261111T120000-ABC12345",
            "command_id": "clear-command-1",
            "monitor_state": "OK",
            "virtual_pump_outputs_off": True,
            "simulated": True,
            "fresh_normal_samples": 6,
            "required_samples": 6,
            "sample_span_seconds": 300,
            "stable_seconds": 300,
            "expected_interval_seconds": 60,
            "soil_humidity_range_pct": [38.7, 40.1],
            "sample_freshness_seconds": 10,
            "newest_sample_at": "2026-11-11T12:05:00+00:00",
            "clear_ack": {
                "command_id": "clear-command-1", "action": "CLEAR", "applied": True,
                "verified": True, "safe_mode_active": False, "synthetic": True,
                "timestamp": "2026-11-11T12:05:01+00:00",
                "virtual_output": {f"bit{i}": 0 for i in range(8)},
            },
        }
        self.assertTrue(telemetry_health._valid_flatline_verifier_result(details))

    def test_does_not_close_when_verifier_refuses(self):
        fake = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}), \
                mock.patch.object(telemetry_health.subprocess, "run",
                                  return_value=_completed(1, "", "Refusing to clear HOLD: monitor is ALERT")):
            ok = telemetry_health._track_flatline_recovery("greenhouse_a", 2, "s", [1.0, 2.0], 5.0)
        self.assertFalse(ok)
        fake.close_flatline_incident.assert_not_called()

    def test_throttles_verifier_calls_per_node(self):
        fake = mock.MagicMock()
        fake.close_flatline_incident.return_value = False
        run = mock.MagicMock(return_value=_completed(1, "", "Refusing"))
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}), \
                mock.patch.object(telemetry_health.subprocess, "run", run):
            telemetry_health._track_flatline_recovery("greenhouse_a", 2, "s", [1.0, 2.0], 5.0)
            telemetry_health._track_flatline_recovery("greenhouse_a", 2, "s", [1.0, 2.0], 5.0)
        self.assertEqual(run.call_count, 1)

    def test_out_of_scope_value_error_is_ignored(self):
        fake = mock.MagicMock()
        fake.close_flatline_incident.side_effect = ValueError("scope")
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}), \
                mock.patch.object(telemetry_health.subprocess, "run",
                                  return_value=_completed(0, json.dumps({"result": "cleared"}))):
            self.assertFalse(telemetry_health._track_flatline_recovery(
                "greenhouse_b", 1, "s", [1.0, 2.0], 5.0))

    def test_mongo_error_does_not_raise(self):
        fake = mock.MagicMock()
        fake.close_flatline_incident.side_effect = RuntimeError("down")
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}), \
                mock.patch.object(telemetry_health.subprocess, "run",
                                  return_value=_completed(0, json.dumps({"result": "cleared"}))):
            self.assertFalse(telemetry_health._track_flatline_recovery(
                "greenhouse_a", 2, "s", [1.0, 2.0], 5.0))


if __name__ == "__main__":
    unittest.main()
