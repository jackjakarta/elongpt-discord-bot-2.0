"""Tools that let the model read the Discord server it is running in.

Every handler here mirrors the *invoking user's* permissions, not the bot's.
The bot is typically the more privileged of the two, and the model reads
attacker-writable text from three directions (the context header, search
snippets, fetched pages) — without the mirror, /ask would be a permission
escalation path and any crafted page a lever on it. `_resolve_readable()` is
the single door all of that goes through.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from pydantic import BaseModel, Field

from bot.ai.chat import run_transcript_extraction
from bot.ai.tool_context import ToolContext
from bot.utils import split_message
from bot.utils.settings import DISCORD_SEND_TOOL_ENABLED

MAX_HISTORY_LIMIT = 200
# a transcript at or under this goes back raw; past it a helper model reads it
MAX_TRANSCRIPT_CHARS = 12_000
MAX_EXTRACTION_CHARS = 50_000  # hard cap on what the helper model is handed
SEARCH_SCAN_CAP = 500  # 5 REST pages
MAX_SEARCH_RESULTS = 50
SNIPPET_CHARS = 300
MAX_LISTED_CHANNELS = 100
MAX_LISTED_ROLES = 50
MAX_LISTED_EMOJI = 100
MAX_EMBED_DESCRIPTION_CHARS = 500
MAX_TOPIC_CHARS = 200
MAX_CANDIDATES = 10
# an announcement longer than this is a mistake, and the cap bounds how much a
# successful injection could make the bot shout into a channel
MAX_SEND_CHARS = 4_000

DEFAULT_TRANSCRIPT_PROMPT = (
    "Summarise this conversation. Keep track of who said what, and preserve any "
    "decisions, questions left open, and links that were shared."
)

# channels whose history can actually be read. ForumChannel is deliberately
# absent — it holds threads rather than messages and is not Messageable
_READABLE_TYPES = (discord.TextChannel, discord.Thread, discord.VoiceChannel)

_CHANNEL_MENTION = re.compile(r"^<#(\d+)>$")
_USER_MENTION = re.compile(r"^<@!?(\d+)>$")
_MESSAGE_LINK = re.compile(r"channels/(\d+|@me)/(\d+)/(\d+)")


class ReadChannel(BaseModel):
    """Read recent messages from a channel in this Discord server.

    You cannot see the conversation on your own, so reach for this whenever the
    request refers to it — "this", "above", "earlier", "what did they say",
    "summarise the channel". `channel` defaults to the one the command was run
    in; pass a name like "general" to read a different one. Optionally give a
    `prompt` describing what you want from the messages and a helper model will
    answer it using only that transcript."""

    channel: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=MAX_HISTORY_LIMIT)
    prompt: Optional[str] = None


class SearchMessages(BaseModel):
    """Search one channel's history for messages matching a query.

    Returns messages containing every word in `query`, newest first, each with a
    link. Use it to find something said further back than a channel read would
    reach. Scans a single channel — call it once per channel to cover several.
    Narrow with `author` (display name or username) and `days`."""

    query: str
    channel: Optional[str] = None
    author: Optional[str] = None
    days: Optional[int] = Field(default=None, ge=1, le=365)
    limit: int = Field(default=20, ge=1, le=MAX_SEARCH_RESULTS)


class GetMessage(BaseModel):
    """Fetch one specific Discord message by link or ID.

    Use this when the user pastes a Discord message link or asks about a
    particular message. Returns its author, text, attachments, embeds and
    reactions. A bare numeric ID is looked up in the current channel. Do not use
    the web-fetch tool on a discord.com link — it cannot read one."""

    reference: str


class ListEvents(BaseModel):
    """List the scheduled events in this Discord server.

    Returns each event's name, description, start and end time, location and
    link. Use it for any question about what is coming up."""


class GetMemberInfo(BaseModel):
    """Look up a member of this Discord server.

    Accepts a display name, username, mention or ID. Returns their roles, when
    they joined, their current status and which voice channel they are in."""

    name: str


class ServerSnapshot(BaseModel):
    """Describe this Discord server: channels and their topics, roles, custom
    emoji, who is in voice, and member counts.

    Use it to orient yourself before another tool — for instance to find the
    name of the channel the user means."""


class SendToChannel(BaseModel):
    """Post a message into a channel in this Discord server.

    Only for when the user explicitly asks for something to be posted, announced
    or cross-posted somewhere. Your own reply already reaches the channel the
    command was run in, so this is for reaching a different one. Write `message`
    as the text to post, not as a report about posting it — it goes out verbatim,
    attributed to the user who asked. Mentions are inert: @everyone and role
    pings in the text will not notify anyone."""

    channel: str
    message: str


def _error(message: str, **extra) -> str:
    return json.dumps({"error": message, **extra})


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def _can(channel, member: discord.Member, *permissions: str) -> bool:
    resolved = channel.permissions_for(member)

    return all(getattr(resolved, permission) for permission in permissions)


def _guild_and_member(
    ctx: ToolContext,
) -> tuple[discord.Guild | None, discord.Member | None, str | None]:
    """Resolve the invoking user as a member of the guild, or explain why not."""
    if ctx.guild is None:
        return None, None, _error("This requires a server. It cannot be used in DMs.")

    member = ctx.user
    if not isinstance(member, discord.Member):
        member = ctx.guild.get_member(ctx.user.id)

    if member is None:
        return None, None, _error("Could not resolve you as a member of this server.")

    return ctx.guild, member, None


def _lookup_channel(guild: discord.Guild, reference: str):
    reference = reference.strip()

    mention = _CHANNEL_MENTION.match(reference)
    if mention:
        return guild.get_channel_or_thread(int(mention.group(1)))

    if reference.isdigit():
        return guild.get_channel_or_thread(int(reference))

    name = reference.lstrip("#").strip().lower()
    for channel in (*guild.text_channels, *guild.voice_channels, *guild.threads):
        if channel.name.lower() == name:
            return channel

    return None


# reading needs history; posting deliberately does not — a suggestions channel
# you may write to but not read back is an ordinary Discord setup, and demanding
# read access to post would refuse it
_READ_PERMISSIONS = ("view_channel", "read_message_history")
_WRITE_PERMISSIONS = ("view_channel", "send_messages")


def _resolve_channel(
    ctx: ToolContext,
    reference: Optional[str],
    permissions: tuple[str, ...],
    verb: str,
):
    """Return (channel, None) or (None, error_json) for a channel we may use.

    The asker is checked before the bot: a "you cannot do that" answer is the
    truthful one when the model reaches somewhere the user could not, and it
    keeps the bot's own wider access from leaking out through /ask.
    """
    guild, member, error = _guild_and_member(ctx)
    if error:
        return None, error

    if reference:
        channel = _lookup_channel(guild, reference)
        if channel is None:
            return None, _error(f"No channel called '{reference}' in this server.")
    else:
        channel = ctx.channel

    if not isinstance(channel, _READABLE_TYPES):
        name = getattr(channel, "name", reference or "that channel")
        return None, _error(f"'{name}' is not a channel I can use.")

    if not _can(channel, member, *permissions):
        return None, _error(f"You do not have permission to {verb} #{channel.name}.")

    if not _can(channel, guild.me, *permissions):
        return None, _error(f"I do not have permission to {verb} #{channel.name}.")

    return channel, None


def _resolve_readable(ctx: ToolContext, reference: Optional[str]):
    return _resolve_channel(ctx, reference, _READ_PERMISSIONS, "read")


def _resolve_writable(ctx: ToolContext, reference: Optional[str]):
    return _resolve_channel(ctx, reference, _WRITE_PERMISSIONS, "post in")


def _lookup_member(guild: discord.Guild, reference: str):
    """Return (member, None) or (None, error_json), naming candidates if unsure."""
    reference = reference.strip()

    mention = _USER_MENTION.match(reference)
    if mention:
        found = guild.get_member(int(mention.group(1)))
        return (found, None) if found else (None, _error("That member is not here."))

    if reference.isdigit():
        found = guild.get_member(int(reference))
        return (found, None) if found else (None, _error("That member is not here."))

    needle = reference.lstrip("@").lower()

    exact = [
        m for m in guild.members if needle in (m.display_name.lower(), m.name.lower())
    ]
    if exact:
        return exact[0], None

    partial = [
        m
        for m in guild.members
        if needle in m.display_name.lower() or needle in m.name.lower()
    ]
    if len(partial) == 1:
        return partial[0], None

    if partial:
        names = [m.display_name for m in partial[:MAX_CANDIDATES]]
        return None, _error(f"'{reference}' matches several members.", candidates=names)

    return None, _error(f"No member called '{reference}' in this server.")


def _activity_label(activity) -> str | None:
    # a custom status carries its text in .state; .name is the literal
    # string "Custom Status", which tells the model nothing
    if isinstance(activity, discord.CustomActivity):
        return activity.state

    return getattr(activity, "name", None)


def _format_message(message: discord.Message) -> str:
    """One transcript line. Non-text content is named so it isn't lost."""
    parts = []

    content = message.clean_content.strip()  # mentions rendered as names, not IDs
    if content:
        parts.append(content)

    parts += [f"[attachment: {a.filename}]" for a in message.attachments]
    parts += [f"[embed: {e.title}]" for e in message.embeds if e.title]
    parts += [f"[sticker: {s.name}]" for s in message.stickers]

    body = " ".join(parts) or "[no text content]"
    stamp = message.created_at.strftime("%Y-%m-%d %H:%M")

    return f"[{stamp}] {message.author.display_name}: {body}"


