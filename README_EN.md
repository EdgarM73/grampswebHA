# Gramps HA Integration for Home Assistant

This custom integration allows you to integrate data from a Gramps Web instance into Home Assistant and display upcoming birthdays on your dashboard.

I came up with this because I've been using Gramps Web for a while, but only recently discovered that Gramps Web is also available as an add-on: https://github.com/alexbelgium/hassio-addons/tree/master - thank you for that!

And if you already have a family tree, you might as well display family birthdays.

**Note:** Most of this integration is AI-generated, otherwise I wouldn't have had the time to create it.

## Features

- 🎂 Displays the next 6 birthdays
- 📅 Automatically calculates days until the next birthday
- 🎉 Shows the person's age on their upcoming birthday
- 🧩 Three sensors per birthday: Name, Age, Date
- 🔄 Automatic updates every 6 hours
- 🔐 Supports authenticated and public Gramps Web instances
- 🌍 Translations: German, English, French, Italian, Bosnian
- 👤 Surname filter for targeted display

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click on the three dots (⋮) in the top right
3. Select **Custom repositories**
4. Add the repository URL: `https://github.com/EdgarM73/gramps-ha`
5. Select category: **Integration**
6. Click **Add**
7. Search for "Gramps HA" and install it
8. Restart Home Assistant

### Manual Installation

1. Download the latest version from [GitHub](https://github.com/EdgarM73/gramps-ha/releases)
2. Extract the archive
3. Copy the `custom_components/gramps_ha` folder to your `<config>/custom_components/` directory
4. Restart Home Assistant

#### Or via Git:

```bash
cd /config/custom_components
git clone https://github.com/EdgarM73/gramps-ha.git temp
mv temp/custom_components/gramps_ha ./
rm -rf temp
```

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Gramps HA"
4. Enter the following information:
   - **URL**: The URL of your Gramps Web instance (e.g., `https://my-gramps.example.com`)
   - **Username**: (optional) Your Gramps Web username
   - **Password**: (optional) Your Gramps Web password
   - **Surname Filter**: (optional) Only display people with this surname

## Sensors

The integration creates the following sensors:

### Next Birthdays (Name/Age/Date each)

For the next 6 birthdays, three sensors are created each:

- `sensor.next_birthday_1_name`, `sensor.next_birthday_1_age`, `sensor.next_birthday_1_date`
- `sensor.next_birthday_2_name`, `sensor.next_birthday_2_age`, `sensor.next_birthday_2_date`
- `sensor.next_birthday_3_name`, `sensor.next_birthday_3_age`, `sensor.next_birthday_3_date`
- `sensor.next_birthday_4_name`, `sensor.next_birthday_4_age`, `sensor.next_birthday_4_date`
- `sensor.next_birthday_5_name`, `sensor.next_birthday_5_age`, `sensor.next_birthday_5_date`
- `sensor.next_birthday_6_name`, `sensor.next_birthday_6_age`, `sensor.next_birthday_6_date`

Note: Sensor IDs may vary slightly depending on your system. Check the exact entities under Settings → Devices & Services → Entities.

All these sensors contain attributes with additional information:
- `person_name`: Person's name
- `birth_date`: Birth date
- `age`: Age on upcoming birthday
- `days_until`: Days until birthday
- `next_birthday`: Date of next birthday (ISO format)

Additionally, an aggregated sensor is provided:

- `sensor.all_upcoming_birthdays` – Count/list of all upcoming birthdays

## Dashboard Configuration

Example templates (Grid and Markdown) with the new separate sensors can be found in [EXAMPLES.md](EXAMPLES.md).

### Custom Button Card (requires custom:button-card)

```yaml
type: custom:button-card
entity: sensor.next_birthday_1_name
name: |
  [[[
    return states['sensor.next_birthday_1_name'].state;
  ]]]
label: |
  [[[
    const days = states['sensor.next_birthday_1_name'].attributes.days_until;
    const age = states['sensor.next_birthday_1_name'].attributes.age;
    return `In ${days} days turns ${age} years old`;
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

This integration uses the Gramps Web API. Make sure that:

1. Your Gramps Web instance is reachable
2. The API is enabled
3. Authentication is configured correctly if needed

## Troubleshooting

### Connection Errors

- Check the URL of your Gramps Web instance
- Make sure Home Assistant can reach the instance
- Verify username and password

### No Birthdays Displayed

- Ensure that birth dates are present in your Gramps database
- Check the logs in Home Assistant (`Settings` → `System` → `Logs`)

### Enable Logs

Add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.gramps_ha: debug
```

## Development

This integration is under active development. Contributions are welcome!

### Planned Features

- [ ] Configurable number of birthdays
- [ ] Age group filtering
- [ ] Death anniversaries and memorial dates
- [ ] Wedding anniversaries
- [ ] Notifications for upcoming birthdays
- [ ] Support for multiple Gramps Web instances

## License

MIT License

## Support

For issues or questions, please create an issue on GitHub.

---

[🇩🇪 Deutsche Version](README.md) | 🇬🇧 English Version
