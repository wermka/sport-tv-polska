#!/usr/bin/env python3
"""Automatically discover Poland senior national-team fixtures from ESPN schedules.

Never add a match by hand. TV broadcasts are only marked verified when a
matching live Teleman listing is available. No club or youth matches.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Warsaw")
LEAGUES = ("uefa.nations", "fifa.worldq.uefa", "fifa.friendly", "fifa.world")
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
POLAND = {"poland", "polska"}
EXCLUDE = re.compile(r"\b(u[- ]?\d{2}|under[- ]?\d{2}|youth|junior|futsal|beach)\b", re.I)

def fetch(league, start, end):
    url = f"{BASE}/{league}/scoreboard?dates={start:%Y%m%d}-{end:%Y%m%d}&limit=300"
    req = Request(url, headers={"User-Agent": "SportTVPolska/1.0", "Accept": "application/json"})
    with urlopen(req, timeout=20) as response:
        return json.load(response).get("events", [])

def is_poland(team):
    return (str(team.get("displayName", "")).strip().casefold() in POLAND
            or str(team.get("name", "")).strip().casefold() in POLAND
            or str(team.get("abbreviation", "")).strip().upper() == "POL")

def parse(events, now):
    output = {}
    for league, matches in events:
        for match in matches:
            competitions = match.get("competitions") or []
            teams = (competitions[0].get("competitors") or []) if competitions else []
            if len(teams) != 2:
                continue
            first, second = (item.get("team") or {} for item in teams)
            if sum(is_poland(team) for team in (first, second)) != 1:
                continue
            names = [str(team.get("displayName") or team.get("name") or "") for team in (first, second)]
            if not all(names) or EXCLUDE.search(" ".join(names) + " " + str(match.get("name", ""))):
                continue
            state = (match.get("status") or {}).get("type") or {}
            if state.get("completed") or state.get("state") == "post":
                continue
            try:
                start = datetime.fromisoformat(match["date"].replace("Z", "+00:00")).astimezone(TZ)
            except (KeyError, ValueError, TypeError):
                continue
            if not now - timedelta(hours=3) <= start <= now + timedelta(days=21):
                continue
            match_id = str(match.get("id") or "")
            if not match_id:
                continue
            key = (start.date().isoformat(), tuple(sorted(names)))
            output[key] = {"start": start.isoformat(),
                "displayUntil": (start + timedelta(hours=3)).isoformat(),
                "sport": "pilka", "name": " – ".join(names),
                "tournament": (match.get("season") or {}).get("displayName") or league,
                "channel": None, "verifiedLive": False,
                "matchScheduled": True, "timeType": "match_planned",
                "sourceUrl": (match.get("links") or [{}])[0].get("href") or f"{BASE}/{league}/summary?event={match_id}",
                "competitionId": f"espn:{league}:{match_id}",
                "verification": "Poland senior national team fixture from ESPN; TV not confirmed"}
    return sorted(output.values(), key=lambda x: x["start"])

def merge(existing, discovered, now):
    # Rebuild football from the current schedule, so cancellations/time shifts
    # are reflected; preserve independently verified TV only for same fixture/time.
    other = [x for x in existing if x.get("sport") != "pilka"]
    previous = {x.get("competitionId"): x for x in existing if x.get("sport") == "pilka"}
    for row in discovered:
        old = previous.get(row["competitionId"])
        if old and old.get("verifiedLive") and old.get("start") == row["start"]:
            row.update({k: old[k] for k in ("channel", "verifiedLive", "tvStart", "tvEnd")
                        if k in old})
    return sorted(other + discovered, key=lambda x: x["start"])

UEFA_URL = "https://www.uefa.com/uefanationsleague/news/02a2-1fea18abbcbc-456e846509e7-1000--2026-27-uefa-nations-league-all-the-league-phase-fixtures-a/"

def parse_uefa(html, now):
    """Discover fixtures from the official UEFA matchday listing, not manual entries."""
    from html.parser import HTMLParser
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.hidden = 0
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"): self.hidden += 1
            if tag in ("p", "div", "li", "h2", "h3", "br"): self.parts.append("\n")
        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript") and self.hidden: self.hidden -= 1
            if tag in ("p", "div", "li", "h2", "h3"): self.parts.append("\n")
        def handle_data(self, value):
            if not self.hidden: self.parts.append(value)
    parser = Text()
    parser.feed(html)
    lines = [" ".join(s.split()) for s in "".join(parser.parts).splitlines()]
    months = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
    date = None
    found = {}
    for line in lines:
        heading = re.fullmatch(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})\s+([A-Za-z]+)", line)
        if heading:
            month = months.get(heading.group(2))
            date = datetime(now.year, month, int(heading.group(1)), tzinfo=TZ) if month else None
            continue
        if date is None: continue
        match = re.fullmatch(r"(?:[A-D]\d\s+)?(.+?)\s+vs\s+(.+?)(?:\s+\((\d{1,2}:\d{2})\))?", line)
        if not match: continue
        home, away = match.group(1).strip(), match.group(2).strip()
        if sum(n.casefold() == "poland" for n in (home, away)) != 1: continue
        hour = match.group(3) or "20:45"
        start = date.replace(hour=int(hour[:2]), minute=int(hour[3:]))
        if not now - timedelta(hours=3) <= start <= now + timedelta(days=21): continue
        key = (start.date().isoformat(), home, away)
        found[key] = {"start": start.isoformat(), "displayUntil": (start + timedelta(hours=3)).isoformat(),
            "sport": "pilka", "name": f"{home} – {away}", "tournament": "Liga Narodów UEFA",
            "channel": None, "verifiedLive": False, "matchScheduled": True, "timeType": "match_planned",
            "sourceUrl": UEFA_URL, "competitionId": f"uefa:{start.date()}:{home}:{away}",
            "verification": "Official UEFA matchday listing; TV unconfirmed"}
    return list(found.values())

def fetch_uefa(now):
    req = Request(UEFA_URL, headers={"User-Agent": "Mozilla/5.0 SportTVPolska"})
    with urlopen(req, timeout=25) as response:
        return parse_uefa(response.read(3000000).decode("utf-8", "replace"), now)

def main():
    now = datetime.now(TZ)
    collected = []
    successful = 0
    for league in LEAGUES:
        try:
            matches = fetch(league, now - timedelta(days=1), now + timedelta(days=21))
            collected.append((league, matches))
            successful += 1
            print(f"{league}: {len(matches)} matches")
        except (OSError, ValueError, TimeoutError) as exc:
            print(f"{league}: unavailable ({type(exc).__name__})")
    if not successful:
        print("ESPN unavailable; checking UEFA instead")
    path = ROOT / "events.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    found = parse(collected, now)
    try:
        official = fetch_uefa(now)
        print(f"Official UEFA Poland fixtures: {len(official)}")
        for fixture in official:
            found = [e for e in found if not (e["start"][:10] == fixture["start"][:10] and set(e["name"].lower().split(" – ")) == set(fixture["name"].lower().split(" – ")))]
            found.append(fixture)
    except (OSError, ValueError, TimeoutError) as exc:
        print(f"UEFA unavailable: {type(exc).__name__}")
    found.sort(key=lambda e: e["start"])
    if not found:
        print("No fixtures returned by ESPN; preserving previously discovered future matches")
        found = [e for e in data.get("events", []) if e.get("sport") == "pilka" and e.get("start", "") >= (now - timedelta(hours=3)).isoformat()]
    data["events"] = merge(data.get("events", []), found, now)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Poland national-team fixtures automatically discovered: {len(found)}")

if __name__ == "__main__":
    main()
