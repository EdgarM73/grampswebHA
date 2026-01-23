"""Sensor platform for Gramps Web integration."""

from __future__ import annotations

import logging
from datetime import datetime, date

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo, DeviceEntryType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_PERSON_NAME,
    ATTR_BIRTH_DATE,
    ATTR_AGE,
    ATTR_DAYS_UNTIL,
    CONF_URL,
    CONF_NUM_BIRTHDAYS,
    DEFAULT_NUM_BIRTHDAYS,
    CONF_SHOW_DEATHDAYS,
    CONF_SHOW_ANNIVERSARIES,
    DEFAULT_SHOW_DEATHDAYS,
    DEFAULT_SHOW_ANNIVERSARIES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gramps Web sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get configuration
    num_birthdays = entry.data.get(CONF_NUM_BIRTHDAYS, DEFAULT_NUM_BIRTHDAYS)
    show_deathdays = entry.data.get(CONF_SHOW_DEATHDAYS, DEFAULT_SHOW_DEATHDAYS)
    show_anniversaries = entry.data.get(CONF_SHOW_ANNIVERSARIES, DEFAULT_SHOW_ANNIVERSARIES)

    sensors: list[SensorEntity] = []
    
    # Birthday sensors
    for i in range(num_birthdays):
        sensors.append(GrampsWebNextBirthdayNameSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayAgeSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayDateSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayDaysUntilSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayImageSensor(coordinator, entry, i))

    # Deathday sensors (if enabled)
    if show_deathdays:
        for i in range(num_birthdays):
            sensors.append(GrampsWebNextDeathdayNameSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayDateSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayYearsAgoSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayDaysUntilSensor(coordinator, entry, i))

    # Anniversary sensors (if enabled)
    if show_anniversaries:
        for i in range(num_birthdays):
            sensors.append(GrampsWebNextAnniversaryNameSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryYearsTogetherSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryDateSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryDaysUntilSensor(coordinator, entry, i))

    sensors.append(GrampsWebAllBirthdaysSensor(coordinator, entry))

    async_add_entities(sensors)


class GrampsWebNextBirthdayBase(CoordinatorEntity, SensorEntity):
    """Base class shared by the per-field next birthday sensors."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._entry = entry

    def _get_birthday(self) -> dict | None:
        if not self.coordinator.data:
            return None
        if self._index >= len(self.coordinator.data):
            return None
        return self.coordinator.data[self._index]

    @property
    def device_info(self) -> DeviceInfo:
        config_url = self._entry.data.get(CONF_URL)
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or "Gramps HA",
            manufacturer="Gramps Web",
            model="Birthdays",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=config_url,
        )

    @property
    def extra_state_attributes(self):
        birthday = self._get_birthday()
        if not birthday:
            return {}
        return {
            ATTR_PERSON_NAME: birthday.get("person_name"),
            ATTR_BIRTH_DATE: birthday.get("birth_date"),
            ATTR_AGE: birthday.get("age"),
            ATTR_DAYS_UNTIL: birthday.get("days_until"),
            "next_birthday": birthday.get("next_birthday"),
            "image_url": birthday.get("image_url"),
        }

    @property
    def entity_picture(self):
        """Return entity picture from Gramps if available."""
        birthday = self._get_birthday()
        if not birthday:
            return None
        return birthday.get("image_url")


class GrampsWebNextBirthdayNameSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing only the name."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Name"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_name"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        return birthday.get("person_name")

    @property
    def icon(self):
        return "mdi:account"


class GrampsWebNextBirthdayAgeSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing only the age."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Age"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_age"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        return birthday.get("age")

    @property
    def icon(self):
        return "mdi:numeric"


class GrampsWebNextBirthdayDateSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing only the date."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Date"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_date"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        birth_date = birthday.get("birth_date")
        # We display the original birth date (not the upcoming birthday)
        if birth_date:
            try:
                dt = datetime.fromisoformat(birth_date)
                return dt.date()
            except Exception:
                return None
        return None

    @property
    def icon(self):
        return "mdi:calendar"


class GrampsWebNextBirthdayDaysUntilSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing days until birthday."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Days Until"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_days_until"
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        return birthday.get("days_until")

    @property
    def icon(self):
        return "mdi:calendar-clock"


class GrampsWebNextBirthdayImageSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing image URL."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Image"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_image"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        return birthday.get("image_url", "No Image")

    @property
    def icon(self):
        return "mdi:image-outline"

    @property
    def entity_picture(self):
        """Return entity picture from Gramps if available."""
        birthday = self._get_birthday()
        if not birthday:
            return None
        return birthday.get("image_url")


class GrampsWebAllBirthdaysSensor(CoordinatorEntity, SensorEntity):
    """Representation of all upcoming birthdays sensor."""

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "All Upcoming Birthdays"
        self._attr_unique_id = f"{entry.entry_id}_all_birthdays"
        self._entry = entry

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return 0

        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data:
            return {"birthdays": []}

        return {
            "birthdays": self.coordinator.data,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:calendar-multiple"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for grouping in HA UI."""
        config_url = self._entry.data.get(CONF_URL)
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title or "Gramps HA",
            manufacturer="Gramps Web",
            model="Birthdays",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=config_url,
        )


class GrampsWebNextDeathdayNameSensor(GrampsWebNextBirthdayBase):
    """Next deathday sensor showing name."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Name"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_name"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        # Fetch deathday data
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        return deathday_list[self._index].get("person_name")

    @property
    def icon(self):
        return "mdi:skull"


class GrampsWebNextDeathdayDateSensor(GrampsWebNextBirthdayBase):
    """Next deathday sensor showing death date."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Date"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_date"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        death_date = deathday_list[self._index].get("death_date")
        if death_date:
            return datetime.fromisoformat(death_date).date()
        return None

    @property
    def icon(self):
        return "mdi:calendar"


class GrampsWebNextDeathdayYearsAgoSensor(GrampsWebNextBirthdayBase):
    """Next deathday sensor showing years ago."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Years Ago"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_years_ago"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        return deathday_list[self._index].get("years_ago")

    @property
    def icon(self):
        return "mdi:history"


class GrampsWebNextDeathdayDaysUntilSensor(GrampsWebNextBirthdayBase):
    """Next deathday sensor showing days until."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Days Until"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_days_until"
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        return deathday_list[self._index].get("days_until")

    @property
    def icon(self):
        return "mdi:calendar-clock"


class GrampsWebNextAnniversaryNameSensor(GrampsWebNextBirthdayBase):
    """Next anniversary sensor showing names."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Name"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_name"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("person_name")

    @property
    def icon(self):
        return "mdi:heart-multiple"


class GrampsWebNextAnniversaryYearsTogetherSensor(GrampsWebNextBirthdayBase):
    """Next anniversary sensor showing years together."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Years Together"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_years_together"
        self._attr_native_unit_of_measurement = "years"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("years_together")

    @property
    def icon(self):
        return "mdi:numeric"


class GrampsWebNextAnniversaryDateSensor(GrampsWebNextBirthdayBase):
    """Next anniversary sensor showing marriage date."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Date"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_date"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        marriage_date = anniversary_list[self._index].get("marriage_date")
        if marriage_date:
            return datetime.fromisoformat(marriage_date).date()
        return None

    @property
    def icon(self):
        return "mdi:calendar"


class GrampsWebNextAnniversaryDaysUntilSensor(GrampsWebNextBirthdayBase):
    """Next anniversary sensor showing days until."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Days Until"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_days_until"
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("days_until")

    @property
    def icon(self):
        return "mdi:calendar-clock"
