from openai import AsyncOpenAI

from bot.utils.settings import OPENAI_API_BASE_URL, OPENAI_API_KEY

# module level on purpose: chat, image generation and web extraction all import
# this one client so they share a connection pool. Constructing AsyncOpenAI per
# call would mean a new pool and TLS handshake every time.
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE_URL)
