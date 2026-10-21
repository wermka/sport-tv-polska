#!/usr/bin/env python3
"""Offline regression tests: fake data only, no network requests."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from verify_tennis_broadcasts import verify, parse_teleman_date, both_named, surnames

NOW = datetime(2026, 10, 20, 19, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
MATCH = {"id": 101, "status": "upcoming", "sport": "tenis",
         "name": "Magda Linette – Claire Liu", "start": "2026-10-21T04:30:00+02:00",
         "polishParticipantConfirmedByApi": True}
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
        self.assertEqual(len(verify([MATCH], [{**TV, "telemanLiveBadge": False}], [EPG], NOW, NOW)), 1)
        self.assertIsNone(verify([MATCH], [{**TV, "telemanLiveBadge": False}], [EPG], NOW, NOW)[0]["channel"])

    def test_different_time(self):
        self.assertIsNone(verify([MATCH], [{**TV, "timeLabel": "19:45"}], [EPG], NOW, NOW)[0]["channel"])

    def test_different_opponent(self):
        self.assertIsNone(verify([MATCH], [{**TV, "title": "Tenis: Claire Liu – Iga Świątek"}], [EPG], NOW, NOW)[0]["channel"])

    def test_removed_or_cancelled(self):
        self.assertEqual(verify([{**MATCH, "status": "cancelled"}], [TV], [EPG], NOW, NOW), [])

    def test_no_tv_listing_creates_planned_match(self):
        rows = verify([MATCH], [], [], NOW, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start"], MATCH["start"])
        self.assertTrue(rows[0]["matchScheduled"])
        self.assertFalse(rows[0]["verifiedLive"])
        self.assertIsNone(rows[0]["channel"])
        self.assertEqual(rows[0]["timeType"], "match_planned")

    def test_missing_country_confirmation_is_not_published(self):
        self.assertEqual(verify([{**MATCH, "polishParticipantConfirmedByApi": False}], [], [], NOW, NOW), [])

    def test_same_api_match_not_duplicated(self):
        self.assertEqual(len(verify([MATCH, MATCH], [], [], NOW, NOW)), 1)

    def test_inflected_kawa_and_bencic_assigns_channel(self):
        match = {**MATCH, "name": "Katarzyna Kawa – Belinda Bencic"}
        tv = {**TV, "title": "Tenis: mecz Katarzyny Kawy i Belindy Bencic"}
        rows = verify([match], [tv], [], NOW, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "CANAL+ Sport 2")
        self.assertTrue(rows[0]["verifiedLive"])

    def test_inflection_does_not_accept_one_surname(self):
        self.assertFalse(both_named("Mecz Katarzyny Kawy", ["kawa", "bencic"]))
        self.assertFalse(both_named("Mecz Belindy Bencic", ["kawa", "bencic"]))

    def test_inflection_does_not_accept_partial_surname(self):
        self.assertFalse(both_named("Kawycz i Bencic", ["kawa", "bencic"]))
        self.assertFalse(both_named("Kawy i Bencicowa", ["kawa", "bencic"]))

    def test_other_polish_inflected_endings(self):
        self.assertTrue(both_named("Mecz Anny Kowalskiej i Jana Kowalskiego", ["kowalska", "kowalski"]))
        self.assertTrue(both_named("Mecz Oli Gizy i Belindy Bencic", ["giza", "bencic"]))

    def test_named_live_match_one_hour_after_api_gets_channel(self):
        match = {**MATCH, "name": "Magda Linette – Katerina Siniakova",
                 "start": "2026-10-22T07:30:00+02:00"}
        tv = {**TV, "title": "Tenis: WTA Osaka: Magda Linette - Kateřina Siniaková",
              "dateLabel": "czwartek, 22 października", "timeLabel": "8:30",
              "channel": "CANAL+ Sport"}
        rows = verify([match], [tv], [], NOW, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "CANAL+ Sport")
        self.assertEqual(rows[0]["start"], "2026-10-22T08:30:00+02:00")
        self.assertEqual(rows[0]["matchScheduledStart"], match["start"])

    def test_too_distant_named_tv_time_is_not_accepted(self):
        tv = {**TV, "timeLabel": "6:10"}
        self.assertIsNone(verify([MATCH], [tv], [], NOW, NOW)[0]["channel"])

    def test_ambiguous_two_channels_does_not_guess(self):
        tv2 = {**TV, "channel": "CANAL+ Sport"}
        self.assertIsNone(verify([MATCH], [TV, tv2], [], NOW, NOW)[0]["channel"])

    def test_night_date(self):
        self.assertEqual(parse_teleman_date("noc wt./śr., 20 na 21 października", "2:25", NOW).day, 21)

if __name__ == "__main__":
    unittest.main()