async def handle_read_channel(args: ReadChannel, ctx: ToolContext) -> str:
    channel, error = _resolve_readable(ctx, args.channel)
    if error:
        return error

    try:
        messages = [m async for m in channel.history(limit=args.limit)]
    except discord.Forbidden:
        return _error(f"I was denied access to #{channel.name}.")
    except discord.HTTPException as e:
        return _error(f"Failed to read #{channel.name}: {e}")

    if not messages:
        return _error(f"#{channel.name} has no readable messages.")

    messages.reverse()  # history() yields newest first; read it as a conversation
    transcript = "\n".join(_format_message(m) for m in messages)

    base = {"channel": channel.name, "message_count": len(messages)}

    # same trade-off WebFetch makes: a short read is cheaper handed back raw than
    # paying a helper-model round trip, but a long one has to be summarised —
    # /ask re-sends every accumulated tool message on every round of its loop
    if args.prompt is None and len(transcript) <= MAX_TRANSCRIPT_CHARS:
        payload = json.dumps({**base, "transcript": transcript})
        return f"<channel_transcript>{payload}</channel_transcript>"

    if len(transcript) > MAX_EXTRACTION_CHARS:
        transcript = transcript[-MAX_EXTRACTION_CHARS:]  # keep the recent end

    try:
        result = await run_transcript_extraction(
            args.prompt or DEFAULT_TRANSCRIPT_PROMPT, transcript
        )
    except Exception as e:
        # the helper is a nice-to-have — hand back the tail rather than losing
        # a read we already paid for
        print(f"Transcript extraction failed, returning raw excerpt: {e}")
        result = transcript[-MAX_TRANSCRIPT_CHARS:]

    payload = json.dumps({**base, "result": result})
    return f"<channel_transcript>{payload}</channel_transcript>"


