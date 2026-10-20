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
ALLOWED = ("pzn.pl", "fis-ski.com", "worldathletics.org", "fidal.it", "domtel-sport.pl",
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

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.suppressed += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.suppressed:
            self.suppressed -= 1
    def handle_data(self, value):
        if not self.suppressed:
            self.parts.append(value)

def normalized_words(value):
    import unicodedata
    value = unicodedata.normalize("NFKD", str(value).translate(str.maketrans({"ł": "l", "Ł": "L"}))).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", value))

def official_roster_matches(html, event):
    """Never infer a roster from the whole page mentioning 'Poland'."""
    if event.get("sport") != "skoki" or not event.get("rosterNames"):
        return False
    p = VisibleText()
    p.feed(html)
    text = normalized_words(" ".join(p.parts))
    venue = normalized_words(event.get("venue", ""))
    if len(venue) < 4 or not re.search(r"(?<!\w)" + re.escape(venue) + r"(?!\w)", text):
        return False
    names = event["rosterNames"]
    if not isinstance(names, list) or len(names) < 2:
        return False
    found = 0
    for person in set(normalized_words(n) for n in names):
        parts = person.split()
        if len(parts) < 2 or not all(len(part) >= 3 for part in parts):
            continue
        # Name may appear in surname-first order in published squads.
        a, b = parts[0], parts[-1]
        if re.search(r"\b" + re.escape(a) + r"\s+" + re.escape(b) + r"\b", text) or re.search(r"\b" + re.escape(b) + r"\s+" + re.escape(a) + r"\b", text):
            found += 1
    minimum = max(2, int(event.get("rosterMinimumMatches", 2)))
    return found >= minimum

def verify(entries, downloader=fetch):
    checked = []
    for event in entries:
        row = dict(event)
        row["polishParticipantsConfirmed"] = False
        row["participantsCheckedAt"] = None
        row["participationEvidence"] = None
        # The start list is stronger evidence than an announced squad.
        entry_url = event.get("entryListUrl", "")
        if allowed_url(entry_url):
            try:
                if has_polish_athlete(downloader(entry_url)):
                    row["polishParticipantsConfirmed"] = True
                    row["participantsCheckedAt"] = datetime.now(WARSAW).isoformat()
                    row["participationEvidence"] = "official_start_list"
            except (OSError, ValueError, TimeoutError) as exc:
                print(f"Lista startowa niedostepna: {event.get('competitionId')}: {type(exc).__name__}")
        if not row["polishParticipantsConfirmed"] and event.get("sport") == "skoki":
            roster_url = event.get("rosterUrl", "")
            # Only the Polish Ski Association's announcement is accepted.
            if allowed_url(roster_url) and (urlparse(roster_url).hostname or "").lower() == "pzn.pl":
                try:
                    if official_roster_matches(downloader(roster_url), event):
                        row["polishParticipantsConfirmed"] = True
                        row["participantsCheckedAt"] = datetime.now(WARSAW).isoformat()
                        row["participationEvidence"] = "official_roster_announced"
                except (OSError, ValueError, TimeoutError) as exc:
                    print(f"Kadra niedostepna: {event.get('competitionId')}: {type(exc).__name__}")
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
    missing = [e.get("competitionId") for e in checked if not e.get("entryListUrl") and not e.get("rosterUrl")]
    if missing:
        print("BRAK oficjalnej listy startowej (nie publikujemy):", ", ".join(str(x) for x in missing))

if __name__ == "__main__":
    main()
