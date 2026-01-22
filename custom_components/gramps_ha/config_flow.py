"""Config flow for Gramps Web integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_SURNAME_FILTER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SURNAME_FILTER): cv.string,
    }
)


class GrampsHAConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gramps HA."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            errors = {}
            
            # Validate URL format
            url = user_input.get(CONF_URL, "").strip()
            if not url:
                errors[CONF_URL] = "required"
            elif not url.startswith(("http://", "https://")):
                errors[CONF_URL] = "invalid_url"
            
            if not errors:
                return self.async_create_entry(
                    title="Gramps HA",
                    data=user_input
                )
            
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
        )
