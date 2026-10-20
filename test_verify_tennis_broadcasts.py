#!/usr/bin/env python3
"""Offline regression tests: fake data only, no network requests."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from verify_tennis_broadcasts import verify, parse_teleman_date

NOW = datetime(2026, 10, 20, 19, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
MATCH = {"id": 101, "status": "upcoming", "sport": "tenis",
         "name": "Magda Linette – Claire Liu", "start": "2026-10-21T04:30:00+02:00"}
TV = {"dateLabel": "środa, 21 października", "timeLabel": "4:30",
      "channel": "CANAL+ Sport 2", "title": "Tenis: Claire Liu – Magda Linette",
      "sport": "tenis", "telemanLiveBadge": True,
      "sourceUrl": "https://www.teleman.pl/sport?live=1"}
EPG = {"sport": "tenis", "channel": "CANAL+ Sport 2",
       "name": "Claire Liu – Magda Linette", "start": "2026-10-21T04:30:00+02:00",
       "end": "2026-10-21T06:30:00+02:00"}

class CheckVerifiedBroadcasts(unittest.TestCase):
    def test_three_sources_agree(self):
        self.assertEqual(len(verify([MATCH], [TV], [EPG], NOW, NOW)), 1)

    def test_teleman_live_and_api_without_epg(self):
        rows = verify([MATCH], [TV], [], NOW, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start"], "2026-10-21T04:30:00+02:00")
        self.assertNotIn("end", rows[0])
        self.assertIn("displayUntil", rows[0])

    def test_replay_not_live(self):
        self.assertEqual(verify([MATCH], [{**TV, "telemanLiveBadge": False}], [EPG], NOW, NOW), [])

    def test_different_time(self):
        self.assertEqual(verify([MATCH], [{**TV, "timeLabel": "19:45"}], [EPG], NOW, NOW), [])

    def test_different_opponent(self):
        self.assertEqual(verify([MATCH], [{**TV, "title": "Tenis: Claire Liu – Iga Świątek"}], [EPG], NOW, NOW), [])

    def test_removed_or_cancelled(self):
        self.assertEqual(verify([{**MATCH, "status": "cancelled"}], [TV], [EPG], NOW, NOW), [])

    def test_night_date(self):
        self.assertEqual(parse_teleman_date("noc wt./śr., 20 na 21 października", "2:25", NOW).day, 21)

if __name__ == "__main__":
    unittest.main()
