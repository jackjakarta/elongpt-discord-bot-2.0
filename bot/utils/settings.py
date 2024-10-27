from decouple import config

DISCORD_TOKEN = config("DISCORD_TOKEN")
OPENAI_API_KEY = config("OPENAI_API_KEY")
OPENAI_MODEL = config("OPENAI_MODEL", default="gpt-4o")
CMC_API_KEY = config("CMC_PRO_API_KEY")
CMC_API_URL = config(
    "CMC_API_URL",
    default="https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest",
)
VISION_BRAIN_API_KEY = config(
    "VISION_BRAIN_API_KEY", default="no-api-key-for-bot-to-start"
)
VISION_BRAIN_API_URL = config(
    "VISION_BRAIN_API_URL", default="https://visionbrain.xyz/api/tts/"
)
OLLAMA_SERVER = config("OLLAMA_SERVER", default="http://127.0.0.1:11434")
OLLAMA_MODEL = config("OLLAMA_MODEL", default="orca-mini")

BACKEND_API_URL = config("BACKEND_API_URL", default="http://127.0.0.1:3000/api")
BACKEND_API_KEY = config("BACKEND_API_KEY")
