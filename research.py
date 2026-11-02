import datetime as dt
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE_URL = 'https://api.tech.ec.europa.eu/search-api/prod/rest/search'
PAGE_SIZE = 100
MAX_PAGES = 200  # Bis zu 20.000 Datensaetze; Testmodus
KEYWORDS = {
    'Film & Kultur': ['film', 'filme', 'filmproduktion', 'filmförderung', 'dokumentarfilm', 'kino', 'kultur', 'kulturförderung', 'medienkunst', 'bewegtbild', 'audiovisuell', 'cinema', 'documentary', 'culture', 'creative', 'media', 'audiovisual'],
    'Feminismus & Queer': ['feminismus', 'gleichstellung', 'geschlechtergerechtigkeit', 'frauenrechte', 'queer', 'gender', 'women', 'feminist', 'equality', 'lgbti', 'lgbtq'],
    'Arbeit & Soziales': ['arbeitskampf', 'gewerkschaft', 'arbeitnehmer', 'arbeitsbedingungen', 'mitbestimmung', 'sozialpolitik', 'labour', 'labor', 'workers', 'employment', 'social inclusion', 'trade union'],
    'Klima & Umwelt': ['klima', 'klimaschutz', 'klimawandel', 'umwelt', 'nachhaltigkeit', 'biodiversität', 'bodenschutz', 'ortskernbelebung', 'climate', 'environment', 'biodiversity', 'soil', 'nature', 'sustainability'],
    'Inklusion & Bildung': ['behinderung', 'barrierefreiheit', 'inklusion', 'bildung', 'antidiskriminierung', 'jugend', 'disability', 'accessibility', 'inclusion', 'education', 'childhood', 'youth'],
    'Demokratie & Gesellschaft': ['demokratie', 'partizipation', 'aktivismus', 'zivilgesellschaft', 'menschenrechte', 'democracy', 'participation', 'civil society', 'human rights'],
    'Regionen & Sport': ['regionalentwicklung', 'gemeindeentwicklung', 'ländlicher raum', 'stadtentwicklung', 'sport', 'rural', 'regional development', 'community', 'local development'],
}

def first(value):
    if isinstance(value, list):
        return first(value[0]) if value else ''
    return str(value or '').strip()

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', first(value)))).strip()

def multipart(fields):
    boundary = '----Foerderradar' + uuid.uuid4().hex
    body = bytearray()
    for name, value, content_type in fields:
        body.extend((f'--{boundary}\r\n'
                     f'Content-Disposition: form-data; name="{name}"\r\n'
                     f'Content-Type: {content_type}\r\n\r\n'
                     f'{value}\r\n').encode('utf-8'))
    body.extend(f'--{boundary}--\r\n'.encode('utf-8'))
    return bytes(body), boundary

def fetch_page(page):
    params = urllib.parse.urlencode({
        'apiKey': 'SEDIA', 'text': '*', 'pageSize': PAGE_SIZE, 'pageNumber': page,
    })
    fields = [
        ('query', json.dumps({'bool': {'must': []}}), 'application/json'),
        ('languages', '["en", "de"]', 'application/json'),
        ('displayLanguage', 'en', 'text/plain'),
    ]
    body, boundary = multipart(fields)
    request = urllib.request.Request(
        f'{BASE_URL}?{params}', data=body,
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Accept': 'application/json',
            'User-Agent': 'Foerderradar/1.0',
            'Referer': 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/',
            'Origin': 'https://ec.europa.eu',
        }, method='POST',
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        return json.load(response)

def extract_deadline(metadata, today):
    dates = []
    for key in ('deadlineDate', 'closingDate', 'deadline', 'submissionDeadline',
                'deadlineDates', 'submissionDeadlineDate'):
        value = metadata.get(key)
        values = value if isinstance(value, list) else [value]
        for raw in values:
            for match in re.findall(r'\d{4}-\d{2}-\d{2}', str(raw or '')):
                try:
                    date = dt.date.fromisoformat(match)
                    if date >= today:
                        dates.append(date)
                except ValueError:
                    pass
    return min(dates).isoformat() if dates else ''

def main():
    today = dt.date.today()
    found = {}
    scanned = 0
    total = None
    for page in range(1, MAX_PAGES + 1):
        try:
            data = fetch_page(page)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f'Seite {page} fehlgeschlagen: {exc}')
            break
        results = data.get('results') or []
        if page == 1:
            total = data.get('totalResults')
            print('Gesamtzahl laut API:', total)
            print('Metadatenfelder:', sorted((results[0].get('metadata') or {}).keys()) if results else [])
            if results:
                m = results[0].get('metadata') or {}
                print('Beispiel Status/Typ/Frist:', {k: m.get(k) for k in ('status', 'type', 'deadlineDate', 'closingDate')})
        if not results:
            print('Keine weiteren Ergebnisse.')
            break
        scanned += len(results)
        for item in results:
            metadata = item.get('metadata') or {}
            title = clean(metadata.get('title')) or clean(item.get('summary'))
            description = clean(metadata.get('description'))
            combined = (title + ' ' + description).lower()
            topics = [category for category, words in KEYWORDS.items()
                      if any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', combined) for word in words)]
            deadline = extract_deadline(metadata, today)
            results:
            metadata = item.get('metadata') or {}
            title = clean(metadata.get('title')) or clean(item.get('summary'))
            description = clean(metadata.get('description'))
            combined = (title + ' ' + description).lower()
            topics = [category for category, words in KEYWORDS.items()
                      if any(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', combined) for word in words)]
            deadline = extract_deadline(metadata, today)
            url = first(item.get('url')) or first(metadata.get('url'))
            if title and topics and deadline and url.startswith('https://'):
                found[url] = {
                    'title': title, 'deadline': deadline, 'url': url,
                    'topic': ', '.join(topics),
                    'status': first(metadata.get('status')),
                    'type': first(metadata.get('type')),
                }
        print(f'Seite {page}: {len(results)} Datensaetze; insgesamt {scanned}; Treffer {len(found)}')
        if len(results) < PA
            
            url = first(item.get('url')) or first(metadata.get('url'))
            if title and topics and deadline and url.startswith('https://'):
                found[url] = {
                    'title': title, 'deadline': deadline, 'url': url,
                    'topic': ', '.join(topics),
                    'status': first(metadata.get('status')),
                    'type': first(metadata.get('type')),
                }
        print(f'Seite {page}: {len(results)} Datensaetze; insgesamt {scanned}; Treffer {len(found)}')
        if len(results) < PAGE_SIZE or (isinstance(total, int) and scanned >= total):
            break
        time.sleep(0.15)
    calls = sorted(found.values(), key=lambda c: (c['deadline'], c['title']))
    print(f'\nGescannt: {scanned} | Passende Calls mit zukuenftiger Frist: {len(calls)}')
    for call in calls[:30]:
        print(f"{call['deadline']} | {call['topic']} | {call['title']} | {call['url']}")
    print('TESTLAUF: calls.csv wurde nicht veraendert.')
    print('Hinweis: Treffer sind noch nicht auf Foerderfaehigkeit und offenen Status geprueft.')

if __name__ == '__main__':
    main()