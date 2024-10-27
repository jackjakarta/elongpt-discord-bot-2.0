import discord
import requests
from decouple import config
from discord.ext import commands
from httpx import ConnectError

from .ai.chat import ChatGPT, Ollama
from .api import db_create_completion
from .utils import create_embed
from .utils.settings import OLLAMA_MODEL

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())
admin_user_id = config("ADMIN_USER_ID")


@bot.tree.command(name="hello", description="Say hello to the bot")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"Hello, {interaction.user.mention}. I am ", ephemeral=True
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


@bot.tree.command(name="ask", description="Ask a question to ChatGPT")
@discord.app_commands.describe(question="The question you want to ask")
async def ask_command(interaction: discord.Interaction, question: str):
    await interaction.response.defer()

    try:
        ai = ChatGPT()
        prompt = question
        answer = ai.ask(prompt)

        await interaction.followup.send(
            f"***Answer for {interaction.user.mention}:***\n\n{answer}"
        )

        api_response = db_create_completion(str(interaction.user), prompt, answer)
        print(api_response)

    except requests.exceptions.HTTPError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.response.send_message(embed=embed)
        print(f"API Error: {e}")

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.response.send_message(embed=embed)
        print(f"Error: {e}")


@bot.tree.command(name="ollama", description="Ask a question to Ollama")
@discord.app_commands.describe(
    question="The question you want to ask", model="The model you want to use"
)
async def ollama(
    interaction: discord.Interaction, question: str, model: str = OLLAMA_MODEL
):
    await interaction.response.defer()

    try:
        ai = Ollama(model=model)
        prompt = question
        response = ai.ask(prompt)

        await interaction.followup.send(
            f"***Answer for {interaction.user.mention}:***\n\n{response}"
        )

        api_response = db_create_completion(str(interaction.user), prompt, response)
        print(api_response)

    except ConnectError as e:
        description = f"Connection to Model failed. Error: {e}"
        embed = create_embed(title="Model Connection Error:", description=description)
        await interaction.followup.send(embed=embed, ephemeral=True)
