from typing import Final, Optional

from decouple import config as env

DISCORD_TOKEN: Final[str] = env("DISCORD_TOKEN")
ADMIN_USER_ID: Final[str] = env("ADMIN_USER_ID")

OPENAI_API_KEY: Final[str] = env("OPENAI_API_KEY")
OPENAI_API_BASE_URL: Optional[str] = env("OPENAI_API_BASE_URL", None)
OPENAI_MODEL: Final[str] = env("OPENAI_MODEL", "gpt-5.4-mini")

BACKEND_API_KEY: Optional[str] = env("BACKEND_API_KEY", None)
BACKEND_API_URL: Optional[str] = env("BACKEND_API_URL", None)

CMC_API_KEY: Optional[str] = env("CMC_PRO_API_KEY", None)
EVENTS_VOICE_CHANNEL_ID: Optional[int] = env(
    "EVENTS_VOICE_CHANNEL_ID",
    default=None,
    cast=lambda v: int(v) if v else None,
)
