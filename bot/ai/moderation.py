from openai import OpenAI
from openai.types import ModerationCreateResponse

from bot.utils.settings import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


async def check_moderate(input_text: str) -> bool:
    response: ModerationCreateResponse = client.moderations.create(
        input=input_text, model="text-moderation-stable"
    )

    is_flagged = response.results[0].flagged

    return is_flagged
