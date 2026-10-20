#!/usr/bin/env python3
"""Synthetic XMLTV regression tests: no network, no real matches."""
import io
import json
import tempfile
import urllib.error
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import update_epg
from update_epg import candidates_from_xml

NOW = datetime(2026, 10, 20, 19, 0, tzinfo=ZoneInfo("Europe/Warsaw"))

def programmes():
    return """<?xml version="1.0" encoding="UTF-8"?>
<tv>
<channel id="1"><display-name>Eurosport 2</display-name></channel>
<channel id="2"><display-name>Polsat Sport</display-name></channel>
<programme channel="1" start="20261024132000 +0200" stop="20261024153000 +0200">
<title>Skoki narciarskie: Letnie Grand Prix w Klingenthal</title></programme>
<programme channel="2" start="20261020190000 +0200" stop="20261020200000 +0200">
<title>Tenis stolowy: Lotto Superliga</title></programme>
<programme channel="2" start="20261020200000 +0200" stop="20261020210000 +0200">
<title>Tenis stołowy: Superliga</title></programme>
<programme channel="2" start="20261020210000 +0200" stop="20261020220000 +0200">
<title>Tenis: Magda Linette - rywalka</title></programme>
<programme channel="1" start="20261024200000 +0200" stop="20261024210000 +0200">
<title>Skoki narciarskie: Powtórka z Klingenthal</title></programme>
</tv>""".encode("utf-8")

class EpgRegressionTests(unittest.TestCase):
    def test_ski_without_poland_word_is_retained_as_unverified(self):
        with patch("update_epg.urllib.request.urlopen", return_value=io.BytesIO(programmes())):
            rows = candidates_from_xml("https://example.org/test", NOW)
        ski = [e for e in rows if e["sport"] == "skoki"]
        self.assertEqual(len(ski), 1)
        self.assertFalse(ski[0]["verifiedLive"])
        self.assertEqual(ski[0]["channel"], "Eurosport 2")

    def test_table_tennis_not_included(self):
        with patch("update_epg.urllib.request.urlopen", return_value=io.BytesIO(programmes())):
            rows = candidates_from_xml("https://example.org/test", NOW)
        self.assertEqual(len([e for e in rows if e["sport"] == "tenis"]), 1)

    def test_http_522_uses_safe_fallback_after_three_attempts(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            # Independently confirmed entries must remain available.
            now = NOW
            verified = [{
                "start": "2026-10-24T13:30:00+02:00",
                "end": "2026-10-24T15:25:00+02:00",
                "sport": "skoki", "name": "Klingenthal",
                "channel": "Eurosport 2",
                "sourceUrl": "https://www.skijumping.pl/skoki-dzisiaj/",
                "verifiedLive": True,
            }]
            (base / "verified_events.json").write_text(json.dumps(verified), encoding="utf-8")
            failure = urllib.error.HTTPError("https://example.org/epg.xml.gz", 522, "Connection timed out", {}, None)
            with patch.object(update_epg, "BASE", base), \
                 patch.object(update_epg, "candidates_from_xml", side_effect=failure) as call, \
                 patch.object(update_epg, "time") as clock, \
                 patch.object(update_epg, "datetime", wraps=datetime) as dt:
                dt.now.return_value = now
                update_epg.main("https://example.org/epg.xml.gz")
            self.assertEqual(call.call_count, 3)
            self.assertEqual(clock.sleep.call_count, 2)
            epg = json.loads((base / "candidates.json").read_text(encoding="utf-8"))
            output = json.loads((base / "events.json").read_text(encoding="utf-8"))
            self.assertFalse(epg["epgAvailable"])
            self.assertEqual(epg["events"], [])
            self.assertEqual(len(output["events"]), 1)
            self.assertEqual(output["events"][0]["name"], "Klingenthal")

    def test_replay_skipped(self):
        with patch("update_epg.urllib.request.urlopen", return_value=io.BytesIO(programmes())):
            rows = candidates_from_xml("https://example.org/test", NOW)
        self.assertFalse(any("Powt" in e["name"] for e in rows))

class EpgOutageTests(unittest.TestCase):
    def test_http_522_does_not_abort_or_publish_stale_candidates(self):
        confirmed = [{"start": "2026-10-24T13:30:00+02:00", "end": "2026-10-24T15:25:00+02:00",
                      "sport": "skoki", "name": "Klingenthal", "channel": "Eurosport 2",
                      "verifiedLive": True, "sourceUrl": "https://example.org/source"}]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            error = urllib.error.HTTPError("https://example.org/epg.xml.gz", 522, "timeout", {}, None)
            with patch.object(update_epg, "BASE", folder), patch.object(update_epg, "candidates_from_xml", side_effect=error) as fetcher, patch.object(update_epg, "validated_events", return_value=confirmed), patch("update_epg.time.sleep") as sleep:
                update_epg.main("https://example.org/epg.xml.gz")
            self.assertEqual(fetcher.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            candidates = json.loads((folder / "candidates.json").read_text(encoding="utf-8"))
            events = json.loads((folder / "events.json").read_text(encoding="utf-8"))
            self.assertFalse(candidates["epgAvailable"])
            self.assertEqual(candidates["events"], [])
            self.assertEqual(events["events"], confirmed)

if __name__ == "__main__":
    unittest.main()
