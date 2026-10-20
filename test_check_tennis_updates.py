#!/usr/bin/env python3
"""Offline regression checks for tennis monitoring; no live API calls."""
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from check_tennis_updates import eligible, shifted_times

TZ = ZoneInfo("Europe/Warsaw")
NOW = datetime(2026, 10, 20, 14, 0, tzinfo=TZ)
EVENT = {
    "sport": "tenis", "verifiedLive": True,
    "name": "Magda Linette – Claire Liu", "channel": "Canal+ Sport 2",
    "start": "2026-10-20T14:00:00+02:00",
    "end": "2026-10-20T16:30:00+02:00",
    "matchId": "123", "matchScheduledStart": "2026-10-20T14:05:00+02:00",
}

class TennisMonitoringTests(unittest.TestCase):
    def test_eligible_near_match(self):
        self.assertEqual(len(eligible([EVENT], NOW)), 1)

    def test_no_call_far_from_match(self):
        self.assertEqual(eligible([EVENT], NOW - timedelta(hours=2)), [])

    def test_unverified_never_watched(self):
        self.assertEqual(eligible([{**EVENT, "verifiedLive": False}], NOW), [])

    def test_legacy_event_without_id_not_watched(self):
        self.assertEqual(eligible([{k: v for k, v in EVENT.items() if k != "matchId"}], NOW), [])

    def test_confirmed_time_shift(self):
        matches = [{"id": 123, "status": "upcoming", "scheduled_time": "2026-10-20T14:45:00+02:00"}]
        found = shifted_times([EVENT], matches, NOW)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["scheduledStart"], "2026-10-20T14:45:00+02:00")
        self.assertEqual(found[0]["tvStart"], EVENT["start"])

    def test_small_drift_not_a_delay(self):
        matches = [{"id": 123, "status": "upcoming", "scheduled_time": "2026-10-20T14:10:00+02:00"}]
        self.assertEqual(shifted_times([EVENT], matches, NOW), [])

    def test_missing_or_live_match_not_interpreted_as_delay(self):
        self.assertEqual(shifted_times([EVENT], [], NOW), [])
        matches = [{"id": 123, "status": "live", "scheduled_time": "2026-10-20T15:00:00+02:00"}]
        self.assertEqual(shifted_times([EVENT], matches, NOW), [])

    def test_other_match_not_used(self):
        matches = [{"id": 999, "status": "upcoming", "scheduled_time": "2026-10-20T15:00:00+02:00"}]
        self.assertEqual(shifted_times([EVENT], matches, NOW), [])

if __name__ == "__main__":
    unittest.main()
