"""attach_monitor_and_workflow khong duoc ghi de gio phat hien da co."""
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, ".")
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

import service  # noqa: E402

il = None
_PRESENT_BEFORE = "service.incident_lifecycle" in sys.modules


def setUpModule():
    # Import o day (khong o dau file) de cac test test_flatline_* van patch duoc sys.modules.
    global il
    from service import incident_lifecycle as _il  # noqa: E402
    il = _il


def tearDownModule():
    if not _PRESENT_BEFORE:
        if hasattr(service, "incident_lifecycle"):
            delattr(service, "incident_lifecycle")
        sys.modules.pop("service.incident_lifecycle", None)


OPENED = datetime(2026, 11, 6, 3, 7, 19, tzinfo=timezone.utc)


def _coll(existing):
    c = mock.MagicMock()
    c.find_one.return_value = existing
    return c


class AttachDetectedAtTests(unittest.TestCase):
    def _set_fields(self, coll):
        return coll.update_one.call_args.args[1]["$set"]

    def test_keeps_existing_detected_at(self):
        coll = _coll({"detected_at": OPENED})
        with mock.patch.object(il, "collection", return_value=coll):
            il.attach_monitor_and_workflow("INC-1", monitor_id="1", workflow_id="w", execution_id="e")
        self.assertNotIn("detected_at", self._set_fields(coll))
        self.assertEqual(self._set_fields(coll)["monitor_id"], "1")

    def test_sets_detected_at_when_missing(self):
        coll = _coll({"detected_at": None})
        with mock.patch.object(il, "collection", return_value=coll):
            il.attach_monitor_and_workflow("INC-1", monitor_id="1")
        self.assertIsInstance(self._set_fields(coll)["detected_at"], datetime)

    def test_explicit_trigger_time_wins(self):
        coll = _coll({"detected_at": OPENED})
        trig = datetime(2026, 11, 6, 3, 11, 43, tzinfo=timezone.utc)
        with mock.patch.object(il, "collection", return_value=coll):
            il.attach_monitor_and_workflow("INC-1", monitor_id="1", triggered_at=trig)
        self.assertEqual(self._set_fields(coll)["detected_at"], trig)


if __name__ == "__main__":
    unittest.main()
