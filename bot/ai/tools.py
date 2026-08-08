import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
import httpx
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter
from openai import pydantic_function_tool
from pydantic import BaseModel, Field

from bot.ai.chat import run_web_extraction
from bot.utils.net import UnsafeUrlError, assert_public_url
from bot.utils.settings import DGPT_SEARCH_URL, EVENTS_VOICE_CHANNEL_ID, OPENAI_API_KEY

MAX_FETCH_CHARS = 50_000  # markdown handed to the helper model
# hard body cap so a huge page can't exhaust memory. Everything past
# MAX_FETCH_CHARS of markdown is discarded anyway, so parsing more than this
# only buys parse time
MAX_FETCH_BYTES = 2_000_000
MAX_REDIRECTS = 5
WEB_FETCH_TIMEOUT = 15.0
WEB_FETCH_USER_AGENT = "Mozilla/5.0 (compatible; elongpt-bot/1.0)"
WEB_FETCH_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
FALLBACK_EXCERPT_CHARS = 8_000


class CreateScheduledEvent(BaseModel):
    """Create a scheduled event in the Discord server.
    Use this when the user wants to schedule or create an event."""

    name: str
    start_time: str  # ISO 8601
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None


class WebSearch(BaseModel):
    """Search the web for current or factual information.
    Use this when the user asks about recent events, current data, or facts
    that may have changed since your training cutoff. Results are short snippets
    only — use WebFetch on a result URL to read what the page actually says."""

    query: str
    count: int = Field(default=10, ge=1, le=20)


class WebFetch(BaseModel):
    """Fetch a single web page and answer a question about its contents.

    Give the `url` to retrieve and a `prompt` describing what you want from the
    page (e.g. "summarize this", "what version is documented?"). The page is
    downloaded, converted to Markdown, and read by a helper model that answers
    your prompt using only that content. Reach for this after a WebSearch to
    read a specific result, or whenever the user hands you a URL. Internal and
    loopback addresses are always refused."""

    url: str
    prompt: str


class _FetchError(Exception):
    """A fetch failure whose message is meant to be handed back to the model."""


# web search and web fetch authenticate with OPENAI_API_KEY, which is required,
# so they are always available — only the event tool needs a feature gate
TOOL_DEFINITIONS = [
    pydantic_function_tool(WebSearch),
    pydantic_function_tool(WebFetch),
]

if EVENTS_VOICE_CHANNEL_ID is not None:
    TOOL_DEFINITIONS.append(pydantic_function_tool(CreateScheduledEvent))


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


# Dropped before conversion. script/style/noscript/template because
# markdownify's `strip` option keeps their inner text (inline JS/CSS leaks in);
# nav/footer/aside/form because chrome otherwise eats the MAX_FETCH_CHARS budget
# ahead of the article. `header` is left in — it often carries the title/byline.
NON_CONTENT_TAGS = [
    "script",
    "style",
    "noscript",
    "template",
    "nav",
    "footer",
    "aside",
    "form",
]


def _html_to_markdown(html: bytes) -> str:
    """Convert a page body to Markdown. Blocking — call it via asyncio.to_thread.

    Takes bytes rather than str so BeautifulSoup can sniff the encoding itself:
    plenty of pages declare their charset only in <meta charset=...>, and
    decoding those as UTF-8 up front turns them into mojibake the extraction
    model then reads as fact.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(NON_CONTENT_TAGS):
        tag.decompose()

    # convert_soup, not markdownify(str(soup)): the latter re-serializes the
    # whole tree and markdownify parses it a second time, doubling the work
    return MarkdownConverter().convert_soup(soup)


async def _read_capped(response: httpx.Response) -> bytes:
    """Read a streamed body, stopping once MAX_FETCH_BYTES have arrived."""
    chunks: list[bytes] = []
    total = 0

    async for chunk in response.aiter_bytes():
        remaining = MAX_FETCH_BYTES - total
        if len(chunk) >= remaining:
            chunks.append(chunk[:remaining])
            break

        chunks.append(chunk)
        total += len(chunk)

    return b"".join(chunks)


async def _fetch_page(url: str) -> tuple[str, str]:
    """Fetch a URL and return (final_url, page text as Markdown).

    Redirects are followed by hand so every hop is re-validated. httpx's own
    redirect handling is off on purpose: it would only check the URL the model
    gave us, letting a public host 302 into the private network or at the cloud
    metadata endpoint.
    """
    headers = {"User-Agent": WEB_FETCH_USER_AGENT, "Accept": WEB_FETCH_ACCEPT}
    current = url

    async with httpx.AsyncClient(
        timeout=WEB_FETCH_TIMEOUT, follow_redirects=False, headers=headers
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await assert_public_url(current)

            # the model picks the whole URL, query string included, so this is
            # the only record of what the bot sent where. Redirect hops land
            # here too, since each one goes through this loop
            print(f"WebFetch: GET {current}")

            async with client.stream("GET", current) as response:
                if response.has_redirect_location:
                    current = str(response.next_request.url)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                is_html = "html" in content_type

                if not is_html and not (
                    content_type.startswith("text/") or "json" in content_type
                ):
                    raise _FetchError(
                        f"Unsupported content type: {content_type or 'unknown'}"
                    )

                body = await _read_capped(response)
                final_url = str(response.url)
                charset = response.charset_encoding

            # converted after the connection is released. html.parser is pure
            # Python and markdownify walks the whole tree, so on a large page
            # this is hundreds of ms of CPU — enough to stall the gateway
            # heartbeat and every other command with it if left on the loop
            if is_html:
                return final_url, await asyncio.to_thread(_html_to_markdown, body)

            # non-HTML has no <meta charset> to sniff, so the header is all we get
            return final_url, body.decode(charset or "utf-8", errors="replace")

    raise _FetchError("Too many redirects.")


async def handle_web_fetch(args: WebFetch, _guild: discord.Guild | None) -> str:
    url = args.url.strip()

    try:
        final_url, content = await _fetch_page(url)
    except (UnsafeUrlError, _FetchError) as e:
        return json.dumps({"error": str(e), "url": url})
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": f"Fetch returned HTTP {e.response.status_code}", "url": url}
        )
    except Exception as e:
        return json.dumps({"error": str(e), "url": url})

    content = content.strip()
    if not content:
        return json.dumps(
            {"error": "Fetched page had no readable content.", "url": url}
        )

    if len(content) > MAX_FETCH_CHARS:
        content = content[:MAX_FETCH_CHARS] + "\n\n... [content truncated]"

    try:
        result = await run_web_extraction(args.prompt, content)
    except Exception as e:
        # the helper model is a nice-to-have — hand back a raw excerpt rather
        # than throwing away a page we already paid to fetch
        print(f"Web extraction failed, returning raw excerpt: {e}")
        result = content[:FALLBACK_EXCERPT_CHARS]

    return json.dumps({"url": url, "final_url": final_url, "result": result})


TOOL_HANDLERS = {
    "CreateScheduledEvent": (CreateScheduledEvent, handle_create_scheduled_event),
    "WebSearch": (WebSearch, handle_web_search),
    "WebFetch": (WebFetch, handle_web_fetch),
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
