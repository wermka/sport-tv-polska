#!/usr/bin/env python3
"""Synthetic XMLTV regression tests: no network, no real matches."""
import io
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from update_epg import candidates_from_xml

NOW = datetime(2026, 10, 20, 19, 0, tzinfo=ZoneInfo("Europe/Warsaw"))

def programmes():
    return b"""<?xml version="1.0" encoding="UTF-8"?>
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
</tv>"""

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

    def test_replay_skipped(self):
        with patch("update_epg.urllib.request.urlopen", return_value=io.BytesIO(programmes())):
            rows = candidates_from_xml("https://example.org/test", NOW)
        self.assertFalse(any("Powt" in e["name"] for e in rows))

if __name__ == "__main__":
    unittest.main()