async def handle_search_messages(args: SearchMessages, ctx: ToolContext) -> str:
    channel, error = _resolve_readable(ctx, args.channel)
    if error:
        return error

    terms = args.query.lower().split()
    if not terms:
        return _error("Search query was empty.")

    after = None
    if args.days:
        after = datetime.now(timezone.utc) - timedelta(days=args.days)

    author = args.author.strip().lstrip("@").lower() if args.author else None

    matches = []
    scanned = 0

    try:
        # oldest_first is explicit: history() flips it to True on its own when
        # `after` is set, which would return the oldest matches rather than the
        # newest ones the caller asked for
        async for message in channel.history(
            limit=SEARCH_SCAN_CAP, after=after, oldest_first=False
        ):
            scanned += 1

            if author and author not in (
                message.author.display_name.lower(),
                message.author.name.lower(),
            ):
                continue

            content = message.clean_content
            haystack = content.lower()
            if not all(term in haystack for term in terms):
                continue

            matches.append(
                {
                    "author": message.author.display_name,
                    "sent_at": _stamp(message.created_at),
                    "snippet": " ".join(content.split())[:SNIPPET_CHARS],
                    "jump_url": message.jump_url,
                }
            )

            if len(matches) >= args.limit:
                break
    except discord.Forbidden:
        return _error(f"I was denied access to #{channel.name}.")
    except discord.HTTPException as e:
        return _error(f"Failed to search #{channel.name}: {e}")

    payload = json.dumps(
        {
            "channel": channel.name,
            "query": args.query,
            "scanned": scanned,
            "hit_scan_cap": scanned >= SEARCH_SCAN_CAP,
            "matches": matches,
        }
    )

    return f"<channel_search_results>{payload}</channel_search_results>"


