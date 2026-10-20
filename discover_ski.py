#!/usr/bin/env python3
"""Discover Polish ski-jumping TV events without a hand-written competition list.

Discovery starts with LIVE Teleman listings. Polish participation must be
verified in a contemporary official PZN team announcement describing the same
place and competition dates. No guessed athlete names or start times.
"""
import json
import re
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from verify_tennis_broadcasts import normalize, parse_teleman_date
from verify_polish_entries import normalized_words

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Warsaw")
NEWS = "https://pzn.pl/aktualnosci"
MONTHS = {"stycznia":1,"lutego":2,"marca":3,"kwietnia":4,"maja":5,"czerwca":6,
          "lipca":7,"sierpnia":8,"wrzesnia":9,"pazdziernika":10,
          "listopada":11,"grudnia":12}

class NewsLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.caption = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.caption = []
    def handle_data(self, data):
        if self.href is not None:
            self.caption.append(data)
    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join(self.caption)))
            self.href = None

class Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.active = False
        self.parts = []
        self.ignore = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style"):
            self.ignore += 1
        if tag == "p" and not self.ignore:
            self.active = True
            self.parts = []
    def handle_data(self, data):
        if self.active and not self.ignore:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == "p" and self.active:
            self.paragraphs.append(" ".join("".join(self.parts).split()))
            self.active = False
        if tag in ("script","style") and self.ignore:
            self.ignore -= 1

def official_article_links(html):
    parser = NewsLinks()
    parser.feed(html)
    items = []
    for href, caption in parser.links:
        url = urljoin(NEWS, href)
        if urlparse(url).hostname not in ("pzn.pl", "www.pzn.pl"):
            continue
        if "/skoki-narciarskie/aktualnosci/" not in url:
            continue
        if not any(word in normalized_words(caption) for word in ("sklad", "kadra", "reprezentacj", "powolan")):
            continue
        if url not in items:
            items.append(url)
    return items[:12]

def listed_venue(title):
    clean = normalize(title)
    if not ("skoki" in clean or "ski jumping" in clean):
        return None
    match = re.search(r"(?:grand prix|puchar swiata|world cup|lgp).*?\b(?:w|we)\s+([a-z][a-z0-9-]{3,})", clean)
    if not match:
        return None
    return match.group(1)

def declared_squad_for_date(html, venue, broadcast_date):
    """Require a PZN squad announcement, explicit date range and two named skiers."""
    parser = Paragraphs()
    parser.feed(html)
    for paragraph in parser.paragraphs:
        p = normalized_words(paragraph)
        if venue not in p or not any(x in p for x in ("sklad", "kadra", "reprezentacj")):
            continue
        if not any(x in p for x in ("wystapia", "powolani", "pojada", "reprezentacji")):
            continue
        dates = re.findall(r"(\d{1,2})\s*(?:-|–|—|do)\s*(\d{1,2})\s+([a-ząćęłńóśźż]+)", paragraph.casefold())
        accepted = False
        for lower, upper, month in dates:
            m = MONTHS.get(normalized_words(month))
            if m == broadcast_date.month and int(lower) <= broadcast_date.day <= int(upper):
                accepted = True
        if not accepted:
            # A precise single date is also accepted.
            single = re.findall(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)", paragraph.casefold())
            accepted = any(int(day) == broadcast_date.day and MONTHS.get(normalized_words(month)) == broadcast_date.month
                           for day, month in single)
        if not accepted:
            continue
        # Names must appear after the announcement marker, not in older
        # results described earlier in the article.
        marker = re.search(r"wyst[aą]pi[aą]:|powo[lł]ani:|sk[lł]ad\s*(?:to|:)", paragraph, re.I)
        if not marker:
            continue
        tail = paragraph[marker.end():].split(".")[0][:350]
        names = re.findall(r"\b[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}\s+[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]{2,}\b", tail)
        if len(names) >= 2:
            return names
    return []

def discover(rows, updated, news_html, article_html_by_url, now):
    entries = []
    news_links = official_article_links(news_html)
    seen = set()
    for tv in rows:
        if tv.get("sport") != "skoki" or tv.get("telemanLiveBadge") is not True:
            continue
        venue = listed_venue(tv.get("title", ""))
        if not venue:
            continue
        tv_start = parse_teleman_date(tv.get("dateLabel", ""), tv.get("timeLabel", ""), updated)
        if tv_start is None or not now <= tv_start <= now + timedelta(days=7):
            continue
        # We do not know exact race start from Teleman. Keep only the date.
        for url in news_links:
            if url not in article_html_by_url:
                continue
            names = declared_squad_for_date(article_html_by_url[url], venue, tv_start.date())
            if len(names) < 2:
                continue
            competition_id = "auto-ski-" + tv_start.date().isoformat() + "-" + venue
            if competition_id in seen:
                break
            seen.add(competition_id)
            entries.append({
                "competitionId": competition_id,
                "sport": "skoki", "competitionDate": tv_start.date().isoformat(),
                "venue": venue, "eventType": "men",
                "name": tv["title"], "sourceUrl": url, "rosterUrl": url,
                "polishParticipantsConfirmed": True,
                "participationEvidence": "official_roster_announced",
                "participationSourceUrl": url,
                "participantsCheckedAt": now.isoformat(),
                "discoveredAutomatically": True,
            })
            break
    return entries

def fetch(url):
    req = Request(url, headers={"User-Agent": "SportTVPolska/1.0 (noncommercial sports schedule)"})
    with urlopen(req, timeout=25) as response:
        data = response.read(1_500_001)
        if len(data) > 1_500_000:
            raise ValueError("Dokument zbyt duzy")
        return data.decode("utf-8", "replace")

def main():
    now = datetime.now(TZ)
    television = json.loads((ROOT / "teleman_review.json").read_text(encoding="utf-8"))
    updated = datetime.fromisoformat(television["updatedAt"]).astimezone(TZ)
    if abs((now - updated).total_seconds()) > 5 * 3600:
        raise SystemExit("Teleman nieaktualny; nie wykrywam nowych zawodow.")
    try:
        links_html = fetch(NEWS)
        links = official_article_links(links_html)
        articles = {url: fetch(url) for url in links}
        entries = discover(television["rows"], updated, links_html, articles, now)
    except (OSError, ValueError, TimeoutError) as exc:
        print("Nie mozna zweryfikowac PZN: ", type(exc).__name__, str(exc))
        entries = []
    path = ROOT / "participation_verified.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    old = payload.get("competitions", [])
    known_ids = {e.get("competitionId") for e in old}
    payload["competitions"] = old + [e for e in entries if e["competitionId"] not in known_ids]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Nowe konkursy z automatycznym potwierdzeniem PZN:", len(entries))

if __name__ == "__main__":
    main()
