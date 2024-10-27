from typing import Final

import discord
from decouple import config
from discord.ext import tasks

from commands import bot

DISCORD_TOKEN: Final[str] = config("DISCORD_TOKEN")


@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(name="with discord.py"))


@bot.event
async def on_ready():
    change_bot_status.start()


bot.run(DISCORD_TOKEN)