async def handle_get_message(args: GetMessage, ctx: ToolContext) -> str:
    guild, _member, error = _guild_and_member(ctx)
    if error:
        return error

    reference = args.reference.strip()
    link = _MESSAGE_LINK.search(reference)

    if link:
        guild_id, channel_ref, message_id = link.groups()
        if guild_id != str(guild.id):
            return _error("That message link points at a different server.")
    elif reference.isdigit():
        channel_ref, message_id = None, reference
    else:
        return _error("Give a Discord message link or a numeric message ID.")

    channel, error = _resolve_readable(ctx, channel_ref)
    if error:
        return error

    try:
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        return _error(f"No message {message_id} in #{channel.name}.")
    except discord.Forbidden:
        return _error(f"I was denied access to #{channel.name}.")
    except discord.HTTPException as e:
        return _error(f"Failed to fetch that message: {e}")

    payload = json.dumps(
        {
            "channel": channel.name,
            "author": message.author.display_name,
            "author_username": message.author.name,
            "sent_at": _stamp(message.created_at),
            "content": message.clean_content,
            "jump_url": message.jump_url,
            "attachments": [
                {"filename": a.filename, "content_type": a.content_type, "url": a.url}
                for a in message.attachments
            ],
            "embeds": [
                {
                    "title": e.title,
                    "description": (e.description or "")[:MAX_EMBED_DESCRIPTION_CHARS],
                    "url": e.url,
                }
                for e in message.embeds
            ],
            "reactions": [
                {"emoji": str(r.emoji), "count": r.count} for r in message.reactions
            ],
        }
    )

    return f"<discord_message>{payload}</discord_message>"


async def handle_list_events(_args: ListEvents, ctx: ToolContext) -> str:
    guild, _member, error = _guild_and_member(ctx)
    if error:
        return error

    try:
        events = await guild.fetch_scheduled_events()
    except discord.HTTPException as e:
        return _error(f"Failed to list events: {e}")

    if not events:
        return json.dumps({"events": [], "note": "No upcoming events in this server."})

    payload = json.dumps(
        {
            "events": [
                {
                    "name": event.name,
                    "description": event.description,
                    # UTC, as Discord stores them
                    "start_time": _stamp(event.start_time),
                    "end_time": _stamp(event.end_time) if event.end_time else None,
                    # .location is set for external events, .channel for the rest
                    "location": event.location or getattr(event.channel, "name", None),
                    "interested": event.user_count,
                    # .name, not str(): EventStatus has no __str__ override and
                    # would render as "EventStatus.scheduled"
                    "status": event.status.name,
                    "url": event.url,
                }
                for event in sorted(events, key=lambda e: e.start_time)
            ]
        }
    )

    return f"<discord_events>{payload}</discord_events>"


async def handle_get_member_info(args: GetMemberInfo, ctx: ToolContext) -> str:
    guild, member, error = _guild_and_member(ctx)
    if error:
        return error

    target, error = _lookup_member(guild, args.name)
    if error:
        return error

    # a voice channel the asker cannot see should not be named back to them
    voice = None
    if target.voice and target.voice.channel:
        if _can(target.voice.channel, member, "view_channel"):
            voice = target.voice.channel.name

    activities = [a for a in (_activity_label(a) for a in target.activities) if a]

    payload = json.dumps(
        {
            "display_name": target.display_name,
            "username": target.name,
            "id": str(target.id),
            "is_bot": target.bot,
            "joined_server": _stamp(target.joined_at) if target.joined_at else None,
            "account_created": _stamp(target.created_at),
            "roles": [r.name for r in reversed(target.roles) if not r.is_default()],
            "top_role": (
                target.top_role.name if not target.top_role.is_default() else None
            ),
            "status": str(target.status),
            "activities": activities,
            "voice_channel": voice,
        }
    )

    return f"<discord_member>{payload}</discord_member>"


