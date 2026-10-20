import unittest
from datetime import datetime, timezone
from update_tennis import convert, is_minor_itf

NOW = datetime(2026, 10, 20, 18, tzinfo=timezone.utc)

def match(mid, tour, tier=None, tournament="Example"):
    return {
        "id": mid, "status": "upcoming", "scheduled_time": "2026-10-22T12:00:00Z",
        "tour": tour, "tier": tier, "tournament": tournament,
        "players": {
            "p1": {"name": "Magda Linette", "country": "pol"},
            "p2": {"name": "Test Opponent", "country": "cze"},
        },
    }

class TennisLevelTests(unittest.TestCase):
    def test_itf_low_levels_are_filtered(self):
        for idx, tier in enumerate(("itf_w15", "itf_w35", "itf_m15", "itf_m25"), 1):
            with self.subTest(tier=tier):
                self.assertEqual(convert([match(idx, "itf", tier)], NOW), [])

    def test_other_itf_levels_are_filtered(self):
        self.assertEqual(convert([match(5, "itf", "itf_w75")], NOW), [])

    def test_tier_detects_itf_when_tour_missing(self):
        self.assertTrue(is_minor_itf(match(6, "", "itf_m25")))
        self.assertEqual(convert([match(6, "", None, "ITF W15 Karlovy Vary")], NOW), [])

    def test_wta_atp_and_challenger_remain(self):
        rows = convert([
            match(7, "wta", None, "Osaka"),
            match(8, "atp", None, "Paris"),
            match(9, "challenger", None, "Brest"),
        ], NOW)
        self.assertEqual({row["id"] for row in rows}, {7, 8, 9})

    def test_polish_participant_still_required(self):
        item = match(10, "wta", None, "Osaka")
        item["players"]["p1"]["country"] = "usa"
        self.assertEqual(convert([item], NOW), [])

if __name__ == "__main__":
    unittest.main()
