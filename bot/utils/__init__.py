from discord import Embed


def create_embed(title, description, color=0xFFFFFF):
    """Create a Discord embed."""
    return Embed(title=title, description=description, color=color)
