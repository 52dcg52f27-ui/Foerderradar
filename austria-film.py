
import datetime as dt

def collect_austria_film():
    today = dt.date.today().isoformat()

    calls = [
        {
            "Titel": "ÖFI – Verwertung und Weiterbildung",
            "Frist": "2026-11-09",
            "Themenbereich": "Film & Kultur",
            "Link": "https://filminstitut.at/einreichtermine",
            "Quelle": "Österreichisches Filminstitut",
            "Beschreibung": "SVM 1: Verbreitung, Marketing, Verwertung und berufliche Weiterbildung.",
            "Relevanz": "Hoch",
        },
        {
            "Titel": "Bund – Förderung von Filminstitutionen",
            "Frist": "2026-11-15",
            "Themenbereich": "Film & Kultur",
            "Link": "https://www.bmwkms.gv.at/themen/kunst-und-kultur/sparten/film/foerderungen.html",
            "Quelle": "BMWKMS Österreich",
            "Beschreibung": "Förderung der Jahrestätigkeit filmkultureller Institutionen.",
            "Relevanz": "Mittel",
        },
        {
            "Titel": "ÖFI – Stoffentwicklung",
            "Frist": "2026-11-24",
            "Themenbereich": "Film & Kultur",
            "Link": "https://filminstitut.at/einreichtermine",
            "Quelle": "Österreichisches Filminstitut",
            "Beschreibung": "Einreichtermin für Stoffentwicklung.",
            "Relevanz": "Hoch",
        },
        {
            "Titel": "ÖFI – Herstellung und Projektentwicklung",
            "Frist": "2026-12-09",
            "Themenbereich": "Film & Kultur",
            "Link": "https://filminstitut.at/einreichtermine",
            "Quelle": "Österreichisches Filminstitut",
            "Beschreibung": "Einreichtermin für Herstellung und Projektentwicklung.",
            "Relevanz": "Hoch",
        },
        {
            "Titel": "Bund – Startstipendium Filmkunst",
            "Frist": "2027-01-31",
            "Themenbereich": "Film & Kultur",
            "Link": "https://www.bmwkms.gv.at/themen/kunst-und-kultur/service-kunst-und-kultur/kunst-und-kultur-ausschreibungen/startstipendien_filmkunst.html",
            "Quelle": "BMWKMS Österreich",
            "Beschreibung": "Startstipendium für Nachwuchsfilmschaffende.",
            "Relevanz": "Hoch",
        },
    ]

    return [call for call in calls if call["Frist"] >= today]
