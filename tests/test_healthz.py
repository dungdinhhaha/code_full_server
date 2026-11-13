"""Unit tests for the /healthz helpers in main.py.

main.py khoi tao DB va MQTT ngay luc import, nen test khong import main.
Thay vao do lay rieng cac ham can thiet bang AST va giả lập dependency
(Mongo, MQTT), nen chay duoc khong can MongoDB hay broker.

Chay: py -3.12 -X utf8 -m unittest discover -s tests -v
"""

import ast
import asyncio
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAIN_PATH = Path(__file__).resolve().parents[1] / "main.py"
WANTED_NAMES = {"build_healthz_payload", "_read_mongo_health", "HEALTHZ_MONGO_TIMEOUT_SECONDS"}
EXPECTED_KEYS = {"app", "mongo", "mqtt", "newest_sample_age_seconds", "time_utc"}


def _load_helpers(database_fn=None, collection_fn=None):
    """Compile only the healthz helpers from main.py, with injected dependencies."""
    tree = ast.parse(MAIN_PATH.read_text(encoding="utf-8"), filename=str(MAIN_PATH))
    body = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in WANTED_NAMES:
            body.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in WANTED_NAMES for t in node.targets
        ):
            body.append(node)
    namespace = {
        "asyncio": asyncio,
        "datetime": datetime,
        "timezone": timezone,
        "database": database_fn,
        "collection": collection_fn,
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), str(MAIN_PATH), "exec"), namespace)
    return namespace


class FakeDatabase:
    def __init__(self, ping_delay=0.0, ping_error=None):
        self.ping_delay = ping_delay
        self.ping_error = ping_error

    def command(self, name):
        if self.ping_delay:
            time.sleep(self.ping_delay)
        if self.ping_error is not None:
            raise self.ping_error
        return {"ok": 1.0}


class FakeCollection:
    def __init__(self, newest):
        self.newest = newest
        self.calls = []

    def find_one(self, filter=None, projection=None, sort=None):
        self.calls.append((filter, projection, sort))
        return {"timestamp": self.newest} if self.newest is not None else None


class BuildHealthzPayloadTests(unittest.TestCase):
    def setUp(self):
        self.helpers = _load_helpers()
        self.build = self.helpers["build_healthz_payload"]
        self.now = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)

    def test_all_ok_payload_has_expected_keys_and_values(self):
        payload = self.build(
            mongo_ok=True,
            mqtt_ok=True,
            newest_sample_at=self.now - timedelta(seconds=30),
            now=self.now,
        )
        self.assertEqual(set(payload), EXPECTED_KEYS)
        self.assertEqual(payload["app"], "ok")
        self.assertEqual(payload["mongo"], "ok")
        self.assertEqual(payload["mqtt"], "ok")
        self.assertEqual(payload["newest_sample_age_seconds"], 30.0)
        self.assertEqual(payload["time_utc"], "2026-11-06T12:00:00+00:00")

    def test_mongo_failure_reported_without_age_and_app_still_ok(self):
        payload = self.build(mongo_ok=False, mqtt_ok=True, newest_sample_at=None, now=self.now)
        self.assertEqual(payload["app"], "ok")
        self.assertEqual(payload["mongo"], "fail")
        self.assertIsNone(payload["newest_sample_age_seconds"])

    def test_mqtt_failure_reported(self):
        payload = self.build(mongo_ok=True, mqtt_ok=False, newest_sample_at=self.now, now=self.now)
        self.assertEqual(payload["mqtt"], "fail")
        self.assertEqual(payload["mongo"], "ok")

    def test_naive_datetimes_are_treated_as_utc(self):
        payload = self.build(
            mongo_ok=True,
            mqtt_ok=True,
            newest_sample_at=datetime(2026, 11, 6, 11, 59, 30),
            now=self.now.replace(tzinfo=None),
        )
        self.assertEqual(payload["newest_sample_age_seconds"], 30.0)

    def test_future_sample_clamped_to_zero(self):
        payload = self.build(
            mongo_ok=True,
            mqtt_ok=True,
            newest_sample_at=self.now + timedelta(seconds=5),
            now=self.now,
        )
        self.assertEqual(payload["newest_sample_age_seconds"], 0.0)

    def test_payload_contains_no_error_text_or_secrets(self):
        payload = self.build(mongo_ok=False, mqtt_ok=False, newest_sample_at=None, now=self.now)
        for value in payload.values():
            self.assertNotIn("mongodb", str(value).lower())
            self.assertNotIn("error", str(value).lower())


class ReadMongoHealthTests(unittest.TestCase):
    def _run(self, coro_fn, **kwargs):
        loop = asyncio.new_event_loop()
        try:
            started = time.monotonic()
            result = loop.run_until_complete(coro_fn(**kwargs))
            elapsed = time.monotonic() - started
        finally:
            loop.close()
        return result, elapsed

    def test_healthy_mongo_returns_newest_timestamp(self):
        newest = datetime(2026, 11, 6, 11, 59, 0)
        collection = FakeCollection(newest)
        helpers = _load_helpers(database_fn=lambda: FakeDatabase(), collection_fn=lambda name: collection)
        (ok, value), _ = self._run(helpers["_read_mongo_health"], timeout=1.0)
        self.assertTrue(ok)
        self.assertEqual(value, newest)
        self.assertEqual(collection.calls[0][2], [("timestamp", -1)])

    def test_empty_collection_is_ok_without_timestamp(self):
        helpers = _load_helpers(database_fn=lambda: FakeDatabase(), collection_fn=lambda name: FakeCollection(None))
        (ok, value), _ = self._run(helpers["_read_mongo_health"], timeout=1.0)
        self.assertTrue(ok)
        self.assertIsNone(value)

    def test_slow_ping_times_out_quickly(self):
        helpers = _load_helpers(
            database_fn=lambda: FakeDatabase(ping_delay=0.5),
            collection_fn=lambda name: FakeCollection(None),
        )
        (ok, value), elapsed = self._run(helpers["_read_mongo_health"], timeout=0.1)
        self.assertFalse(ok)
        self.assertIsNone(value)
        self.assertLess(elapsed, 0.4)

    def test_ping_exception_is_contained(self):
        helpers = _load_helpers(
            database_fn=lambda: FakeDatabase(ping_error=ConnectionError("boom mongodb://secret@host")),
            collection_fn=lambda name: FakeCollection(None),
        )
        (ok, value), _ = self._run(helpers["_read_mongo_health"], timeout=1.0)
        self.assertFalse(ok)
        self.assertIsNone(value)

    def test_missing_mongodb_uri_is_contained(self):
        def no_uri():
            raise RuntimeError("MONGODB_URI is required for MongoDB primary mode")

        helpers = _load_helpers(database_fn=no_uri, collection_fn=lambda name: FakeCollection(None))
        (ok, value), _ = self._run(helpers["_read_mongo_health"], timeout=1.0)
        self.assertFalse(ok)
        self.assertIsNone(value)


if __name__ == "__main__":
    unittest.main()
