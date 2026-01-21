"""The Gramps Web integration."""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .grampsweb_api import GrampsWebAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(hours=6)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gramps Web from a config entry."""
    from .const import CONF_URL, CONF_USERNAME, CONF_PASSWORD
    
    hass.data.setdefault(DOMAIN, {})
    
    api = GrampsWebAPI(
        url=entry.data[CONF_URL],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )
    
    coordinator = GrampsWebCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class GrampsWebCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gramps Web data."""

    def __init__(self, hass: HomeAssistant, api: GrampsWebAPI) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            return await self.hass.async_add_executor_job(self.api.get_birthdays)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
