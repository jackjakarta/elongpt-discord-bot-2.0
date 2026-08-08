from openai import AsyncOpenAI

from bot.utils.settings import OPENAI_API_BASE_URL, OPENAI_API_KEY

client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE_URL)
