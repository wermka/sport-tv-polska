#!/usr/bin/env python3
"""Publish only tennis broadcasts supported by three independent signals.

Requirements:
- upcoming Polish tennis match from Live Tennis API,
- the same two players in a Teleman listing explicitly marked LIVE,
- the same players and channel in XMLTV with matching start time and known end.

No guesses from generic tournament slots. Other sports stay in the manual
verification queue until independent competition calendars are integrated.
"""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
MONTHS = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
          "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9,
          "pazdziernika": 10, "października": 10, "listopada": 11, "grudnia": 12}
MAX_FEED_AGE = timedelta(hours=5)

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def surnames(name):
    players = re.split(r"\s+[–—-]\s+", str(name or ""), maxsplit=1)
    if len(players) != 2:
        return None
    names = [normalize(player).split()[-1] for player in players if normalize(player)]
    return names if len(names) == 2 and all(len(n) >= 4 for n in names) and names[0] != names[1] else None

def both_named(title, names):
    title = " " + normalize(title) + " "
    return all(re.search(r"\b" + re.escape(n) + r"\b", title) for n in names)

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
    rows, seen = [], set()
    for match in tennis:
        if match.get("status") != "upcoming" or match.get("sport") != "tenis":
            continue
        names = surnames(match.get("name"))
        if not names:
            continue
        try:
            start = datetime.fromisoformat(match["start"]).astimezone(WARSAW)
        except (KeyError, TypeError, ValueError):
            continue
        if not now <= start <= now + timedelta(days=7):
            continue
        for tv in teleman:
            if tv.get("sport") != "tenis" or tv.get("telemanLiveBadge") is not True:
                continue
            if not both_named(tv.get("title", ""), names):
                continue
            tv_start = parse_teleman_date(tv.get("dateLabel", ""), tv.get("timeLabel", ""), teleman_updated)
            if tv_start is None or abs((tv_start - start).total_seconds()) > 45 * 60:
                continue
            channel = normalize(tv.get("channel"))
            for programme in epg:
                if programme.get("sport") != "tenis" or normalize(programme.get("channel")) != channel:
                    continue
                if not both_named(programme.get("name", "") + " " + programme.get("description", ""), names):
                    continue
                try:
                    epg_start = datetime.fromisoformat(programme["start"]).astimezone(WARSAW)
                    epg_end = datetime.fromisoformat(programme["end"]).astimezone(WARSAW)
                except (KeyError, TypeError, ValueError):
                    continue
                if abs((epg_start - tv_start).total_seconds()) > 30 * 60 or not epg_start <= start <= epg_end:
                    continue
                if epg_end <= now or epg_end <= start:
                    continue
                key = (match.get("id"), channel, tv_start.isoformat())
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "start": tv_start.isoformat(), "end": epg_end.isoformat(),
                    "sport": "tenis", "name": match["name"], "channel": tv["channel"],
                    "verifiedLive": True, "sourceUrl": tv.get("sourceUrl", "https://www.teleman.pl/sport?live=1"),
                    "verification": "API upcoming + Teleman LIVE with both names + XMLTV same match/channel/time",
                })
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
              if e.get("verifiedLive") is True and e.get("verification") != "API upcoming + Teleman LIVE with both names + XMLTV same match/channel/time"]
    all_events = manual + found
    payload["updatedAt"] = now.isoformat()
    payload["source"] = "Independent verification; tennis requires API + Teleman LIVE + XMLTV"
    payload["events"] = sorted(all_events, key=lambda e: e["start"])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Potwierdzone mecze tenisowe: {len(found)}; pozostale zweryfikowane: {len(manual)}")
    print("Brak dopasowania = brak publikacji; nie przypisujemy kanałów na podstawie samego turnieju.")

if __name__ == "__main__":
    main()
