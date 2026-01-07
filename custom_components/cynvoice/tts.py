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
    TTSAudioRequest,
    TTSAudioResponse,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

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

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CynVoice TTS from a config entry."""
    async_add_entities([CynVoiceEntity(hass, config_entry)])


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
        session = async_get_clientsession(hass)
        self._engine = CynVoiceEngine(
            session=session,
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

        # If streaming is requested, prefer streaming URL via our proxy view
        if streaming:
            try:
                # Build streaming URL for clients: /api/cynvoice/tts_stream?text=...
                base = "/api/cynvoice/tts_stream"
                # Note: HA will not use this URL directly in TTS service, so we
                # fall back to non-streaming bytes for compatibility.
                # Still log the URL so users can use media_player.play_media.
                from urllib.parse import quote
                q = (
                    f"text={quote(message)}&voice={quote(voice)}&"
                    f"temperature={temperature}&repetition_penalty={repetition_penalty}&"
                    f"api_url={quote(self._get_option_or_config(CONF_API_URL, DEFAULT_URL))}"
                )
                stream_url = f"{base}?{q}"
                _LOGGER.info("CynVoice streaming URL: %s", stream_url)
            except Exception:
                pass

        # Fall back to non-streaming full download to satisfy HA TTS service
        try:
            audio_response = await self._engine.async_get_tts(
                text=message,
                voice=voice,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
                streaming=False,
            )
            if not audio_response:
                return None
            data = audio_response.content
            return "wav", data
        except Exception as e:
            _LOGGER.error("Error generating TTS: %s", e)
            return None

    async def async_stream_tts_audio(
        self, request: TTSAudioRequest
    ) -> TTSAudioResponse | None:
        """Stream TTS audio for Assist Pipeline."""
        # 1. Accumulate the full text from the generator
        # CynVoice currently requires full text context
        text_parts = []
        async for chunk in request.message_gen:
            text_parts.append(chunk)
        message = "".join(text_parts)

        # 2. Extract options
        options = request.options or {}
        voice = options.get(CONF_VOICE, self._engine._voice)
        temperature = options.get(CONF_TEMPERATURE, self._engine._temperature)
        repetition_penalty = options.get(CONF_REPETITION_PENALTY, self._engine._repetition_penalty)

        # 3. Stream from engine
        # We define a generator that yields bytes from the upstream response
        async def audio_data_gen():
            try:
                async for chunk in self._engine.async_stream_tts(
                    text=message,
                    voice=voice,
                    temperature=temperature,
                    repetition_penalty=repetition_penalty,
                ):
                    yield chunk
            except Exception as err:
                _LOGGER.error("Streaming failed: %s", err)

        return TTSAudioResponse(
            extension="wav",
            data_gen=audio_data_gen(),
        )
