"""Calendar platform for Gramps Web integration."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_SHOW_DEATHDAYS,
    CONF_SHOW_ANNIVERSARIES,
    DEFAULT_SHOW_DEATHDAYS,
    DEFAULT_SHOW_ANNIVERSARIES,
)

_LOGGER = logging.getLogger(__name__)

# Only refreshes the "next event" state; the data itself comes from the
# cached Gramps snapshot, so this does not hit the Gramps server.
SCAN_INTERVAL = timedelta(hours=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Gramps calendar."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GrampsWebCalendar(coordinator.api, entry)], True)


class GrampsWebCalendar(CalendarEntity):
    """Calendar with birthdays, memorial days and anniversaries."""

    _attr_icon = "mdi:family-tree"

    def __init__(self, api, entry: ConfigEntry) -> None:
        self._api = api
        self._entry = entry
        self._event: CalendarEvent | None = None
        self._attr_name = "Gramps Calendar"
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def event(self) -> CalendarEvent | None:
        """Next upcoming event."""
        return self._event

    def _include(self) -> tuple[bool, bool]:
        data = self._entry.data
        return (
            bool(data.get(CONF_SHOW_DEATHDAYS, DEFAULT_SHOW_DEATHDAYS)),
            bool(data.get(CONF_SHOW_ANNIVERSARIES, DEFAULT_SHOW_ANNIVERSARIES)),
        )

    @staticmethod
    def _to_event(item: dict) -> CalendarEvent:
        start: date = item["date"]
        return CalendarEvent(
            start=start,
            end=start + timedelta(days=1),
            summary=item["summary"],
            description=item.get("milestone") or None,
        )

    async def async_update(self) -> None:
        """Compute the next event."""
        today = dt_util.now().date()
        deaths, anniversaries = self._include()
        items = await self.hass.async_add_executor_job(
            self._api.get_calendar_events,
            today,
            today + timedelta(days=366),
            deaths,
            anniversaries,
        )
        self._event = self._to_event(items[0]) if items else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return events in the requested range (end is exclusive)."""
        start = dt_util.as_local(start_date).date()
        end = dt_util.as_local(end_date - timedelta(seconds=1)).date()
        if end < start:
            return []
        deaths, anniversaries = self._include()
        items = await hass.async_add_executor_job(
            self._api.get_calendar_events, start, end, deaths, anniversaries
        )
        return [self._to_event(item) for item in items]
