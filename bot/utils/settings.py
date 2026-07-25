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

# dynamodb (credentials/region default to boto3's chain — i.e. ~/.aws/ — when unset)
AWS_REGION: Optional[str] = config("AWS_REGION", default=None)
AWS_ACCESS_KEY_ID: Optional[str] = config("AWS_ACCESS_KEY_ID", default=None)
AWS_SECRET_ACCESS_KEY: Optional[str] = config("AWS_SECRET_ACCESS_KEY", default=None)
DYNAMODB_TABLE_NAME: str = config("DYNAMODB_TABLE_NAME", default="elongpt-completions")

# tools (no setting this will not enable certain tools the model has)
# web search authenticates with OPENAI_API_KEY, so it needs no key of its own
DGPT_SEARCH_URL: str = config(
    "DGPT_SEARCH_URL",
    default="https://api.deutschlandgpt.de/v2/search",
)
EVENTS_VOICE_CHANNEL_ID: Optional[int] = config(
    "EVENTS_VOICE_CHANNEL_ID",
    default=None,
    cast=lambda v: int(v) if v else None,
)

# idle-voice auto-mover (feature is off unless timeout + target are both set)
IDLE_VOICE_TIMEOUT_SECONDS: Optional[int] = config(
    "IDLE_VOICE_TIMEOUT_SECONDS",
    default=None,
    cast=lambda v: int(v) if v else None,
)
IDLE_VOICE_TARGET_CHANNEL_ID: Optional[int] = config(
    "IDLE_VOICE_TARGET_CHANNEL_ID",
    default=None,
    cast=lambda v: int(v) if v else None,
)
IDLE_VOICE_NOTIFY_CHANNEL_ID: Optional[int] = config(
    "IDLE_VOICE_NOTIFY_CHANNEL_ID",
    default=None,
    cast=lambda v: int(v) if v else None,
)
