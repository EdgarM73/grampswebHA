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
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import persistent_notification

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CALENDAR, Platform.BINARY_SENSOR]

EVENT_GRAMPS = f"{DOMAIN}_event"

SCAN_INTERVAL = timedelta(hours=6)


async def _async_owner_person_name(hass: HomeAssistant) -> str | None:
    """Name of the HA person linked to the owner account (or the owner's name)."""
    try:
        users = await hass.auth.async_get_users()
        owner = next((u for u in users if u.is_owner and u.is_active), None)
        if owner is None:
            return None
        for state in hass.states.async_all("person"):
            if state.attributes.get("user_id") == owner.id:
                return state.attributes.get("friendly_name") or state.name
        return owner.name
    except Exception as err:  # never block setup because of this
        _LOGGER.debug("Could not determine the owner person: %s", err)
        return None


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
            language=hass.config.language,
        )
        # Relationships are calculated from the HA owner's person if Gramps
        # has exactly one person with that name.
        api.main_person_name = await _async_owner_person_name(hass)
        _LOGGER.debug("HA owner person name: %s", api.main_person_name)

        # Get scan interval from config (in hours), default to DEFAULT_SCAN_INTERVAL
        scan_interval_hours = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        
        coordinator = GrampsWebCoordinator(hass, api, entry, scan_interval_hours=scan_interval_hours)

        # Try initial refresh, but don't fail if it doesn't work
        try:
            await coordinator.async_config_entry_first_refresh()
            _LOGGER.info("Initial data fetch successful")
        except Exception as refresh_err:
            _LOGGER.warning("Initial data fetch failed (will retry): %s", refresh_err)
            # Don't fail setup, just log the warning

        hass.data[DOMAIN][entry.entry_id] = coordinator

        # Refresh every night: the list is relative to "today" (days_until,
        # next date, ordering), so it goes stale after a day even if the
        # configured scan interval is much longer.
        async def _nightly_refresh(_now) -> None:
            _LOGGER.debug("Nightly refresh of Gramps data")
            await hass.async_add_executor_job(api.invalidate_cache)
            await coordinator.async_refresh()
            coordinator.fire_today_events()

        entry.async_on_unload(
            async_track_time_change(hass, _nightly_refresh, hour=0, minute=5, second=0)
        )

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

    def __init__(self, hass: HomeAssistant, api, entry: ConfigEntry, scan_interval_hours: int = None) -> None:
        """Initialize."""
        if scan_interval_hours is None:
            scan_interval_hours = DEFAULT_SCAN_INTERVAL
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=scan_interval_hours),
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
                _LOGGER.debug(
                    "Deathdays fetched: %s entries%s",
                    len(deathdays) if deathdays else 0,
                    f" | first: {deathdays[0]}" if deathdays else "",
                )
            else:
                _LOGGER.debug("Deathdays disabled in config; skipping fetch")
            
            # Fetch anniversaries if enabled
            if self.entry.data.get("show_anniversaries", False):
                anniversaries = await self.hass.async_add_executor_job(self.api.get_anniversaries)
                self.hass.data.setdefault(f"{DOMAIN}_anniversaries", {})[self.entry.entry_id] = anniversaries or []
                _LOGGER.debug(
                    "Anniversaries fetched: %s entries%s",
                    len(anniversaries) if anniversaries else 0,
                    f" | first: {anniversaries[0]}" if anniversaries else "",
                )
            else:
                _LOGGER.debug("Anniversaries disabled in config; skipping fetch")
            
            # Round birthdays / anniversaries coming up in the next year
            milestones = await self.hass.async_add_executor_job(
                self.api.get_milestones,
                365,
                10,
                self.entry.data.get("show_deathdays", False),
                self.entry.data.get("show_anniversaries", False),
            )
            self.hass.data.setdefault(f"{DOMAIN}_milestones", {})[
                self.entry.entry_id
            ] = milestones or []

            # "On this day" and tree statistics (served from the cached snapshot)
            on_this_day = await self.hass.async_add_executor_job(
                self.api.get_on_this_day
            )
            self.hass.data.setdefault(f"{DOMAIN}_on_this_day", {})[
                self.entry.entry_id
            ] = on_this_day or []
            stats = await self.hass.async_add_executor_job(self.api.get_statistics)
            self.hass.data.setdefault(f"{DOMAIN}_stats", {})[
                self.entry.entry_id
            ] = stats or {}

            # Store current list for next comparison
            self.last_birthdays = data or []
            
            return data
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def fire_today_events(self) -> None:
        """Fire a `gramps_ha_event` on the event bus for every entry that is today.

        Meant to be called once per day right after the nightly refresh.
        """
        today = date.today().isoformat()
        sources = (
            ("birthday", self.data or [], "next_birthday", "age"),
            (
                "deathday",
                self.hass.data.get(f"{DOMAIN}_deathdays", {}).get(self.entry.entry_id, []),
                "next_deathday",
                "years_ago",
            ),
            (
                "anniversary",
                self.hass.data.get(f"{DOMAIN}_anniversaries", {}).get(
                    self.entry.entry_id, []
                ),
                "next_anniversary",
                "years_together",
            ),
        )
        for kind, items, date_key, years_key in sources:
            for item in items:
                if item.get(date_key) != today:
                    continue
                self.hass.bus.async_fire(
                    EVENT_GRAMPS,
                    {
                        "entry_id": self.entry.entry_id,
                        "type": kind,
                        "person_name": item.get("person_name"),
                        "years": item.get(years_key),
                        "milestone": item.get("milestone"),
                    },
                )
                _LOGGER.debug("Fired %s for %s", EVENT_GRAMPS, item.get("person_name"))

    async def _check_notifications(self, current_birthdays):
        """Send only one notification: always 1 day before the event."""
        if not current_birthdays:
            return

        today = date.today()
        tomorrow = today + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")

        for person in current_birthdays:
            next_bday = person.get("next_birthday", "")
            if next_bday.startswith(tomorrow_str):
                age = person.get("age", "?")
                title = "🎉 Geburtstag morgen!"
                message = f"{person.get('person_name')} hat morgen Geburtstag!\n\nZukünftiges Alter: {age + 1} Jahre"
                persistent_notification.create(
                    self.hass,
                    message,
                    title=title,
                    notification_id=f"gramps_tomorrow_{person.get('person_name')}"
                )
                _LOGGER.info("Birthday tomorrow notification: %s", person.get("person_name"))
