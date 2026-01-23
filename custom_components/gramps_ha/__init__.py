"""The Gramps HA integration."""

import logging
from datetime import timedelta, datetime, date
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    async_get as async_get_device_registry,
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import persistent_notification

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(hours=6)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gramps HA from a config entry."""
    _LOGGER.info("Setting up Gramps HA integration")

    try:
        from .grampsweb_api import GrampsWebAPI

        hass.data.setdefault(DOMAIN, {})

        url = entry.data.get(CONF_URL)
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)

        _LOGGER.debug("Gramps Web URL: %s", url)
        _LOGGER.debug("Username provided: %s", bool(username))

        # Register device in device registry
        device_registry = async_get_device_registry(hass)
        device = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "Gramps Web",
            manufacturer="Gramps Web",
            model="Birthday Tracker",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=url,
        )
        _LOGGER.debug("Device registered: %s", device.name)

        api = GrampsWebAPI(
            url=url,
            username=username,
            password=password,
            hass_config_path=hass.config.config_dir,
        )

        coordinator = GrampsWebCoordinator(hass, api, entry)

        # Try initial refresh, but don't fail if it doesn't work
        try:
            await coordinator.async_config_entry_first_refresh()
            _LOGGER.info("Initial data fetch successful")
        except Exception as refresh_err:
            _LOGGER.warning("Initial data fetch failed (will retry): %s", refresh_err)
            # Don't fail setup, just log the warning

        hass.data[DOMAIN][entry.entry_id] = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        _LOGGER.info("Gramps HA setup completed successfully")
        return True

    except Exception as err:
        _LOGGER.error("Failed to setup Gramps HA: %s", err, exc_info=True)
        return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        if unload_ok := await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        ):
            hass.data[DOMAIN].pop(entry.entry_id)

        return unload_ok
    except Exception as err:
        _LOGGER.error("Failed to unload Gramps HA: %s", err)
        return False


class GrampsWebCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gramps Web data."""

    def __init__(self, hass: HomeAssistant, api, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api
        self.entry = entry
        self.last_birthdays = []  # Track previous list for comparison

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            _LOGGER.debug("Fetching birthday data from Gramps Web")
            data = await self.hass.async_add_executor_job(self.api.get_birthdays)
            _LOGGER.debug("Fetched %s birthdays", len(data) if data else 0)
            
            # Check for notifications
            await self._check_notifications(data)
            
            # Fetch deathdays if enabled
            if self.entry.data.get("show_deathdays", False):
                deathdays = await self.hass.async_add_executor_job(self.api.get_deathdays)
                self.hass.data.setdefault(f"{DOMAIN}_deathdays", {})[self.entry.entry_id] = deathdays or []
            
            # Fetch anniversaries if enabled
            if self.entry.data.get("show_anniversaries", False):
                anniversaries = await self.hass.async_add_executor_job(self.api.get_anniversaries)
                self.hass.data.setdefault(f"{DOMAIN}_anniversaries", {})[self.entry.entry_id] = anniversaries or []
            
            # Store current list for next comparison
            self.last_birthdays = data or []
            
            return data
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def _check_notifications(self, current_birthdays):
        """Check for new birthdays and birthdays tomorrow."""
        if not current_birthdays:
            return
        
        # Check for new people in the list
        current_names = {b.get("person_name") for b in current_birthdays}
        last_names = {b.get("person_name") for b in self.last_birthdays}
        new_people = current_names - last_names
        
        if new_people:
            for person in current_birthdays:
                if person.get("person_name") in new_people:
                    age = person.get("age", "?")
                    next_birthday = person.get("next_birthday", "?")
                    title = "🎂 Neuer Geburtstag erkannt"
                    message = f"{person.get('person_name')} hat bald Geburtstag!\n\nDatum: {next_birthday}\nAlter: {age} Jahre"
                    persistent_notification.create(
                        self.hass,
                        message,
                        title=title,
                        notification_id=f"gramps_new_{person.get('person_name')}"
                    )
                    _LOGGER.info("New birthday notification: %s", person.get("person_name"))
        
        # Check for birthdays tomorrow
        today = date.today()
        tomorrow = today.replace(day=today.day + 1) if today.day < 28 else date(today.year if today.month < 12 else today.year + 1, today.month if today.month < 12 else 1, 1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        
        for person in current_birthdays:
            next_bday = person.get("next_birthday", "")
            if next_bday.startswith(tomorrow_str):
                age = person.get("age", "?")
                title = "🎉 Geburtstag morgen!"
                message = f"{person.get('person_name')} hat morgen Geburtstag!\n\nZukunftiges Alter: {age + 1} Jahre"
                persistent_notification.create(
                    self.hass,
                    message,
                    title=title,
                    notification_id=f"gramps_tomorrow_{person.get('person_name')}"
                )
                _LOGGER.info("Birthday tomorrow notification: %s", person.get("person_name"))
