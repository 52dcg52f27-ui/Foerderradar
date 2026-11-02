
import datetime as dt
import html
import json
import re
import time
import urllib.parse
import urllib.request
import uuid

# EU-Foerderradar
# Testmodus: calls.csv wird nicht veraendert.

BASE_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
PAGE_SIZE = 100
MAX_PAGES = 100

KEYWORDS = {
    "Film & Kultur": [
        "film", "dokumentarfilm", "filmproduktion",
        "kino", "kultur", "medienkunst", "bewegtbild",
        "documentary", "cinema", "culture",
        "creative", "audiovisual", "media"
    ],
    "Feminismus & Queer": [
        "feminismus", "gleichstellung", "frauenrechte",
        "geschlechtergerechtigkeit", "queer",
        "gender", "feminist", "equality",
        "women", "lgbti", "lgbtq"
    ],
    "Arbeit & Soziales": [
        "arbeitskampf", "gewerkschaft",
        "arbeitnehmer", "mitbestimmung",
        "sozialpolitik", "arbeitsbedingungen",
        "labour", "labor", "workers",
        "employment", "trade union"
    ],
    "Klima & Umwelt": [
        "klima", "klimaschutz", "umwelt",
        "nachhaltigkeit", "biodiversität",
        "bodenschutz", "ortskernbelebung",
        "climate", "environment", "soil",
        "biodiversity", "sustainability"
    ],
    "Inklusion & Bildung": [
        "behinderung", "barrierefreiheit",
        "inklusion", "bildung", "antidiskriminierung",
        "disability", "accessibility",
        "inclusion", "education", "youth"
    ],
    "Demokratie & Gesellschaft": [
        "demokratie", "partizipation",
        "zivilgesellschaft", "menschenrechte",
        "aktivismus", "democracy",
        "participation", "civil society",
        "human rights"
    ],
    "Regionen & Sport": [
        "regionalentwicklung", "gemeindeentwicklung",
        "ländlicher raum", "stadtentwicklung",
        "sport", "rural", "regional development",
        "community", "local development"
    ]
}


def first(value):
    if isinstance(value, list):
        return first(value[0]) if value else ""
    return str(value or "").strip()


def clean(value):
    text = first(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def multipart(fields):
    boundary = "----Foerderradar" + uuid.uuid4().hex
    body = bytearray()

    for name, value, content_type in fields:
        part = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
            f"{value}\r\n"
        )
        body.extend(part.encode("utf-8"))

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), boundary


