#!/usr/bin/env python3
"""Lightweight, conservative tennis schedule-change checks.

Calls Live Tennis API ONLY near an independently confirmed tennis TV broadcast.
Never changes TV broadcast times; missing API matches are not proof of delays.
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from update_tennis import fetch_matches, normalized_status

ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
UPDATES = ROOT / "tennis_updates.json"
USAGE = ROOT / "tennis_api_usage.json"
MAX_DAILY_MONITOR_CALLS = 60


def parse(stamp):
    d = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("Brak strefy czasowej")
    return d.astimezone(WARSAW)


def eligible(events, now):
    result = []
    for e in events:
        if e.get("sport") != "tenis" or e.get("verifiedLive") is not True:
            continue
        if not e.get("matchId") or not e.get("matchScheduledStart"):
            continue
        try:
            start = parse(e["matchScheduledStart"])
            end = parse(e["end"])
        except (ValueError, TypeError, KeyError):
            continue
        if start - timedelta(minutes=60) <= now <= min(start + timedelta(hours=3), end + timedelta(hours=2)):
            result.append(e)
    return result


def shifted_times(events, api_matches, now):
    by_id = {str(m["id"]): m for m in api_matches if isinstance(m, dict) and m.get("id") is not None}
    updates = []
    for e in events:
        match = by_id.get(str(e["matchId"]))
        if not match or normalized_status(match.get("status")) != "upcoming":
            continue
        try:
            original = parse(e["matchScheduledStart"])
            latest = parse(match["scheduled_time"])
        except (KeyError, ValueError, TypeError):
            continue
        # Do not label scheduling drift under 10 minutes as a delay.
        if latest - original < timedelta(minutes=10):
            continue
        if latest < now - timedelta(minutes=10):
            continue
        updates.append({
            "matchId": str(e["matchId"]),
            "tvStart": e["start"],
            "scheduledStart": latest.isoformat(),
            "note": "API podało późniejszą planowaną godzinę meczu; ramówka TV bez zmian.",
        })
    return updates


def write_if_changed(path, payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def main():
    now = datetime.now(WARSAW)
    events = json.loads((ROOT / "events.json").read_text(encoding="utf-8")).get("events", [])
    watch = eligible(events, now)

    if not watch:
        # Clear old alerts so they don't survive after monitoring closes.
        write_if_changed(UPDATES, {"checkedAt": None, "updates": []})
        print("Brak potwierdzonego meczu tenisowego w oknie monitorowania; 0 zapytań API.")
        return

    key = os.getenv("LIVE_TENNIS_API_KEY")
    if not key:
        raise SystemExit("Brak LIVE_TENNIS_API_KEY; nie pobieram danych i nie zgaduję statusu.")

    today = now.date().isoformat()
    try:
        usage = json.loads(USAGE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        usage = {}
    calls = int(usage.get("calls", 0)) if usage.get("date") == today else 0
    if calls >= MAX_DAILY_MONITOR_CALLS:
        print("Dzienny limit kontroli API wykorzystany; pomijam, bez zgadywania.")
        return

    # Reserve the request even if the API fails. Other scheduled full updates
    # use at most three additional calls per day.
    write_if_changed(USAGE, {"date": today, "calls": calls + 1})
    matches = fetch_matches(key)
    updates = shifted_times(watch, matches, now)
    write_if_changed(UPDATES, {"checkedAt": now.isoformat(), "updates": updates})
    print(f"Sprawdzono {len(watch)} potwierdzonych transmisji; przesunięcia godzin: {len(updates)}.")


if __name__ == "__main__":
    main()
