import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
import httpx
import openai
import pydantic

from bot.utils.settings import DGPT_SEARCH_URL, EVENTS_VOICE_CHANNEL_ID, OPENAI_API_KEY


class CreateScheduledEvent(pydantic.BaseModel):
    """Create a scheduled event in the Discord server.
    Use this when the user wants to schedule or create an event."""

    name: str
    start_time: str  # ISO 8601
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


class WebSearch(pydantic.BaseModel):
    """Search the web for current or factual information.
    Use this when the user asks about recent events, current data, or facts
    that may have changed since your training cutoff."""

    query: str
    count: int = pydantic.Field(default=10, ge=1, le=20)


# web search authenticates with OPENAI_API_KEY, which is required, so it is
# always available — only the event tool needs a feature gate
TOOL_DEFINITIONS = [openai.pydantic_function_tool(WebSearch)]
if EVENTS_VOICE_CHANNEL_ID is not None:
    TOOL_DEFINITIONS.append(openai.pydantic_function_tool(CreateScheduledEvent))


async def handle_create_scheduled_event(
    args: CreateScheduledEvent, guild: discord.Guild | None
) -> str:
    if guild is None:
        return json.dumps(
            {"error": "Scheduling events requires a server. It cannot be used in DMs."}
        )
    try:
        start = datetime.fromisoformat(args.start_time)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        start = start - timedelta(hours=1)

        if args.end_time:
            end = datetime.fromisoformat(args.end_time)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            end = end - timedelta(hours=1)
        else:
            end = start + timedelta(hours=1)

        event = await guild.create_scheduled_event(
            name=args.name,
            start_time=start,
            end_time=end,
            description=args.description or "",
            channel=discord.Object(id=EVENTS_VOICE_CHANNEL_ID),
            entity_type=discord.EntityType.voice,
            privacy_level=discord.PrivacyLevel.guild_only,
        )

        return json.dumps(
            {"success": True, "event_name": event.name, "event_url": event.url}
        )

    except discord.Forbidden:
        return json.dumps(
            {"error": "Bot lacks permission to create events in this server."}
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


async def handle_web_search(args: WebSearch, _guild: discord.Guild | None) -> str:
    payload_body = {"query": args.query, "count": args.count}

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                DGPT_SEARCH_URL, json=payload_body, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        results = [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "description": r.get("description"),
                "age": r.get("age"),
            }
            for r in data.get("data", [])
        ]
        payload = json.dumps({"query": args.query, "results": results})
        return f"<search_results>{payload}</search_results>"
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": f"Web search returned HTTP {e.response.status_code}"}
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


TOOL_HANDLERS = {
    "CreateScheduledEvent": (CreateScheduledEvent, handle_create_scheduled_event),
    "WebSearch": (WebSearch, handle_web_search),
}


async def execute_tool_call(
    tool_name: str, arguments_json: str, guild: discord.Guild | None
) -> str:
    handler_entry = TOOL_HANDLERS.get(tool_name)
    if not handler_entry:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    model_cls, handler_fn = handler_entry
    try:
        args = model_cls.model_validate_json(arguments_json)
        return await handler_fn(args, guild)
    except Exception as e:
        return json.dumps({"error": str(e)})
