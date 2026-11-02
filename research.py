import csv
import datetime as dt
import html
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = 'https://api.tech.ec.europa.eu/search-api/prod/rest/search'
PAGE_SIZE = 100
MAX_PAGES = 100
CSV_PATH = Path('calls.csv')

# Förderradar: Datenquellen
SOURCES = {
    "eu_sedia": True,
    "austria_film": False,
    "austria_culture": False,
    "austria_tenders": False,
    "germany": False,
    "switzerland": False,
    "festivals": False,
    "residencies": False,
    "paid_projects": False,
}

TEST_MODE = os.getenv('TEST_MODE', '0') != '0'  # Set TEST_MODE=1 to test without writing
KEYWORDS = {
    'Film & Kultur': ['film', 'documentary', 'cinema', 'audiovisual', 'culture', 'cultural', 'creative', 'arts', 'media'],
    'Feminismus & Queer': ['gender', 'feminist', 'women', 'lgbt', 'queer', 'equality', 'gender-based violence'],
    'Arbeit & Soziales': ['labour', 'labor', 'workers', 'employment', 'trade union', 'social rights'],
    'Klima & Umwelt': ['climate', 'environment', 'sustainability', 'biodiversity', 'green transition'],
    'Inklusion & Bildung': ['disability', 'accessibility', 'education', 'inclusion', 'inclusive'],
    'Demokratie & Gesellschaft': ['democracy', 'civil society', 'participation', 'human rights'],
    'Regionen & Sport': ['rural', 'regional development', 'community', 'sport'],
}

DEFAULT_COLUMNS = [
    'Titel',
    'Frist',
    'Themenbereich',
    'Link',
    'Quelle',
    'Beschreibung',
    'Relevanz',
    'Typ',
    'Ort',
    'Status',
    'Veranstaltungsdatum',
    'Honorar',
    'Förderfähigkeit',
]

COLUMN_ALIASES = {
    'Titel': ['titel', 'title', 'name'],
    'Frist': ['frist', 'deadline', 'einreichfrist', 'bewerbungsfrist'],
    'Themenbereich': ['themenbereich', 'thema', 'kategorie', 'category', 'topics'],
    'Link': ['link', 'url', 'website', 'ausschreibung'],
    'Quelle': ['quelle', 'source', 'fördergeber', 'foerdergeber'],
    'Beschreibung': ['beschreibung', 'description', 'summary'],
    'Relevanz': ['relevanz', 'score', 'priorität', 'prioritaet'],
    
    
    'Typ': ['typ', 'type', 'art'],
    'Ort': ['ort', 'location', 'standort'],
    'Status': ['status'],
    'Veranstaltungsdatum': [
        'veranstaltungsdatum', 'event_date'
    ],
    'Honorar': [
        'honorar', 'förderhöhe', 'foerderhoehe', 'amount'
    ],
    'Förderfähigkeit': [
        'förderfähigkeit', 'foerderfaehigkeit',
        'eligibility'
    ],

}

def first(value):
    if isinstance(value, list):
        return first(value[0]) if value else ''
    return str(value or '').strip()

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', first(value)))).strip()

def multipart(fields):
    boundary = '----Radar' + uuid.uuid4().hex
    chunks = []
    for key, value, content_type in fields:
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\nContent-Type: {content_type}\r\n\r\n{value}\r\n')
    chunks.append(f'--{boundary}--\r\n')
    return ''.join(chunks).encode('utf-8'), boundary

