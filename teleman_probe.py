#!/usr/bin/env python3
"""Diagnostyczny odczyt pierwszej strony Teleman: bez publikowania danych.
Uruchomienie: python teleman_probe.py
"""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

URL = 'https://www.teleman.pl/sport?live=1'

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
                    alt = (attrs.get('alt') or '').lower()
                    title = (attrs.get('title') or '').lower()
                    if 'na żywo' in alt or 'na zywo' in alt or 'na żywo' in title:
                        self.cell['live'] = True

    def handle_data(self, data):
        if self.cell is not None:
            self.cell['text'].append(data)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.depth -= 1
            if self.depth == 0:
                cell = self.cell
                self.row.append((' '.join(''.join(cell['text']).split()), cell['live']))
                self.cell = None
        elif tag == 'tr' and self.row is not None:
            if len(self.row) >= 4:
                self.rows.append(self.row)
            self.row = None
            self.cell = None


def main():
    req = Request(URL, headers={'User-Agent': 'Mozilla/5.0 (compatible; personal schedule validation)'})
    try:
        with urlopen(req, timeout=25) as response:
            html = response.read(3_000_000).decode('utf-8', errors='replace')
    except (URLError, HTTPError, TimeoutError) as exc:
        print('Nie udalo sie pobrac strony:', exc)
        raise SystemExit(1)

    parser = TableReader()
    parser.feed(html)
    print('Pobrano strone Teleman (tylko test).')
    print('Wiersze tabeli:', len(parser.rows))
    for cells in parser.rows[:15]:
        date, hour, channel, title = (c[0] for c in cells[:4])
        live = any(c[1] for c in cells)
        print(f'{date} | {hour} | {channel} | {"LIVE" if live else "BRAK OZNACZENIA"} | {title[:110]}')
    if not parser.rows:
        print('Brak wierszy: mozliwa zmiana HTML, blokada dostepu lub strona renderowana dynamicznie.')
        raise SystemExit(2)
    print('UWAGA: etykieta LIVE pochodzi tylko z ramowki; nie potwierdza udzialu Polakow ani terminu zawodow.')

if __name__ == '__main__':
    main()
