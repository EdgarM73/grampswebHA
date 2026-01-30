
# HACS Default Repository Einreichung

Aktueller Stand: v2026.01.24

Anleitung zur Einreichung von Gramps HA in die offiziellen HACS-Repositories.

## Voraussetzungen (bereits erfüllt ✅)

- ✅ GitHub Repository: https://github.com/EdgarM73/grampswebDates
- ✅ `hacs.json` vorhanden und korrekt
- ✅ `manifest.json` mit korrekter Struktur
- ✅ Release v2026.1.1 Tag erstellt
- ✅ README.md mit Installationsanleitung
- ✅ Icon/Logo (icon.png)
- ✅ Übersetzungen in mehreren Sprachen


## Schritt 1: GitHub Release erstellen

⚠️ **Wichtig:** HACS benötigt einen offiziellen GitHub Release (nicht nur ein Tag)!

1. Gehe zu: https://github.com/EdgarM73/grampswebDates/releases/new

2. **Einstellungen:**
  - **Choose a tag:** v2026.1.1 (aus Dropdown wählen)
  - **Release title:** `v2026.1.1 - Gramps HA Integration`
  - **Description:** (siehe unten)

3. **Release-Beschreibung:**

```markdown
# Gramps HA Integration v2026.1.1

Aktuelle Version der Gramps Web Integration für Home Assistant.

## Features

- 🎂 Zeigt die nächsten 6 ( konfigurierbar ) Geburtstage an (je 7 Sensoren pro Geburtstag)
- 🪦 Optional: Zeigt die nächsten 6 Gedenktage/Todestage an (je 7 Sensoren)
- 💍 Optional: Zeigt die nächsten 6 Hochzeitstage/Jahrestage an (je 8 Sensoren)
- 📅 Berechnet automatisch die Tage bis zum nächsten Ereignis
- 🎉 Zeigt das Alter der Person am kommenden Geburtstag
- 🔄 Automatische Aktualisierung alle 6 Stunden
- 🔔 Benachrichtigung immer genau 1 Tag vor dem Ereignis (nur einmal)
- 🖼️ Lädt Profilbilder aus Gramps Web herunter (falls vorhanden)
- 🔗 Direkt-Links zu Personen und Familien in Gramps Web
- 🔐 Unterstützt authentifizierte und öffentliche Gramps Web Instanzen
- 🌍 Mehrsprachig: Deutsch, Englisch, Französisch, Italienisch, Bosnisch
```

## Sensoren

Die Integration erstellt für die nächsten 10 Geburtstage, Todestage und Hochzeitstage jeweils 7 bzw. 8 Sensoren pro Ereignis (Name, Alter/Jahre, Datum, nächstes Datum, Tage verbleibend, Bild(er), Link). Sensoren ohne Daten zeigen Standardwerte.

## Installation

### Via HACS (empfohlen)

1. HACS öffnen → Integrationen
2. ⋮ (Menü) → Custom repositories
3. Repository-URL: `https://github.com/EdgarM73/grampswebDates`
4. Kategorie: **Integration**
5. Nach "Gramps HA" suchen und installieren
6. Home Assistant neu starten

### Manuelle Installation

