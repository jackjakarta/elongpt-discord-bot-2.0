from typing import Final

from decouple import config as env

DISCORD_TOKEN: Final[str] = env("DISCORD_TOKEN")
EVENTS_VOICE_CHANNEL_ID: Final[int] = env("EVENTS_VOICE_CHANNEL_ID", cast=int)
OPENAI_API_KEY: Final[str] = env("OPENAI_API_KEY")
OPENAI_MODEL: Final[str] = env("OPENAI_MODEL")
CMC_API_KEY: Final[str] = env("CMC_PRO_API_KEY")
ADMIN_USER_ID: Final[str] = env("ADMIN_USER_ID")
BACKEND_API_KEY: Final[str] = env("BACKEND_API_KEY")
BACKEND_API_URL: Final[str] = env("BACKEND_API_URL")
UTILS_API_KEY: Final[str] = env("UTILS_API_KEY")
UTILS_API_URL: Final[str] = env("UTILS_API_URL")
