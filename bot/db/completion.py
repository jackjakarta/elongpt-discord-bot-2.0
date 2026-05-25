from datetime import datetime, timezone

from bot.utils.settings import DYNAMODB_TABLE_NAME

from .client import dynamodb
from .types import CompletionModel
from .utils import generate_uuid

table = dynamodb.Table(DYNAMODB_TABLE_NAME)


def db_insert_completion(prompt: str, completion: str, discord_user: str):
    unique_id = generate_uuid()
    today = datetime.now(timezone.utc).isoformat()

    item = CompletionModel(
        id=unique_id,
        prompt=prompt,
        completion=completion,
        discord_user=discord_user,
        created_at=today,
    )

    response = table.put_item(Item=item.model_dump())
    return response
