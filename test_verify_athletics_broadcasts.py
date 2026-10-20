import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from verify_athletics_broadcasts import verify_athletics

NOW = datetime(2026, 10, 20, 19, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
COMP = {"competitionId":"frankfurt-test","sport":"lekkoatletyka","competitionStart":"2026-10-25T10:00:00+01:00",
        "venue":"Frankfurt","venueAliases":["Frankfurcie"],"name":"Maraton we Frankfurcie","polishParticipantsConfirmed":True,
        "entryListUrl":"https://www.fidal.it/risultati/startlist", "participantsCheckedAt":"2026-10-20T19:00:00+02:00"}
TV = {"sport":"lekkoatletyka","telemanLiveBadge":True,"dateLabel":"niedziela, 25 października",
      "timeLabel":"9:55","title":"Lekkoatletyka: Maraton we Frankfurcie","channel":"TVP Sport"}
EPG = {"sport":"lekkoatletyka","channel":"TVP Sport","name":"Maraton we Frankfurcie",
       "start":"2026-10-25T09:55:00+01:00","end":"2026-10-25T13:00:00+01:00"}

class AthleticsTests(unittest.TestCase):
    def test_all_sources_agree(self):
        rows=verify_athletics([COMP],[TV],[EPG],NOW,NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["start"],"2026-10-25T09:55:00+01:00")
    def test_poland_not_confirmed(self):
        self.assertEqual(verify_athletics([{**COMP,"polishParticipantsConfirmed":False}],[TV],[EPG],NOW,NOW),[])
    def test_epg_other_channel_does_not_provide_end(self):
        rows = verify_athletics([COMP],[TV],[{**EPG,"channel":"Eurosport 2"}],NOW,NOW)
        self.assertEqual(len(rows),1)
        self.assertNotIn("end",rows[0])

    def test_teleman_works_without_epg(self):
        rows = verify_athletics([COMP],[TV],[],NOW,NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["start"],"2026-10-25T09:55:00+01:00")
        self.assertNotIn("end",rows[0])
        self.assertIn("displayUntil",rows[0])
    def test_not_live(self):
        self.assertEqual(verify_athletics([COMP],[{**TV,"telemanLiveBadge":False}],[EPG],NOW,NOW),[])
    def test_other_city(self):
        self.assertEqual(verify_athletics([COMP],[{**TV,"title":"Maraton w Berlinie"}],[EPG],NOW,NOW),[])
    def test_stale_entry_list(self):
        self.assertEqual(verify_athletics([{**COMP,"participantsCheckedAt":"2026-10-18T19:00:00+02:00"}],[TV],[EPG],NOW,NOW),[])

if __name__=="__main__":
    unittest.main()
