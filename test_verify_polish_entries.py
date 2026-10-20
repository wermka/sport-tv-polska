import unittest
from verify_polish_entries import has_polish_athlete, verify, official_roster_matches

ATHLETES = """<table><tr><th>Rank</th><th>Athlete</th><th>Nation</th></tr>
<tr><td>4</td><td>Anna Wielgosz</td><td>POL</td></tr></table>"""
JUDGES = """<table><tr><th>Jury</th><th>Nat.</th></tr>
<tr><td>Judge A Tomasz Kowalski</td><td>POL</td></tr></table>"""
OTHERS = """<table><tr><th>Athlete</th><th>Nation</th></tr>
<tr><td>Max Mustermann</td><td>GER</td></tr></table>"""

class StartListTests(unittest.TestCase):
    def test_athlete_from_poland(self):
        self.assertTrue(has_polish_athlete(ATHLETES))
    def test_judge_is_not_athlete(self):
        self.assertFalse(has_polish_athlete(JUDGES))
    def test_foreign_only(self):
        self.assertFalse(has_polish_athlete(OTHERS))
    def test_poland_in_free_text_not_accepted(self):
        self.assertFalse(has_polish_athlete("<div>Poland team announced</div>"))
    def test_no_url_keeps_event_unconfirmed(self):
        self.assertFalse(verify([{"competitionId":"test", "polishParticipantsConfirmed":True}])[0]["polishParticipantsConfirmed"])
    def test_official_page_proves_polish_athlete(self):
        rows = verify([{"competitionId":"test", "entryListUrl":"https://www.fis-ski.com/DB/general/results.html?raceid=1"}],
                      downloader=lambda _: ATHLETES)
        self.assertTrue(rows[0]["polishParticipantsConfirmed"])
    def test_non_official_url_rejected(self):
        rows = verify([{"competitionId":"test", "entryListUrl":"https://untrusted.example/scores"}],
                      downloader=lambda _: ATHLETES)
        self.assertFalse(rows[0]["polishParticipantsConfirmed"])
    def test_failed_download_does_not_publish(self):
        def fail(_):
            raise OSError("offline")
        rows = verify([{"competitionId":"test", "entryListUrl":"https://www.fis-ski.com/startlist"}], fail)
        self.assertFalse(rows[0]["polishParticipantsConfirmed"])


    def test_pzn_squad_confirms_before_start_list(self):
        item={"competitionId":"test", "sport":"skoki", "venue":"Klingenthal",
              "rosterUrl":"https://pzn.pl/skoki-narciarskie/aktualnosci/test",
              "rosterNames":["Kacper Tomasiak","Paweł Wąsek","Dawid Kubacki"],
              "rosterMinimumMatches":2}
        html="<article><h1>Kadra na Klingenthal</h1><p>Wystąpią Kacper Tomasiak, Paweł Wąsek i Dawid Kubacki.</p></article>"
        rows=verify([item],downloader=lambda _:html)
        self.assertTrue(rows[0]["polishParticipantsConfirmed"])
        self.assertEqual(rows[0]["participationEvidence"],"official_roster_announced")

    def test_other_venue_does_not_confirm_squad(self):
        item={"sport":"skoki", "venue":"Klingenthal", "rosterNames":["Kacper Tomasiak","Dawid Kubacki"]}
        html="<p>Zakopane: Kacper Tomasiak i Dawid Kubacki.</p>"
        self.assertFalse(official_roster_matches(html,item))

    def test_unofficial_roster_does_not_confirm(self):
        item={"sport":"skoki", "venue":"Klingenthal",
              "rosterUrl":"https://www.fis-ski.com/unrelated",
              "rosterNames":["Kacper Tomasiak","Dawid Kubacki"]}
        html="<p>Klingenthal Kacper Tomasiak i Dawid Kubacki</p>"
        self.assertFalse(verify([item],downloader=lambda _:html)[0]["polishParticipantsConfirmed"])

    def test_start_list_has_priority_over_roster(self):
        item={"sport":"skoki", "venue":"Klingenthal",
              "entryListUrl":"https://www.fis-ski.com/race/123",
              "rosterUrl":"https://pzn.pl/article",
              "rosterNames":["Kacper Tomasiak","Dawid Kubacki"]}
        rows=verify([item],downloader=lambda _:ATHLETES)
        self.assertEqual(rows[0]["participationEvidence"],"official_start_list")

if __name__ == "__main__":
    unittest.main()
