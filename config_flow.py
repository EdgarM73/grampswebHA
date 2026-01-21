"""Config flow for Gramps Web integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD
from .grampsweb_api import GrampsWebAPI

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = GrampsWebAPI(
        url=data[CONF_URL],
        username=data.get(CONF_USERNAME),
        password=data.get(CONF_PASSWORD),
    )

    # Test the connection
    try:
        await hass.async_add_executor_job(api.get_people)
    except Exception as err:
        _LOGGER.error("Failed to connect to Gramps Web: %s", err)
        raise

    return {"title": "Gramps Web"}


class GrampsWebConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gramps Web."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
