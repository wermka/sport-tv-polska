#!/usr/bin/env python3
"""Polish tennis matches from Live Tennis API, NOT verified TV broadcasts.

This intentionally writes only tennis_candidates.json, never events.json.
Missing/cancelled/non-upcoming matches are not shown in the next snapshot.
When the API fails, the script removes the last snapshot rather than leaving
stale matches masquerading as current information.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

API = 'https://api.livetennisapi.com/api/public/v1/matches'
OUTPUT = Path(__file__).with_name('tennis_candidates.json')
WARSAW = ZoneInfo('Europe/Warsaw')
BLOCKED = {'cancelled', 'canceled', 'postponed', 'withdrawn', 'walkover', 'wo', 'retired', 'completed', 'finished', 'live', 'in_progress'}


def fetch_matches(key):
    query = urlencode({'status': 'upcoming', 'country': 'pol', 'limit': 100})
    req = Request(f'{API}?{query}', headers={'X-API-Key': key, 'Accept': 'application/json', 'User-Agent': 'SportTVPolska/1.0'})
    with urlopen(req, timeout=35) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise ValueError('Nieoczekiwana odpowiedź API (brak listy data)')
    return payload['data']


def normalized_status(value):
    if isinstance(value, dict):
        value = value.get('status') or value.get('name') or value.get('type') or ''
    return str(value or '').strip().lower().replace(' ', '_')


def is_minor_itf(match):
    """Exclude ITF circuit fixtures; preserve WTA, ATP and Challenger events."""
    tour = str(match.get('tour') or '').strip().lower()
    tier = str(match.get('tier') or '').strip().lower()
    tournament = str(match.get('tournament') or '').strip().lower()
    if tour == 'itf' or tour.startswith('itf_') or tier.startswith('itf'):
        return True
    # Some API records omit the circuit label while identifying the event as
    # ITF W15/W35/M15/M25 in the tier or tournament name.
    if re.search(r'\b(?:w15|w35|m15|m25)\b', tier + ' ' + tournament):
        return True
    return False


def convert(matches, now):
    rows, seen = [], set()
    for match in matches:
        if not isinstance(match, dict):
            continue
        status = normalized_status(match.get('status'))
        event_status = normalized_status(match.get('event_status'))
        if status != 'upcoming' or event_status in BLOCKED:
            continue
        if is_minor_itf(match):
            continue
        players = match.get('players')
        if not isinstance(players, dict):
            continue
        p1, p2 = players.get('p1'), players.get('p2')
        if not isinstance(p1, dict) or not isinstance(p2, dict):
            continue
        if not any(str(p.get('country') or '').lower() == 'pol' for p in (p1, p2)):
            continue
        stamp = match.get('scheduled_time')
        if not isinstance(stamp, str):
            continue
        try:
            start = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if start.tzinfo is None:
                continue
            start = start.astimezone(timezone.utc)
        except ValueError:
            continue
        if not now <= start < now + timedelta(days=7):
            continue
        mid = match.get('id')
        if mid is None or str(mid) in seen:
            continue
        seen.add(str(mid))
        rows.append({
            'id': mid,
            'start': start.astimezone(WARSAW).isoformat(),
            'sport': 'tenis',
            'name': f"{p1.get('name') or 'Nieznany zawodnik'} – {p2.get('name') or 'Nieznany zawodnik'}",
            'tournament': match.get('tournament'),
            'tour': match.get('tour'),
            'tier': match.get('tier'),
            'doubles': bool(match.get('is_doubles')),
            'status': status,
            'channel': None,
            'broadcastVerified': False,
            'polishParticipantConfirmedByApi': True,
        })
    rows.sort(key=lambda row: row['start'])
    return rows


def save_snapshot(rows, note):
    obj = {
        'updatedAt': datetime.now(WARSAW).isoformat(),
        'source': 'Live Tennis API',
        'note': note,
        'matches': rows,
    }
    tmp = OUTPUT.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(OUTPUT)


def main():
    key = os.environ.get('LIVE_TENNIS_API_KEY')
    if not key:
        raise SystemExit('Brak LIVE_TENNIS_API_KEY w GitHub Secrets')
    try:
        matches = fetch_matches(key)
        rows = convert(matches, datetime.now(timezone.utc))
    except Exception as exc:
        save_snapshot([], 'API niedostępne: brak aktualnie potwierdzonych danych. Nie wyświetlaj starego terminarza.')
        print(f'BŁĄD pobierania API: {type(exc).__name__}: {exc}')
        raise SystemExit(1) from exc
    save_snapshot(rows, 'Zaplanowane mecze z polskim zawodnikiem wedlug aktualnej odpowiedzi API; kanal TV wymaga osobnej weryfikacji.')
    print(f'Zapisano {len(rows)} zaplanowanych meczów z udziałem Polaków do tennis_candidates.json.')
    print('Mecze odwołane/usunięte przez API nie są zachowywane z poprzedniej aktualizacji.')
    print('UWAGA: opóźnienia w aktualizacji statusów przez dostawcę API są nadal możliwe.')


if __name__ == '__main__':
    main()
