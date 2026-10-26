#!/usr/bin/env python3
"""Offline regression tests: fake data only, no network requests."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from verify_tennis_broadcasts import verify, parse_teleman_date, both_named, surnames, preserve_recent_started

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
        rows = verify([MATCH], [TV], [EPG], NOW, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start"], MATCH["start"])
        self.assertEqual(rows[0]["tvStart"], TV["dateLabel"] and MATCH["start"])
        self.assertEqual(rows[0]["tvEnd"], EPG["end"])

    def test_teleman_live_and_api_without_epg(self):
        rows = verify([MATCH], [TV], [], NOW, NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start"], "2026-10-21T04:30:00+02:00")
        self.assertNotIn("end", rows[0])
        self.assertIn("displayUntil", rows[0])
        self.assertEqual(rows[0]["tvStart"], MATCH["start"])

    def test_replay_not_live(self):
        self.assertEqual(len(verify([MATCH], [{**TV, "telemanLiveBadge": False}], [EPG], NOW, NOW)), 1)
        self.assertIsNone(verify([MATCH], [{**TV, "telemanLiveBadge": False}], [EPG], NOW, NOW)[0]["channel"])

    def test_different_time(self):
        self.assertIsNone(verify([MATCH], [{**TV, "timeLabel": "19:45"}], [EPG], NOW, NOW)[0]["channel"])

    def test_different_opponent(self):
        self.assertIsNone(verify([MATCH], [{**TV, "title": "Tenis: Claire Liu – Iga Świątek"}], [EPG], NOW, NOW)[0]["channel"])

    def test_removed_or_cancelled(self):
        self.assertEqual(verify([{**MATCH, "status": "cancelled"}], [TV], [EPG], NOW, NOW), [])

    def test_tournament_name_is_preserved_without_tv(self):
        match = {**MATCH, "tournament": "Wimbledon", "tour": "wta"}
        event = verify([match], [], [], NOW, NOW)[0]
        self.assertEqual(event["tournament"], "Wimbledon")
        self.assertIsNone(event["channel"])

    def test_tournament_name_is_preserved_with_verified_tv(self):
        match = {**MATCH, "tournament": "US Open", "tour": "wta"}
        event = verify([match], [TV], [], NOW, NOW)[0]
        self.assertEqual(event["tournament"], "US Open")
        self.assertEqual(event["channel"], "CANAL+ Sport 2")

    def test_missing_tournament_does_not_invent_one(self):
        event = verify([MATCH], [], [], NOW, NOW)[0]
        self.assertIsNone(event["tournament"])

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
        self.assertEqual(rows[0]["start"], "2026-10-22T07:30:00+02:00")
        self.assertEqual(rows[0]["tvStart"], "2026-10-22T08:30:00+02:00")
        self.assertEqual(rows[0]["timeType"], "match_planned")
        self.assertEqual(rows[0]["matchScheduledStart"], match["start"])

    def test_too_distant_named_tv_time_is_not_accepted(self):
        tv = {**TV, "timeLabel": "6:10"}
        self.assertIsNone(verify([MATCH], [tv], [], NOW, NOW)[0]["channel"])

    def test_ambiguous_two_channels_does_not_guess(self):
        tv2 = {**TV, "channel": "CANAL+ Sport"}
        self.assertIsNone(verify([MATCH], [TV, tv2], [], NOW, NOW)[0]["channel"])

    def test_keep_recent_started_but_missing_from_upcoming_feed(self):
        previous = [{"sport": "tenis", "matchId": "207303", "matchScheduled": True,
                     "matchScheduledStart": "2026-10-22T08:45:00+02:00",
                     "start": "2026-10-22T08:45:00+02:00", "name": "Kawa – Bencic",
                     "channel": None, "verifiedLive": False,
                     "displayUntil": "2026-10-22T12:45:00+02:00"}]
        now = datetime(2026, 10, 22, 9, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        rows = preserve_recent_started(previous, [], now)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["statusUnconfirmedAfterStart"])
        self.assertEqual(rows[0]["displayUntil"], "2026-10-22T12:45:00+02:00")
        later = datetime(2026, 10, 22, 12, 45, tzinfo=now.tzinfo)
        self.assertEqual(preserve_recent_started(previous, [], later), [])

    def test_no_retention_before_start_or_for_cancelled(self):
        previous = [{"sport": "tenis", "matchId": "1", "matchScheduled": True,
                     "matchScheduledStart": "2026-10-22T08:45:00+02:00"}]
        early = datetime(2026, 10, 22, 8, 40, tzinfo=ZoneInfo("Europe/Warsaw"))
        later = datetime(2026, 10, 22, 9, 0, tzinfo=early.tzinfo)
        self.assertEqual(preserve_recent_started(previous, [], early), [])
        self.assertEqual(preserve_recent_started(previous, [], later, {"1": "cancelled"}), [])
        self.assertEqual(preserve_recent_started(previous, [], later, {"1": "finished"}), [])

    def test_no_retention_when_fresh_fixture_exists(self):
        previous = [{"sport": "tenis", "matchId": "1", "matchScheduled": True,
                     "matchScheduledStart": "2026-10-22T08:45:00+02:00"}]
        now = datetime(2026, 10, 22, 9, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        self.assertEqual(preserve_recent_started(previous, [{"matchId": "1"}], now), [])

    def test_night_date(self):
        self.assertEqual(parse_teleman_date("noc wt./śr., 20 na 21 października", "2:25", NOW).day, 21)

if __name__ == "__main__":
    unittest.main()
