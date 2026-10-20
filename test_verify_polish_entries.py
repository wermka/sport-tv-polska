import unittest
from verify_polish_entries import has_polish_athlete, verify

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

if __name__ == "__main__":
    unittest.main()
