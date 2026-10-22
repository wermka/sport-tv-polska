#!/usr/bin/env python3
"""Teleman live-TV candidates for Sport TV Polska. Diagnostic only.

Does NOT modify events.json. No claims that a broadcaster's LIVE badge proves
Polish participation or that an event is actually happening. Respect Teleman's
terms, robots rules and server limits; only enable scheduled collection if permitted.
Python standard library only.
"""
import argparse
import json
import re
import time
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = 'https://www.teleman.pl/sport?live=1'
OUT = Path(__file__).with_name('teleman_review.json')
WARSAW = ZoneInfo('Europe/Warsaw')

class Reader(HTMLParser):
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
                    marker = ' '.join((attrs.get('alt') or '', attrs.get('title') or '')).lower()
                    if 'na żywo' in marker or 'na zywo' in marker:
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

SPORT_PATTERNS = (
    ('tenis', r'\btenis\b|\bwta\b|\batp\b'),
    ('siatkowka', r'siatkówk|siatkowk|volleyball'),
    ('skoki', r'skoki narciarskie|ski jumping'),
    ('lekkoatletyka', r'lekkoatletyk|athletics|diamentowa liga|diamond league|skok o tyczce|rzut młotem|pchnięcie kulą|sztafeta|bieg na \d+\s*m'),
    ('pilka', r'piłka nożna|pilka nozna'),
)
NON_MATCH = re.compile(r'\b(studio|magazyn|skrót|skrot|powtórka|powtorka|retransmisja|podsumowanie)\b', re.I)
# W siatkówce interesują nas wyłącznie reprezentacje Polski, nigdy kluby.
POLAND_TEAM = re.compile(r'\b(polska|poland|reprezentacj[aei] polski)\b', re.I)
VOLLEYBALL_CLUB_CONTEXT = re.compile(
    r'\b(tauron liga|plusliga|liga mistrzów|liga mistrzow|champions league|'
    r'puchar polski|ekstraklasa|liga siatkówki|liga siatkowki|'
    r'liga kobiet|liga mężczyzn|liga mezczyzn)\b', re.I
)

def polish_volleyball_national_team(title):
    """Ostrożny filtr: potrzebne jawne wskazanie Polski jako reprezentacji."""
    if VOLLEYBALL_CLUB_CONTEXT.search(title):
        return False
    return bool(POLAND_TEAM.search(title))

def classify(title):
    low = title.lower()
    if re.search(r'tenis stołowy|tenis stolowy', low) or NON_MATCH.search(title):
        return None
    for sport, pattern in SPORT_PATTERNS:
        if re.search(pattern, low):
            return sport
    return None

def evidence(sport, title, tennis):
    # This is supporting evidence only, not proof of a live, confirmed broadcast.
    if sport == 'pilka':
        return 'national_team_named' if POLAND_TEAM.search(title) else 'not_poland_national_team'
    if sport == 'siatkowka':
        return 'national_team_named' if polish_volleyball_national_team(title) else 'not_poland_national_team'
    if sport == 'tenis':
        norm = title.casefold()
        for match in tennis:
            name = str(match.get('name') or '')
            players = [p.strip() for p in re.split(r'\s+[–-]\s+', name) if p.strip()]
            if len(players) != 2:
                continue
            # Require both surnames, avoid matching only a generic tournament.
            surnames = [p.split()[-1].casefold() for p in players]
            if len(set(surnames)) == 2 and all(re.search(r'(?<!\w)' + re.escape(s) + r'(?!\w)', norm) for s in surnames):
                return 'both_tennis_surnames_named'
        return 'needs_tennis_match_check'
    return 'needs_participant_check'

def load_tennis():
    path = Path(__file__).with_name('tennis_candidates.json')
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data.get('matches', []) if isinstance(data.get('matches'), list) else []
    except (OSError, ValueError, AttributeError):
        return []

def parse_rows(html):
    parser = Reader()
    parser.feed(html)
    return parser.rows

