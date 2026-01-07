"""TTS Engine for CynVoice."""
import json
import logging
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from asyncio import CancelledError
from typing import Optional, Iterator, Callable, Union, AsyncGenerator
import aiohttp

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

# Chunk size for streaming (in bytes)
CHUNK_SIZE = 8192

class AudioResponse:
    """A simple response wrapper."""
    def __init__(self, content: bytes):
        self.content = content

class StreamingAudioResponse:
    """A streaming response wrapper."""
    def __init__(self, response, on_first_chunk: Optional[Callable[[], None]] = None):
        self.response = response
        self._chunks = []
        self._first_chunk_callback = on_first_chunk
        self._first_chunk_received = False
        
    def read_all(self) -> bytes:
        """Read all chunks and return complete audio."""
        while True:
            chunk = self.response.read(CHUNK_SIZE)
            if not chunk:
                break
            
            if not self._first_chunk_received and self._first_chunk_callback:
                self._first_chunk_received = True
                self._first_chunk_callback()
                
            self._chunks.append(chunk)
        
        return b''.join(self._chunks)

class CynVoiceEngine:
    def __init__(self, url: str, voice: str, temperature: float, repetition_penalty: float, streaming: bool):
        self._url = url
        self._voice = voice
        self._temperature = temperature
        self._repetition_penalty = repetition_penalty
        self._streaming = streaming

    def get_tts(
        self,
        text: str,
        voice: str | None = None,
        temperature: float | None = None,
        repetition_penalty: float | None = None,
        streaming: bool | None = None,
        stream: bool = False, # Used by caller to indicate preference
        on_first_chunk: Optional[Callable[[], None]] = None
    ) -> Union[AudioResponse, StreamingAudioResponse]:
        """TTS request."""
        
        # Resolve parameters
        voice = voice if voice is not None else self._voice
        temperature = temperature if temperature is not None else self._temperature
        repetition_penalty = repetition_penalty if repetition_penalty is not None else self._repetition_penalty
        streaming = streaming if streaming is not None else self._streaming
        
        # stream parameter is from tts.py logic, streaming parameter is for API payload
        # If tts.py asks for stream=True, we should probably set payload streaming=True too
        if stream:
            # Note: We are ignoring the 'stream' request param from HA because
            # we are forcing standard download for robustness, as requested.
            pass

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
            "use_memory_cache": "off",
            "normalize": True,
            "streaming": False,
            "max_new_tokens": 1024,
            "top_p": 0.8,
            "repetition_penalty": repetition_penalty,
            "temperature": temperature
        }

        _LOGGER.debug("CynVoice API request: %s", payload)

        try:
            req = Request(
                self._url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            
            if stream:
                # Fallback to standard request even if stream requested
                with urlopen(req, timeout=60) as resp:
                    return AudioResponse(resp.read())
            else:
                with urlopen(req, timeout=60) as resp:
                    return AudioResponse(resp.read())

        except Exception as e:
            _LOGGER.error("Error fetching TTS: %s", e)
            raise HomeAssistantError(f"Error fetching TTS: {e}") from e

    async def async_get_tts_stream(
        self,
        text: str,
        voice: str | None = None,
        temperature: float | None = None,
        repetition_penalty: float | None = None
    ) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio."""
        
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
            "use_memory_cache": "off",
            "normalize": True,
            "streaming": True, # Always stream here
            "max_new_tokens": 1024,
            "top_p": 0.8,
            "repetition_penalty": repetition_penalty,
            "temperature": temperature
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self._url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    response.raise_for_status()
                    
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        if chunk:
                            yield chunk

            except Exception as e:
                _LOGGER.error("Streaming error: %s", e)
                raise HomeAssistantError(f"Streaming error: {e}") from e
