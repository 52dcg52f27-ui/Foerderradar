
import csv
import datetime as dt
import hashlib
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
CSV_PATH = ROOT / "calls.csv"
ICS_PATH = ROOT / "foerderradar.ics"

TODAY = dt.datetime.now(
    dt.timezone.utc
).date()

NOW = dt.datetime.now(
    dt.timezone.utc
).strftime("%Y%m%dT%H%M%SZ")


def get(row, *names):
    """Liest deutsche und englische Spalten."""
    normalized = {
        str(k).strip().casefold(): v
        for k, v in row.items()
        if k is not None
    }

    for name in names:
        value = normalized.get(name.casefold(), "")
        if value is not None and str(value).strip():
            return str(value).strip()

    return ""


def escape(value):
    """Sonderzeichen für ICS formatieren."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold(line):
    """ICS-Zeilen auf maximal 75 Bytes falten."""
    parts = []
    current = ""

    for char in line:
        candidate = current + char

        if len(candidate.encode("utf-8")) > 75:
            parts.append(current)
            current = " " + char
        else:
            current = candidate

    parts.append(current)
    return "\r\n".join(parts)


def parse_date(value):
    """Akzeptiert ISO-Daten und Datumsangaben."""
    value = str(value).strip()

    for pattern in (
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ):
        try:
            return dt.datetime.strptime(
                value[:10], pattern
            ).date()
        except ValueError:
            pass

    match = re.search(
        r"\d{4}-\d{2}-\d{2}", value
    )

    if match:
        try:
            return dt.date.fromisoformat(
                match.group()
            )
        except ValueError:
            pass

    return None


def create_calendar():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV nicht gefunden: {CSV_PATH}"
        )

    with CSV_PATH.open(
        encoding="utf-8-sig",
        newline=""
    ) as file:
        rows = list(csv.DictReader(file))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Foerderradar//DACH EU//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Foerderradar DACH + EU",
        "X-WR-CALDESC:Foerderungen und Ausschreibungen",
        "X-PUBLISHED-TTL:PT12H",
    ]

    count = 0
    skipped = 0
    seen = set()

    for row in rows:
        title = get(row, "Titel", "title")
        deadline = get(row, "Frist", "deadline")
        url = get(row, "Link", "url")
        topic = get(
            row, "Themenbereich", "topic"
        )
        source = get(row, "Quelle", "source")
        description = get(
            row, "Beschreibung",
            "description", "notes"
        )
        relevance = get(
            row, "Relevanz", "priority"
        )
        status = get(
            row, "Status", "status"
        ).casefold()

        if not title or not deadline:
            skipped += 1
            continue

        if status in (
            "rejected", "archived",
            "abgelehnt", "archiviert",
            "ungültig", "invalid"
        ):
            skipped += 1
            continue

        date = parse_date(deadline)

        if date is None or date < TODAY:
            skipped += 1
            continue

        key = (
            title.casefold(),
            date.isoformat(),
            url
        )

        if key in seen:
            skipped += 1
            continue

        seen.add(key)

        uid = (
            hashlib.sha256(
                repr(key).encode("utf-8")
            ).hexdigest()[:24]
            + "@foerderradar"
        )

        details = [
            topic,
            f"Quelle: {source}" if source else "",
            f"Relevanz: {relevance}" if relevance else "",
            f"Status: {status}" if status else "",
            get(row, "Typ", "type"),
            get(row, "Ort", "location"),
            get(row, "Honorar", "amount"),
            get(row, "Förderfähigkeit", "eligibility"),
            description,
            url,
        ]

        event_description = "\n".join(
            x for x in details if x
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{NOW}",
            f"DTSTART;VALUE=DATE:{date:%Y%m%d}",
            (
                "DTEND;VALUE=DATE:"
                f"{date + dt.timedelta(days=1):%Y%m%d}"
            ),
            f"SUMMARY:{escape('Frist: ' + title)}",
            f"DESCRIPTION:{escape(event_description)}",
        ])

        if url.startswith(
            ("https://", "http://")
        ):
            lines.append(f"URL:{url}")

        for days in (14, 3):
            lines.extend([
                "BEGIN:VALARM",
                f"TRIGGER:-P{days}D",
                "ACTION:DISPLAY",
                (
                    "DESCRIPTION:"
                    + escape("Förderfrist: " + title)
                ),
                "END:VALARM",
            ])

        lines.append("END:VEVENT")
        count += 1

    lines.append("END:VCALENDAR")

    content = (
        "\r\n".join(
            fold(line) for line in lines
        )
        + "\r\n"
    )

    if count == 0:
        raise RuntimeError(
            "Keine Kalendereinträge erstellt. "
            "CSV und Spaltennamen prüfen. "
            "Bestehender Kalender bleibt erhalten."
        )

    ICS_PATH.write_bytes(
        content.encode("utf-8")
    )

    print(f"CSV-Einträge insgesamt: {len(rows)}")
    print(f"Kalendereinträge erstellt: {count}")
    print(f"Übersprungene Einträge: {skipped}")
    print(f"Kalender gespeichert: {ICS_PATH}")


if __name__ == "__main__":
    create_calendar()

