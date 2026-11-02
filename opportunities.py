
import datetime as dt

# Manuell erfasste Chancen.
# Später ergänzen wir automatische Datenquellen.
OPPORTUNITIES = [
    {
        "Titel": "ENCOURAGE Film Talents – Berlinale 2027",
        "Frist": "2026-11-29",
        "Themenbereich": "Film & Kultur",
        "Link": "https://www.instagram.com/encouragefilmtalents/",
        "Quelle": "ENCOURAGE Film Talents",
        "Beschreibung": (
            "Open Call für ein Get-together "
            "anlässlich der Berlinale 2027. "
            "Bewerbung über FilmFreeway."
        ),
        "Relevanz": "Hoch",
        "Typ": "Open Call",
        "Ort": "Berlin",
        "Status": "Zu prüfen",
    },
    {
        "Titel": "Queere Projektförderung – ländliche Regionen",
        "Frist": "2026-12-31",
        "Themenbereich": "Feminismus & Queer",
        "Link": "https://www.instagram.com/hirschfeldstiftung/",
        "Quelle": "Hirschfeld-Stiftung",
        "Beschreibung": (
            "Queere Projektförderung mit Fokus "
            "auf ländliche Regionen."
        ),
        "Relevanz": "Hoch",
        "Typ": "Projektförderung",
        "Ort": "Deutschland",
        "Status": "Zu prüfen",
    },
    {
        "Titel": "Filmmakers Connect – Wien",
        "Frist": "2026-11-04",
        "Themenbereich": "Film & Kultur",
        "Link": "https://www.instagram.com/styleandsoundhi/",
        "Quelle": "Style & Sound",
        "Beschreibung": (
            "Networking-Veranstaltung für "
            "Filmschaffende am 4. November 2026."
        ),
        "Relevanz": "Mittel",
        "Typ": "Networking",
        "Ort": "Wien",
        "Status": "Zu prüfen",
    },
]

def collect_opportunities():
    today = dt.date.today().isoformat()

    results = [
        item.copy()
        for item in OPPORTUNITIES
        if item["Frist"] >= today
    ]

    print(
        f"Manuelle Chancen: {len(results)}",
        flush=True
    )
    return results


if __name__ == "__main__":
    for item in collect_opportunities():
        print(
            item["Frist"],
            "|",
            item["Typ"],
            "|",
            item["Titel"]
        )
