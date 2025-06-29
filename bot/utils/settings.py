from typing import Final

from decouple import config as env

DISCORD_TOKEN: Final[str] = env("DISCORD_TOKEN")
OPENAI_API_KEY: Final[str] = env("OPENAI_API_KEY")
OPENAI_MODEL: Final[str] = env("OPENAI_MODEL")
CMC_API_KEY: Final[str] = env("CMC_PRO_API_KEY")
OLLAMA_SERVER: Final[str] = env("OLLAMA_SERVER")
OLLAMA_MODEL: Final[str] = env("OLLAMA_MODEL")
ADMIN_USER_ID: Final[str] = env("ADMIN_USER_ID")
KLIKR_API_KEY: Final[str] = env("KLIKR_API_KEY")
KLIKR_API_URL: Final[str] = env("KLIKR_API_URL")
BACKEND_API_KEY: Final[str] = env("BACKEND_API_KEY")
BACKEND_API_URL: Final[str] = env("BACKEND_API_URL")
UTILS_API_KEY: Final[str] = env("UTILS_API_KEY")
UTILS_API_URL: Final[str] = env("UTILS_API_URL")
