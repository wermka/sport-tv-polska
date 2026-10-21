import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from schedule_gate import latest_due, should_refresh

TZ = ZoneInfo("Europe/Warsaw")


def time(day, hour, minute):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


class ScheduleGateTests(unittest.TestCase):
    def test_before_morning_slot_uses_previous_evening(self):
        self.assertEqual(latest_due(time(21, 7, 30)), time(20, 20, 17))

    def test_morning_due(self):
        self.assertEqual(latest_due(time(21, 8, 17)), time(21, 8, 17))
        self.assertTrue(should_refresh(time(21, 8, 20), {"updatedAt":time(20, 22, 45).isoformat()}))
        self.assertFalse(should_refresh(time(21, 9, 53), {"updatedAt":time(21, 8, 32).isoformat()}))

    def test_afternoon_missing_and_late_retry(self):
        self.assertTrue(should_refresh(time(21, 14, 29), {"updatedAt":time(21, 8, 32).isoformat()}))
        self.assertTrue(should_refresh(time(21, 17, 37), {"updatedAt":time(21, 8, 32).isoformat()}))
        self.assertFalse(should_refresh(time(21, 17, 37), {"updatedAt":time(21, 14, 39).isoformat()}))

    def test_evening_due_and_next_day(self):
        self.assertTrue(should_refresh(time(21, 20, 37), {"updatedAt":time(21, 14, 30).isoformat()}))
        self.assertFalse(should_refresh(time(22, 7, 37), {"updatedAt":time(21, 20, 45).isoformat()}))

    def test_malformed_timestamp_starts_refresh(self):
        self.assertTrue(should_refresh(time(21, 14, 37), {}))
        self.assertTrue(should_refresh(time(21, 14, 37), {"updatedAt":"garbage"}))
        self.assertTrue(should_refresh(time(21, 14, 37), {"updatedAt":"2026-10-21T14:50:00"}))

    def test_winter_dst_is_polish_local(self):
        now = datetime(2026, 10, 26, 14, 37, tzinfo=TZ)
        self.assertEqual(latest_due(now), datetime(2026,10,26,14,17,tzinfo=TZ))


if __name__ == "__main__":
    unittest.main()
