import base64

from discord import Embed


def create_embed(title, description, color=0xFFFFFF):
    """Create a Discord embed."""
    return Embed(title=title, description=description, color=color)


def image_to_base64(file_data: str) -> str:
    base64_image = base64.b64encode(file_data).decode("utf-8")

    return base64_image
