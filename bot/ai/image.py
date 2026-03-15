import base64

from openai import AsyncOpenAI

from bot.utils.settings import OPENAI_API_KEY


class ImageDallE:
    """Image Generation with the OpenAI Image 1.5 model."""

    def __init__(self, model="gpt-image-1.5"):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = model

    async def generate_image(self, prompt):
        response = await self.client.images.generate(
            model=self.model,
            prompt=prompt,
            n=1,
            size="1024x1024",
            moderation="low",
        )

        image_bytes = base64.b64decode(response.data[0].b64_json)
        return image_bytes
