#!/usr/bin/env python3
"""No network: prove an unseen LIVE ski listing becomes a competition event."""
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from discover_ski import official_article_links, declared_squad_for_date, discover
from verify_ski_broadcasts import verify_ski

NOW = datetime(2026,10,20,19,0,tzinfo=ZoneInfo("Europe/Warsaw"))
URL = "https://pzn.pl/skoki-narciarskie/aktualnosci/nowy-sklad-klingenthal"
NEWS = ('<a href="/skoki-narciarskie/aktualnosci/nowy-sklad-klingenthal">'
        'Trener ogłosił skład na finał sezonu</a>')
ARTICLE = ('<article><p>Ogłosił skład naszej reprezentacji na LGP w Klingenthal '
           '(24-25 października). W Niemczech wystąpią: Kacper Tomasiak, '
           'Paweł Wąsek, Dawid Kubacki i Jakub Wolny.</p></article>')
TV = {"sport":"skoki","telemanLiveBadge":True,
      "dateLabel":"sobota, 24 października","timeLabel":"13:20",
      "title":"Skoki narciarskie: Letnie Grand Prix w Klingenthal",
      "channel":"Eurosport 2"}

class DiscoveryTests(unittest.TestCase):
    def test_official_news_link(self):
        self.assertEqual(official_article_links(NEWS), [URL])

    def test_official_announced_squad_has_names_and_dates(self):
        self.assertGreaterEqual(len(declared_squad_for_date(ARTICLE,"klingenthal",
                                                           datetime(2026,10,24).date())),2)

    def test_other_venue_is_rejected(self):
        self.assertEqual(declared_squad_for_date(ARTICLE,"zakopane",
                                                  datetime(2026,10,24).date()),[])

    def test_other_date_is_rejected(self):
        self.assertEqual(declared_squad_for_date(ARTICLE,"klingenthal",
                                                  datetime(2026,11,24).date()),[])

    def test_no_announcement_no_event(self):
        self.assertEqual(discover([TV],NOW,NEWS,{},NOW),[])

    def test_rerun_does_not_create_candidate(self):
        self.assertEqual(discover([{**TV,"telemanLiveBadge":False}],NOW,NEWS,{URL:ARTICLE},NOW),[])

    def test_new_event_without_manual_competition_list(self):
        candidates=discover([TV],NOW,NEWS,{URL:ARTICLE},NOW)
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0]["participationEvidence"],"official_roster_announced")
        events=verify_ski(candidates,[TV],NOW,NOW,epg=[])
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["start"],"2026-10-24T13:20:00+02:00")
        self.assertNotIn("end",events[0])

if __name__=="__main__":
    unittest.main()
