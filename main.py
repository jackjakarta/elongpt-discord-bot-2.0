import ctypes.util
import sys

import discord
import discord.opus
from discord.ext import tasks

from bot.commands import bot
from bot.utils.settings import DISCORD_TOKEN

if not discord.opus.is_loaded():
    opus_path = ctypes.util.find_library("opus")
    if opus_path is None and sys.platform == "darwin":
        opus_path = "/opt/homebrew/lib/libopus.dylib"
    if opus_path:
        discord.opus.load_opus(opus_path)
    if not discord.opus.is_loaded():
        print("Warning: opus library not found. Voice features will not work.")


@tasks.loop(seconds=5)
async def change_bot_status():
    await bot.change_presence(activity=discord.Game(name="/ask"))


@bot.event
async def on_ready():
    change_bot_status.start()


bot.run(DISCORD_TOKEN)