def collect(pages, pause):
    tennis = load_tennis()
    results, seen = [], set()
    for page in range(1, pages + 1):
        url = BASE if page == 1 else f'{BASE}&page={page}'
        req = Request(url, headers={'User-Agent': 'SportTVPolska/1.0 (personal noncommercial EPG diagnostics)'})
        with urlopen(req, timeout=30) as response:
            html = response.read(3_000_000).decode('utf-8', errors='replace')
        rows = parse_rows(html)
        if not rows:
            raise RuntimeError(f'Nie znaleziono tabeli na stronie {page}; przerywam, by nie zapisywać niepełnych danych')
        print(f'Strona {page}/{pages}: {len(rows)} programów')
        for cells in rows:
            date, hour, channel, title = (c[0] for c in cells[:4])
            live = any(c[1] for c in cells)
            sport = classify(title)
            if not live or not sport:
                continue
            # Nie zbieraj siatkówki klubowej ani nieokreślonych spotkań.
            if sport == 'siatkowka' and not polish_volleyball_national_team(title):
                continue
            # W piłce nożnej również wyłącznie reprezentacja Polski.
            if sport == 'pilka' and not POLAND_TEAM.search(title):
                continue
            key = (date, hour, channel, title)
            if key in seen:
                continue
            seen.add(key)
            results.append({
                'dateLabel': date,
                'timeLabel': hour,
                'channel': channel,
                'title': title,
                'sport': sport,
                'telemanLiveBadge': True,
                'participantEvidence': evidence(sport, title, tennis),
                'verified': False,
                'sourceUrl': url,
            })
        if page < pages:
            time.sleep(pause)
    return results


def station_live_tennis(html, day, tennis):
    """Only named LIVE tennis pairings from a dated CANAL+ Sport 2 channel listing."""
    class TextReader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
        def handle_data(self, data):
            if data.strip():
                self.parts.append(data.strip())
    parser = TextReader()
    parser.feed(html)
    text = ' '.join(parser.parts)
    times = list(re.finditer(r'(?<!\d)([01]?\d|2[0-3]):[0-5]\d(?!\d)', text))
    found = []
    months = ['stycznia','lutego','marca','kwietnia','maja','czerwca','lipca','sierpnia','września','października','listopada','grudnia']
    for i, stamp in enumerate(times):
        block = text[stamp.end():times[i+1].start() if i+1<len(times) else len(text)]
        title = re.search(r'(Tenis:\s*.{8,220}?)\s*\|?\s*na\s+żywo\b', block, re.I)
        if not title:
            continue
        name = ' '.join(title.group(1).split())
        if classify(name) != 'tenis' or evidence('tenis', name, tennis) != 'both_tennis_surnames_named':
            continue
        found.append({
            'dateLabel': f'{day.day} {months[day.month-1]}',
            'timeLabel': stamp.group(0),
            'channel': 'CANAL+ Sport 2',
            'title': name, 'sport': 'tenis', 'telemanLiveBadge': True,
            'participantEvidence': 'both_tennis_surnames_named', 'verified': False,
            'sourceUrl': f'https://m.teleman.pl/stations/CanalPlus-Sport-2?date={day.isoformat()}',
        })
    return found


def station_matches(tennis, pause):
    today = datetime.now(WARSAW).date()
    dates = set()
    for match in tennis:
        if match.get('status') != 'upcoming':
            continue
        try:
            day = datetime.fromisoformat(match['start']).astimezone(WARSAW).date()
        except (KeyError, TypeError, ValueError):
            continue
        if today <= day <= today + timedelta(days=2):
            dates.add(day)
    results = []
    for day in sorted(dates):
        url = f'https://m.teleman.pl/stations/CanalPlus-Sport-2?date={day.isoformat()}'
        req = Request(url, headers={'User-Agent': 'SportTVPolska/1.0 (personal noncommercial EPG diagnostics)'})
        try:
            with urlopen(req, timeout=30) as response:
                html = response.read(3_000_000).decode('utf-8', errors='replace')
            results.extend(station_live_tennis(html, day, tennis))
        except Exception as exc:
            print(f'Szczegolowa ramowka CANAL+ Sport 2 niedostepna ({day}): {type(exc).__name__}')
        time.sleep(pause)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=3, help='Liczba stron do sprawdzenia (1-18). Na start 3.')
    parser.add_argument('--pause', type=float, default=2.0, help='Przerwa między zapytaniami')
    args = parser.parse_args()
    if not 1 <= args.pages <= 18 or args.pause < 1:
        parser.error('pages musi wynosić 1-18, pause co najmniej 1 sekundę')
    rows = collect(args.pages, args.pause)
    payload = {
        'updatedAt': datetime.now(WARSAW).isoformat(),
        'source': 'Teleman, zbiorcza ramówka LIVE (dane diagnostyczne)',
        'warning': 'LIVE = oznaczenie w ramówce. Nie potwierdza udziału Polaków ani rzeczywistego terminu zawodów. Nie publikować w events.json.',
        'pagesChecked': args.pages,
        'rows': rows,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Zapisano {len(rows)} kandydatów do {OUT.name}; do events.json nie zapisano nic.')
    from collections import Counter
    print('Dyscypliny:', dict(Counter(row['sport'] for row in rows)))
    print('Wpisy z potencjalnymi polskimi uczestnikami:', sum(row['participantEvidence'] in ('national_team_named', 'both_tennis_surnames_named') for row in rows))

if __name__ == '__main__':
    main()
