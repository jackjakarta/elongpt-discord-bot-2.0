import discord
from discord.ext import tasks

from bot.commands import bot
from bot.utils.settings import DISCORD_TOKEN
from bot.voice_idle import setup_idle_monitor


@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(name="/ask"))


@bot.event
async def on_ready():
    if not change_bot_status.is_running():
        change_bot_status.start()
    setup_idle_monitor(bot)


bot.run(DISCORD_TOKEN)
