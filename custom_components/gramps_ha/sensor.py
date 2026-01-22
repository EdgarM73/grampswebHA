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
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gramps Web sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors: list[SensorEntity] = []
    for i in range(6):  # Create sensors for next 6 birthdays
        sensors.append(GrampsWebNextBirthdayNameSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayAgeSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayDateSensor(coordinator, entry, i))

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
        }


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
