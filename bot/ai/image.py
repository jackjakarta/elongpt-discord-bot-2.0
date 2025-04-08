from openai import AsyncOpenAI

from bot.utils.settings import OPENAI_API_KEY


class ImageDallE:
    """Image Generation with the OpenAI DALL-E model."""

    def __init__(self, model="dall-e-3"):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = model
        self.prompt = None
        self.response = None
        self.image_url = None

    async def generate_image(self, prompt):
        self.prompt = prompt
        self.response = await self.client.images.generate(
            model=self.model,
            prompt=self.prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        self.image_url = self.response.data[0].url
        
        return self.image_url
