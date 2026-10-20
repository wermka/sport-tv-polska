#!/usr/bin/env python3
"""Publish only tennis broadcasts supported by three independent signals.

Requirements:
- upcoming Polish tennis match from Live Tennis API,
- the same two players in a Teleman listing explicitly marked LIVE,
- the XMLTV can optionally confirm programme end but is not required.

No guesses from generic tournament slots. Other sports stay in the manual
verification queue until independent competition calendars are integrated.
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from tv_schedule import tv_times, usable_epg_end

ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
MONTHS = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
          "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9,
          "pazdziernika": 10, "października": 10, "listopada": 11, "grudnia": 12}
MAX_FEED_AGE = timedelta(hours=5)

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or "").replace("ł", "l").replace("Ł", "L"))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def surnames(name):
    players = re.split(r"\s+[–—-]\s+", str(name or ""), maxsplit=1)
    if len(players) != 2:
        return None
    names = [normalize(player).split()[-1] for player in players if normalize(player)]
    return names if len(names) == 2 and all(len(n) >= 3 for n in names) and names[0] != names[1] else None

def surname_forms(surname):
    """Small, explicit set of Polish surname inflections, not fuzzy matching."""
    forms = {surname}
    # Kawa -> Kawy, Giza -> Gizy, Kowalska -> Kowalskiej.
    if surname.endswith(("ska", "cka", "dzka")):
        forms.add(surname[:-1] + "iej")
    elif surname.endswith("a") and len(surname) >= 4:
        forms.add(surname[:-1] + "y")
    # Kowalski -> Kowalskiego.
    if surname.endswith(("ski", "cki", "dzki")):
        forms.add(surname[:-1] + "iego")
    return forms


def both_named(title, names):
    words = set(normalize(title).split())
    return all(bool(words & surname_forms(n)) for n in names)

def parse_teleman_date(label, hour, updated):
    text = normalize(label)
    # For overnight entries choose the second date: "20 na 21 października".
    night = re.search(r"(\d{1,2})\s+na\s+(\d{1,2})\s+([a-z]+)", text)
    regular = re.search(r"(\d{1,2})\s+([a-z]+)", text)
    if night:
        day, month_word = int(night.group(2)), night.group(3)
    elif regular:
        day, month_word = int(regular.group(1)), regular.group(2)
    else:
        return None
    month = MONTHS.get(month_word)
    hm = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(hour))
    if month is None or hm is None:
        return None
    try:
        values = [datetime(year, month, day, int(hm.group(1)), int(hm.group(2)), tzinfo=WARSAW)
                  for year in (updated.year - 1, updated.year, updated.year + 1)]
    except ValueError:
        return None
    return min(values, key=lambda dt: abs((dt - updated).total_seconds()))

def load(name, key, now):
    data = json.loads((ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise ValueError(f"{name}: brak listy {key}")
    updated = datetime.fromisoformat(data["updatedAt"])
    if updated.tzinfo is None or not (-timedelta(minutes=10) <= now - updated <= MAX_FEED_AGE):
        raise ValueError(f"{name}: dane nieaktualne lub znacznik czasu niepoprawny")
    return data[key], updated.astimezone(WARSAW)

def verify(tennis, teleman, epg, teleman_updated, now):
    """Publish upcoming API tennis fixtures; TV channel requires a LIVE name match.

    The upstream API query and conversion check that at least one player has
    country=POL. Raw rows without that provenance must not be accepted.
    """
    rows, seen = [], set()
    for match in tennis:
        if match.get("status") != "upcoming" or match.get("sport") != "tenis":
            continue
        if match.get("polishParticipantConfirmedByApi") is not True:
            continue
        names = surnames(match.get("name"))
        if not names or not match.get("id"):
            continue
        try:
            start = datetime.fromisoformat(match["start"]).astimezone(WARSAW)
        except (KeyError, TypeError, ValueError):
            continue
        if not now <= start <= now + timedelta(days=7):
            continue
        mid = str(match["id"])
        if mid in seen:
            continue
        seen.add(mid)

        # This is a FIXTURE, not a confirmed live TV broadcast.
        result = {
            **tv_times(start),
            "sport": "tenis", "name": match["name"],
            "matchId": mid, "matchScheduledStart": start.isoformat(),
            "matchScheduled": True, "timeType": "match_planned",
            "channel": None, "verifiedLive": False,
            "sourceUrl": "https://api.livetennisapi.com/",
            "verification": "Upcoming Polish fixture from Live Tennis API; TV unconfirmed",
        }
        possible_tv = []
        for tv in teleman:
            if tv.get("sport") != "tenis" or tv.get("telemanLiveBadge") is not True:
                continue
            if not both_named(tv.get("title", ""), names):
                continue
            tv_start = parse_teleman_date(tv.get("dateLabel", ""), tv.get("timeLabel", ""), teleman_updated)
            if tv_start is None or abs((tv_start - start).total_seconds()) > 45 * 60:
                continue
            if not normalize(tv.get("channel")):
                continue
            possible_tv.append((tv, tv_start))
        # A single specific broadcast may promote the fixture into TV listing.
        slots = {(normalize(tv["channel"]), tv_start.isoformat()): (tv, tv_start)
                 for tv, tv_start in possible_tv}
        if len(slots) == 1:
            tv, tv_start = next(iter(slots.values()))
            end = usable_epg_end(
                epg, tv_start, tv["channel"], "tenis",
                lambda p: both_named(p.get("name", "") + " " + p.get("description", ""), names),
                normalize,
            )
            if end is not None and end < start:
                end = None
            result.update(tv_times(tv_start, end))
            result.update({
                "channel": tv["channel"], "verifiedLive": True,
                "timeType": "tv_broadcast",
                "sourceUrl": tv.get("sourceUrl", "https://www.teleman.pl/sport?live=1"),
                "verification": "API upcoming + Teleman LIVE with both names (EPG optional)",
            })
        rows.append(result)
    rows.sort(key=lambda x: x["start"])
    return rows

def main():
    now = datetime.now(WARSAW)
    try:
        tennis, _ = load("tennis_candidates.json", "matches", now)
        teleman, tv_updated = load("teleman_review.json", "rows", now)
        epg, _ = load("candidates.json", "events", now)
        found = verify(tennis, teleman, epg, tv_updated, now)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit(f"Nie publikuję: {exc}") from exc
    # Preserve previously independently verified/manual entries for other sports.
    path = ROOT / "events.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    manual = [e for e in payload.get("events", [])
              if e.get("verifiedLive") is True and not (e.get("sport") == "tenis" and e.get("matchId"))]
    all_events = manual + found
    payload["updatedAt"] = now.isoformat()
    payload["source"] = "Upcoming Polish tennis fixtures from API; TV channel requires Teleman LIVE"
    payload["events"] = sorted(all_events, key=lambda e: e["start"])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Zaplanowane mecze Polakow: {len(found)}; z potwierdzona TV: {sum(bool(e.get('channel')) for e in found)}; inne wydarzenia: {len(manual)}")
    print("Brak dopasowania TV = mecz z godzina API bez kanalu. Nie zgadujemy nadawcy.")

if __name__ == "__main__":
    main()
