import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pages import farm_overview_component as overview


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *_args):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def __iter__(self):
        return iter(self.rows)


class FakeNotifications:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.projection = None

    def find(self, query, projection):
        self.query = query
        self.projection = projection
        matches = [
            row.copy() for row in self.rows
            if row.get("farm_key") in (None, "") and row.get("source") != "demo_seed"
        ]
        return FakeCursor(matches)


class FarmOverviewNotificationTests(unittest.TestCase):
    def test_unscoped_notices_are_queried_and_kept_as_system_level(self):
        datadog = {
            "source": "datadog_workflow",
            "message": "Workflow needs operator review",
            "created_at": "2026-11-10T04:29:43Z",
            "farm_key": None,
        }
        legacy_unscoped = {
            "source": "system",
            "message": "Maintenance notice",
            "created_at": "2026-11-10T04:00:00Z",
        }
        scoped = {
            "source": "system",
            "message": "Farm sensor needs review",
            "created_at": "2026-11-10T03:00:00Z",
            "farm_key": "greenhouse_a",
        }
        demo = {
            "source": "demo_seed",
            "message": "SMIOT demo: seeded notice",
            "created_at": "2026-11-10T02:00:00Z",
        }
        collection = FakeNotifications([datadog, legacy_unscoped, scoped, demo])
        fake_db = SimpleNamespace(notifications=collection)

        with patch.object(overview, "database", return_value=fake_db):
            notices = overview._aggregate_unscoped_notices()

        self.assertEqual([notice["message"] for notice in notices], [datadog["message"], legacy_unscoped["message"]])
        self.assertEqual(collection.query["farm_key"], {"$in": [None, ""]})
        self.assertEqual(collection.query["source"], {"$ne": "demo_seed"})

        farm_card = {"farm_key": "greenhouse_a", "notices": [scoped]}
        entries = overview._notice_feed_entries(
            [farm_card], {"greenhouse_a": "Nhà màng A"}, notices
        )
        global_entry = next(entry for entry in entries if entry[2]["message"] == datadog["message"])
        farm_entry = next(entry for entry in entries if entry[2]["message"] == scoped["message"])
        self.assertEqual(global_entry[0], "Toàn hệ thống")
        self.assertIsNone(global_entry[1])
        self.assertEqual(farm_entry[0], "Nhà màng A")
        self.assertIs(farm_entry[1], farm_card)


if __name__ == "__main__":
    unittest.main()
