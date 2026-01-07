"""CynVoice integration init: registers streaming HTTP view."""
from __future__ import annotations

import logging
from urllib.parse import unquote, quote

from aiohttp import web
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_ENTITY_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.network import get_url

from .const import (
    CONF_API_URL,
    CONF_VOICE,
    CONF_TEMPERATURE,
    CONF_REPETITION_PENALTY,
    DEFAULT_URL,
    DEFAULT_VOICE,
    DEFAULT_TEMPERATURE,
    DEFAULT_REPETITION_PENALTY,
    DOMAIN,
)
from .cynvoice_engine import CynVoiceEngine

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.TTS]

SERVICE_SPEAK = "speak"

SERVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Required("message"): cv.string,
    vol.Optional("voice"): cv.string,
    vol.Optional("temperature"): vol.Coerce(float),
    vol.Optional("repetition_penalty"): vol.Coerce(float),
})

async def async_setup(hass: HomeAssistant, config):
    """Set up CynVoice component and register streaming view."""
    hass.http.register_view(CynVoiceStreamView(hass))
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CynVoice from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_service_handle(service: ServiceCall):
        """Handle custom service to stream TTS directly to player."""
        entity_ids = service.data.get(CONF_ENTITY_ID)
        message = service.data.get("message")
        voice = service.data.get("voice") or entry.options.get(CONF_VOICE, DEFAULT_VOICE)
        temperature = service.data.get("temperature") or entry.options.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE)
        repetition_penalty = service.data.get("repetition_penalty") or entry.options.get(CONF_REPETITION_PENALTY, DEFAULT_REPETITION_PENALTY)
        api_url = entry.options.get(CONF_API_URL, entry.data.get(CONF_API_URL, DEFAULT_URL))

        # Generate local URL
        base_url = get_url(hass)
        query = (
            f"text={quote(message)}&voice={quote(voice)}&"
            f"temperature={temperature}&repetition_penalty={repetition_penalty}&"
            f"api_url={quote(api_url)}"
        )
        stream_url = f"{base_url}/api/cynvoice/tts_stream?{query}"
        
        _LOGGER.debug("Calling play_media with streaming URL: %s", stream_url)

        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": entity_ids,
                "media_content_id": stream_url,
                "media_content_type": "music",
            },
            blocking=False,
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SPEAK,
        async_service_handle,
        schema=SERVICE_SCHEMA,
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class CynVoiceStreamView(HomeAssistantView):
    """HTTP view that proxies CynVoice streaming TTS."""

    url = "/api/cynvoice/tts_stream"
    name = "api:cynvoice:tts_stream"
    requires_auth = False # Allow local media players to access without auth headers if needed

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    async def get(self, request: web.Request):
        """Handle GET request to stream audio."""
        hass = self._hass
        params = request.rel_url.query

        text = unquote(params.get("text", ""))
        voice = params.get("voice") or DEFAULT_VOICE
        try:
            temperature = float(params.get("temperature", DEFAULT_TEMPERATURE))
        except Exception:
            temperature = DEFAULT_TEMPERATURE
        try:
            repetition_penalty = float(params.get("repetition_penalty", DEFAULT_REPETITION_PENALTY))
        except Exception:
            repetition_penalty = DEFAULT_REPETITION_PENALTY

        api_url = params.get("api_url") or DEFAULT_URL

        session = async_get_clientsession(hass)
        engine = CynVoiceEngine(
            session=session,
            url=api_url,
            voice=voice,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            streaming=True,
        )

        resp = web.StreamResponse(status=200, reason="OK", headers={
            "Content-Type": "audio/wav",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        })
        await resp.prepare(request)

        try:
            upstream = await engine.async_stream_tts(
                text=text,
                voice=voice,
                temperature=temperature,
                repetition_penalty=repetition_penalty,
            )
            try:
                # 8KB chunks
                async for chunk in upstream.content.iter_chunked(8192):
                    if chunk:
                        await resp.write(chunk)
                await resp.write_eof()
            finally:
                upstream.close()
        except Exception as err:
            _LOGGER.error("CynVoice streaming error: %s", err)
            return web.Response(status=500, text="Streaming error")

        return resp
