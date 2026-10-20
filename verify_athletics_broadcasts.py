#!/usr/bin/env python3
"""Only publish an athletics broadcast when a Polish athlete appears in its
event-specific official entries AND TV LIVE and XMLTV agree."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from verify_tennis_broadcasts import normalize, load, parse_teleman_date

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Warsaw")

def verify_athletics(entries, tv_rows, epg_rows, updated, now, existing=()):
    found = []
    for event in entries:
        if event.get("sport") != "lekkoatletyka" or event.get("polishParticipantsConfirmed") is not True:
            continue
        if not event.get("entryListUrl") or not event.get("participantsCheckedAt"):
            continue
        try:
            start = datetime.fromisoformat(event["competitionStart"]).astimezone(TZ)
            verified_at = datetime.fromisoformat(event["participantsCheckedAt"]).astimezone(TZ)
        except (ValueError, TypeError, KeyError):
            continue
        if not (now <= start < now + timedelta(days=7)) or now - verified_at > timedelta(hours=8):
            continue
        places = [normalize(value) for value in [event.get("venue"), *event.get("venueAliases", [])]]
        places = [value for value in places if len(value) >= 4]
        if not places:
            continue
        place = places[0]
        if any(e.get("sport") == "lekkoatletyka" and place in normalize(e.get("name", ""))
               and abs((datetime.fromisoformat(e["start"]).astimezone(TZ) - start).total_seconds()) < 3600
               for e in existing if e.get("start")):
            continue
        matching = []
        for tv in tv_rows:
            if tv.get("sport") != "lekkoatletyka" or tv.get("telemanLiveBadge") is not True:
                continue
            if not any(place_name in normalize(tv.get("title")) for place_name in places):
                continue
            tv_time = parse_teleman_date(tv.get("dateLabel"), tv.get("timeLabel"), updated)
            if tv_time is None or tv_time.date() != start.date():
                continue
            if not tv_time - timedelta(minutes=15) <= start <= tv_time + timedelta(minutes=40):
                continue
            for epg in epg_rows:
                if epg.get("sport") != "lekkoatletyka" or normalize(epg.get("channel")) != normalize(tv.get("channel")):
                    continue
                if not any(place_name in normalize(epg.get("name", "") + " " + epg.get("description", "")) for place_name in places):
                    continue
                try:
                    epg_start = datetime.fromisoformat(epg["start"]).astimezone(TZ)
                    epg_end = datetime.fromisoformat(epg["end"]).astimezone(TZ)
                except (ValueError, TypeError, KeyError):
                    continue
                if abs((epg_start - tv_time).total_seconds()) <= 30 * 60 and epg_end > start:
                    matching.append((tv, tv_time, epg_end))
        unique = {(tv["channel"], time.isoformat()): (tv, time, end) for tv, time, end in matching}
        if len(unique) != 1:
            continue
        tv, time, end = next(iter(unique.values()))
        found.append({"start": time.isoformat(), "end": end.isoformat(), "sport": "lekkoatletyka",
                      "name": event["name"], "channel": tv["channel"], "verifiedLive": True,
                      "sourceUrl": tv.get("sourceUrl", "https://www.teleman.pl/sport?live=1"),
                      "competitionId": event["competitionId"],
                      "verification": "Official athlete entries POL + Teleman LIVE + matching XMLTV"})
    return found

def main():
    now = datetime.now(TZ)
    tv, updated = load("teleman_review.json", "rows", now)
    epg, _ = load("candidates.json", "events", now)
    events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
    entries = json.loads((ROOT / "participation_verified.json").read_text(encoding="utf-8"))["competitions"]
    new = verify_athletics(entries, tv, epg, updated, now, events.get("events", []))
    events["events"] = sorted(events.get("events", []) + new, key=lambda item: item["start"])
    (ROOT / "events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Nowe potwierdzone transmisje lekkoatletyczne:", len(new))

if __name__ == "__main__":
    main()
