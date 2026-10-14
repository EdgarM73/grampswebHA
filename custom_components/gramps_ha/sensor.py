"""Sensor platform for Gramps Web integration."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    DeviceEntryType,
    async_get as async_get_device_registry,
)
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


def _via_device(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    """Return the via_device_id kwarg linking to the main Gramps HA device."""
    registry = async_get_device_registry(hass)
    identifier = (DOMAIN, entry.entry_id)
    if hasattr(registry, "async_get_device_by_identifier"):
        parent = registry.async_get_device_by_identifier(identifier, entry.entry_id)
    else:  # older Home Assistant versions
        parent = registry.async_get_device(identifiers={identifier})
    return {"via_device_id": parent.id} if parent else {}


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
    
    # Birthday sensors - create as many as configured
    # even if there aren't enough birthdays. Sensors ohne Daten zeigen Defaultwerte.
    for i in range(num_birthdays):
        sensors.append(GrampsWebNextBirthdayNameSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayAgeSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayDateSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayUpcomingDateSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayDaysUntilSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayImageSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayLinkSensor(coordinator, entry, i))
        sensors.append(GrampsWebNextBirthdayRelationshipSensor(coordinator, entry, i))

    # Deathday sensors (if enabled) - create as many as configured
    if show_deathdays:
        for i in range(num_birthdays):
            sensors.append(GrampsWebNextDeathdayNameSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayDateSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayUpcomingDateSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayYearsAgoSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayDaysUntilSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayImageSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayLinkSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextDeathdayRelationshipSensor(coordinator, entry, i))

    # Anniversary sensors (if enabled) - create as many as configured
    if show_anniversaries:
        for i in range(num_birthdays):
            sensors.append(GrampsWebNextAnniversaryNameSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryYearsTogetherSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryDateSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryUpcomingDateSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryDaysUntilSensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryImagePerson1Sensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryImagePerson2Sensor(coordinator, entry, i))
            sensors.append(GrampsWebNextAnniversaryLinkSensor(coordinator, entry, i))

    sensors.append(GrampsWebAllBirthdaysSensor(coordinator, entry))
    sensors.append(GrampsWebNextMilestoneSensor(coordinator, entry))
    sensors.append(GrampsWebOnThisDaySensor(coordinator, entry))
    sensors.extend(
        GrampsWebStatSensor(coordinator, entry, *spec) for spec in STAT_SENSORS
    )

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
            identifiers={(DOMAIN, f"{self._entry.entry_id}_birthdays")},
            name="Geburtstage" if self._entry.data.get("language") == "de" else "Birthdays",
            manufacturer="Gramps Web",
            model="Birthdays",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=config_url,
            **_via_device(self.hass, self._entry),
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
            "relationship": birthday.get("relationship"),
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
            return "Keine Daten"
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
            except Exception as e:
                _LOGGER.error(f"Birthday {self._index}: Error parsing date {birth_date}: {e}")
                return None
        return None

    @property
    def icon(self):
        return "mdi:calendar"


class GrampsWebNextBirthdayUpcomingDateSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing the upcoming birthday date."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Upcoming Date"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_upcoming_date"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        next_birthday = birthday.get("next_birthday")
        # Display the upcoming birthday
        if next_birthday:
            try:
                dt = datetime.fromisoformat(next_birthday)
                return dt.date()
            except Exception as e:
                _LOGGER.error(f"Birthday Upcoming {self._index}: Error parsing date {next_birthday}: {e}")
                return None
        return None

    @property
    def icon(self):
        return "mdi:cake"


class GrampsWebNextBirthdayDaysUntilSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing days until birthday."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Days Until"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_days_until"
        self._attr_native_unit_of_measurement = "days"
        self._attr_native_value = 999

    @property
    def native_value(self):
        birthday = self._get_birthday()
        result = None
        if not birthday:
            result = 999
            _LOGGER.debug(f"Birthday {self._index + 1} Days Until: No birthday data, returning 999")
        else:
            result = birthday.get("days_until", 999)
            _LOGGER.debug(
                f"Birthday {self._index + 1} Days Until: "
                f"Name={birthday.get('person_name')}, "
                f"Days={result}, "
                f"Type={type(result)}"
            )
        return result

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def icon(self):
        return "mdi:calendar-clock"


class GrampsWebNextBirthdayImageSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing image URL."""
    
    _attr_entity_registry_enabled_default = True

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


