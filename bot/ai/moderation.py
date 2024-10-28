from openai import OpenAI

from bot.utils.settings import OPENAI_API_KEY


async def check_moderate(input_text: str) -> bool:
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.moderations.create(
        input=input_text, model="text-moderation-stable"
    )
    categories_object = response.results[0].categories

    if any(getattr(categories_object, attr) for attr in categories_object.__dict__):
        return True

    return False
