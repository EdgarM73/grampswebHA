"""The Gramps HA integration."""
import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_SURNAME_FILTER

_LOGGER = logging.getLogger(__name__)

# Setup file logging
def setup_file_logging(hass: HomeAssistant):
    """Setup file logging for Gramps HA."""
    try:
        log_file = Path(hass.config.path("gramps_ha.log"))
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to our logger and the API logger
        logger = logging.getLogger(__name__)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        
        api_logger = logging.getLogger(f"{__name__}.grampsweb_api")
        api_logger.addHandler(file_handler)
        api_logger.setLevel(logging.DEBUG)
        
        _LOGGER.info("File logging setup complete: %s", log_file)
    except Exception as err:
        _LOGGER.error("Failed to setup file logging: %s", err)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SCAN_INTERVAL = timedelta(hours=6)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gramps HA from a config entry."""
    _LOGGER.info("Setting up Gramps HA integration")
    
    # Setup file logging
    setup_file_logging(hass)
    
    try:
        from .grampsweb_api import GrampsWebAPI
        
        hass.data.setdefault(DOMAIN, {})
        
        url = entry.data.get(CONF_URL)
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        surname_filter = entry.data.get(CONF_SURNAME_FILTER, "")
        
        _LOGGER.debug("Gramps Web URL: %s", url)
        _LOGGER.debug("Username provided: %s", bool(username))
        _LOGGER.debug("Surname filter: %s", surname_filter if surname_filter else "None")
        
        api = GrampsWebAPI(
            url=url,
            username=username,
            password=password,
            surname_filter=surname_filter,
        )
        
        coordinator = GrampsWebCoordinator(hass, api)
        
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
        if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
            hass.data[DOMAIN].pop(entry.entry_id)
        
        return unload_ok
    except Exception as err:
        _LOGGER.error("Failed to unload Gramps HA: %s", err)
        return False


class GrampsWebCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gramps Web data."""

    def __init__(self, hass: HomeAssistant, api) -> None:
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
            _LOGGER.debug("Fetching birthday data from Gramps Web")
            data = await self.hass.async_add_executor_job(self.api.get_birthdays)
            _LOGGER.debug("Fetched %s birthdays", len(data) if data else 0)
            return data
        except Exception as err:
            _LOGGER.error("Error fetching data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