class GrampsWebNextBirthdayLinkSensor(GrampsWebNextBirthdayBase):
    """Next birthday sensor showing Gramps Web link."""
    
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Link"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_link"
        self._entry = entry

    @property
    def native_value(self):
        birthday = self._get_birthday()
        if not birthday:
            return None
        person_handle = birthday.get("person_handle")
        if not person_handle:
            return None
        base_url = self._entry.data.get(CONF_URL, "").rstrip("/")
        return f"{base_url}/person/{person_handle}"

    @property
    def icon(self):
        return "mdi:link"


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


class GrampsWebNextDeathdayBase(CoordinatorEntity, SensorEntity):
    """Base class for deathday sensors."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        config_url = self._entry.data.get(CONF_URL)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_deathdays")},
            name="Gedenktage" if self._entry.data.get("language") == "de" else "Deathdays",
            manufacturer="Gramps Web",
            model="Deathdays",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=config_url,
            **_via_device(self.hass, self._entry),
        )


class GrampsWebNextAnniversaryBase(CoordinatorEntity, SensorEntity):
    """Base class for anniversary sensors."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator)
        self._index = index
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        config_url = self._entry.data.get(CONF_URL)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_anniversaries")},
            name="Hochzeitstage" if self._entry.data.get("language") == "de" else "Anniversaries",
            manufacturer="Gramps Web",
            model="Anniversaries",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=config_url,
            **_via_device(self.hass, self._entry),
        )


class GrampsWebNextDeathdayNameSensor(GrampsWebNextDeathdayBase):
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


class GrampsWebNextDeathdayDateSensor(GrampsWebNextDeathdayBase):
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
            try:
                dt = datetime.fromisoformat(death_date)
                return dt.date()
            except Exception as e:
                _LOGGER.error(f"Deathday {self._index}: Error parsing date {death_date}: {e}")
                return None
        return None

    @property
    def icon(self):
        return "mdi:calendar"


class GrampsWebNextDeathdayUpcomingDateSensor(GrampsWebNextDeathdayBase):
    """Next deathday sensor showing the upcoming deathday date."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Upcoming Date"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_upcoming_date"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        next_deathday = deathday_list[self._index].get("next_deathday")
        if next_deathday:
            try:
                dt = datetime.fromisoformat(next_deathday)
                return dt.date()
            except Exception as e:
                _LOGGER.error(f"Deathday Upcoming {self._index}: Error parsing date {next_deathday}: {e}")
                return None
        return None

    @property
    def icon(self):
        return "mdi:skull"


class GrampsWebNextDeathdayYearsAgoSensor(GrampsWebNextDeathdayBase):
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


class GrampsWebNextDeathdayDaysUntilSensor(GrampsWebNextDeathdayBase):
    """Next deathday sensor showing days until."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Days Until"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_days_until"
        self._attr_native_unit_of_measurement = "days"
        self._attr_native_value = 999

    @property
    def native_value(self):
        if not self.coordinator.data:
            return 999
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return 999
        return deathday_list[self._index].get("days_until", 999)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def icon(self):
        return "mdi:calendar-clock"


class GrampsWebNextDeathdayImageSensor(GrampsWebNextDeathdayBase):
    """Next deathday sensor showing image URL."""
    
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Image"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_image"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        return deathday_list[self._index].get("image_url", "No Image")

    @property
    def icon(self):
        return "mdi:image-outline"

    @property
    def entity_picture(self):
        """Return entity picture from Gramps if available."""
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        return deathday_list[self._index].get("image_url")


class GrampsWebNextDeathdayLinkSensor(GrampsWebNextDeathdayBase):
    """Next deathday sensor showing Gramps Web link."""
    
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Link"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_link"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        deathday_list = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(deathday_list):
            return None
        person_handle = deathday_list[self._index].get("person_handle")
        if not person_handle:
            return None
        base_url = self._entry.data.get(CONF_URL, "").rstrip("/")
        return f"{base_url}/person/{person_handle}"

    @property
    def icon(self):
        return "mdi:link"


class GrampsWebNextAnniversaryNameSensor(GrampsWebNextAnniversaryBase):
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


class GrampsWebNextAnniversaryYearsTogetherSensor(GrampsWebNextAnniversaryBase):
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


