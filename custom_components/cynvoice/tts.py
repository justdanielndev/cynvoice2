"""Support for CynVoice TTS."""
from __future__ import annotations

import logging
from typing import Any
from functools import partial
import asyncio

import voluptuous as vol

from homeassistant.components.tts import (
    TextToSpeechEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
from .cynvoice_engine import CynVoiceEngine

_LOGGER = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["en"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_URL, default=DEFAULT_URL): cv.string,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): cv.string,
        vol.Optional(CONF_TEMPERATURE, default=DEFAULT_TEMPERATURE): vol.Coerce(float),
        vol.Optional(CONF_REPETITION_PENALTY, default=DEFAULT_REPETITION_PENALTY): vol.Coerce(float),
        vol.Optional(CONF_STREAMING, default=DEFAULT_STREAMING): cv.boolean,
    }
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CynVoice TTS from a config entry."""
    async_add_entities([CynVoiceEntity(hass, config_entry)])

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the CynVoice TTS platform."""
    async_add_entities([CynVoiceEntity(hass, config)])


class CynVoiceEntity(TextToSpeechEntity):
    """The CynVoice TTS Entity."""

    _attr_has_entity_name = True
    _attr_name = "CynVoice"

    def __init__(self, hass: HomeAssistant, config: ConfigEntry | ConfigType) -> None:
        """Init CynVoice TTS service."""
        self.hass = hass
        if isinstance(config, ConfigEntry):
             self._config = config.data
             self._options = config.options
             self._attr_unique_id = config.entry_id
        else:
             self._config = config
             self._options = {}
             self._attr_unique_id = "cynvoice_yaml"

        # Initialize engine
        self._engine = CynVoiceEngine(
            url=self._get_option_or_config(CONF_API_URL, DEFAULT_URL),
            voice=self._get_option_or_config(CONF_VOICE, DEFAULT_VOICE),
            temperature=self._get_option_or_config(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
            repetition_penalty=self._get_option_or_config(CONF_REPETITION_PENALTY, DEFAULT_REPETITION_PENALTY),
            streaming=self._get_option_or_config(CONF_STREAMING, DEFAULT_STREAMING),
        )

    def _get_option_or_config(self, key: str, default: Any) -> Any:
        """Get value from options, falling back to config, then default."""
        return self._options.get(key, self._config.get(key, default))

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return "en"

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options."""
        return [
            CONF_VOICE,
            CONF_TEMPERATURE,
            CONF_REPETITION_PENALTY,
            CONF_STREAMING,
        ]

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> tuple[str, bytes] | None:
        """Load TTS from CynVoice."""
        options = options or {}
        
        # Override parameters from options if present
        voice = options.get(CONF_VOICE, self._engine._voice)
        temperature = options.get(CONF_TEMPERATURE, self._engine._temperature)
        repetition_penalty = options.get(CONF_REPETITION_PENALTY, self._engine._repetition_penalty)
        streaming = options.get(CONF_STREAMING, self._engine._streaming)

        try:
            loop = asyncio.get_running_loop()
            audio_response = await loop.run_in_executor(
                None,
                partial(
                    self._engine.get_tts,
                    text=message,
                    voice=voice,
                    temperature=temperature,
                    repetition_penalty=repetition_penalty,
                    streaming=streaming,
                    stream=False # Regular request
                )
            )
            
            if not audio_response:
                return None
                
            if hasattr(audio_response, 'read_all'):
                data = audio_response.read_all()
            else:
                data = audio_response.content

            return "wav", data

        except Exception as e:
            _LOGGER.error("Error generating TTS: %s", e)
            return None
