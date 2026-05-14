from bot.utils.settings import BACKEND_API_KEY, BACKEND_API_URL


def get_endpoint_url(endpoint: str) -> str | None:
    if BACKEND_API_URL is None:
        return None

    return f"{BACKEND_API_URL}/{endpoint}"


def get_request_headers() -> dict | None:
    if BACKEND_API_KEY is None:
        return None

    headers = {
        "Authorization": f"Bearer {BACKEND_API_KEY}",
        "Content-Type": "application/json",
    }

    return headers
