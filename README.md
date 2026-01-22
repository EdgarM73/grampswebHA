# Gramps HA Integration für Home Assistant

Diese Custom Integration ermöglicht es, Daten von einer Gramps Web Instanz in Home Assistant zu integrieren und anstehende Geburtstage auf dem Dashboard anzuzeigen.
Ich kam darauf, da ich grampsweb bisher zwar nutze, aber erst jetzt gesehen habe, dass es grampsweb auch als addon gibt : https://github.com/alexbelgium/hassio-addons/tree/master , danke dafür.

und wenn man schon einen Stammbaum hat, kann man auch die Familien Geburtstage anzeigen.

!Achtung !  Der größte Teil dieser Integration ist KI generiert, sonst hätte ich aktuell gar nicht die Zeit gehabt.

## Features

- 🎂 Zeigt die nächsten 6 Geburtstage an
- 📅 Berechnet automatisch die Tage bis zum nächsten Geburtstag
- 🎉 Zeigt das Alter der Person am kommenden Geburtstag
- 🧩 Pro Geburtstag drei Sensoren: Name, Alter, Datum
- 🔄 Automatische Aktualisierung alle 6 Stunden
- 🔐 Unterstützt authentifizierte und öffentliche Gramps Web Instanzen

## Installation

### HACS (empfohlen)

1. Öffnen Sie HACS in Home Assistant
2. Klicken Sie auf die drei Punkte (⋮) oben rechts
3. Wählen Sie **Benutzerdefinierte Repositorys**
4. Fügen Sie die Repository-URL hinzu: `https://github.com/EdgarM73/gramps-ha`
5. Wählen Sie Kategorie: **Integration**
6. Klicken Sie auf **Hinzufügen**
7. Suchen Sie nach "Gramps HA" und installieren Sie es
8. Starten Sie Home Assistant neu

### Manuelle Installation

1. Laden Sie die neueste Version von [GitHub](https://github.com/EdgarM73/gramps-ha/releases) herunter
2. Entpacken Sie das Archiv
3. Kopieren Sie den Ordner `custom_components/gramps_ha` in Ihr `<config>/custom_components/` Verzeichnis
4. Starten Sie Home Assistant neu

#### Oder via Git:

```bash
cd /config/custom_components
git clone https://github.com/EdgarM73/gramps-ha.git temp
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
  - **Nachname-Filter**: (optional) Nur Personen mit diesem Nachnamen anzeigen

## Sensoren

Die Integration erstellt folgende Sensoren:

### Nächste Geburtstage (jeweils Name/Alter/Datum)

Für die nächsten 6 Geburtstage werden je drei Sensoren angelegt:

- `sensor.next_birthday_1_name`, `sensor.next_birthday_1_age`, `sensor.next_birthday_1_date`
- `sensor.next_birthday_2_name`, `sensor.next_birthday_2_age`, `sensor.next_birthday_2_date`
- `sensor.next_birthday_3_name`, `sensor.next_birthday_3_age`, `sensor.next_birthday_3_date`
- `sensor.next_birthday_4_name`, `sensor.next_birthday_4_age`, `sensor.next_birthday_4_date`
- `sensor.next_birthday_5_name`, `sensor.next_birthday_5_age`, `sensor.next_birthday_5_date`
- `sensor.next_birthday_6_name`, `sensor.next_birthday_6_age`, `sensor.next_birthday_6_date`

Hinweis: Die Sensor-IDs können je nach System leicht variieren. Prüfen Sie die exakten Entitäten unter Einstellungen → Geräte & Dienste → Entitäten.

Alle diese Sensoren enthalten Attribute mit Zusatzinformationen:
- `person_name`: Name der Person
- `birth_date`: Geburtsdatum
- `age`: Alter am kommenden Geburtstag
- `days_until`: Tage bis zum Geburtstag
- `next_birthday`: Datum des nächsten Geburtstags (ISO)

Zusätzlich wird ein aggregierter Sensor bereitgestellt:

- `sensor.all_upcoming_birthdays` – Anzahl/Liste aller anstehenden Geburtstage

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

- [ ] Konfigurierbare Anzahl von Geburtstagen
- [ ] Filterung nach Altersgruppen
- [ ] Todestage und Gedenktage
- [ ] Hochzeitstage
- [ ] Benachrichtigungen für anstehende Geburtstage
- [ ] Unterstützung für mehrere Gramps Web Instanzen

## Lizenz

MIT License

## Support

Bei Problemen oder Fragen erstellen Sie bitte ein Issue auf GitHub.

---

🇩🇪 Deutsche Version | [🇬🇧 English Version](README_EN.md)
