import base64

from bot.utils.settings import OPENAI_IMAGE_MODEL

from .openai_client import client


async def generate_image(prompt: str) -> bytes:
    response = await client.images.generate(
        model=OPENAI_IMAGE_MODEL,
        prompt=prompt,
        n=1,
        size="1024x1024",
        moderation="low",
    )

    image_bytes = base64.b64decode(response.data[0].b64_json)
    return image_bytes
