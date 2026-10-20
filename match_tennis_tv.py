#!/usr/bin/env python3
"""Conservative EPG vs tennis-match cross-check. Produces review candidates, NOT verified TV broadcasts."""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent


def normalize(value):
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c)).casefold()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def surname(full_name):
    bits = normalize(full_name).split()
    return bits[-1] if bits else ''


def load(path, field):
    data = json.loads((BASE / path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        raise ValueError(f'{path}: expected list in {field}')
    updated = datetime.fromisoformat(data['updatedAt'])
    if updated.tzinfo is None:
        raise ValueError(f'{path}: timestamp without timezone')
    return data, updated.astimezone(timezone.utc)


def main():
    now = datetime.now(timezone.utc)
    tennis, tennis_updated = load('tennis_candidates.json', 'matches')
    epg, epg_updated = load('candidates.json', 'events')
    # If either feed is stale, do not suggest matches at all.
    if any(not now - timedelta(minutes=15) <= t <= now + timedelta(minutes=10)
           for t in (tennis_updated, epg_updated)):
        output = {'updatedAt': now.isoformat(), 'source': 'Tennis API x XMLTV',
                  'warning': 'Stale or future source snapshot: no matches suggested.', 'matches': []}
    else:
        matches = []
        seen = set()
        for match in tennis['matches']:
            if match.get('status') != 'upcoming' or match.get('sport') != 'tenis':
                continue
            try:
                start = datetime.fromisoformat(match['start']).astimezone(timezone.utc)
            except (ValueError, TypeError, KeyError):
                continue
            if start < now or start > now + timedelta(days=7):
                continue
            parts = re.split(r'\s+[–—-]\s+', match.get('name', ''), maxsplit=1)
            if len(parts) != 2:
                continue
            names = [surname(p) for p in parts]
            if any(len(n) < 4 for n in names) or names[0] == names[1]:
                continue
            for listing in epg['events']:
                if listing.get('sport') != 'tenis':
                    continue
                blob = ' ' + normalize(listing.get('name', '') + ' ' + listing.get('description', '')) + ' '
                # BOTH opponents must be explicitly named, not just the tournament or sport.
                if not all(re.search(r'\b' + re.escape(n) + r'\b', blob) for n in names):
                    continue
                try:
                    tv_start = datetime.fromisoformat(listing['start']).astimezone(timezone.utc)
                    tv_end = datetime.fromisoformat(listing['end']).astimezone(timezone.utc)
                except (ValueError, TypeError, KeyError):
                    continue
                if not (tv_start - timedelta(minutes=30) <= start <= tv_end):
                    continue
                key = (str(match.get('id')), str(listing.get('channel')), listing.get('start'))
                if key in seen:
                    continue
                seen.add(key)
                matches.append({'matchId': match.get('id'), 'name': match['name'],
                                'scheduledStart': match['start'], 'tournament': match.get('tournament'),
                                'channel': listing['channel'], 'epgTitle': listing.get('name'),
                                'epgStart': listing['start'], 'epgEnd': listing['end'],
                                'broadcastVerified': False, 'verifiedLive': False,
                                'reason': 'Both player surnames present in EPG and times overlap; manual/independent confirmation still required'})
        output = {'updatedAt': now.isoformat(), 'source': 'Tennis API x XMLTV',
                  'warning': 'Potential matches only; do not publish to events.json automatically.',
                  'matches': sorted(matches, key=lambda x: x['scheduledStart'])}
    (BASE / 'tennis_tv_matches.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Dopasowano {len(output['matches'])} kandydatow TV; transmisje NIE sa potwierdzone.")
    if not output['matches']:
        print('0 wynikow jest prawidlowe, gdy EPG nie wymienia obu zawodnikow lub dane sa nieaktualne.')


if __name__ == '__main__':
    main()
