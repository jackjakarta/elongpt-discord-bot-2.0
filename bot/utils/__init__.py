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
    widest = 0

    for separator in ("\n\n", "\n", " "):
        cut = window.rfind(separator)

        # a boundary in the first half wastes most of the chunk — a short
        # opening paragraph would be sent on its own while the rest spills
        # over. Fall through to a finer separator that cuts closer to the cap
        if cut > budget // 2:
            return cut

        widest = max(widest, cut)

    # every boundary sits in the first half, so the tail is one long unbroken
    # run. Cutting at the boundary is only worth the stub message it produces
    # when the run then fits whole in the next chunk
    if widest > 0 and len(text) - widest <= budget:
        return widest

    return budget  # nothing useful to break on


def _drop_separator(text: str) -> str:
    """Drop the whitespace a cut landed on, keeping the next line's indent."""
    if text.startswith("\n"):
        return text.lstrip("\n")  # spaces after the newline are indentation

    if text.startswith(" "):
        return text.lstrip(" ")  # a word break, so these are just the gap

    return text  # hard cut mid-word — nothing to drop


def _dangling_fence(chunk: str) -> str | None:
    """Return the opening line of a code fence `chunk` leaves unclosed."""
    opener = None

    for line in chunk.split("\n"):
        if line.lstrip().startswith(CODE_FENCE):
            opener = None if opener else line

    return opener


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split `text` into chunks Discord will accept as message content.

    Breaks on the widest natural boundary that fits and lands past the halfway
    mark — paragraph, then line, then word — and hard-cuts only when a single
    run of characters is longer than `limit`. A code fence left open by a cut is
    closed and reopened on the next chunk, so neither message renders as broken
    markdown, and the continued line keeps its indentation.
    """
    chunks = []
    remaining = text.strip()
    reopen = None

    while remaining:
        prefix = f"{reopen}\n" if reopen else ""

        if len(prefix) + len(remaining) <= limit:
            chunks.append((prefix + remaining).rstrip())
            break

        # hold back room for the closing fence a cut inside a code block needs
        budget = limit - len(prefix) - len(CODE_FENCE) - 1

        if budget < 1:  # pathologically long fence opener — drop the reopen
            prefix, budget = "", limit

        cut = _find_cut(remaining, budget)
        chunk = prefix + remaining[:cut].rstrip()
        # not .strip(): that ate the leading indentation of the continued line,
        # which mangles a code block cut mid-body
        remaining = _drop_separator(remaining[cut:])

        reopen = _dangling_fence(chunk)
        if reopen:
            chunk += f"\n{CODE_FENCE}"

        chunks.append(chunk)

    return chunks
