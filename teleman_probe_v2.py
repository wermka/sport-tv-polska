#!/usr/bin/env python3
"""Test Teleman live, pages 1-3. Diagnostic only; no events.json writes.
Uses standard library. Respect provider terms and robots.txt before production use.
"""
import time
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.request import Request, urlopen

BASE = 'https://www.teleman.pl/sport?live=1'
PAGES = 3

class TableReader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.row = None
        self.cell = None
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr' and self.row is None:
            self.row = []
        elif self.row is not None:
            if tag in ('td', 'th') and self.cell is None:
                self.cell = {'text': [], 'live': False}
                self.depth = 1
            elif self.cell is not None:
                if tag in ('td', 'th'):
                    self.depth += 1
                if tag == 'img':
                    mark = ' '.join((attrs.get('alt') or '', attrs.get('title') or '')).lower()
                    if 'na żywo' in mark or 'na zywo' in mark:
                        self.cell['live'] = True

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'].append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.depth -= 1
            if self.depth == 0:
                self.row.append((' '.join(''.join(self.cell['text']).split()), self.cell['live']))
                self.cell = None
        elif tag == 'tr' and self.row is not None:
            if len(self.row) >= 4:
                self.rows.append(self.row)
            self.row = None
            self.cell = None


def main():
    seen = set()
    all_rows = []
    for page in range(1, PAGES + 1):
        url = BASE if page == 1 else f'{BASE}&page={page}'
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; SportTVPolska diagnostic; low frequency)'})
        try:
            with urlopen(req, timeout=25) as resp:
                html = resp.read(3_000_000).decode('utf-8', errors='replace')
        except Exception as exc:
            print(f'Strona {page}: BLAD pobierania: {exc}')
            raise SystemExit(1)
        parser = TableReader()
        parser.feed(html)
        print(f'Strona {page}: {len(parser.rows)} wierszy')
        if not parser.rows:
            raise SystemExit(f'Brak danych na stronie {page}; możliwa zmiana układu strony')
        for cells in parser.rows:
            date, hour, channel, title = (c[0] for c in cells[:4])
            live = any(c[1] for c in cells)
            k = (date, hour, channel, title)
            if k in seen:
                continue
            seen.add(k)
            all_rows.append((date, hour, channel, title, live))
        if page < PAGES:
            time.sleep(1.5)

    print(f'\nRazem unikalnych pozycji (pierwsze {PAGES} strony): {len(all_rows)}')
    relevant = []
    counts = Counter()
    for date, hour, channel, title, live in all_rows:
        text = title.lower()
        if re.search(r'tenis stołowy|tenis stolowy', text):
            continue
        if re.search(r'\btenis\b|\bwta\b|\batp\b', text):
            sport = 'TENIS'
        elif 'siatkówk' in text or 'siatkowk' in text:
            sport = 'SIATKÓWKA'
        elif 'skoki narciarskie' in text:
            sport = 'SKOKI'
        elif 'piłka nożna' in text or 'pilka nozna' in text:
            sport = 'PIŁKA NOŻNA (do weryfikacji reprezentacji Polski)'
        elif re.search(
            r'lekkoatletyk|athletics|diamentowa liga|diamond league|'
            r'skok o tyczce|rzut młotem|pchnięcie kulą|'
            r'bieg na \d+ m|sztafeta',
            text
        ):
            sport = 'LEKKOATLETYKA'
        else:
            continue
        counts[sport] += 1
        relevant.append((date, hour, channel, title, live, sport))
    print('Wpisy w czterech dyscyplinach (jeszcze bez weryfikacji udziału Polaków):', len(relevant))
    print('Podział:', dict(counts))
    print('\nPierwsze 25 wpisów z interesujących dyscyplin:')
    for date, hour, channel, title, live, sport in relevant[:25]:
        print(f'{date} | {hour} | {channel} | {"LIVE" if live else "BRAK LIVE"} | {sport} | {title[:170]}')
    print('\nUWAGA: TYLKO TEST. Nic nie zostało zapisane do events.json.')

if __name__ == '__main__':
    main()
