# Gramps HA Integration für Home Assistant

Diese Custom Integration ermöglicht es, Daten von einer Gramps Web Instanz in Home Assistant zu integrieren und anstehende Geburtstage auf dem Dashboard anzuzeigen.

## Features

- 🎂 Zeigt die nächsten 5 Geburtstage an
- 📅 Berechnet automatisch die Tage bis zum nächsten Geburtstag
- 🎉 Zeigt das Alter der Person am kommenden Geburtstag
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

## Sensoren

Die Integration erstellt folgende Sensoren:

### Einzelne Geburtstags-Sensoren

- `sensor.gramps_ha_next_birthday_1` - Der nächste Geburtstag
- `sensor.gramps_ha_next_birthday_2` - Der zweitnächste Geburtstag
- `sensor.gramps_ha_next_birthday_3` - Der drittnächste Geburtstag
- `sensor.gramps_ha_next_birthday_4` - Der viertnächste Geburtstag
- `sensor.gramps_ha_next_birthday_5` - Der fünftnächste Geburtstag

Jeder Sensor enthält folgende Attribute:
- `person_name`: Name der Person
- `birth_date`: Geburtsdatum
- `age`: Alter am kommenden Geburtstag
- `days_until`: Tage bis zum Geburtstag
- `next_birthday`: Datum des nächsten Geburtstags

### Alle Geburtstage Sensor

- `sensor.gramps_ha_all_upcoming_birthdays` - Enthält eine Liste aller anstehenden Geburtstage

## Dashboard Konfiguration

### Entities Card

```yaml
type: entities
title: Nächste Geburtstage
entities:
  - entity: sensor.next_birthday_1
    secondary_info: attribute
    attribute: days_until
    name: 🎂 1. Geburtstag
  - entity: sensor.next_birthday_2
    secondary_info: attribute
    attribute: days_until
    name: 🎂 2. Geburtstag
  - entity: sensor.next_birthday_3
    secondary_info: attribute
    attribute: days_until
    name: 🎂 3. Geburtstag
  - entity: sensor.next_birthday_4
    secondary_info: attribute
    attribute: days_until
    name: 🎂 4. Geburtstag
  - entity: sensor.next_birthday_5
    secondary_info: attribute
    attribute: days_until
    name: 🎂 5. Geburtstag
```

### Markdown Card (erweiterte Anzeige)

```yaml
type: markdown
content: >
  ## 🎂 Nächste Geburtstage

  {% for i in range(1, 6) %}
  {% set sensor = 'sensor.next_birthday_' ~ i %}
  {% if states(sensor) != 'unknown' and states(sensor) != 'unavailable' %}
  **{{ states(sensor) }}**  
  📅 In {{ state_attr(sensor, 'days_until') }} Tagen ({{ state_attr(sensor, 'age') }} Jahre)  
  {{ state_attr(sensor, 'next_birthday') }}
  
  {% endif %}
  {% endfor %}
```

### Custom Button Card (erfordert custom:button-card)

```yaml
type: custom:button-card
entity: sensor.next_birthday_1
name: |
  [[[
    return states['sensor.next_birthday_1'].state;
  ]]]
label: |
  [[[
    const days = states['sensor.next_birthday_1'].attributes.days_until;
    const age = states['sensor.next_birthday_1'].attributes.age;
    return `In ${days} Tagen wird ${age} Jahre alt`;
  ]]]
show_label: true
icon: mdi:cake-variant
styles:
  card:
    - background: |
        [[[
          const days = states['sensor.next_birthday_1'].attributes.days_until;
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
