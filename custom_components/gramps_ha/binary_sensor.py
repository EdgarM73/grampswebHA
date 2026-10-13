"""Binary sensors: is there a birthday / memorial day / anniversary today?"""

from __future__ import annotations

from datetime import date

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SHOW_DEATHDAYS,
    CONF_SHOW_ANNIVERSARIES,
    DEFAULT_SHOW_DEATHDAYS,
    DEFAULT_SHOW_ANNIVERSARIES,
)

# kind -> (name, icon, date key inside the list items, hass.data key or None)
KINDS = {
    "birthday": ("Birthday Today", "mdi:cake-variant", "next_birthday", None),
    "deathday": ("Memorial Day Today", "mdi:candle", "next_deathday", f"{DOMAIN}_deathdays"),
    "anniversary": (
        "Anniversary Today",
        "mdi:ring",
        "next_anniversary",
        f"{DOMAIN}_anniversaries",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    kinds = ["birthday"]
    if entry.data.get(CONF_SHOW_DEATHDAYS, DEFAULT_SHOW_DEATHDAYS):
        kinds.append("deathday")
    if entry.data.get(CONF_SHOW_ANNIVERSARIES, DEFAULT_SHOW_ANNIVERSARIES):
        kinds.append("anniversary")
    async_add_entities(GrampsWebTodayBinarySensor(coordinator, entry, k) for k in kinds)


class GrampsWebTodayBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """On while at least one entry of this kind falls on today's date."""

    def __init__(self, coordinator, entry: ConfigEntry, kind: str) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._kind = kind
        name, icon, _date_key, _data_key = KINDS[kind]
        self._attr_name = f"Gramps {name}"
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_today_{kind}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    def _today_items(self) -> list[dict]:
        _name, _icon, date_key, data_key = KINDS[self._kind]
        if data_key is None:
            items = self.coordinator.data or []
        else:
            items = self.coordinator.hass.data.get(data_key, {}).get(
                self._entry.entry_id, []
            )
        today = date.today().isoformat()
        return [i for i in items if i.get(date_key) == today]

    @property
    def is_on(self) -> bool:
        return bool(self._today_items())

    @property
    def extra_state_attributes(self) -> dict:
        items = self._today_items()
        return {
            "count": len(items),
            "names": [i.get("person_name") for i in items],
            "milestones": [i["milestone"] for i in items if i.get("milestone")],
        }
