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
from tv_schedule import tv_times, usable_epg_end

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
        # Teleman LIVE + official Polish squad/start list is sufficient.
        # XMLTV only supplies an independently grounded programme end.
        unique = {(tv["channel"], start.isoformat()): (tv, start)
                  for tv, start in matches}
        if len(unique) != 1:
            continue
        tv, tv_start = next(iter(unique.values()))
        end = usable_epg_end(
            epg, tv_start, tv["channel"], "skoki",
            lambda p: normalize(comp["venue"]) in normalize(
                p.get("name", "") + " " + p.get("description", "")),
            normalize,
        )
        # Contradictory EPG is not evidence of a different TV start; refuse
        # to infer the end unless it is consistent with the competition.
        if end is not None and end <= race:
            end = None
        confirmed.append({
            **tv_times(tv_start, end),
            "sport": "skoki",
            "name": comp["name"],
            "channel": tv["channel"],
            "sourceUrl": tv.get("sourceUrl", "https://www.teleman.pl/sport?live=1"),
            "verifiedLive": True,
            "competitionId": comp["competitionId"],
            "participationEvidence": comp.get("participationEvidence", "official_start_list"),
            "participationSourceUrl": comp.get("entryListUrl") if comp.get("participationEvidence") == "official_start_list" else comp.get("rosterUrl", comp["sourceUrl"]),
            "verification": "Official squad or start list + exact competition/date + Teleman LIVE (EPG optional)",
        })
    return confirmed

def main():
    now = datetime.now(WARSAW)
    listing, updated = load("teleman_review.json", "rows", now)
    competitions = [e for e in json.loads((ROOT / "participation_verified.json").read_text(encoding="utf-8"))["competitions"] if e.get("sport") == "skoki"]
    if not isinstance(competitions, list):
        raise SystemExit("Lista zawodow w participation_verified.json jest niepoprawna")
    file = ROOT / "events.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    old = payload.get("events", [])
    # When the official start list arrives, upgrade an earlier roster-based
    # confirmation, without altering the TV channel or programme start time.
    for event in old:
        if event.get("sport") != "skoki":
            continue
        for comp in competitions:
            if (event.get("competitionId") == comp.get("competitionId")
                    and comp.get("polishParticipantsConfirmed") is True
                    and comp.get("participationEvidence") == "official_start_list"):
                event["participationEvidence"] = "official_start_list"
                event["participationSourceUrl"] = comp.get("entryListUrl")
    # A subsequent run must not erase independently verified broadcast listings.
    epg, _ = load("candidates.json", "events", now)
    added = verify_ski(competitions, listing, updated, now, old, epg)
    payload["events"] = sorted(old + added, key=lambda e: e["start"])
    file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Nowe potwierdzone transmisje skoków: {len(added)}")
    print("Bez listy Polaków i jednoznacznej emisji LIVE niczego nie dodajemy.")

if __name__ == "__main__":
    main()