def fetch(page):
    query = {'bool': {'must': [
        {'terms': {'type': ['1', '2', '8']}},
        {'terms': {'status': ['31094501', '31094502']}},
    ]}}
    fields = [
        ('query', json.dumps(query), 'application/json'),
        ('languages', '["en"]', 'application/json'),
        ('displayLanguage', 'en', 'text/plain'),
    ]
    body, boundary = multipart(fields)
    params = urllib.parse.urlencode({'apiKey': 'SEDIA', 'text': '*', 'pageSize': PAGE_SIZE, 'pageNumber': page})
    request = urllib.request.Request(BASE + '?' + params, data=body, method='POST', headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': 'application/json', 'User-Agent': 'Foerderradar/1.0',
        'Referer': 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/',
        'Origin': 'https://ec.europa.eu',
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == 2:
                raise RuntimeError(f'API page {page} failed') from exc
            time.sleep(2 ** attempt)

def future_deadline(meta):
    today = dt.datetime.now(dt.timezone.utc).date()
    dates = []
    # closingDate in observed API responses is not reliably the submission deadline.
    for field in ('deadlineDate', 'submissionDeadline', 'deadlineDates'):
        raw = meta.get(field, [])
        for value in raw if isinstance(raw, list) else [raw]:
            for match in re.findall(r'\d{4}-\d{2}-\d{2}', str(value)):
                try:
                    date = dt.date.fromisoformat(match)
                    if date >= today:
                        dates.append(date)
                except ValueError:
                    pass
    return min(dates).isoformat() if dates else ''

# Strong signals in the title are preferred to generic words in descriptions.
HIGH_SIGNALS = [
    'documentary', 'film', 'cinema', 'audiovisual', 'creative europe',
    'creative innovation', 'media literacy', 'media freedom', 'journalism',
    'cultural', 'culture', 'artist', 'arts', 'gender-based violence',
    'women rights', 'women’s rights', 'lgbtiq', 'disability', 'accessibility',
    'civil society', 'human rights', 'democracy', 'trade union', 'labour rights',
]
MEDIUM_SIGNALS = [
    'participation', 'inclusive', 'inclusion', 'education', 'rural communities',
    'community-led', 'social economy', 'climate resilience', 'heritage',
    'gender', 'equality', 'sustainable cities', 'new european bauhaus',
]
EXCLUDE_TITLE = [
    'law enforcement', 'policing', 'aircraft', 'aviation', 'photovoltaic',
    'data centres', 'livestock', 'microbiome', 'pfas', 'wastewater',
    'solar radiation', 'forestry', 'forest and forestry', 'agriculture',
    'industrial electrification', 'research infrastructure',
    'biodiversity monitoring', 'ocean observing', 'clean technologies',
    'cybersecurity', 'cloud and mixed model',
]

def contains(text, word):
    return bool(re.search(r'(?<!\w)' + re.escape(word.casefold()) + r'(?!\w)', text.casefold()))

def topics_and_score(title, description):
    title_cf, desc_cf = title.casefold(), description.casefold()
    topics = []
    score = 0
    for category, words in KEYWORDS.items():
        title_hits = sum(contains(title_cf, w) for w in words)
        desc_hits = sum(contains(desc_cf, w) for w in words)
        if title_hits or desc_hits:
            topics.append(category)
            score += title_hits * 3 + min(desc_hits, 3)
    return topics, score

def classify(title, description):
    topics, score = topics_and_score(title, description)
    if any(contains(title, x) for x in EXCLUDE_TITLE):
        return topics, score, 'Niedrig'
    if any(contains(title, x) for x in HIGH_SIGNALS):
        return topics, score, 'Hoch'
    if any(contains(title, x) for x in MEDIUM_SIGNALS):
        return topics, score, 'Mittel'
    return topics, score, 'Niedrig'

def normalize_url(url):
    parsed = urllib.parse.urlsplit(url.strip())
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip('/'), parsed.query, ''))

def collect():
    found = {}
    total = None
    scanned = 0
    for page in range(1, MAX_PAGES + 1):
        data = fetch(page)
        if page == 1:
            total = int(data.get('totalResults') or 0)
            print('SEDIA-Gesamtzahl:', total, flush=True)
        rows = data.get('results') or []
        if not rows:
            break
        for item in rows:
            scanned += 1
            meta = item.get('metadata') or {}
            title = clean(meta.get('title')) or clean(item.get('summary'))
            description = clean(meta.get('description'))
            deadline = future_deadline(meta)
            topics, score, priority = classify(title, description)
            url = first(item.get('url')) or first(meta.get('url'))
            if not (title and deadline and topics and priority != 'Niedrig' and url.startswith('https://')):
                continue
            url = normalize_url(url)
            record = {
                'Titel': title, 'Frist': deadline, 'Themenbereich': ', '.join(topics),
                'Link': url, 'Quelle': 'EU Funding & Tenders (SEDIA)',
                'Beschreibung': description[:1200], 'Relevanz': priority,
            }
            old = found.get(url)
            if old is None or (deadline, -score) < (old['Frist'], 0):
                found[url] = record
        print(f'Seite {page}: {len(rows)} Ergebnisse', flush=True)
        if len(rows) < PAGE_SIZE:
            break
    if total is not None and scanned < total:
        raise RuntimeError(f'Incomplete scan: {scanned}/{total}; CSV not modified')
    print(f'Gescannte Datensätze: {scanned}; relevante Treffer: {len(found)}', flush=True)
    return sorted(found.values(), key=lambda r: (r['Frist'], r['Titel']))