class GrampsWebNextAnniversaryDateSensor(GrampsWebNextAnniversaryBase):
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
            try:
                dt = datetime.fromisoformat(marriage_date)
                return dt.date()
            except Exception as e:
                _LOGGER.error(f"Anniversary {self._index}: Error parsing date {marriage_date}: {e}")
                return None
        return None

    @property
    def icon(self):
        return "mdi:calendar"


class GrampsWebNextAnniversaryUpcomingDateSensor(GrampsWebNextAnniversaryBase):
    """Next anniversary sensor showing the upcoming anniversary date."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Upcoming Date"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_upcoming_date"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        next_anniversary = anniversary_list[self._index].get("next_anniversary")
        if next_anniversary:
            try:
                dt = datetime.fromisoformat(next_anniversary)
                return dt.date()
            except Exception as e:
                _LOGGER.error(f"Anniversary Upcoming {self._index}: Error parsing date {next_anniversary}: {e}")
                return None
        return None

    @property
    def icon(self):
        return "mdi:heart"


class GrampsWebNextAnniversaryDaysUntilSensor(GrampsWebNextAnniversaryBase):
    """Next anniversary sensor showing days until."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Days Until"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_days_until"
        self._attr_native_unit_of_measurement = "days"
        self._attr_native_value = 999

    @property
    def native_value(self):
        if not self.coordinator.data:
            return 999
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return 999
        return anniversary_list[self._index].get("days_until", 999)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True

    @property
    def icon(self):
        return "mdi:calendar-clock"


class GrampsWebNextAnniversaryImagePerson1Sensor(GrampsWebNextAnniversaryBase):
    """Next anniversary sensor showing image of person 1."""
    
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Image Person 1"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_image_person1"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("image_url_person1", "No Image")

    @property
    def icon(self):
        return "mdi:image-outline"

    @property
    def entity_picture(self):
        """Return entity picture from Gramps if available."""
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("image_url_person1")


class GrampsWebNextAnniversaryImagePerson2Sensor(GrampsWebNextAnniversaryBase):
    """Next anniversary sensor showing image of person 2."""
    
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Image Person 2"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_image_person2"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("image_url_person2", "No Image")

    @property
    def icon(self):
        return "mdi:image-outline"

    @property
    def entity_picture(self):
        """Return entity picture from Gramps if available."""
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        return anniversary_list[self._index].get("image_url_person2")


class GrampsWebNextAnniversaryLinkSensor(GrampsWebNextAnniversaryBase):
    """Next anniversary sensor showing Gramps Web link to family."""
    
    _attr_entity_registry_enabled_default = True

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Anniversary {index + 1} Link"
        self._attr_unique_id = f"{entry.entry_id}_anniversary_{index}_link"

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        anniversaries = self.coordinator.hass.data.get(f"{DOMAIN}_anniversaries", {})
        anniversary_list = anniversaries.get(self._entry.entry_id, [])
        if self._index >= len(anniversary_list):
            return None
        family_handle = anniversary_list[self._index].get("family_handle")
        if not family_handle:
            return None
        base_url = self._entry.data.get(CONF_URL, "").rstrip("/")
        return f"{base_url}/family/{family_handle}"

    @property
    def icon(self):
        return "mdi:link"


class GrampsWebNextMilestoneSensor(CoordinatorEntity, SensorEntity):
    """Next round birthday / anniversary (for gift planning)."""

    _attr_icon = "mdi:party-popper"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Gramps Next Milestone"
        self._attr_unique_id = f"{entry.entry_id}_next_milestone"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    def _milestones(self) -> list[dict]:
        return self.coordinator.hass.data.get(f"{DOMAIN}_milestones", {}).get(
            self._entry.entry_id, []
        )

    @property
    def native_value(self):
        milestones = self._milestones()
        if not milestones:
            return None
        first = milestones[0]
        return f"{first['person_name']}: {first['label']}"

    @property
    def extra_state_attributes(self):
        milestones = self._milestones()
        if not milestones:
            return {"upcoming": []}
        first = milestones[0]
        return {
            "person_name": first["person_name"],
            "label": first["label"],
            "kind": first["kind"],
            "date": first["date"],
            "days_until": first["days_until"],
            "years": first["years"],
            "upcoming": milestones,
        }


