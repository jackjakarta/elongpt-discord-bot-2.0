from typing import Final

from decouple import config as env

DISCORD_TOKEN: Final[str] = env("DISCORD_TOKEN")
OPENAI_API_KEY: Final[str] = env("OPENAI_API_KEY")
OPENAI_MODEL: Final[str] = env("OPENAI_MODEL", default="gpt-4o")
CMC_API_KEY: Final[str] = env("CMC_PRO_API_KEY")
OLLAMA_SERVER: Final[str] = env("OLLAMA_SERVER", default="http://127.0.0.1:11434")
OLLAMA_MODEL: Final[str] = env("OLLAMA_MODEL", default="orca-mini")
ADMIN_USER_ID: Final[str] = env("ADMIN_USER_ID")
BACKEND_API_KEY: Final[str] = env("BACKEND_API_KEY")
BACKEND_API_URL: Final[str] = env(
    "BACKEND_API_URL", default="http://127.0.0.1:3000/api"
)
