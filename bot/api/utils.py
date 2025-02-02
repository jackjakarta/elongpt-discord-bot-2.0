from bot.utils.settings import BACKEND_API_KEY, BACKEND_API_URL


def get_endpoint(endpoint: str) -> str:
    return f"{BACKEND_API_URL}/{endpoint}"


def get_headers() -> dict:
    headers = {
        "Authorization": f"Bearer {BACKEND_API_KEY}",
        "Content-Type": "application/json",
    }

    return headers
