import base64

from discord import Embed

DISCORD_MESSAGE_LIMIT = 2000
CODE_FENCE = "```"


def create_embed(title, description, color=0xFFFFFF):
    """Create a Discord embed."""
    return Embed(title=title, description=description, color=color)


def image_to_base64(file_data: str) -> str:
    base64_image = base64.b64encode(file_data).decode("utf-8")

    return base64_image


def _find_cut(text: str, budget: int) -> int:
    """Index to cut `text` at so the first part stays within `budget` chars."""
    window = text[:budget]

    for separator in ("\n\n", "\n", " "):
        cut = window.rfind(separator)
        if cut > 0:
            return cut

    return budget  # one unbroken run of characters — nothing to break on


def _dangling_fence(chunk: str) -> str | None:
    """Return the opening line of a code fence `chunk` leaves unclosed."""
    opener = None

    for line in chunk.split("\n"):
        if line.lstrip().startswith(CODE_FENCE):
            opener = None if opener else line

    return opener


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split `text` into chunks Discord will accept as message content.

    Breaks on the widest natural boundary that fits — paragraph, then line, then
    word — and hard-cuts only when a single run of characters is longer than
    `limit`. A code fence left open by a cut is closed and reopened on the next
    chunk, so neither message renders as broken markdown.
    """
    chunks = []
    remaining = text.strip()
    reopen = None

    while remaining:
        prefix = f"{reopen}\n" if reopen else ""

        if len(prefix) + len(remaining) <= limit:
            chunks.append(prefix + remaining)
            break

        # hold back room for the closing fence a cut inside a code block needs
        budget = limit - len(prefix) - len(CODE_FENCE) - 1

        if budget < 1:  # pathologically long fence opener — drop the reopen
            prefix, budget = "", limit

        cut = _find_cut(remaining, budget)
        chunk = prefix + remaining[:cut].rstrip()
        remaining = remaining[cut:].strip()

        reopen = _dangling_fence(chunk)
        if reopen:
            chunk += f"\n{CODE_FENCE}"

        chunks.append(chunk)

    return chunks
