#!/usr/bin/env python3
"""Sport TV Polska: XMLTV candidates + independently confirmed events.

EPG is a TV broadcast schedule, NOT proof that an event takes place live.
- candidates.json: potential sports broadcasts, deduplicated, NOT user-facing.
- events.json: only events explicitly validated in verified_events.json.

This safe interim pipeline does not pretend to verify real sporting events.
"""
import gzip
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
WARSAW = ZoneInfo('Europe/Warsaw')
CHANNELS = [
    ('canal+ sport 5', 'CANAL+ Sport 5'),
    ('canal+ sport 4', 'CANAL+ Sport 4'),
    ('canal+ sport 3', 'CANAL+ Sport 3'),
    ('canal+ sport 2', 'CANAL+ Sport 2'),
    ('canal+ sport', 'CANAL+ Sport'),
    ('polsat sport 3', 'Polsat Sport 3'),
    ('polsat sport 2', 'Polsat Sport 2'),
    ('polsat sport 1', 'Polsat Sport 1'),
    ('polsat sport', 'Polsat Sport'),
    ('eurosport 2', 'Eurosport 2'),
    ('eurosport 1', 'Eurosport 1'),
    ('tvp sport', 'TVP Sport'),
    ('tvp 1', 'TVP 1'),
    ('tvp 2', 'TVP 2'),
]
SPORTS = {
    'tenis': re.compile(r'\b(tenis|wta|atp|wimbledon|roland garros|australian open|us open)\b', re.I),
    'siatkowka': re.compile(r'\b(siatk[oó]wk\w*|volleyball|liga mistrz[oó]w|plusliga|tauron liga)\b', re.I),
    'pilka': re.compile(r'\b(pi[lł]ka no[zż]na|football|eliminacje|liga narod[oó]w)\b', re.I),
    'skoki': re.compile(r'\b(skoki narciarskie|skoki|ski jumping)\b', re.I),
    'lekkoatletyka': re.compile(r'\b(lekkoatletyka|lekkoatletyczne|athletics|diamentowa liga|diamond league|skok o tyczce|rzut młotem|pchnięcie kulą|sztafeta)\b', re.I),
}
POLISH_TENNIS = re.compile(r'\b([śs]wi[aą]tek|hurkacz|linette|fr[eę]ch|chwali[nń]ska|majchrzak|zieli[nń]ski)\b', re.I)
POLAND = re.compile(r'\b(polska|polski|polacy|polak[oó]w|reprezentacja polski)\b', re.I)
REPLAY = re.compile(r'\b(powt[oó]rka|retransmisja|skr[oó]t|podsumowanie|magazyn|archiwum|replay|highlights)\b', re.I)
NOT_CLASSIC_FOOTBALL = re.compile(r'\b(futsal|pi[lł]ka pla[zż]owa|ekstraklasa|legia|lech pozna[nń]|rak[oó]w|jagiellonia)\b', re.I)
LIVE_HINT = re.compile(r'\b(na [zż]ywo|live|transmisja na [zż]ywo)\b', re.I)


def parse_time(value):
    match = re.match(r'(\d{14})\s*([+-]\d{4})?', value or '')
    if not match:
        return None
    dt = datetime.strptime(match.group(1), '%Y%m%d%H%M%S')
    offset = match.group(2)
    if offset:
        direction = 1 if offset[0] == '+' else -1
        minutes = int(offset[1:3]) * 60 + int(offset[3:])
        dt = dt.replace(tzinfo=timezone(direction * timedelta(minutes=minutes)))
    else:
        dt = dt.replace(tzinfo=WARSAW)
    return dt.astimezone(WARSAW)


