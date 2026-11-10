import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from update_football import parse, merge, parse_uefa

NOW = datetime(2026, 11, 10, 12, tzinfo=ZoneInfo("Europe/Warsaw"))

def game(id, start, home, away):
    return {"id": id, "date": start, "competitions": [{"competitors": [
        {"team": {"displayName": home, "abbreviation": "POL" if home == "Poland" else "ROM"}},
        {"team": {"displayName": away, "abbreviation": "POL" if away == "Poland" else "SWE"}}]}],
        "status": {"type": {"state": "pre", "completed": False}}, "links": []}

class FootballTests(unittest.TestCase):
    def test_discovers_poland_without_manual_events(self):
        fixtures = [game("1", "2026-11-14T19:45:00Z", "Romania", "Poland"),
                    game("2", "2026-11-17T19:45:00Z", "Poland", "Sweden"),
                    game("3", "2026-11-14T19:45:00Z", "Romania", "Sweden")]
        result = parse([("uefa.nations", fixtures)], NOW)
        self.assertEqual(len(result), 2)
        self.assertEqual([x["start"] for x in result],
                         ["2026-11-14T20:45:00+01:00", "2026-11-17T20:45:00+01:00"])
        self.assertTrue(all(x["sport"] == "pilka" for x in result))
        self.assertTrue(all(x["channel"] is None for x in result))
    def test_uefa_html(self):
        html = '<h3>Saturday 14 November</h3><p>B4 Romania vs Poland</p><h3>Tuesday 17 November</h3><p>B4 Poland vs Sweden</p>'
        rows = parse_uefa(html, NOW)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['start'], '2026-11-14T20:45:00+01:00')
    def test_excludes_youth(self):
        result = parse([("uefa.nations", [game("4", "2026-11-14T19:45:00Z", "Poland U21", "Sweden")])], NOW)
        self.assertEqual(result, [])
    def test_does_not_erase_tennis(self):
        football = parse([("uefa.nations", [game("1", "2026-11-14T19:45:00Z", "Romania", "Poland")])], NOW)
        result = merge([{"sport": "tenis", "start": "2026-11-11T12:00:00+01:00"}], football, NOW)
        self.assertEqual(len(result), 2)

if __name__ == "__main__":
    unittest.main()
