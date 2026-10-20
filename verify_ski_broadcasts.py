#!/usr/bin/env python3
"""Conservative ski-jumping TV verifier.

A LIVE Teleman listing must match a separately confirmed competition entry
with Polish athletes. TV listings are the source of broadcast start times.
No independent Polish starter confirmation => no publication.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from verify_tennis_broadcasts import normalize, parse_teleman_date, load

ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
MAX_TV_EARLY_MINUTES = 40
MAX_TV_LATE_MINUTES = 15

def verify_ski(competitions, listings, listing_updated, now, existing=(), epg=()):
    confirmed = []
    existing_ids = {
        e.get("competitionId") for e in existing if e.get("competitionId")
    }
    for comp in competitions:
        if comp.get("polishParticipantsConfirmed") is not True:
            continue
        if not (comp.get("sourceUrl", "").startswith("https://")
                and comp.get("competitionId") and comp.get("venue")):
            continue
        try:
            race = datetime.fromisoformat(comp["competitionStart"]).astimezone(WARSAW)
        except (ValueError, TypeError, KeyError):
            continue
        if not now <= race <= now + timedelta(days=7):
            continue
        if comp["competitionId"] in existing_ids:
            continue
        # Avoid duplicating previously approved manual TV listings for this event.
        if any(e.get("sport") == "skoki" and normalize(comp["venue"]) in normalize(e.get("name", ""))
               and abs((datetime.fromisoformat(e["start"]).astimezone(WARSAW) - race).total_seconds()) <= 3600
               for e in existing if e.get("start")):
            continue
        matches = []
        for tv in listings:
            if tv.get("sport") != "skoki" or tv.get("telemanLiveBadge") is not True:
                continue
            title = normalize(tv.get("title", ""))
            if normalize(comp["venue"]) not in title:
                continue
            # Never infer an individual event from an explicitly named other type.
            kind = comp.get("eventType")
            other_types = {"men": ("kobiet", "pan", "women", "mixed", "mieszany", "druzynowy", "druzynowe"),
                           "women": ("mezczyzn", "panow", "men", "mixed", "mieszany", "druzynowy"),
                           "mixed": ("kobiet", "mezczyzn", "individual", "indywidualny")}
            if kind not in other_types:
                continue
            if any(phrase in title.split() for phrase in other_types[kind]):
                continue
            start = parse_teleman_date(tv.get("dateLabel", ""), tv.get("timeLabel", ""), listing_updated)
            if start is None or not (start - timedelta(minutes=MAX_TV_LATE_MINUTES)
                                     <= race <= start + timedelta(minutes=MAX_TV_EARLY_MINUTES)):
                continue
            if start.date() != race.date():
                continue
            matches.append((tv, start))
        # Independently require an XMLTV programme ending after the competition starts.
        supported = []
        for tv, start in matches:
            for p in epg:
                if p.get("sport") != "skoki" or normalize(p.get("channel")) != normalize(tv["channel"]):
                    continue
                if normalize(comp["venue"]) not in normalize(p.get("name", "") + " " + p.get("description", "")):
                    continue
                try:
                    epg_start = datetime.fromisoformat(p["start"]).astimezone(WARSAW)
                    epg_end = datetime.fromisoformat(p["end"]).astimezone(WARSAW)
                except (ValueError, TypeError, KeyError):
                    continue
                if abs((epg_start - start).total_seconds()) > 30 * 60 or epg_end <= race:
                    continue
                supported.append((tv, start, epg_end))
        # Multiple different programme slots would be ambiguous.
        unique = {(tv["channel"], start.isoformat()): (tv, start, end)
                  for tv, start, end in supported}
        if len(unique) != 1:
            continue
        tv, tv_start, end = next(iter(unique.values()))
        confirmed.append({
            "start": tv_start.isoformat(),
            "end": end.isoformat(),
            "sport": "skoki",
            "name": comp["name"],
            "channel": tv["channel"],
            "sourceUrl": tv.get("sourceUrl", "https://www.teleman.pl/sport?live=1"),
            "verifiedLive": True,
            "competitionId": comp["competitionId"],
            "verification": "Polish starters independently confirmed + exact venue/date + Teleman LIVE",
        })
    return confirmed

def main():
    now = datetime.now(WARSAW)
    listing, updated = load("teleman_review.json", "rows", now)
    competitions = json.loads((ROOT / "ski_competitions.json").read_text(encoding="utf-8"))
    if not isinstance(competitions, list):
        raise SystemExit("ski_competitions.json must be a list")
    file = ROOT / "events.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    old = payload.get("events", [])
    # A subsequent run must not erase independently verified broadcast listings.
    epg, _ = load("candidates.json", "events", now)
    added = verify_ski(competitions, listing, updated, now, old, epg)
    payload["events"] = sorted(old + added, key=lambda e: e["start"])
    file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Nowe potwierdzone transmisje skoków: {len(added)}")
    print("Bez listy Polaków i jednoznacznej emisji LIVE niczego nie dodajemy.")

if __name__ == "__main__":
    main()
