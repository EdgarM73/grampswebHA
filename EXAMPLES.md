# Gramps Web Home Assistant Integration - Beispielkonfigurationen

## Lovelace Dashboard Beispiele

### 1. Einfache Liste mit Entities Card

```yaml
type: entities
title: Kommende Geburtstage
entities:
  - sensor.next_birthday_1
  - sensor.next_birthday_2
  - sensor.next_birthday_3
  - sensor.next_birthday_4
  - sensor.next_birthday_5
show_header_toggle: false
```

### 2. Detaillierte Ansicht mit Template

```yaml
type: markdown
title: 🎂 Geburtstage
content: |
  {% set ns = namespace(found=false) %}
  {% for i in range(1, 6) %}
    {% set entity_id = 'sensor.next_birthday_' ~ i %}
    {% if states(entity_id) not in ['unknown', 'unavailable', 'none'] %}
      {% set ns.found = true %}
      <ha-icon icon="mdi:cake-variant"></ha-icon> **{{ states(entity_id) }}**
      - 🎈 Wird {{ state_attr(entity_id, 'age') }} Jahre alt
      - 📅 {{ state_attr(entity_id, 'next_birthday') }}
      - ⏰ In {{ state_attr(entity_id, 'days_until') }} Tagen
      
    {% endif %}
  {% endfor %}
  {% if not ns.found %}
  Keine anstehenden Geburtstage gefunden.
  {% endif %}
```

### 3. Kompakte Tabellenansicht

```yaml
type: markdown
content: |
  | Name | Alter | Datum | Tage |
  |------|-------|-------|------|
  {% for i in range(1, 6) %}
  {% set e = 'sensor.next_birthday_' ~ i %}
  {% if states(e) not in ['unknown', 'unavailable'] %}
  | {{ states(e) }} | {{ state_attr(e, 'age') }} | {{ state_attr(e, 'next_birthday') }} | {{ state_attr(e, 'days_until') }} |
  {% endif %}
  {% endfor %}
```

### 4. Conditional Card - Nur anzeigen wenn Geburtstag in 7 Tagen

```yaml
type: conditional
conditions:
  - entity: sensor.next_birthday_1
    state_not: unavailable
  - entity: sensor.next_birthday_1
    attribute: days_until
    below: 8
card:
  type: markdown
  content: |
    # ⚠️ Geburtstag bald!
    **{{ states('sensor.next_birthday_1') }}** wird in {{ state_attr('sensor.next_birthday_1', 'days_until') }} Tagen {{ state_attr('sensor.next_birthday_1', 'age') }} Jahre alt! 🎉
```

### 5. Glance Card für schnelle Übersicht

```yaml
type: glance
title: Nächste 5 Geburtstage
entities:
  - entity: sensor.next_birthday_1
    name: 1.
  - entity: sensor.next_birthday_2
    name: 2.
  - entity: sensor.next_birthday_3
    name: 3.
  - entity: sensor.next_birthday_4
    name: 4.
  - entity: sensor.next_birthday_5
    name: 5.
show_name: true
show_icon: true
show_state: true
```

## Automatisierungen

### Benachrichtigung 7 Tage vor Geburtstag

```yaml
automation:
  - alias: "Geburtstag in 7 Tagen Erinnerung"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: >
          {% set ns = namespace(found=false) %}
          {% for i in range(1, 6) %}
            {% set entity_id = 'sensor.next_birthday_' ~ i %}
            {% if state_attr(entity_id, 'days_until') == 7 %}
              {% set ns.found = true %}
            {% endif %}
          {% endfor %}
          {{ ns.found }}
    action:
      - service: notify.notify
        data:
          title: "Geburtstag in 7 Tagen"
          message: >
            {% for i in range(1, 6) %}
              {% set entity_id = 'sensor.next_birthday_' ~ i %}
              {% if state_attr(entity_id, 'days_until') == 7 %}
                {{ states(entity_id) }} wird in 7 Tagen {{ state_attr(entity_id, 'age') }} Jahre alt!
              {% endif %}
            {% endfor %}
```

### Benachrichtigung am Geburtstag