def fetch_page(page):
    params = urllib.parse.urlencode({
        "apiKey": "SEDIA",
        "text": "*",
        "pageSize": PAGE_SIZE,
        "pageNumber": page
    })

    fields = [
        (
            "query",
            json.dumps({"bool": {"must": []}}),
            "application/json"
        ),
        ("languages", '["en", "de"]', "application/json"),
        ("displayLanguage", "en", "text/plain")
    ]

    body, boundary = multipart(fields)

    request = urllib.request.Request(
        BASE_URL + "?" + params,
        data=body,
        headers={
            "Content-Type": (
                f"multipart/form-data; boundary={boundary}"
            ),
            "Accept": "application/json",
            "User-Agent": "Foerderradar/1.0",
            "Referer": (
                "https://ec.europa.eu/info/"
                "funding-tenders/opportunities/portal/"
            ),
            "Origin": "https://ec.europa.eu"
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request, timeout=45
    ) as response:
        return json.load(response)


def extract_deadline(metadata, today):
    dates = []

    keys = [
        "deadlineDate",
        "closingDate",
        "deadline",
        "submissionDeadline",
        "deadlineDates",
        "submissionDeadlineDate"
    ]

    for key in keys:
        value = metadata.get(key)
        values = value if isinstance(value, list) else [value]

        for raw in values:
            matches = re.findall(
                r"\d{4}-\d{2}-\d{2}",
                str(raw or "")
            )

            for match in matches:
                try:
                    date = dt.date.fromisoformat(match)
                    if date >= today:
                        dates.append(date)
                except ValueError:
                    pass

    return min(dates).isoformat() if dates else ""


def get_topics(text):
    text = text.casefold()
    topics = []

    for category, words in KEYWORDS.items():
        for word in words:
            pattern = (
                r"(?<!\w)"
                + re.escape(word.casefold())
                + r"(?!\w)"
            )

            if re.search(pattern, text):
                topics.append(category)
                break

    return topics


def main():
    today = dt.date.today()

    found = {}
    scanned = 0
    topic_matches = 0
    deadline_matches = 0
    both_matches = 0
    total = None

    print("Foerderradar gestartet", flush=True)
    print("Datum:", today, flush=True)

    for page in range(1, MAX_PAGES + 1):

        try:
            data = fetch_page(page)
        except Exception as error:
            print(
                "API-Fehler auf Seite",
                page,
                ":",
                error,
                flush=True
            )
            raise

        results = data.get("results") or []

        if page == 1:
            total = data.get("totalResults")
            print("API-Gesamtzahl:", total, flush=True)

            if results:
                example = results[0]
                metadata = example.get("metadata") or {}

                print(
                    "Beispiel Titel:",
                    clean(metadata.get("title")),
                    flush=True
                )

                print(
                    "Beispiel Fristen:",
                    {
                        "deadlineDate": metadata.get("deadlineDate"),
                        "closingDate": metadata.get("closingDate")
                    },
                    flush=True
                )

                print(
                    "Beispiel Status:",
                    metadata.get("status"),
                    flush=True
                )

        if not results:
            print("Keine weiteren Ergebnisse.", flush=True)
            break

        for item in results:
            scanned += 1

            metadata = item.get("metadata") or {}

            title = (
                clean(metadata.get("title"))
                or clean(item.get("summary"))
            )

            description = clean(metadata.get("description"))

            combined = title + " " + description

            topics = get_topics(combined)

            deadline = extract_deadline(metadata, today)

            url = (
                first(item.get("url"))
                or first(metadata.get("url"))
            )

            if topics:
                topic_matches += 1

            if deadline:
                deadline_matches += 1

            if topics and deadline:
                both_matches += 1

            # Diagnose der ersten drei Datensaetze
            if scanned <= 3:
                print(
                    "DEBUG:",
                    title[:60],
                    "| Themen:", topics,
                    "| Frist:", deadline,
                    "| Rohfrist:", metadata.get("deadlineDate"),
                    "| Closing:", metadata.get("closingDate"),
                    flush=True
                )

            if (
                title
                and topics
                and deadline
                and url.startswith("https://")
            ):
                found[url] = {
                    "title": title,
                    "deadline": deadline,
                    "url": url,
                    "topic": ", ".join(topics),
                    "status": first(metadata.get("status")),
                    "type": first(metadata.get("type"))
                }

        print(
            f"Seite {page}: "
            f"{len(results)} Datensaetze | "
            f"Gescannt: {scanned} | "
            f"Treffer: {len(found)}",
            flush=True
        )

        if len(results) < PAGE_SIZE:
            break

        if isinstance(total, int) and scanned >= total:
            break

        time.sleep(0.1)

    calls = sorted(
        found.values(),
        key=lambda call: (
            call["deadline"],
            call["title"]
        )
    )

    print("\n===== AUSWERTUNG =====", flush=True)
    print("Datensaetze:", scanned)
    print("Thematisch passend:", topic_matches)
    print("Zukuenftige Frist:", deadline_matches)
    print("Thema und Frist:", both_matches)
    print("Gueltige Treffer mit Link:", len(calls))

    for call in calls[:30]:
        print(
            call["deadline"],
            "|",
            call["topic"],
            "|",
            call["title"],
            "|",
            call["url"]
        )

    print("\nTESTMODUS: calls.csv bleibt unveraendert.")
    print(
        "Hinweis: Treffer sind noch nicht auf "
        "Foerderfaehigkeit und offenen Status geprueft."
    )


if __name__ == "__main__":
    main()