class GrampsWebNextBirthdayRelationshipSensor(GrampsWebNextBirthdayBase):
    """Relationship of the next birthday person to the Gramps home person."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Birthday {index + 1} Relationship"
        self._attr_unique_id = f"{entry.entry_id}_birthday_{index}_relationship"

    @property
    def native_value(self):
        birthday = self._get_birthday()
        return birthday.get("relationship") if birthday else None

    @property
    def icon(self):
        return "mdi:family-tree"


class GrampsWebNextDeathdayRelationshipSensor(GrampsWebNextDeathdayBase):
    """Relationship of the next memorial-day person to the Gramps home person."""

    def __init__(self, coordinator, entry: ConfigEntry, index: int) -> None:
        super().__init__(coordinator, entry, index)
        self._attr_name = f"Next Deathday {index + 1} Relationship"
        self._attr_unique_id = f"{entry.entry_id}_deathday_{index}_relationship"

    @property
    def native_value(self):
        deathdays = self.coordinator.hass.data.get(f"{DOMAIN}_deathdays", {})
        items = deathdays.get(self._entry.entry_id, [])
        if self._index >= len(items):
            return None
        return items[self._index].get("relationship")

    @property
    def icon(self):
        return "mdi:family-tree"


class GrampsWebOnThisDaySensor(CoordinatorEntity, SensorEntity):
    """Everything in the tree that happened on today's day and month."""

    _attr_icon = "mdi:calendar-today"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Gramps On This Day"
        self._attr_unique_id = f"{entry.entry_id}_on_this_day"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    def _items(self) -> list[dict]:
        return self.coordinator.hass.data.get(f"{DOMAIN}_on_this_day", {}).get(
            self._entry.entry_id, []
        )

    @property
    def native_value(self):
        return len(self._items())

    @property
    def extra_state_attributes(self):
        items = self._items()
        return {
            "events": items,
            "text": "\n".join(i["text"] for i in items),
        }


# key, name, icon, unit, enabled by default
STAT_SENSORS = (
    ("people", "People", "mdi:account-group", None, True),
    ("families", "Families", "mdi:human-male-female-child", None, True),
    ("events", "Events", "mdi:calendar-star", None, True),
    ("places", "Places", "mdi:map-marker", None, True),
    ("media", "Media", "mdi:image-multiple", None, True),
    ("living", "Living People", "mdi:account-heart", None, True),
    ("deceased", "Deceased People", "mdi:candle", None, True),
    ("avg_age_living", "Average Age (Living)", "mdi:cake-variant", "years", True),
    ("avg_lifespan", "Average Lifespan", "mdi:timeline-clock", "years", True),
    ("oldest_living", "Oldest Living Person", "mdi:human-cane", "years", True),
    ("top_surnames", "Most Common Surname", "mdi:card-account-details", None, True),
    ("main_person", "Main Person", "mdi:account-star", None, True),
    ("sources", "Sources", "mdi:book-open-variant", None, False),
    ("citations", "Citations", "mdi:format-quote-close", None, False),
    ("repositories", "Repositories", "mdi:bank", None, False),
    ("notes", "Notes", "mdi:note-text", None, False),
    ("tags", "Tags", "mdi:tag-multiple", None, False),
    ("male", "Male People", "mdi:gender-male", None, False),
    ("female", "Female People", "mdi:gender-female", None, False),
    ("without_birth_date", "People Without Birth Date", "mdi:calendar-question", None, False),
    ("without_photo", "People Without Photo", "mdi:image-off", None, False),
)


class GrampsWebStatSensor(CoordinatorEntity, SensorEntity):
    """One statistic about the whole Gramps tree."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        unit: str | None,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_name = f"Gramps Statistics {name}"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_stat_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_entity_registry_enabled_default = enabled_default
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})
        if key not in ("top_surnames", "main_person"):
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def _stats(self) -> dict:
        return self.coordinator.hass.data.get(f"{DOMAIN}_stats", {}).get(
            self._entry.entry_id, {}
        )

    @property
    def native_value(self):
        value = self._stats().get(self._key)
        if self._key == "oldest_living":
            return value["age"] if value else None
        if self._key == "top_surnames":
            return value[0]["surname"] if value else None
        if self._key == "main_person":
            return value["name"] if value else None
        return value

    @property
    def extra_state_attributes(self):
        value = self._stats().get(self._key)
        if self._key == "oldest_living" and value:
            return {"person_name": value["name"], "birth_date": value["birth_date"]}
        if self._key == "top_surnames" and value:
            return {"top": value}
        if self._key == "main_person" and value:
            # source: "name" = matched HA owner, "gramps" = Gramps home person
            return {"source": value["source"], "person_handle": value["handle"]}
        return {}
