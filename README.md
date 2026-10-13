# Gramps HA Integration für Home Assistant

Diese Custom Integration ermöglicht es, Daten von einer Gramps Web Instanz in Home Assistant zu integrieren und anstehende Geburtstage auf dem Dashboard anzuzeigen.
Ich kam darauf, da ich grampsweb bisher zwar nutze, aber erst jetzt gesehen habe, dass es grampsweb auch als addon gibt : https://github.com/alexbelgium/hassio-addons/tree/master , danke dafür.

und wenn man schon einen Stammbaum hat, kann man auch die Familien Geburtstage anzeigen.

!Achtung !  Der größte Teil dieser Integration ist KI generiert, sonst hätte ich aktuell gar nicht die Zeit gehabt.



## Features

- 🎂 Zeigt die nächsten 6 ( konfigurierbar ) Geburtstage an
- 📅 Berechnet automatisch die Tage bis zum nächsten Geburtstag
- 🎉 Zeigt das Alter der Person am kommenden Geburtstag
- 🧩 Pro Geburtstag 7 Sensoren: Name, Alter, Datum, Nächstes Datum, Tage verbleibend, Bild, Link
- 🖼️ Lädt Profilbilder aus Gramps Web herunter (falls vorhanden)
- 🔗 Direkt-Links zu Personen und Familien in Gramps Web
- 🔄 Automatische Aktualisierung alle 6 Stunden
- 🔐 Unterstützt authentifizierte und öffentliche Gramps Web Instanzen
- 🪦 **Optional: Zeigt die nächsten 6 Gedenktage/Todestage an** (mit Bild und Link)
- 💍 **Optional: Zeigt die nächsten 6 Hochzeitstage/Jahrestage an** (mit Bildern beider Partner und Link zur Familie)
- 🌍 Mehrsprachig: Deutsch, Englisch, Französisch, Italienisch, Bosnisch

## Installation

### HACS (empfohlen)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=EdgarM73&repository=https%3A%2F%2Fgithub.com%2FEdgarM73%2FgrampswebHA&category=Integration)

1. Öffnen Sie HACS in Home Assistant
2. Klicken Sie auf die drei Punkte (⋮) oben rechts
3. Wählen Sie **Benutzerdefinierte Repositorys**
4. Fügen Sie die Repository-URL hinzu: `https://github.com/EdgarM73/grampswebHA`
5. Wählen Sie Kategorie: **Integration**
6. Klicken Sie auf **Hinzufügen**
7. Suchen Sie nach "Gramps HA" und installieren Sie es
8. Starten Sie Home Assistant neu

### Manuelle Installation

