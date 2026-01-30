# Gramps HA Integration for Home Assistant

This custom integration allows you to integrate data from a Gramps Web instance into Home Assistant and display upcoming birthdays on your dashboard.

I came up with this because I've been using Gramps Web for a while, but only recently discovered that Gramps Web is also available as an add-on: https://github.com/alexbelgium/hassio-addons/tree/master - thank you for that!

And if you already have a family tree, you might as well display family birthdays.

**Note:** Most of this integration is AI-generated, otherwise I wouldn't have had the time to create it.

## Features

- 🎂 Displays the next 6 ( configurable ) birthdays
- 📅 Automatically calculates days until the next birthday
- 🎉 Shows the person's age on their upcoming birthday
- 🧩 7 sensors per birthday: Name, Age, Date, Upcoming Date, Days Remaining, Image, Link
- 🖼️ Downloads profile pictures from Gramps Web (if available)
- 🔗 Direct links to persons and families in Gramps Web
- 🔄 Automatic updates every 6 hours
- 🔐 Supports authenticated and public Gramps Web instances
- 🪦 **Optional: Displays upcoming 6 memorial dates/death anniversaries** (with image and link)
- 💍 **Optional: Displays upcoming 6 wedding anniversaries** (with images of both partners and family link)
- 🌍 Multilingual: German, English, French, Italian, Bosnian

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click on the three dots (⋮) in the top right
3. Select **Custom repositories**
4. Add the repository URL: `https://github.com/EdgarM73/grampswebDates`
5. Select category: **Integration**
6. Click **Add**
7. Search for "Gramps HA" and install it
8. Restart Home Assistant

### Manual Installation

1. Download the latest version from [GitHub](https://github.com/EdgarM73/grampswebDates/releases)
2. Extract the archive
3. Copy the `custom_components/gramps_ha` folder to your `<config>/custom_components/` directory
4. Restart Home Assistant

#### Or via Git:

```bash
cd /config/custom_components
git clone https://github.com/EdgarM73/grampswebDates.git temp
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
   - **Number of Birthdays**: (optional, default: 10) Number of birthdays/deathdays/anniversaries to display
   - **Show Deathdays**: (optional, default: No) Show upcoming memorial/death dates
   - **Show Anniversaries**: (optional, default: No) Show upcoming wedding anniversaries

## Sensors

The integration automatically creates 10 sensors per type (birthdays, deathdays, anniversaries), even if fewer data is available. Sensors without data show default values.

### Next Birthdays

For the next 10 birthdays, 7 sensors are created each:

1. **Name** (`sensor.next_birthday_X_name`) - Person's name
2. **Age** (`sensor.next_birthday_X_age`) - Age on next birthday
3. **Date** (`sensor.next_birthday_X_date`) - Birth date (Date type)
4. **Upcoming Date** (`sensor.next_birthday_X_upcoming_date`) - Date of next birthday (Date type)
5. **Days Remaining** (`sensor.next_birthday_X_days_until`) - Days until birthday
6. **Image** (`sensor.next_birthday_X_image`) - URL to profile picture (if available)
7. **Link** (`sensor.next_birthday_X_link`) - Link to person in Gramps Web

All sensors contain additional attributes with detailed information.

### Next Deathdays/Memorial Dates (optional)

If the "Show Deathdays" option is enabled, four sensors are created for each of the next 6 memorial/death dates:

- `sensor.next_deathday_1_name`, `sensor.next_deathday_1_date`, `sensor.next_deathday_1_years_ago`, `sensor.next_deathday_1_days_until`
- `sensor.next_deathday_2_name`, `sensor.next_deathday_2_date`, `sensor.next_deathday_2_years_ago`, `sensor.next_deathday_2_days_until`
- ... up to `sensor.next_deathday_6_*`

These sensors display:
- **name**: Name of the deceased person
- **date**: Death date
- **years_ago**: How many years have passed since death
- **days_until**: Days until the annual memorial reminder

### Next Wedding Anniversaries (optional)

### Next Deathdays/Memorial Dates (optional)

If the "Show Deathdays" option is enabled, 7 sensors are created for each of the next 10 memorial/death dates:

1. **Name** (`sensor.next_deathday_X_name`) - Name of deceased person
2. **Date** (`sensor.next_deathday_X_date`) - Death date (Date type)
3. **Upcoming Date** (`sensor.next_deathday_X_upcoming_date`) - Date of next memorial (Date type)
4. **Years Ago** (`sensor.next_deathday_X_years_ago`) - How many years since death
5. **Days Remaining** (`sensor.next_deathday_X_days_until`) - Days until annual memorial
6. **Image** (`sensor.next_deathday_X_image`) - URL to profile picture (if available)
7. **Link** (`sensor.next_deathday_X_link`) - Link to person in Gramps Web

### Next Wedding Anniversaries (optional)

If the "Show Anniversaries" option is enabled, 8 sensors are created for each of the next 10 wedding anniversaries:

1. **Name** (`sensor.next_anniversary_X_name`) - Names of spouses
2. **Years Together** (`sensor.next_anniversary_X_years_together`) - How many years married
3. **Date** (`sensor.next_anniversary_X_date`) - Marriage date (Date type)
4. **Upcoming Date** (`sensor.next_anniversary_X_upcoming_date`) - Date of next anniversary (Date type)
5. **Days Remaining** (`sensor.next_anniversary_X_days_until`) - Days until next anniversary
6. **Image Person 1** (`sensor.next_anniversary_X_image_person1`) - URL to profile picture of first spouse
7. **Image Person 2** (`sensor.next_anniversary_X_image_person2`) - URL to profile picture of second spouse
8. **Link** (`sensor.next_anniversary_X_link`) - Link to family in Gramps Web

**Important:** Image and Link sensors are disabled by default to avoid database bloat. You can manually enable them under "Settings → Devices & Services → Entities" if needed.

## Notifications

The integration can optionally send notifications (currently experimental).

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

- [x] Configurable number of birthdays
- [x] Death anniversaries and memorial dates with images and links
- [x] Wedding anniversaries with images of both partners and links
- [x] Direct links to persons/families in Gramps Web
- [x] Multilingual support (DE, EN, FR, IT, BS)
- [ ] Age group filtering
- [ ] Notifications for upcoming birthdays
- [ ] Support for multiple Gramps Web instances

## License

MIT License

## Support

For issues or questions, please create an issue on GitHub.

---

[🇩🇪 Deutsche Version](README.md) | 🇬🇧 English Version
