#!/usr/bin/env python3
"""Read named Polish athletes from event-specific official entry/start lists.

Conservative: official source, athlete TABLE row with POL/Poland, configured
event identity, and fresh successful fetch. No guessing from judges or venue.
"""
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
WARSAW = ZoneInfo("Europe/Warsaw")
ALLOWED = ("fis-ski.com", "worldathletics.org", "fidal.it", "domtel-sport.pl",
           "pzla.pl", "european-athletics.com")
COUNTRY = re.compile(r"(?<![A-Za-z])(?:POL|POLAND|POLSKA)(?![A-Za-z])", re.I)
GENERIC = {"athlete", "bib", "rank", "nation", "country", "poland", "polska", "pol",
           "year", "club", "name", "start", "list", "male", "female"}

class TableRows(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = 0
        self.row = None
        self.cell = None
        self.rows = []
        self.groups = []
        self.current_table = None
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables += 1
            if self.tables == 1:
                self.current_table = []
        if self.tables and tag == "tr":
            self.row = []
        if self.row is not None and tag in ("td", "th"):
            self.cell = []
        if self.cell is not None and tag == "img":
            a = dict(attrs)
            self.cell.append(" " + (a.get("alt") or a.get("title") or "") + " ")
    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            if len(self.row) > 1:
                self.rows.append(self.row)
                if self.current_table is not None:
                    self.current_table.append(self.row)
            self.row = None
        if tag == "table" and self.tables:
            self.tables -= 1
            if self.tables == 0 and self.current_table is not None:
                self.groups.append(self.current_table)
                self.current_table = None

def has_polish_athlete(html):
    parser = TableRows()
    parser.feed(html)
    for group in parser.groups:
        heading = " ".join(" ".join(row) for row in group[:3]).casefold()
        if not any(key in heading for key in ("athlete", "zawodnik", "bib", "rank", "name", "start list", "entry list")):
            continue
        if any(key in heading for key in ("technical delegate", "jury", "judge")):
            continue
        for row in group:
            if not any(COUNTRY.search(cell) for cell in row):
                continue
        # Reject metadata and judging tables, which can also show POL.
            combined = " ".join(row).casefold()
            if any(x in combined for x in ("technical delegate", "jury", "judge ", "chief of competition")):
                continue
            names = [cell for cell in row if re.search(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{2,}\s+[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{2,}", cell)
                     and not COUNTRY.fullmatch(cell)]
            if any(len(candidate) <= 90 and not any(w in GENERIC for w in candidate.casefold().split())
                   for candidate in names):
                return True
    return False

def allowed_url(url):
    host = (urlparse(url).hostname or "").lower()
    return urlparse(url).scheme == "https" and any(host == x or host.endswith("." + x) for x in ALLOWED)

def fetch(url):
    if not allowed_url(url):
        raise ValueError("Nieznane lub niebezpieczne zrodlo")
    req = Request(url, headers={"User-Agent": "SportTVPolska/1.0 (start-list verification)"})
    with urlopen(req, timeout=25) as response:
        raw = response.read(1_500_001)
        if len(raw) > 1_500_000:
            raise ValueError("Zbyt duza strona")
        return raw.decode("utf-8", "replace")

def verify(entries, downloader=fetch):
    checked = []
    for event in entries:
        row = dict(event)
        row["polishParticipantsConfirmed"] = False
        row["participantsCheckedAt"] = None
        url = event.get("entryListUrl", "")
        if not allowed_url(url):
            checked.append(row)
            continue
        try:
            html = downloader(url)
            row["polishParticipantsConfirmed"] = has_polish_athlete(html)
            row["participantsCheckedAt"] = datetime.now(WARSAW).isoformat()
        except (OSError, ValueError, TimeoutError) as exc:
            print(f"Brak potwierdzenia uczestnikow: {event.get('competitionId')}: {type(exc).__name__}")
        checked.append(row)
    return checked

def main():
    source = json.loads((ROOT / "sport_competitions.json").read_text(encoding="utf-8"))
    if not isinstance(source, list):
        raise SystemExit("sport_competitions.json musi byc lista")
    checked = verify(source)
    (ROOT / "participation_verified.json").write_text(
        json.dumps({"updatedAt": datetime.now(WARSAW).isoformat(), "competitions": checked},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Wydarzenia:", len(checked), "potwierdzeni Polacy:", sum(e["polishParticipantsConfirmed"] for e in checked))
    missing = [e.get("competitionId") for e in checked if not e.get("entryListUrl")]
    if missing:
        print("BRAK oficjalnej listy startowej (nie publikujemy):", ", ".join(str(x) for x in missing))

if __name__ == "__main__":
    main()
