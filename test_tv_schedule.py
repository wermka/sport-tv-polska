import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from tv_schedule import tv_times, usable_epg_end
from verify_tennis_broadcasts import normalize

START = datetime(2026, 10, 24, 13, 20, tzinfo=ZoneInfo("Europe/Warsaw"))
EPG = {"sport":"skoki", "channel":"Eurosport 2", "name":"Skoki Klingenthal",
       "start":START.isoformat(), "end":(START+timedelta(hours=2)).isoformat()}

class TelemanFirstTests(unittest.TestCase):
    def test_no_epg_does_not_invent_end(self):
        row = tv_times(START)
        self.assertNotIn("end", row)
        self.assertFalse(row["endConfirmedByEpg"])
        self.assertEqual(datetime.fromisoformat(row["displayUntil"]), START+timedelta(hours=4))

    def test_epg_supplies_end(self):
        end = usable_epg_end([EPG], START, "Eurosport 2", "skoki",
                             lambda p: "Klingenthal" in p["name"], normalize)
        row = tv_times(START, end)
        self.assertEqual(row["end"], EPG["end"])
        self.assertNotIn("displayUntil", row)

    def test_wrong_channel_does_not_supply_end(self):
        end = usable_epg_end([EPG], START, "TVP Sport", "skoki",
                             lambda p: True, normalize)
        self.assertIsNone(end)

    def test_multiple_conflicting_end_times_not_used(self):
        other = {**EPG, "end":(START+timedelta(hours=3)).isoformat()}
        end = usable_epg_end([EPG, other], START, "Eurosport 2", "skoki",
                             lambda p: True, normalize)
        self.assertIsNone(end)

if __name__ == "__main__":
    unittest.main()
