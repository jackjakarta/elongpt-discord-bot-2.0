import httpx

from .utils.settings import BACKEND_API_KEY, BACKEND_API_URL


def get_endpoint(endpoint: str) -> str:
    return f"{BACKEND_API_URL}/{endpoint}"


def get_headers() -> dict:
    headers = {
        "Authorization": f"Bearer {BACKEND_API_KEY}",
        "Content-Type": "application/json",
    }

    return headers


async def db_create_recipe(discord_user: str, ingredients: str, instructions: str):
    async with httpx.AsyncClient() as client:
        endpoint_url = get_endpoint("recipes")
        headers = get_headers()

        data = {
            "discordUser": discord_user,
            "ingredients": ingredients,
            "instructions": instructions,
        }

        response = await client.post(url=endpoint_url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()


async def db_create_completion(discord_user: str, prompt: str, completion: str):
    async with httpx.AsyncClient() as client:
        endpoint_url = get_endpoint("completion")
        headers = get_headers()

        data = {
            "discordUser": discord_user,
            "prompt": prompt,
            "completion": completion,
        }

        response = await client.post(url=endpoint_url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()


async def s3_save_image(discord_user: str, image_url: str, prompt: str):
    async with httpx.AsyncClient() as client:
        endpoint_url = get_endpoint("images")
        headers = get_headers()

        data = {
            "discordUser": discord_user,
            "imageUrl": image_url,
            "prompt": prompt,
        }

        response = await client.post(url=endpoint_url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()


async def db_get_user_images(discord_user: str):
    async with httpx.AsyncClient() as client:
        endpoint_url = get_endpoint("images")
        query_endpoint = f"{endpoint_url}?discordUser={discord_user}"
        headers = get_headers()

        response = await client.get(url=query_endpoint, headers=headers)
        response.raise_for_status()

        return response.json()
