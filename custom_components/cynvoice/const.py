"""Constants for CynVoice integration."""

DOMAIN = "cynvoice"
DEFAULT_NAME = "CynVoice"

CONF_API_URL = "url"
DEFAULT_URL = "http://35.196.176.54/v1/tts"


CONF_VOICE = "voice"
DEFAULT_VOICE = "cyn2"

CONF_SPEED = "speed"
CONF_TEMPERATURE = "temperature"
CONF_REPETITION_PENALTY = "repetition_penalty"
CONF_STREAMING = "streaming"
UNIQUE_ID = "unique_id"

# Default values
DEFAULT_TEMPERATURE = 0.95
DEFAULT_REPETITION_PENALTY = 1.1
DEFAULT_STREAMING = False

SUPPORTED_LANGUAGES = ["en"]
