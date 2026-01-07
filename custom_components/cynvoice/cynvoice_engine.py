"""TTS Engine for CynVoice."""
import json
import logging
import aiohttp
from typing import Optional, Callable, Union

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

class AudioResponse:
    """A simple response wrapper."""
    def __init__(self, content: bytes):
        self.content = content

class CynVoiceEngine:
    def __init__(self, session: aiohttp.ClientSession, url: str, voice: str, temperature: float, repetition_penalty: float, streaming: bool):
        self._session = session
        self._url = url
        self._voice = voice
        self._temperature = temperature
        self._repetition_penalty = repetition_penalty
        self._streaming = streaming

    async def async_get_tts(
        self,
        text: str,
        voice: str | None = None,
        temperature: float | None = None,
        repetition_penalty: float | None = None,
        streaming: bool | None = None,
    ) -> AudioResponse:
        """Async TTS request."""
        
        # Resolve parameters
        voice = voice if voice is not None else self._voice
        temperature = temperature if temperature is not None else self._temperature
        repetition_penalty = repetition_penalty if repetition_penalty is not None else self._repetition_penalty
        
        # Force streaming=False in payload to match our current stable strategy
        
        headers = {
            "Content-Type": "application/json",
            "accept": "*/*"
        }

        payload = {
            "text": text,
            "chunk_length": 200,
            "format": "wav",
            "references": [],
            "reference_id": voice,
            "seed": None,
            "use_memory_cache": "on",
            "normalize": True,
            "streaming": False,
            "max_new_tokens": 1024,
            "top_p": 0.8,
            "repetition_penalty": repetition_penalty,
            "temperature": temperature
        }

        _LOGGER.debug("CynVoice API request: %s", payload)

        try:
            # Use a longer timeout for TTS generation
            timeout = aiohttp.ClientTimeout(total=60)
            async with self._session.post(
                self._url,
                json=payload,
                headers=headers,
                timeout=timeout
            ) as response:
                response.raise_for_status()
                data = await response.read()
                return AudioResponse(data)

        except Exception as e:
            _LOGGER.error("Error fetching TTS: %s", e)
            raise HomeAssistantError(f"Error fetching TTS: {e}") from e

    async def async_stream_tts(
        self,
        text: str,
        voice: str | None = None,
        temperature: float | None = None,
        repetition_penalty: float | None = None,
    ):
        """Async streaming TTS request returning an aiohttp response object.

        Yields chunks from CynVoice server with streaming enabled.
        """

        voice = voice if voice is not None else self._voice
        temperature = temperature if temperature is not None else self._temperature
        repetition_penalty = repetition_penalty if repetition_penalty is not None else self._repetition_penalty

        headers = {
            "Content-Type": "application/json",
            "accept": "*/*"
        }

        payload = {
            "text": text,
            "chunk_length": 200,
            "format": "wav",
            "references": [],
            "reference_id": voice,
            "seed": None,
            "use_memory_cache": "on",
            "normalize": True,
            "streaming": True,
            "max_new_tokens": 1024,
            "top_p": 0.8,
            "repetition_penalty": repetition_penalty,
            "temperature": temperature
        }

        _LOGGER.debug("CynVoice API streaming request: %s", payload)

        timeout = aiohttp.ClientTimeout(total=60)
        response = await self._session.post(
            self._url,
            json=payload,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        return response
