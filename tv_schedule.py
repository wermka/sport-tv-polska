#!/usr/bin/env python3
"""Broadcast times come from Teleman; EPG is an optional second confirmation.

Without EPG, the broadcast end is UNKNOWN. displayUntil is only a UI cleanup
cutoff; it must never be shown as an actual TV end or an event duration.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

WARSAW = ZoneInfo("Europe/Warsaw")

def tv_times(start, epg_end=None, max_display_hours=4):
    if start.tzinfo is None:
        raise ValueError("TV start must include a timezone")
    result = {"start": start.isoformat()}
    if epg_end is not None:
        if epg_end.tzinfo is None or epg_end <= start:
            raise ValueError("Invalid EPG end")
        result["end"] = epg_end.isoformat()
        result["endConfirmedByEpg"] = True
    else:
        result["displayUntil"] = (start + timedelta(hours=max_display_hours)).isoformat()
        result["endConfirmedByEpg"] = False
    return result

def usable_epg_end(epg_rows, tv_start, channel, sport, name_matches, normalize, window_minutes=30):
    """No match => unknown end, not a made-up duration."""
    ends = []
    for item in epg_rows:
        if item.get("sport") != sport or normalize(item.get("channel")) != normalize(channel):
            continue
        if not name_matches(item):
            continue
        try:
            begin = datetime.fromisoformat(item["start"]).astimezone(WARSAW)
            finish = datetime.fromisoformat(item["end"]).astimezone(WARSAW)
        except (KeyError, TypeError, ValueError):
            continue
        if abs((begin - tv_start).total_seconds()) <= window_minutes * 60 and finish > tv_start:
            ends.append(finish)
    return ends[0] if len(set(ends)) == 1 else None
