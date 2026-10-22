import unittest
from datetime import date
from teleman_importer import station_live_tennis

MATCHES = [{'id': 208123, 'status': 'upcoming', 'name': 'Elena Rybakina – Katarzyna Kawa',
            'start': '2026-10-23T13:00:00+02:00'}]
DAY = date(2026, 10, 23)


class ChannelListingsTests(unittest.TestCase):
    def test_named_live_pair_is_found(self):
        html = """<main>
        <div>11:00 <a>Tenis: Iva Jovic - Diana Sznajder | na żywo</a>
        <p>opis</p></div>
        <div>13:00 <a>Tenis: Turniej WTA w Ningbo mecz ćwierćfinałowy:
        Jelena Rybakina - Katarzyna Kawa | na żywo</a>
        <p>Katarzyna Kawa walczy o półfinał</p></div>
        <div>17:30 <a>Tenis: Jelena Rybakina - Katarzyna Kawa</a></div>
        </main>"""
        rows = station_live_tennis(html, DAY, MATCHES)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['timeLabel'], '13:00')
        self.assertEqual(rows[0]['channel'], 'CANAL+ Sport 2')
        self.assertTrue(rows[0]['telemanLiveBadge'])

    def test_replay_without_live_badge_is_ignored(self):
        self.assertEqual(station_live_tennis(
            '<div>17:30 Tenis: Jelena Rybakina - Katarzyna Kawa</div>', DAY, MATCHES), [])

    def test_one_player_in_programme_description_is_insufficient(self):
        html = ('<div>13:00 Tenis: Jelena Rybakina - Polina Kudiermietowa | na żywo'
                ' <p>W turnieju występuje także Katarzyna Kawa.</p></div>')
        self.assertEqual(station_live_tennis(html, DAY, MATCHES), [])

    def test_other_pair_live_is_ignored(self):
        self.assertEqual(station_live_tennis(
            '<div>13:00 Tenis: Sara Bejlek - Marie Bouzková | na żywo</div>',
            DAY, MATCHES), [])


if __name__ == '__main__':
    unittest.main()
