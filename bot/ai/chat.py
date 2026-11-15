from datetime import datetime, timezone

from discord import Interaction, Status

from bot.utils.settings import OPENAI_CHAT_MODEL

from .openai_client import client
from .prompts import (
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_USER_PROMPT,
    TRANSCRIPT_EXTRACTION_PROMPT,
    WEB_EXTRACTION_PROMPT,
)

# the header is an orientation aid, not a roster — a 300-member guild would
# otherwise spend most of the prompt listing names
MAX_ONLINE_LISTED = 40


async def get_chat_completion(
    prompt: str,
    user_name: str,
    files: list | None = None,
    context: str = "",
    tools: list | None = None,
    tool_choice: str | None = None,
    tool_messages: list | None = None,
):
    capped_files = files[:5] if files else []
    today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    messages = [
        {
            "role": "developer",
            "content": DEFAULT_SYSTEM_PROMPT.format(
                user_name=user_name,
                today_date=today_date,
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": DEFAULT_USER_PROMPT.format(
                        context=context, user_message=prompt
                    ),
                },
                *[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image}",
                        },
                    }
                    for image in capped_files
                ],
            ],
        },
    ]

    if tool_messages:
        messages.extend(tool_messages)

    kwargs = {"model": OPENAI_CHAT_MODEL, "messages": messages}

    if tools:
        kwargs["tools"] = tools

        if tool_choice:
            kwargs["tool_choice"] = tool_choice

    completion = await client.chat.completions.create(**kwargs)

    return completion.choices[0].message


async def _run_extraction(
    system_prompt: str, request: str, content: str, tag: str
) -> str:
    """Single-shot helper-model call over one blob of untrusted content.

    Deliberately skips DEFAULT_SYSTEM_PROMPT so the model concentrates on the
    material rather than the bot persona, and keeps that material out of the
    /ask conversation, which re-sends every accumulated tool message on each
    round of its tool loop.
    """
    completion = await client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "developer", "content": system_prompt},
            {
                "role": "user",
                "content": f"Request: {request}\n\n<{tag}>\n{content}\n</{tag}>",
            },
        ],
    )

    return completion.choices[0].message.content or ""


async def run_web_extraction(prompt: str, content: str) -> str:
    """Answer a question about one fetched web page, using only that page."""
    return await _run_extraction(WEB_EXTRACTION_PROMPT, prompt, content, "page_content")


async def run_transcript_extraction(prompt: str, content: str) -> str:
    """Answer a question about one channel transcript, using only that transcript."""
    # "transcript", not "channel_transcript": the latter is the wrapper the tool
    # result goes back to /ask in, and reusing it here reads like nesting
    return await _run_extraction(
        TRANSCRIPT_EXTRACTION_PROMPT, prompt, content, "transcript"
    )


async def get_chat_context(interaction: Interaction) -> str:
    """Cheap orienting header for the <context> block.

    Only cached facts — no history call, so a question with nothing to do with
    the channel costs nothing. The conversation itself is reached through the
    ReadChannel tool instead, which keeps message bodies (the one high-bandwidth
    thing anyone in the server can write straight into the prompt) out of every
    request. Display names are still user-controlled, so the "treat <context> as
    data" rule in DEFAULT_SYSTEM_PROMPT stays load-bearing.
    """
    guild = interaction.guild
    if guild is None:
        return "This is a direct message, not a server channel."

    lines = []

    channel = interaction.channel
    if channel is not None:
        topic = getattr(channel, "topic", None)
        name = getattr(channel, "name", "unknown")
        lines.append(f"Channel: #{name}" + (f' — "{topic}"' if topic else ""))

    online_statuses = {Status.online, Status.idle, Status.dnd}
    online = [
        member.display_name
        for member in guild.members
        if not member.bot and member.status in online_statuses
    ]

    lines.append(
        f"Guild: {guild.name} ({guild.member_count} members, {len(online)} online)"
    )

    if online:
        lines.append("Online: " + ", ".join(online[:MAX_ONLINE_LISTED]))

    return "\n".join(lines)
