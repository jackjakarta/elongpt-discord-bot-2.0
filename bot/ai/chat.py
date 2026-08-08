from datetime import datetime, timezone

from discord import Interaction, Status

from bot.utils.settings import OPENAI_CHAT_MODEL

from .openai_client import client
from .prompts import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT, WEB_EXTRACTION_PROMPT


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


async def run_web_extraction(prompt: str, content: str) -> str:
    """Answer a question about one fetched web page, using only that page.

    Deliberately skips DEFAULT_SYSTEM_PROMPT so the model concentrates on the
    page rather than the bot persona. It also keeps the page markdown out of the
    /ask conversation, which re-sends every accumulated tool message on each
    round of its tool loop.
    """
    completion = await client.chat.completions.create(
        model=OPENAI_CHAT_MODEL,
        messages=[
            {"role": "developer", "content": WEB_EXTRACTION_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Request: {prompt}\n\n"
                    f"<page_content>\n{content}\n</page_content>"
                ),
            },
        ],
    )

    return completion.choices[0].message.content or ""


async def get_chat_context(
    interaction: Interaction,
):
    context = ""

    if interaction.guild is not None:
        online_statuses = {
            Status.online,
            Status.idle,
            Status.dnd,
        }

        online_users = [
            member.display_name
            for member in interaction.guild.members
            if not member.bot and member.status in online_statuses
        ]

        if online_users:
            context += f"Online users: {', '.join(online_users)}\n\n"

        messages = [msg async for msg in interaction.channel.history(limit=10)]
        messages.reverse()

        if messages:
            lines = [
                f"[{msg.author.display_name}] {msg.content}"
                for msg in messages
                if msg.content
            ]

            if lines:
                context += "Recent messages in this channel:\n" + "\n".join(lines)

    return context
