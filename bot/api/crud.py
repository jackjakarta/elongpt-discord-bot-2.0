import httpx

from bot.utils.settings import OLLAMA_SERVER

from .utils import get_endpoint_url, get_request_headers


async def db_create_recipe(discord_user: str, ingredients: str, instructions: str):
    async with httpx.AsyncClient() as client:
        endpoint_url = get_endpoint_url("recipes")
        headers = get_request_headers()

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
        endpoint_url = get_endpoint_url("completion")
        headers = get_request_headers()

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
        endpoint_url = get_endpoint_url("images")
        headers = get_request_headers()

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
        endpoint_url = get_endpoint_url("images")
        headers = get_request_headers()
        query_endpoint = f"{endpoint_url}?discordUser={discord_user}"

        response = await client.get(url=query_endpoint, headers=headers)
        response.raise_for_status()

        return response.json()


async def check_ollama_server_health():
    async with httpx.AsyncClient() as client:
        endpoint_url = f"{OLLAMA_SERVER}/api/tags"

        try:
            response = await client.get(url=endpoint_url)

            if response.status_code != 200:
                return False

            return True
        except httpx.HTTPError:
            return False
        except Exception:
            return False