Siehe [README.md](https://github.com/EdgarM73/grampswebDates#installation)

## Konfiguration

1. Einstellungen → Geräte & Dienste → Integration hinzufügen
2. "Gramps HA" suchen
3. Gramps Web URL eingeben (z.B. `http://localhost:5000`)
4. Optional: Benutzername, Passwort, Nachname-Filter

## Dashboard-Vorlagen

Vollständige Lovelace-Beispiele (Grid, Markdown, Entities) in [EXAMPLES.md](https://github.com/EdgarM73/grampswebDates/blob/main/EXAMPLES.md)

## Changelog


### v2026.01.24 (2026-01-25)
- Benachrichtigung nur noch 1x, immer 1 Tag vor dem Ereignis
- Todestage und Hochzeitstage als eigene Sensorgruppen
- 10 Geburtstage, Todestage, Hochzeitstage (je 7/8 Sensoren)
- Mehrsprachigkeit (DE, EN, FR, IT, BS)
- Verbesserte Dokumentation und README
```

4. **Set as the latest release** ✅ (ankreuzen)
5. **Publish release** klicken

## Schritt 2: HACS Default Repository Fork erstellen

1. Gehe zu: https://github.com/hacs/default

2. Klicke oben rechts auf **Fork**

3. Erstelle den Fork in deinem Account

## Schritt 3: Integration in HACS Default eintragen

1. In deinem Fork, öffne die Datei: **integration**

2. Füge deine Integration alphabetisch sortiert hinzu:

```json
{
  "name": "EdgarM73/gramps-ha",
  "description": "Gramps Web genealogy integration - displays upcoming birthdays from your family tree"
}
```

Die Datei ist eine JSON-Liste, also zwischen zwei anderen Einträgen einfügen:

```json
[
  ...
  {
    "name": "andersonshatch/midea-ac-py",
    "description": "Control Midea air conditioners via LAN"
  },
  {
    "name": "EdgarM73/gramps-ha",
    "description": "Gramps Web genealogy integration - displays upcoming birthdays from your family tree"
  },
  {
    "name": "elad-bar/ha-edgeos",
    "description": "Ubiquiti EdgeOS integration"
  },
  ...
]
```

## Schritt 4: Pull Request erstellen

1. Commit deine Änderungen in deinem Fork

2. Gehe zu: https://github.com/hacs/default/compare

3. Klicke **compare across forks**

4. **Head repository:** Dein Fork (EdgarM73/default)
5. **Base repository:** hacs/default

6. Erstelle Pull Request mit:
   - **Title:** `Add EdgarM73/gramps-ha`
   - **Description:**

```markdown
## Description
Add Gramps HA - A Home Assistant integration for Gramps Web genealogy software.

## Repository
https://github.com/EdgarM73/grampswebDates

## Features
- Displays next 6 birthdays from Gramps Web genealogy database
- Separate sensors for name, age, and date
- Surname filter support
- Auto-update every 6 hours
- Translations: DE, EN, FR, IT, BS
- HACS-ready with proper structure

## Checklist
- [x] Repository is public
- [x] Valid `hacs.json` present
- [x] Valid `manifest.json` present
- [x] Release v1.0.0 created
- [x] README.md with installation instructions
- [x] Icon included
- [x] Integration follows Home Assistant guidelines
- [x] No breaking changes expected
```


## Schritt 5: Nach PR-Einreichung

1. **Warte auf Review** - HACS-Team prüft deinen PR (kann 1-7 Tage dauern)
2. **Automatische Checks** - GitHub Actions prüfen:
  - JSON-Syntax korrekt
  - Repository existiert
  - Release vorhanden (v2026.01.2)
  - `hacs.json` valide
3. **Feedback umsetzen** - Falls Änderungen nötig sind
4. **Merge** - Nach Genehmigung wird dein PR gemerged
5. **Verfügbarkeit** - Innerhalb von 24h in HACS sichtbar

## Alternative: Vorerst als Custom Repository

**Sofort nutzbar ohne Warten auf HACS-Approval:**

Benutzer können dein Repository direkt hinzufügen:

1. HACS öffnen → Integrationen
2. ⋮ → Custom repositories
3. `https://github.com/EdgarM73/grampswebDates`
4. Kategorie: Integration

## Wichtige Links

- **Dein Repository:** https://github.com/EdgarM73/grampswebDates
- **HACS Default Repo:** https://github.com/hacs/default
- **HACS Dokumentation:** https://hacs.xyz/docs/publish/start
- **Integration Requirements:** https://hacs.xyz/docs/publish/integration

## Troubleshooting

### "Release not found"
- Stelle sicher, dass v1.0.0 als GitHub Release (nicht nur Tag) existiert
- Check: https://github.com/EdgarM73/grampswebDates/releases

### "Invalid hacs.json"
```bash
# Validieren:
cd "c:\Users\fake\OneDrive\Dokumente\dev\birthday"
cat hacs.json
```

### "Manifest validation failed"
```bash
# Validieren:
cat custom_components/gramps_ha/manifest.json
```

## Nach erfolgreicher Aufnahme

Benutzer können die Integration direkt in HACS suchen:
1. HACS → Integrationen
2. Suche: "Gramps HA" oder "birthday" oder "genealogy"
3. Installieren

---

**Status:** ⏳ Vorbereitet, bereit für Einreichung
**Nächster Schritt:** GitHub Release erstellen (siehe Schritt 1)
