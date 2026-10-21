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
        self.assertTrue(should_refresh(time(21, 8, 20), {"updatedAt": time(20, 22, 45).isoformat()}))
        self.assertFalse(should_refresh(time(21, 9, 53), {"updatedAt": time(21, 8, 32).isoformat()}))

    def test_afternoon_missing_and_late_retry(self):
        self.assertEqual(latest_due(time(21, 14, 29)), time(21, 14, 17))
        self.assertTrue(should_refresh(time(21, 14, 29), {"updatedAt": time(21, 8, 32).isoformat()}))
        self.assertFalse(should_refresh(time(21, 14, 39), {"updatedAt": time(21, 14, 36).isoformat()}))

    def test_before_evening_slot_no_extra_refresh(self):
        self.assertEqual(latest_due(time(21, 20, 16)), time(21, 14, 17))
        self.assertFalse(should_refresh(time(21, 20, 16), {"updatedAt": time(21, 14, 36).isoformat()}))

    def test_evening_slot_and_late_retry(self):
        self.assertEqual(latest_due(time(21, 20, 17)), time(21, 20, 17))
        self.assertTrue(should_refresh(time(21, 20, 18), {"updatedAt": time(21, 15, 39).isoformat()}))
        self.assertTrue(should_refresh(time(21, 20, 37), {"updatedAt": time(21, 14, 39).isoformat()}))
        self.assertFalse(should_refresh(time(21, 20, 37), {"updatedAt": time(21, 20, 25).isoformat()}))
        self.assertFalse(should_refresh(time(21, 21, 37), {"updatedAt": time(21, 20, 40).isoformat()}))
        self.assertFalse(should_refresh(time(22, 7, 37), {"updatedAt": time(21, 20, 40).isoformat()}))

    def test_malformed_timestamp_starts_refresh(self):
        self.assertTrue(should_refresh(time(21, 14, 37), {}))
        self.assertTrue(should_refresh(time(21, 14, 37), {"updatedAt": "garbage"}))
        self.assertTrue(should_refresh(time(21, 14, 37), {"updatedAt": "2026-10-21T14:50:00"}))

    def test_winter_dst_is_polish_local(self):
        now = datetime(2026, 10, 26, 20, 18, tzinfo=TZ)
        self.assertEqual(latest_due(now), datetime(2026, 10, 26, 20, 17, tzinfo=TZ))


if __name__ == "__main__":
    unittest.main()
