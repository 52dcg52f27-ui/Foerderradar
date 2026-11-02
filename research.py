
import datetime as dt
import json
import re
import urllib.request
import uuid

API = (
    "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
    "?apiKey=SEDIA&text=*&pageSize=100&pageNumber=1"
)

KEYWORDS = {
    "Film & Kultur": [
        "film", "cinema", "documentary", "culture",
        "creative", "media", "audiovisual"
    ],
    "Feminismus & Queer": [
        "gender", "women", "feminist", "equality",
        "lgbti", "lgbtq", "queer"
    ],
    "Arbeit & Soziales": [
        "labour", "labor", "workers", "employment",
        "social inclusion", "trade union"
    ],
    "Klima & Umwelt": [
        "climate", "environment", "biodiversity",
        "soil", "nature", "sustainability"
    ],
    "Inklusion & Bildung": [
        "disability", "accessibility", "inclusion",
        "education", "childhood", "youth"
    ],
    "Regionen & Sport": [
        "rural", "regional development", "sport",
        "community", "local development"
    ],
}

def multipart(fields):
    boundary = "----Foerderradar" + uuid.uuid4().hex
    body = bytearray()

    for name, value, content_type in fields:
        body.extend(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
            f"{value}\r\n".encode("utf-8")
        )

    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), boundary

def first(value):
    if isinstance(value, list):
        return first(value[0]) if value else ""
    return str(value or "").strip()

def extract_deadline(metadata):
    for key in (
        "deadlineDate", "deadline", "submissionDeadline",
        "deadlineDates", "submissionDeadlineDate"
    ):
        value = first(metadata.get(key))
        match = re.search(r"\d{4}-\d{2}-\d{2}", value)
        if match:
            try:
                date = dt.date.fromisoformat(match.group())
                if date >= dt.date.today():
                    return date.isoformat()
            except ValueError:
                pass
    return ""

def main():
    query = {
        "bool": {
            "must": [
                {"terms": {"type": ["1", "2", "8"]}},
                {"terms": {
                    "status": [
                        "31094501",
                        "31094502",
                        "31094503"
                    ]
                }}
            ]
        }
    }

    fields = [
        ("query", json.dumps(query), "application/json"),
        ("languages", '["en"]', "application/json"),
        ("displayLanguage", "en", "text/plain"),
    ]

    body, boundary = multipart(fields)

    request = urllib.request.Request(
        API,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "Foerderradar/1.0",
            "Referer": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/",
            "Origin": "https://ec.europa.eu",
        },
        method="POST",
    )


    with urllib.request.urlopen(request, timeout=40) as response:
        data = json.load(response)

    print("Antwortfelder:", list(data.keys()))
    print("Gesamtzahl:", data.get("totalResults"))
    print(
        "Erster Datensatz:",
        json.dumps(data.get("results", [])[:1], ensure_ascii=False)[:2500]
    )

    results = data.get("results", [])
il
    
    print("EU-Datensaetze abgerufen:", len(results))

    found = []

    for item in results:
        metadata = item.get("metadata") or {}
        title = first(metadata.get("title"))
        description = first(metadata.get("description"))
        combined = (title + " " + description).lower()

        topics = [
            category
            for category, words in KEYWORDS.items()
            if any(word in combined for word in words)
        ]

        deadline = extract_deadline(metadata)
        url = first(item.get("url"))

        if title and topics and deadline and url.startswith("https://"):
            found.append({
                "title": title,
                "deadline": deadline,
                "url": url,
                "topic": ", ".join(topics),
            })

    print("Passende Calls mit Frist:", len(found))

    for call in found[:15]:
        print(
            call["deadline"],
            "|",
            call["topic"],
            "|",
            call["title"],
            "|",
            call["url"],
        )

    print("TESTLAUF: calls.csv wurde nicht verändert.")

if __name__ == "__main__":
    main()
