from typing import Optional

from decouple import config

# required
DISCORD_TOKEN: str = config("DISCORD_TOKEN")
ADMIN_USER_ID: str = config("ADMIN_USER_ID")
OPENAI_API_KEY: str = config("OPENAI_API_KEY")

# optional
OPENAI_CHAT_MODEL: str = config("OPENAI_CHAT_MODEL", default="gpt-5.4-mini")
OPENAI_IMAGE_MODEL: str = config("OPENAI_IMAGE_MODEL", default="gpt-image-1.5")
OPENAI_API_BASE_URL: Optional[str] = config("OPENAI_API_BASE_URL", default=None)
CMC_API_KEY: Optional[str] = config("CMC_PRO_API_KEY", default=None)
BACKEND_API_KEY: Optional[str] = config("BACKEND_API_KEY", default=None)
BACKEND_API_URL: Optional[str] = config("BACKEND_API_URL", default=None)

# tools (no setting this will not enable certain tools the model has)
BRAVE_API_KEY: Optional[str] = config("BRAVE_API_KEY", default=None)
EVENTS_VOICE_CHANNEL_ID: Optional[int] = config(
    "EVENTS_VOICE_CHANNEL_ID",
    default=None,
    cast=lambda v: int(v) if v else None,
)
