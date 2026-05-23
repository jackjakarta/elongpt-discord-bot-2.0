import json

import httpx

from .utils import get_endpoint_url, get_request_headers


async def db_create_completion(discord_user: str, prompt: str, completion: str):
    endpoint_url = get_endpoint_url("completion")
    headers = get_request_headers()

    if endpoint_url is None or headers is None:
        return

    async with httpx.AsyncClient() as client:
        data = {
            "discordUser": discord_user,
            "prompt": prompt,
            "completion": json.dumps(completion, indent=2),
        }

        response = await client.post(url=endpoint_url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()
