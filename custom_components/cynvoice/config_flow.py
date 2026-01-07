"""Config flow for CynVoice."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_API_URL,
    CONF_VOICE,
    CONF_TEMPERATURE,
    CONF_REPETITION_PENALTY,
    CONF_STREAMING,
    DEFAULT_URL,
    DEFAULT_VOICE,
    DEFAULT_TEMPERATURE,
    DEFAULT_REPETITION_PENALTY,
    DEFAULT_STREAMING,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_URL, default=DEFAULT_URL): str,
        vol.Required(CONF_VOICE, default=DEFAULT_VOICE): str,
    }
)

class CynVoiceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CynVoice."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        return self.async_create_entry(title="CynVoice", data=user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return CynVoiceOptionsFlowHandler(config_entry)


class CynVoiceOptionsFlowHandler(config_entries.OptionsFlow):
    """CynVoice config flow options handler."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize HACS options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_VOICE,
                        default=self.config_entry.options.get(
                            CONF_VOICE, self.config_entry.data.get(CONF_VOICE, DEFAULT_VOICE)
                        ),
                    ): str,
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=self.config_entry.options.get(
                            CONF_TEMPERATURE, DEFAULT_TEMPERATURE
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_REPETITION_PENALTY,
                        default=self.config_entry.options.get(
                            CONF_REPETITION_PENALTY, DEFAULT_REPETITION_PENALTY
                        ),
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_STREAMING,
                        default=self.config_entry.options.get(
                            CONF_STREAMING, DEFAULT_STREAMING
                        ),
                    ): bool,
                }
            ),
        )
