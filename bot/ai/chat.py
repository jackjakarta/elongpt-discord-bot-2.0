from datetime import datetime, timezone

from discord import Interaction, Status
from openai import AsyncOpenAI

from bot.utils.settings import OPENAI_API_KEY, OPENAI_MODEL

from .prompts import DEFAULT_SYSTEM_PROMPT


class ChatGPT:
    """ChatGPT Class"""

    def __init__(self, system_prompt=DEFAULT_SYSTEM_PROMPT, model=OPENAI_MODEL):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = model
        self.prompt = None
        self.completion = None
        self.files = []
        self.system_prompt = system_prompt
        self.messages = None
        self.user_name = None

    async def ask(
        self,
        prompt,
        user_name: str,
        files: list | None = None,
        context: str = "",
    ):
        self.prompt = prompt
        self.files = files[:5] if files else []

        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        self.messages = [
            {
                "role": "developer",
                "content": self.system_prompt.format(
                    user_name=user_name,
                    context=context,
                    today_date=today_date,
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": self.prompt,
                    },
                    *(
                        [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image}",
                                },
                            }
                            for image in self.files
                        ]
                        if self.files
                        else []
                    ),
                ],
            },
        ]

        self.completion = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
        )

        return str(self.completion.choices[0].message.content)

    async def ask_with_tools(
        self,
        prompt,
        user_name: str,
        files: list | None = None,
        context: str = "",
        tools: list | None = None,
        tool_messages: list | None = None,
    ):
        self.prompt = prompt
        self.files = files[:5] if files else []
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        self.messages = [
            {
                "role": "developer",
                "content": self.system_prompt.format(
                    user_name=user_name,
                    context=context,
                    today_date=today_date,
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": self.prompt,
                    },
                    *(
                        [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image}",
                                },
                            }
                            for image in self.files
                        ]
                        if self.files
                        else []
                    ),
                ],
            },
        ]

        if tool_messages:
            self.messages.extend(tool_messages)

        kwargs = {"model": self.model, "messages": self.messages}
        if tools:
            kwargs["tools"] = tools

        self.completion = await self.client.chat.completions.create(**kwargs)

        return self.completion.choices[0].message

    async def get_models(self):
        models_list = await self.client.models.list().data
        models = [x.id for x in models_list]

        return sorted(models)


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

        messages = [msg async for msg in interaction.channel.history(limit=15)]
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
