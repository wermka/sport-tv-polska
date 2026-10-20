#!/usr/bin/env python3
"""Offline test fixtures; all broadcasts and participants are synthetic."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from verify_ski_broadcasts import verify_ski

NOW = datetime(2026, 10, 20, 20, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
COMP = {
    "competitionId": "test-klingenthal-men", "competitionStart": "2026-10-24T13:35:00+02:00",
    "venue": "Klingenthal", "eventType": "men",
    "name": "Test: skoki mezczyzn", "polishParticipantsConfirmed": True,
    "sourceUrl": "https://example.org/official",
}
TV = {"sport": "skoki", "telemanLiveBadge": True,
      "dateLabel": "sobota, 24 października", "timeLabel": "13:20",
      "title": "Skoki narciarskie: Letnie Grand Prix w Klingenthal",
      "channel": "Eurosport 2"}

class SkiTests(unittest.TestCase):
    def test_tv_start_precedes_competition(self):
        found = verify_ski([COMP], [TV], NOW, NOW)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["start"], "2026-10-24T13:20:00+02:00")
    def test_participation_must_be_confirmed(self):
        self.assertEqual(verify_ski([{**COMP, "polishParticipantsConfirmed": False}], [TV], NOW, NOW), [])
    def test_rerun_not_live(self):
        self.assertEqual(verify_ski([COMP], [{**TV, "telemanLiveBadge": False}], NOW, NOW), [])
    def test_wrong_day(self):
        self.assertEqual(verify_ski([COMP], [{**TV, "dateLabel": "niedziela, 25 października"}], NOW, NOW), [])
    def test_wrong_venue(self):
        self.assertEqual(verify_ski([COMP], [{**TV, "title": "Skoki w Zakopanem"}], NOW, NOW), [])
    def test_late_broadcast_not_accepted(self):
        self.assertEqual(verify_ski([COMP], [{**TV, "timeLabel": "19:00"}], NOW, NOW), [])
    def test_explicit_other_event_type(self):
        self.assertEqual(verify_ski([COMP], [{**TV, "title": "Skoki Klingenthal konkurs kobiet"}], NOW, NOW), [])
    def test_multiple_slots_ambiguous(self):
        also = {**TV, "channel": "TVP Sport"}
        self.assertEqual(verify_ski([COMP], [TV, also], NOW, NOW), [])
    def test_same_competition_already_confirmed(self):
        self.assertEqual(verify_ski([COMP], [TV], NOW, NOW, [{"competitionId": COMP["competitionId"]}]), [])

if __name__ == "__main__":
    unittest.main()
