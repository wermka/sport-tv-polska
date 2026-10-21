#!/usr/bin/env python3
"""Decide if a full schedule refresh is due using Warsaw local time.

The scheduled GitHub job may be delayed or dropped. Hourly watchdog runs
retry when events.json has not been regenerated since the latest due slot.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")
SLOTS = ((8, 17), (14, 17), (20, 17))


def latest_due(now):
    local = now.astimezone(WARSAW)
    candidates = []
    for day in (local.date() - timedelta(days=1), local.date()):
        for hour, minute in SLOTS:
            candidates.append(datetime(day.year, day.month, day.day, hour, minute, tzinfo=WARSAW))
    return max(slot for slot in candidates if slot <= local)


def should_refresh(now, payload):
    """True when the schedule is missing or predates the latest due slot."""
    due = latest_due(now)
    try:
        updated = datetime.fromisoformat(payload["updatedAt"])
        if updated.tzinfo is None:
            return True
        return updated.astimezone(WARSAW) < due
    except (KeyError, TypeError, ValueError, AttributeError):
        return True


def main():
    import os
    now = datetime.now(WARSAW)
    event = os.environ.get("GITHUB_EVENT_NAME", "schedule")
    if event != "schedule":
        due = True
        reason = f"Manual/code trigger: {event}"
    else:
        try:
            data = json.loads(Path("events.json").read_text(encoding="utf-8"))
            due = should_refresh(now, data)
        except (OSError, ValueError, TypeError):
            due = True
        reason = f"Latest required Warsaw slot: {latest_due(now).isoformat()}"
    print(f"{reason}; full refresh {'REQUIRED' if due else 'not required'}")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"run={'true' if due else 'false'}\n")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(f"### {'Uruchamiam pelna aktualizacje' if due else 'Pominieto: terminarz aktualny'}\n\n{reason}\n")


if __name__ == "__main__":
    main()