def save(name, content):
    (BASE / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def normalize(s):
    return re.sub(r'\s+', ' ', s or '').strip().casefold()


def channel_name(names, channel_id):
    name = names.get(channel_id, '')
    for needle, display in CHANNELS:
        if re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', name):
            return display
    return None


def candidates_from_xml(url, now):
    request = urllib.request.Request(url, headers={'User-Agent': 'SportTVPolska/1.0 (EPG reader)'})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(30_000_001)
    if len(raw) > 30_000_000:
        raise ValueError('EPG too large')
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    root = ET.fromstring(raw)
    if root.tag != 'tv':
        raise ValueError('Not an XMLTV file')
    names = {c.get('id'): ' '.join((e.text or '') for e in c.findall('display-name')).casefold()
             for c in root.findall('channel')}
    dedup = {}
    for p in root.findall('programme'):
        channel = channel_name(names, p.get('channel'))
        if not channel:
            continue
        start, end = parse_time(p.get('start')), parse_time(p.get('stop'))
        if not start or not end or end <= now or start > now + timedelta(days=7):
            continue
        title = ' '.join((e.text or '') for e in p.findall('title')).strip()
        desc = ' '.join((e.text or '') for e in p.findall('desc')).strip()
        blob = title + ' ' + desc
        # Tenis stolowy nie jest tenisem ziemnym i nie trafia do aplikacji.
        if re.search(r'\btenis sto[lł]owy\b|\btable tennis\b', blob, re.I):
            continue
        if REPLAY.search(blob):
            continue
        sport = next((kind for kind, pattern in SPORTS.items() if pattern.search(blob)), None)
        if not sport:
            continue
        if sport == 'siatkowka' and not POLAND.search(blob):
            continue
        if sport == 'pilka' and (NOT_CLASSIC_FOOTBALL.search(blob) or not POLAND.search(blob)):
            continue
        # No inference of Polish athlete participation from place names like Zakopane/Wisła.
        # Ski jumping may list a venue rather than athlete names; verify Polish
        # participation against a separate competition calendar, not EPG text.
        # These entries remain UNVERIFIED candidates until checked independently.
        item = {'start': start.isoformat(), 'end': end.isoformat(), 'sport': sport,
                'name': title, 'channel': channel, 'description': desc[:250],
                'epgSaysLive': bool(LIVE_HINT.search(blob)), 'verifiedLive': False}
        # Deduplicate SD/HD and equivalent entries. Never infer actual event time.
        key = (start.isoformat(), sport, normalize(title), channel)
        dedup[key] = item
    return sorted(dedup.values(), key=lambda e: e['start'])


def validated_events(now):
    """Only manually/independently validated events with explicit evidence.

    verified_events.json is a temporary review interface. Future automated
    official-schedule verification can fill it; no EPG-only claims are promoted.
    """
    path = BASE / 'verified_events.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('verified_events.json must be a JSON list')
    output = []
    required = {'start', 'end', 'sport', 'name', 'channel', 'sourceUrl', 'verifiedLive'}
    for item in data:
        if not isinstance(item, dict) or not required.issubset(item):
            continue
        if item.get('verifiedLive') is not True or not str(item['sourceUrl']).startswith('https://'):
            continue
        if item['sport'] not in SPORTS or item['channel'] not in [n for _, n in CHANNELS]:
            continue
        try:
            start = datetime.fromisoformat(item['start'])
            end = datetime.fromisoformat(item['end'])
            if start.tzinfo is None or end.tzinfo is None:
                continue
        except (ValueError, TypeError):
            continue
        if not (end > now and start <= now + timedelta(days=7) and end > start):
            continue
        output.append({**{key: item[key] for key in required}, **{key: item[key] for key in ("participationEvidence", "participationSourceUrl", "competitionId") if key in item}})
    return sorted(output, key=lambda e: e['start'])


def main(url):
    now = datetime.now(WARSAW)
    candidates = candidates_from_xml(url, now)
    verified = validated_events(now)
    save('candidates.json', {'updatedAt': now.isoformat(), 'source': 'XMLTV; entries unverified', 'events': candidates})
    save('events.json', {'updatedAt': now.isoformat(), 'source': 'Independently verified events only', 'events': verified})
    print(f'EPG candidates: {len(candidates)}; verified events published: {len(verified)}')
    print('EPG candidates are NOT automatically treated as live sporting events.')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: python update_epg.py XMLTV_URL')
    main(sys.argv[1])
