#!/usr/bin/env python3
"""Import XMLTV from a source you are authorized to use. Python standard library only."""
import sys, json, gzip, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CHANNELS={'tvp sport':'TVP Sport','eurosport 1':'Eurosport 1','eurosport 2':'Eurosport 2','polsat sport 1':'Polsat Sport 1','polsat sport 2':'Polsat Sport 2','polsat sport 3':'Polsat Sport 3','polsat sport':'Polsat Sport','tvp 1':'TVP 1','tvp 2':'TVP 2'}
# Conservative: only explicitly named Polish participants. Ambiguous EPG entries are excluded.
POLISH=re.compile(r'\b(polska|polski|polacy|polaków|świątek|swiatek|hurkacz|linette|fręch|frech|chwalińska|chwalinska|majchrzak|fręch|zieliński|zielinski|reprezentacja polski|zakopane|wisła|wisla)\b',re.I)
SPORTS={'tenis':re.compile(r'\b(tenis|wta|atp|wimbledon|roland garros)\b',re.I),'siatkowka':re.compile(r'\b(siatkówka|siatkowka|volleyball)\b',re.I),'pilka':re.compile(r'\b(piłka nożna|pilka nozna|football|liga narodów|liga narodow|eliminacje mistrzostw świata)\b',re.I),'skoki':re.compile(r'\b(skoki narciarskie|skoki|ski jumping)\b',re.I)}

def parse_time(s):
    m=re.match(r'(\d{14})\s*([+-]\d{4})?',s or '')
    if not m:return None
    dt=datetime.strptime(m.group(1),'%Y%m%d%H%M%S')
    if m.group(2):
        z=m.group(2); dt=dt.replace(tz=timezone((1 if z[0]=='+' else -1)*timedelta(hours=int(z[1:3]),minutes=int(z[3:]))))
    else:dt=dt.replace(tz=ZoneInfo('Europe/Warsaw'))
    return dt.astimezone(ZoneInfo('Europe/Warsaw'))

def main(url):
    req=urllib.request.Request(url,headers={'User-Agent':'SportTVPolska/0.2 (personal EPG reader)'})
    with urllib.request.urlopen(req,timeout=35) as r: raw=r.read(25_000_000)
    if raw[:2]==b'\x1f\x8b':raw=gzip.decompress(raw)
    root=ET.fromstring(raw)
    names={}
    for c in root.findall('channel'):
        names[c.get('id')]=' '.join((n.text or '') for n in c.findall('display-name')).lower()
    now=datetime.now(ZoneInfo('Europe/Warsaw'))
    events=[]
    for p in root.findall('programme'):
        raw_name=names.get(p.get('channel'),'')
        channel=next((v for k,v in CHANNELS.items() if re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)',raw_name)),None)
        if not channel:continue
        start=parse_time(p.get('start'));end=parse_time(p.get('stop'))
        if not start or start<now-timedelta(hours=3) or start>now+timedelta(days=7):continue
        title=' '.join((n.text or '') for n in p.findall('title'))
        desc=' '.join((n.text or '') for n in p.findall('desc'))
        blob=title+' '+desc
        sport=next((k for k,v in SPORTS.items() if v.search(blob)),None)
        if not sport or not POLISH.search(blob):continue
        if sport=='pilka' and not re.search(r'(polska|reprezentacja polski|polski\s*[-–:]|[-–:]\s*polska)',blob,re.I):continue
        if sport=='pilka' and re.search(r'(ekstraklasa|legia|lech poznań|raków|jagiellonia)',blob,re.I):continue
        # Do not mistake replays for live transmissions.
        if re.search(r'(powtórka|powtorka|retransmisja|skrót|skrot|podsumowanie|magazyn)',blob,re.I):continue
        events.append({'start':start.isoformat(),'end':end.isoformat() if end else None,'sport':sport,'name':title,'channel':channel,'description':desc[:250],'verifiedLive':False})
    events.sort(key=lambda x:x['start'])
    out={'updatedAt':now.isoformat(),'source':'XMLTV (zewnętrzne EPG; transmisje niezweryfikowane jako na żywo)','events':events}
    Path(__file__).with_name('events.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Zapisano {len(events)} pozycji do events.json')
if __name__=='__main__':
    if len(sys.argv)!=2:sys.exit('Użycie: python update_epg.py ADRES_PLIKU_XMLTV')
    main(sys.argv[1])
