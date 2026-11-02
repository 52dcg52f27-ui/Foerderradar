import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
import uuid

BASE = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
PAGE_SIZE = 100
MAX_PAGES = 5  # Diagnose: erst wenige Seiten prüfen

KEYWORDS = {
    "Film & Kultur": ["film", "dokumentarfilm", "kino", "kultur", "documentary", "cinema", "culture", "audiovisual", "creative"],
    "Feminismus & Queer": ["feminismus", "gleichstellung", "frauenrechte", "gender", "feminist", "equality", "lgbtq", "queer"],
    "Arbeit & Soziales": ["gewerkschaft", "arbeitskampf", "arbeitnehmer", "labour", "labor", "workers", "employment", "trade union"],
    "Klima & Umwelt": ["klima", "umwelt", "nachhaltigkeit", "biodiversität", "climate", "environment", "sustainability", "biodiversity"],
    "Inklusion & Bildung": ["behinderung", "inklusion", "bildung", "barrierefreiheit", "disability", "accessibility", "education", "inclusion"],
    "Demokratie & Gesellschaft": ["demokratie", "zivilgesellschaft", "partizipation", "democracy", "civil society", "participation"],
    "Regionen & Sport": ["regionalentwicklung", "ländlicher raum", "sport", "rural", "regional development", "community"],
}

def first(value):
    if isinstance(value, list):
        return first(value[0]) if value else ""
    return str(value or "").strip()

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", first(value)))).strip()

def multipart(fields):
    boundary = "----Radar" + uuid.uuid4().hex
    chunks = []
    for key, value, content_type in fields:
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n{value}\r\n"
        )
    chunks.append(f"--{boundary}--\r\n")
    return "".join(chunks).encode("utf-8"), boundary

def fetch(page):
    query = {
        "bool": {
            "must": [
                {"terms": {"type": ["1", "2", "8"]}},
                {"terms": {"status": ["31094501", "31094502"]}},
            ]
        }
    }

    fields = [
        ("query", json.dumps(query), "application/json"),
        ("languages", '["en"]', "application/json"),
        ("displayLanguage", "en", "text/plain"),
    ]

    body, boundary = multipart(fields)

    params = urllib.parse.urlencode({
        "apiKey": "SEDIA",
        "text": "*",
        "pageSize": PAGE_SIZE,
        "pageNumber": page,
    })

    request = urllib.request.Request(
        BASE + "?" + params,
        data=body,
        method="POST",
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "Foerderradar/diagnostic",
            "Referer": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/",
            "Origin": "https://ec.europa.eu",
        },
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def future_deadline(meta):
    today = dt.date.today()
    dates = []
    for field in ("deadlineDate", "closingDate", "submissionDeadline", "deadlineDates"):
        raw = meta.get(field, [])
        for value in raw if isinstance(raw, list) else [raw]:
            for match in re.findall(r"\d{4}-\d{2}-\d{2}", str(value)):
                try:
                    date = dt.date.fromisoformat(match)
                    if date >= today:
                        dates.append(date)
                except ValueError:
                    pass
    return min(dates).isoformat() if dates else ""

def main():
    seen = 0
    topics_count = 0
    deadline_count = 0
    matches = {}
    for page in range(1, MAX_PAGES + 1):
        data = fetch(page)
        rows = data.get("results") or []
        if page == 1:
            print("SEDIA-Gesamtzahl:", data.get("totalResults"), flush=True)
            print("API-Warnungen:", data.get("warnings"), flush=True)
        if not rows:
            break
        for item in rows:
            seen += 1
            meta = item.get("metadata") or {}
            title = clean(meta.get("title")) or clean(item.get("summary"))
            description = clean(meta.get("description"))
            combined = (title + " " + description).casefold()
            topics = [
                category for category, words in KEYWORDS.items()
                if any(re.search(r"(?<!\w)" + re.escape(word.casefold()) + r"(?!\w)", combined) for word in words)
            ]
            deadline = future_deadline(meta)
            if topics:
                topics_count += 1
            if deadline:
                deadline_count += 1
            if seen <= 5:
                print("BEISPIEL:", title[:90], flush=True)
                print("  Typ:", meta.get("type"), "Status:", meta.get("status"), flush=True)
                print("  Frist roh:", meta.get("deadlineDate"), "Closing:", meta.get("closingDate"), flush=True)
                print("  Frist erkannt:", deadline, "Themen:", topics, flush=True)
            if title and topics and deadline:
                url = first(item.get("url")) or first(meta.get("url"))
                if url.startswith("https://"):
                    matches[url] = (deadline, title, topics)
        print(f"Seite {page}: {len(rows)} Ergebnisse", flush=True)
        if len(rows) < PAGE_SIZE:
            break
    print("===== DIAGNOSE =====", flush=True)
    print("Gescannte Datensaetze:", seen, flush=True)
    print("Thematisch passend:", topics_count, flush=True)
    print("Zukuenftige Frist erkannt:", deadline_count, flush=True)
    print("Treffer mit Thema, Frist und Link:", len(matches), flush=True)
    for url, (deadline, title, topics) in list(sorted(matches.items(), key=lambda x: x[1][0]))[:15]:
        print(deadline, "|", ", ".join(topics), "|", title, "|", url)
    print("TESTMODUS: calls.csv bleibt unveraendert.", flush=True)

if __name__ == "__main__":
    main()