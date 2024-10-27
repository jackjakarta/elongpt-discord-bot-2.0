import discord
from decouple import config
from discord.ext import commands

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())
admin_user_id = config("ADMIN_USER_ID")


@bot.tree.command(name="hello", description="Say hello to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hello, {interaction.user.mention}", ephemeral=True
    )


@bot.tree.command(name="synccommands", description="Sync commands with discord")
async def sync_commands(interaction: discord.Interaction):
    if str(interaction.user.id) != admin_user_id:
        return await interaction.response.send_message(
            "You are not allowed to use this command"
        )

    try:
        synced_commands = await bot.tree.sync()
        await interaction.response.send_message(
            f"Synced {len(synced_commands)} commands",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.response.send_message(f"Failed to sync commands: {e}")
