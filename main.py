import discord
from discord.ext import tasks

from bot.commands import bot
from bot.utils.settings import DISCORD_TOKEN


@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(name="/ask"))


@bot.event
async def on_ready():
    change_bot_status.start()


bot.run(DISCORD_TOKEN)