async def handle_server_snapshot(_args: ServerSnapshot, ctx: ToolContext) -> str:
    guild, member, error = _guild_and_member(ctx)
    if error:
        return error

    # filtered by the asker's view: an unfiltered list leaks the names of every
    # private channel in the server to anyone who runs /ask
    text_channels = []
    for channel in guild.text_channels:
        if len(text_channels) >= MAX_LISTED_CHANNELS:
            break
        if not _can(channel, member, "view_channel"):
            continue
        text_channels.append(
            {
                "name": channel.name,
                "topic": (channel.topic or "")[:MAX_TOPIC_CHARS] or None,
                "category": channel.category.name if channel.category else None,
            }
        )

    voice_channels = [
        {"name": c.name, "occupants": [m.display_name for m in c.members]}
        for c in guild.voice_channels
        if _can(c, member, "view_channel")
    ]

    online = sum(
        1 for m in guild.members if not m.bot and m.status is not discord.Status.offline
    )

    payload = json.dumps(
        {
            "name": guild.name,
            "member_count": guild.member_count,
            "online_count": online,
            "owner": guild.owner.display_name if guild.owner else None,
            "created_at": _stamp(guild.created_at),
            "boost_tier": guild.premium_tier,
            "boost_count": guild.premium_subscription_count,
            "text_channels": text_channels,
            "voice_channels": voice_channels,
            "roles": [r.name for r in reversed(guild.roles) if not r.is_default()][
                :MAX_LISTED_ROLES
            ],
            "custom_emoji": [e.name for e in guild.emojis][:MAX_LISTED_EMOJI],
        }
    )

    return f"<server_snapshot>{payload}</server_snapshot>"


async def handle_send_to_channel(args: SendToChannel, ctx: ToolContext) -> str:
    channel, error = _resolve_writable(ctx, args.channel)
    if error:
        return error

    body = args.message.strip()
    if not body:
        return _error("Refusing to send an empty message.")

    if len(body) > MAX_SEND_CHARS:
        return _error(
            f"Message is {len(body)} characters; the limit is {MAX_SEND_CHARS}."
        )

    # the model chose these words after reading web pages and channel history it
    # does not control, so this is the only record of what the bot said where —
    # the same reason every WebFetch URL is printed
    print(f"SendToChannel: {ctx.user} -> #{channel.name}: {body[:200]!r}")

    # subtext, so a bot message in another channel is never anonymous
    attributed = f"-# Sent by {ctx.user.display_name} via `/ask`\n{body}"

    posted = None
    try:
        # over 2000 characters Discord answers 50035, and an announcement is
        # exactly the kind of message that runs long
        for chunk in split_message(attributed):
            sent = await channel.send(
                chunk, allowed_mentions=discord.AllowedMentions.none()
            )
            posted = posted or sent
    except (discord.Forbidden, discord.HTTPException) as e:
        # a split message can fail partway. Reporting a flat failure when half
        # of it landed invites the model to retry and double-post, so say so
        if posted is not None:
            return _error(
                f"Only part of the message reached #{channel.name}: {e}",
                jump_url=posted.jump_url,
            )

        if isinstance(e, discord.Forbidden):
            return _error(f"I was denied permission to post in #{channel.name}.")

        return _error(f"Failed to post in #{channel.name}: {e}")

    return json.dumps(
        {"sent": True, "channel": channel.name, "jump_url": posted.jump_url}
    )


# consumed by bot/ai/tools.py, which owns the registry and the definitions
DISCORD_TOOL_HANDLERS = {
    "ReadChannel": (ReadChannel, handle_read_channel),
    "SearchMessages": (SearchMessages, handle_search_messages),
    "GetMessage": (GetMessage, handle_get_message),
    "ListEvents": (ListEvents, handle_list_events),
    "GetMemberInfo": (GetMemberInfo, handle_get_member_info),
    "ServerSnapshot": (ServerSnapshot, handle_server_snapshot),
}

# registered only when switched on, which also removes it from TOOL_DEFINITIONS
# since those are built from this dict. Note this is stricter than the gate on
# CreateScheduledEvent, whose handler stays dispatchable either way: the point
# of this switch is that the tool be unreachable, hallucinated calls included
if DISCORD_SEND_TOOL_ENABLED:
    DISCORD_TOOL_HANDLERS["SendToChannel"] = (SendToChannel, handle_send_to_channel)