def find_columns(fieldnames):
    normalized = {re.sub(r'\s+', '', name.strip().casefold()): name for name in fieldnames}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            key = re.sub(r'\s+', '', alias.casefold())
            if key in normalized:
                mapping[canonical] = normalized[key]
                break
    return mapping


def opportunity_key(record):
    """Unterscheidet Ausschreibungen auch bei gleicher URL."""
    url = normalize_url(record.get("Link", ""))
    title = clean(record.get("Titel", "")).casefold()
    deadline = str(record.get("Frist", "")).strip()
    return (url, title, deadline)

def save(records):
    existing = []
    fieldnames = DEFAULT_COLUMNS[:]

    if CSV_PATH.exists() and CSV_PATH.stat().st_size:
        with CSV_PATH.open(
            'r', encoding='utf-8-sig', newline=''
        ) as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise RuntimeError(
                    'CSV without header: refusing overwrite'
                )
            fieldnames = list(reader.fieldnames)
            existing = list(reader)

    mapping = find_columns(fieldnames)

    if 'Link' not in mapping or 'Titel' not in mapping:
        raise RuntimeError(
            'CSV requires recognizable title and URL columns'
        )

    # Titel, URL und Frist gemeinsam vergleichen.
    # So bleiben unterschiedliche Calls derselben
    # Website als eigene Einträge erhalten.
    by_key = {
        opportunity_key(r): r
        for r in records
    }

    existing_keys = set()
    enriched = 0

    for row in existing:
        canonical = {
            key: row.get(column, '')
            for key, column in mapping.items()
        }

        key = opportunity_key(canonical)
        existing_keys.add(key)

        record = by_key.get(key)

        if not record:
            continue

        # Nur bisher leere Felder ergänzen.
        # Bestehende Angaben niemals überschreiben.
        for field in DEFAULT_COLUMNS:
            column = mapping.get(field)
            value = record.get(field, '')

            if (
                column
                and value
                and not (row.get(column) or '').strip()
            ):
                row[column] = value
                enriched += 1

    new_rows = []

    for key, record in by_key.items():
        if key in existing_keys:
            continue

        row = {field: '' for field in fieldnames}

        for field, value in record.items():
            column = mapping.get(field)

            if column:
                row[column] = value

        if 'topic' in row:
            row['topic'] = record.get(
                'Themenbereich', ''
            )

        if 'status' in row:
            row['status'] = 'Zu prüfen'

        new_rows.append(row)
        existing_keys.add(key)

    print(
        f'Bestehend: {len(existing)}; '
        f'neu: {len(new_rows)}; '
        f'ergänzte Felder: {enriched}',
        flush=True
    )

    if TEST_MODE:
        print('TESTMODUS: CSV bleibt unverändert.')
        return

    if not new_rows and not enriched:
        print('Keine Änderungen.')
        return

    if CSV_PATH.exists():
        backup = CSV_PATH.with_name(
            'calls.backup.csv'
        )
        shutil.copy2(CSV_PATH, backup)
        print('Backup:', backup)

    fd, temp_name = tempfile.mkstemp(
        prefix='calls-',
        suffix='.csv',
        dir=str(CSV_PATH.parent)
    )

    try:
        with os.fdopen(
            fd, 'w', encoding='utf-8', newline=''
        ) as f:
            writer = csv.DictWriter(
                f, fieldnames=fieldnames
            )
            writer.writeheader()
            writer.writerows(existing)
            writer.writerows(new_rows)

        os.replace(temp_name, CSV_PATH)

    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)

    print(
        f'CSV aktualisiert: '
        f'{len(existing)} bestehende, '
        f'{len(new_rows)} neue',
        flush=True
    )



def main():
    from austria_film import collect_austria_film
    from opportunities import collect_opportunities

    # Bestehende EU-Recherche
    records = collect()

    # Zusätzliche Quellen
    film_calls = collect_austria_film()
    other_calls = collect_opportunities()

    records.extend(film_calls)
    records.extend(other_calls)

    print(f"Österreichische Filmförderungen: {len(film_calls)}")
    print(f"Weitere Chancen: {len(other_calls)}")
    print(f"Gesamte Treffer: {len(records)}")

    for r in records[:15]:
        print(
            r['Frist'], '|',
            r['Themenbereich'], '|',
            r['Titel'], '|',
            r['Link']
        )

    save(records)

if __name__ == '__main__':
    main()

