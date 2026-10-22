import io
import unittest
from datetime import date

from teleman_importer import station_live_tennis, sport_station_catalog, station_matches

MATCHES = [{'id': 208123, 'status': 'upcoming', 'name': 'Elena Rybakina – Katarzyna Kawa',
            'start': '2026-10-23T13:00:00+02:00'}]
DAY = date(2026, 10, 23)

LIVE = ('<div>13:00 <a>Tenis: WTA Ningbo: '
        'Jelena Rybakina - Katarzyna Kawa | na żywo</a></div>')
REPLAY = '<div>17:30 Tenis: Jelena Rybakina - Katarzyna Kawa</div>'


class ChannelListingsTests(unittest.TestCase):
    def test_named_live_pair_is_found(self):
        html = """<main>
        <div>11:00 <a>Tenis: Iva Jovic - Diana Sznajder | na żywo</a><p>opis</p></div>
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

    def test_name_and_url_follow_the_station_not_a_constant(self):
        rows = station_live_tennis(LIVE, DAY, MATCHES, 'TVP Sport',
                                   'https://m.teleman.pl/stations/TVP-Sport?date=2026-10-23')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['channel'], 'TVP Sport')
        self.assertIn('/TVP-Sport?', rows[0]['sourceUrl'])

    def test_replay_without_live_badge_is_ignored(self):
        self.assertEqual(station_live_tennis(REPLAY, DAY, MATCHES), [])

    def test_one_player_in_programme_description_is_insufficient(self):
        html = ('<div>13:00 Tenis: Jelena Rybakina - Polina Kudiermietowa | na żywo'
                ' <p>W turnieju występuje także Katarzyna Kawa.</p></div>')
        self.assertEqual(station_live_tennis(html, DAY, MATCHES), [])

    def test_other_pair_live_is_ignored(self):
        self.assertEqual(station_live_tennis(
            '<div>13:00 Tenis: Sara Bejlek - Marie Bouzková | na żywo</div>',
            DAY, MATCHES), [])

    def test_catalog_detects_all_sport_stations_only(self):
        html = """<h3>Ogólnotematyczne</h3>
        <a href="/stations/TVP-1">TVP 1</a>
        <h3>Sportowe</h3>
        <a href="/stations/TVP-Sport">TVP Sport</a>
        <a href="/stations/Polsat-Sport-2">Polsat Sport 2</a>
        <a href="/stations/Eurosport-1">Eurosport 1</a>
        <a href="/stations/CanalPlus-Sport-2">CANAL+ Sport 2</a>
        <a href="/stations/Eleven-Sports-1">Eleven Sports 1</a>
        <a href="/stations/TVP-Sport">TVP Sport</a>
        <a href="https://evil.example/stations/Other">Nieprawidlowy link</a>
        <h3>Informacyjne</h3>
        <a href="/stations/TVN-24">TVN 24</a>"""
        found = sport_station_catalog(html)
        self.assertEqual([name for name, _ in found],
                         ['TVP Sport', 'Polsat Sport 2', 'Eurosport 1',
                          'CANAL+ Sport 2', 'Eleven Sports 1'])

    def test_scans_multiple_channels_for_named_live_events(self):
        stations = [('CANAL+ Sport 2', '/stations/CanalPlus-Sport-2'),
                    ('Polsat Sport 2', '/stations/Polsat-Sport-2'),
                    ('TVP Sport', '/stations/TVP-Sport')]
        urls = []
        def opener(req, timeout):
            urls.append(req.full_url)
            html = REPLAY if '/TVP-Sport?' in req.full_url else LIVE
            return io.BytesIO(html.encode('utf-8'))
        rows = station_matches(MATCHES, 0, station_loader=lambda: stations,
                               opener=opener, today=date(2026, 10, 22),
                               sleep_fn=lambda _: None)
        self.assertEqual(len(urls), 3)
        self.assertEqual({r['channel'] for r in rows},
                         {'CANAL+ Sport 2', 'Polsat Sport 2'})
        self.assertTrue(all(r['telemanLiveBadge'] for r in rows))

    def test_no_tennis_no_channel_requests(self):
        self.assertEqual(station_matches([], 0, station_loader=lambda: self.fail('must not load'),
                                         today=date(2026, 10, 22)), [])


if __name__ == '__main__':
    unittest.main()