1. Laden Sie die neueste Version von [GitHub](https://github.com/EdgarM73/grampswebHA/releases) herunter
2. Entpacken Sie das Archiv
3. Kopieren Sie den Ordner `custom_components/gramps_ha` in Ihr `<config>/custom_components/` Verzeichnis
4. Starten Sie Home Assistant neu

#### Oder via Git:

```bash
cd /config/custom_components
git clone https://github.com/EdgarM73/grampswebHA.git temp
mv temp/custom_components/gramps_ha ./
rm -rf temp
```

## Konfiguration

1. Gehen Sie zu **Einstellungen** → **Geräte & Dienste**
2. Klicken Sie auf **+ Integration hinzufügen**
3. Suchen Sie nach "Gramps HA"
4. Geben Sie die folgenden Informationen ein:
   - **URL**: Die URL Ihrer Gramps Web Instanz (z.B. `https://meine-gramps.example.com`)
   - **Benutzername**: (optional) Ihr Gramps Web Benutzername
   - **Passwort**: (optional) Ihr Gramps Web Passwort
   - **Anzahl Geburtstage**: (optional, Standard: 10) Anzahl der anzuzeigenden Geburtstage/Todestage/Hochzeitstage
   - **Gedenktage anzeigen**: (optional, Standard: Nein) Zeigt die nächsten Todestage/Gedenktage an
   - **Hochzeitstage anzeigen**: (optional, Standard: Nein) Zeigt die nächsten Hochzeitstage/Jahrestage an

## Sensoren

Die Integration erstellt automatisch 10 Sensoren pro Typ (Geburtstage, Gedenktage, Hochzeitstage), auch wenn weniger Daten vorhanden sind. Sensoren ohne Daten zeigen Standardwerte.

### Nächste Geburtstage

Für die nächsten 10 Geburtstage werden je 7 Sensoren angelegt:

1. **Name** (`sensor.next_birthday_X_name`) - Name der Person
2. **Alter** (`sensor.next_birthday_X_age`) - Alter am nächsten Geburtstag  
3. **Datum** (`sensor.next_birthday_X_date`) - Geburtsdatum (Datumtyp)
4. **Nächstes Datum** (`sensor.next_birthday_X_upcoming_date`) - Datum des nächsten Geburtstags (Datumtyp)
5. **Tage verbleibend** (`sensor.next_birthday_X_days_until`) - Tage bis zum Geburtstag
6. **Bild** (`sensor.next_birthday_X_image`) - URL zum Profilbild (wenn vorhanden)
7. **Link** (`sensor.next_birthday_X_link`) - Link zur Person in Gramps Web

Alle Sensoren enthalten zusätzliche Attribute mit detaillierten Informationen.

### Nächste Gedenktage (optional aktivierbar)

Wenn die Option "Gedenktage anzeigen" aktiviert ist, werden für die nächsten 10 Gedenktage/Todestage je 7 Sensoren angelegt:

1. **Name** (`sensor.next_deathday_X_name`) - Name der verstorbenen Person
2. **Datum** (`sensor.next_deathday_X_date`) - Todesdatum (Datumtyp)
3. **Nächstes Datum** (`sensor.next_deathday_X_upcoming_date`) - Datum des nächsten Gedenktags (Datumtyp)
4. **Jahre her** (`sensor.next_deathday_X_years_ago`) - Wie viele Jahre sind seit dem Tod vergangen
5. **Tage verbleibend** (`sensor.next_deathday_X_days_until`) - Tage bis zur jährlichen Gedenkerinnerung
6. **Bild** (`sensor.next_deathday_X_image`) - URL zum Profilbild (wenn vorhanden)
7. **Link** (`sensor.next_deathday_X_link`) - Link zur Person in Gramps Web

### Nächste Hochzeitstage (optional aktivierbar)

Wenn die Option "Hochzeitstage anzeigen" aktiviert ist, werden für die nächsten 10 Hochzeitstage/Jahrestage je 8 Sensoren angelegt:

1. **Name** (`sensor.next_anniversary_X_name`) - Namen der Ehepartner
2. **Jahre zusammen** (`sensor.next_anniversary_X_years_together`) - Wie lange sind die Personen verheiratet
3. **Datum** (`sensor.next_anniversary_X_date`) - Hochzeitsdatum (Datumtyp)
4. **Nächstes Datum** (`sensor.next_anniversary_X_upcoming_date`) - Datum des nächsten Jahrestags (Datumtyp)
5. **Tage verbleibend** (`sensor.next_anniversary_X_days_until`) - Tage bis zum nächsten Jahrestag
6. **Bild Person 1** (`sensor.next_anniversary_X_image_person1`) - URL zum Profilbild des ersten Partners
7. **Bild Person 2** (`sensor.next_anniversary_X_image_person2`) - URL zum Profilbild des zweiten Partners
8. **Link** (`sensor.next_anniversary_X_link`) - Link zur Familie in Gramps Web

**Wichtig:** Bild- und Link-Sensoren sind standardmäßig deaktiviert, um die History-Datenbank nicht zu belasten. Sie können diese bei Bedarf manuell unter "Einstellungen → Geräte & Dienste → Entitäten" aktivieren.


## Benachrichtigungen

Die Integration sendet (wenn aktiviert) nur noch eine Benachrichtigung pro Ereignis, und zwar immer genau 1 Tag vor dem jeweiligen Datum (Geburtstag, Todestag, Hochzeitstag). Wiederholte oder mehrfache Benachrichtigungen entfallen.

## Dashboard Konfiguration

Beispiel-Vorlagen (Grid und Markdown) mit den neuen, getrennten Sensoren finden Sie in [EXAMPLES.md](EXAMPLES.md).

### Custom Button Card (erfordert custom:button-card)

```yaml
type: custom:button-card
entity: sensor.next_birthday_1_name
name: |
  [[[
    return states['sensor.next_birthday_1'].state;
  ]]]
label: |
  [[[
    const days = states['sensor.next_birthday_1_name'].attributes.days_until;
    const age = states['sensor.next_birthday_1_name'].attributes.age;
    return `In ${days} Tagen wird ${age} Jahre alt`;
  ]]]
show_label: true
icon: mdi:cake-variant
styles:
  card:
    - background: |
        [[[
          const days = states['sensor.next_birthday_1_name'].attributes.days_until;
          if (days <= 7) return 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
          return 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)';
        ]]]
```

## Gramps Web API

Diese Integration nutzt die Gramps Web API. Stellen Sie sicher, dass:

1. Ihre Gramps Web Instanz erreichbar ist
2. Die API aktiviert ist
3. Bei Bedarf die Authentifizierung korrekt konfiguriert ist

## Fehlerbehebung

### Verbindungsfehler

- Überprüfen Sie die URL Ihrer Gramps Web Instanz
- Stellen Sie sicher, dass Home Assistant die Instanz erreichen kann
- Prüfen Sie Benutzername und Passwort

### Keine Geburtstage werden angezeigt

- Stellen Sie sicher, dass in Ihrer Gramps-Datenbank Geburtsdaten vorhanden sind
- Überprüfen Sie die Logs in Home Assistant (`Einstellungen` → `System` → `Protokolle`)

### Logs aktivieren

Fügen Sie dies zu Ihrer `configuration.yaml` hinzu:

```yaml
logger:
  default: info
  logs:
    custom_components.gramps_ha: debug
```

## Entwicklung

Diese Integration befindet sich in aktiver Entwicklung. Beiträge sind willkommen!

### Geplante Features

- [x] Konfigurierbare Anzahl von Geburtstagen
- [x] Todestage und Gedenktage mit Bildern und Links
- [x] Hochzeitstage mit Bildern beider Partner und Links
- [x] Direkt-Links zu Personen/Familien in Gramps Web
- [x] Mehrsprachigkeit (DE, EN, FR, IT, BS)
- [ ] Filterung nach Altersgruppen
- [ ] Benachrichtigungen für anstehende Geburtstage
- [ ] Unterstützung für mehrere Gramps Web Instanzen

## Lizenz

MIT License

## Support

Bei Problemen oder Fragen erstellen Sie bitte ein Issue auf GitHub.

---

🇩🇪 Deutsche Version | [🇬🇧 English Version](README_EN.md)

## Kalender, „Heute“-Sensoren und Events

- **Kalender** `calendar.gramps_calendar`: alle Geburtstage, Gedenktage (optional) und Hochzeitstage (optional) im HA-Kalender, auch für beliebige Zeiträume. Runde Termine sind mit 🎉 markiert (Geburtstage: alle 10 Jahre und der 18., Hochzeitstage: alle 5 Jahre, Gedenktage: alle 10 Jahre).
- **Heute-Sensoren** `binary_sensor.gramps_birthday_today`, `..._memorial_day_today`, `..._anniversary_today`: an, solange heute ein passender Termin ist. Attribute: `count`, `names`, `milestones`.
- **Nächster Meilenstein** `sensor.gramps_next_milestone`: der nächste runde Geburtstag bzw. Hochzeitstag der nächsten 12 Monate, Attribut `upcoming` mit bis zu 10 Einträgen.
- **Event** `gramps_ha_event`: wird jede Nacht nach der Aktualisierung (00:05 Uhr) für jeden heutigen Termin ausgelöst. Daten: `type` (`birthday`, `deathday`, `anniversary`), `person_name`, `years`, `milestone`. Für eine Nachricht am Morgen den Sensor „…\_today“ mit einem Zeit-Trigger verwenden.
- In den Listen-Einträgen (Geburtstage, Gedenktage, Hochzeitstage) gibt es bei runden Terminen zusätzlich das Feld `milestone`.