```yaml
automation:
  - alias: "Geburtstag heute!"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: template
        value_template: >
          {% set ns = namespace(found=false) %}
          {% for i in range(1, 6) %}
            {% set entity_id = 'sensor.next_birthday_' ~ i %}
            {% if state_attr(entity_id, 'days_until') == 0 %}
              {% set ns.found = true %}
            {% endif %}
          {% endfor %}
          {{ ns.found }}
    action:
      - service: notify.notify
        data:
          title: "🎉 Geburtstag heute!"
          message: >
            {% for i in range(1, 6) %}
              {% set entity_id = 'sensor.next_birthday_' ~ i %}
              {% if state_attr(entity_id, 'days_until') == 0 %}
                Heute wird {{ states(entity_id) }} {{ state_attr(entity_id, 'age') }} Jahre alt! 🎂
              {% endif %}
            {% endfor %}
```

## Template Sensoren

### Anzahl Geburtstage in den nächsten 30 Tagen

```yaml
template:
  - sensor:
      - name: "Geburtstage nächste 30 Tage"
        state: >
          {% set ns = namespace(count=0) %}
          {% for i in range(1, 6) %}
            {% set entity_id = 'sensor.next_birthday_' ~ i %}
            {% if state_attr(entity_id, 'days_until') is not none and state_attr(entity_id, 'days_until') <= 30 %}
              {% set ns.count = ns.count + 1 %}
            {% endif %}
          {% endfor %}
          {{ ns.count }}
        icon: mdi:calendar-clock
```

### Nächster Geburtstag als einzelner Sensor

```yaml
template:
  - sensor:
      - name: "Nächster Geburtstag"
        state: >
          {{ states('sensor.next_birthday_1') }}
        attributes:
          person: >
            {{ states('sensor.next_birthday_1') }}
          days: >
            {{ state_attr('sensor.next_birthday_1', 'days_until') }}
          age: >
            {{ state_attr('sensor.next_birthday_1', 'age') }}
          date: >
            {{ state_attr('sensor.next_birthday_1', 'next_birthday') }}
        icon: mdi:cake-variant
```

## Scripts

### Script zum Versenden einer Geburtstagserinnerung

```yaml
script:
  send_birthday_reminder:
    alias: "Geburtstagserinnerung versenden"
    sequence:
      - service: notify.mobile_app
        data:
          title: "Anstehende Geburtstage"
          message: |
            {% for i in range(1, 6) %}
              {% set e = 'sensor.next_birthday_' ~ i %}
              {% if states(e) not in ['unknown', 'unavailable'] and state_attr(e, 'days_until') <= 14 %}
                • {{ states(e) }} - in {{ state_attr(e, 'days_until') }} Tagen ({{ state_attr(e, 'age') }} Jahre)
              {% endif %}
            {% endfor %}
```

## Node-RED Flow Beispiel

```json
[
    {
        "id": "birthday_notification",
        "type": "server-state-changed",
        "name": "Geburtstag Check",
        "server": "home_assistant",
        "version": 4,
        "entityidfilter": "sensor.next_birthday_1",
        "entityidfiltertype": "exact",
        "outputinitially": false,
        "state_type": "str",
        "ifstate": "",
        "isstateconfig": "",
        "outputonlystatechange": true,
        "for": "0",
        "forType": "num",
        "forUnits": "minutes",
        "x": 150,
        "y": 100,
        "wires": [["check_days"]]
    },
    {
        "id": "check_days",
        "type": "function",
        "name": "Prüfe Tage bis Geburtstag",
        "func": "const daysUntil = msg.data.attributes.days_until;\nif (daysUntil <= 7) {\n    msg.payload = `${msg.data.state} wird in ${daysUntil} Tagen ${msg.data.attributes.age} Jahre alt!`;\n    return msg;\n}\nreturn null;",
        "outputs": 1,
        "x": 400,
        "y": 100,
        "wires": [["send_notification"]]
    },
    {
        "id": "send_notification",
        "type": "api-call-service",
        "name": "Benachrichtigung senden",
        "server": "home_assistant",
        "version": 5,
        "service_domain": "notify",
        "service": "notify",
        "data": "{\"message\":\"{{payload}}\",\"title\":\"Geburtstag bald!\"}",
        "x": 650,
        "y": 100,
        "wires": [[]]
    }
]
```
