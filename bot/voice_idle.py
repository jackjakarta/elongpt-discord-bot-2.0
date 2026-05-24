import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from .utils import create_embed
from .utils.settings import (
    IDLE_VOICE_NOTIFY_CHANNEL_ID,
    IDLE_VOICE_TARGET_CHANNEL_ID,
    IDLE_VOICE_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 15

# member_id -> moment they became self-deafened
_idle_since: dict[int, datetime] = {}


async def _move_and_announce(
    member: discord.Member,
    source: discord.VoiceChannel,
    target: discord.VoiceChannel,
) -> None:
    try:
        await member.move_to(target, reason="Idle (self-deafened) too long")
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Failed to move %s to idle channel: %s", member, exc)
        return

    logger.info("Moved idle member %s to %s", member, target.name)

    notify_channel = source
    if IDLE_VOICE_NOTIFY_CHANNEL_ID is not None:
        notify_channel = member.guild.get_channel(IDLE_VOICE_NOTIFY_CHANNEL_ID)

    if notify_channel is None:
        return

    embed = create_embed(
        title="Idle in voice",
        description=(
            f"💤 {member.display_name} was moved to "
            f"**{target.name}** for being idle."
        ),
    )
    try:
        await notify_channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Failed to announce idle move for %s: %s", member, exc)


def setup_idle_monitor(bot: commands.Bot) -> None:
    """Start the background loop that moves idle (self-deafened) voice users.

    No-ops when the feature is disabled (missing config) or already running.
    """
    if IDLE_VOICE_TIMEOUT_SECONDS is None or IDLE_VOICE_TARGET_CHANNEL_ID is None:
        logger.info("Idle-voice monitor disabled (missing config).")
        return

    existing = getattr(bot, "idle_monitor_loop", None)
    if existing is not None and existing.is_running():
        return

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def monitor_idle_voice():
        now = datetime.now(timezone.utc)
        still_deafened: set[int] = set()

        for guild in bot.guilds:
            target = guild.get_channel(IDLE_VOICE_TARGET_CHANNEL_ID)
            for vc in guild.voice_channels:
                if vc.id == IDLE_VOICE_TARGET_CHANNEL_ID:
                    continue  # never herd people out of the AFK channel itself
                for member in list(vc.members):
                    vs = member.voice
                    if member.bot or vs is None or not vs.self_deaf:
                        continue

                    still_deafened.add(member.id)
                    since = _idle_since.setdefault(member.id, now)
                    if (now - since).total_seconds() < IDLE_VOICE_TIMEOUT_SECONDS:
                        continue

                    if target is None:
                        logger.warning(
                            "Idle target channel %s not found in guild %s",
                            IDLE_VOICE_TARGET_CHANNEL_ID,
                            guild.id,
                        )
                        continue

                    await _move_and_announce(member, source=vc, target=target)
                    _idle_since.pop(member.id, None)

        # reset timers for anyone no longer deafened / no longer in voice
        for mid in [m for m in _idle_since if m not in still_deafened]:
            _idle_since.pop(mid, None)

    bot.idle_monitor_loop = monitor_idle_voice
    monitor_idle_voice.start()
