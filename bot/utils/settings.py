from typing import Final

from decouple import config as env

DISCORD_TOKEN: Final[str] = env("DISCORD_TOKEN")
OPENAI_API_KEY: Final[str] = env("OPENAI_API_KEY")
OPENAI_MODEL: Final[str] = env("OPENAI_MODEL", default="gpt-4o")
CMC_API_KEY: Final[str] = env("CMC_PRO_API_KEY")
VISION_BRAIN_API_KEY: Final[str] = env(
    "VISION_BRAIN_API_KEY", default="no-api-key-for-bot-to-start"
)
VISION_BRAIN_API_URL: Final[str] = env(
    "VISION_BRAIN_API_URL", default="https://visionbrain.xyz/api/tts/"
)
OLLAMA_SERVER: Final[str] = env("OLLAMA_SERVER", default="http://127.0.0.1:11434")
OLLAMA_MODEL: Final[str] = env("OLLAMA_MODEL", default="orca-mini")
BACKEND_API_URL: Final[str] = env(
    "BACKEND_API_URL", default="http://127.0.0.1:3000/api"
)
BACKEND_API_KEY: Final[str] = env("BACKEND_API_KEY")
ADMIN_USER_ID: Final[str] = env("ADMIN_USER_ID")
