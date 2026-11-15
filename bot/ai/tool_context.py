from dataclasses import dataclass

import discord


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool handler is allowed to know about its invocation.

    Handlers used to receive only the guild, which is why the only Discord tool
    was a guild-level create. Anything that reads or writes a channel needs to
    know where /ask was run and — more importantly — who ran it: every Discord
    tool mirrors the invoking user's permissions rather than the bot's, so the
    model can never reach a channel the asker couldn't open themselves.

    `user` is a Member inside a guild and a plain User in DMs, where `guild` is
    None and every guild tool refuses.
    """

    guild: discord.Guild | None
    channel: discord.abc.Messageable | None
    user: discord.Member | discord.User
