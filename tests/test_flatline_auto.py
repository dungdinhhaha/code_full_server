"""Test mo su co flatline tu dong (khong can Mongo that)."""

import sys
import types
import unittest
from unittest import mock

sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

from service import telemetry_health  # noqa: E402


class FlatlineAutoOpenTests(unittest.TestCase):
    def _fake_lifecycle(self, side_effect=None, return_value="INC-TEST-1"):
        fake = mock.MagicMock()
        fake.start_flatline_incident.side_effect = side_effect
        fake.start_flatline_incident.return_value = return_value
        return fake

    def test_no_action_when_not_flatline(self):
        fake = self._fake_lifecycle()
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}):
            result = telemetry_health._track_flatline_incident("greenhouse_a", 2, False, 0)
        self.assertIsNone(result)
        fake.start_flatline_incident.assert_not_called()

    def test_opens_incident_on_real_flatline_for_node2(self):
        fake = self._fake_lifecycle(return_value="INC-TEST-2")
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}):
            result = telemetry_health._track_flatline_incident("greenhouse_a", 2, True, 10)
        self.assertEqual(result, "INC-TEST-2")
        fake.start_flatline_incident.assert_called_once_with("greenhouse_a", 2)

    def test_out_of_scope_value_error_is_ignored(self):
        fake = self._fake_lifecycle(side_effect=ValueError("scope"))
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}):
            result = telemetry_health._track_flatline_incident("greenhouse_b", 1, True, 10)
        self.assertIsNone(result)

    def test_mongo_error_does_not_raise(self):
        fake = self._fake_lifecycle(side_effect=RuntimeError("mongo down"))
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}):
            result = telemetry_health._track_flatline_incident("greenhouse_a", 2, True, 10)
        self.assertIsNone(result)

    def test_repeated_calls_delegate_dedup_to_lifecycle(self):
        # start_flatline_incident tu tai su dung su co dang mo; ham nay chi goi lai.
        fake = self._fake_lifecycle(return_value="INC-SAME")
        with mock.patch.dict(sys.modules, {"service.incident_lifecycle": fake}):
            first = telemetry_health._track_flatline_incident("greenhouse_a", 2, True, 10)
            second = telemetry_health._track_flatline_incident("greenhouse_a", 2, True, 10)
        self.assertEqual(first, second)
        self.assertEqual(fake.start_flatline_incident.call_count, 2)


if __name__ == "__main__":
    unittest.main()
