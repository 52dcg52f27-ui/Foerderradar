import csv, datetime as dt, pathlib, hashlib
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).parent

def esc(s):
    return str(s).replace('\\','\\\\').replace('\n','\\n').replace(',','\\,').replace(';','\\;')

def fold(s):
    chunks=[]
    while len(s.encode('utf-8'))>73:
        i=1
        while i<len(s) and len(s[:i+1].encode('utf-8'))<=73:i+=1
        chunks.append(s[:i]);s=s[i:]
    chunks.append(s)
    return '\r\n '.join(chunks)

rows=list(csv.DictReader((ROOT/'calls.csv').open(encoding='utf-8-sig',newline='')))
now=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Foerderradar//DACH EU//DE','CALSCALE:GREGORIAN','METHOD:PUBLISH','X-WR-CALNAME:Foerderradar DACH + EU','X-WR-CALDESC:Gepruefte Foerderfristen']
count=0
for r in rows:
    if r.get('status','').strip().lower()!='verified':continue
    try: date=dt.date.fromisoformat(r['deadline'].strip())
    except ValueError:continue
    uid=hashlib.sha256((r['title']+r.get('url','')).encode()).hexdigest()[:24]+'@foerderradar'
    desc=' | '.join(filter(None,[r.get('topic',''),r.get('amount',''),r.get('eligibility',''),r.get('notes',''),r.get('url','')]))
    lines+=['BEGIN:VEVENT',f'UID:{uid}',f'DTSTAMP:{now}',f'DTSTART;VALUE=DATE:{date:%Y%m%d}',f'DTEND;VALUE=DATE:{date+dt.timedelta(days=1):%Y%m%d}',f'SUMMARY:{esc("Frist: "+r["title"])}',f'DESCRIPTION:{esc(desc)}']
    if r.get('url'):lines.append('URL:'+r['url'])
    for days in (14,3):
        lines+=['BEGIN:VALARM',f'TRIGGER:-P{days}D','ACTION:DISPLAY',f'DESCRIPTION:{esc("Foerderfrist: "+r["title"])}','END:VALARM']
    lines+=['END:VEVENT'];count+=1
lines+=['END:VCALENDAR']
(ROOT/'foerderradar.ics').write_bytes(('\r\n'.join(fold(x) for x in lines)+'\r\n').encode('utf-8'))
print('Generated',count,'verified events')
