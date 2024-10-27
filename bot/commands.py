import discord
from decouple import config
from discord.ext import commands
from ai.chat import ChatGPT

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

# @bot.tree.command(name="ask", description="Ask a question to ChatGPT")
# async def ask_command(interaction: discord.Interaction):
#     """
#     Handle the ask command to get an answer from ChatGPT.

#     Args:
#         message: The message object containing the command and user information.
#     """
#     await interaction.response.send_message(
#         f"Hello, {interaction.user.mention}", ephemeral=True
#     )

#     try:
#         ai = ChatGPT()
#         prompt = message.content[5:]
#         answer = ai.ask(prompt)

#         await message.channel.send(
#             f"***Answer for {message.author.name}:***\n\n{answer}"
#         )

#         api_response = db_create_completion(message.author.name, prompt, answer)
#         print(api_response)

#     except requests.exceptions.HTTPError as e:
#         embed = create_embed(title="API Error:", description=e)
#         await message.channel.send(embed=embed)
#         print(f"API Error: {e}")

#     except Exception as e:
#         embed = create_embed(title="Unknown Error:", description=e)
#         await message.channel.send(embed=embed)
#         print(f"Error: {e}")