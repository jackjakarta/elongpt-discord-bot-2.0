import io

import discord
import httpx
from discord.ext import commands
from discord.ui import Button, View

from .ai.chat import ChatGPT
from .ai.image import ImageDallE
from .ai.tools import TOOL_DEFINITIONS, execute_tool_call
from .api.crud import db_create_completion
from .utils import create_embed, image_to_base64
from .utils.settings import ADMIN_USER_ID, CMC_API_KEY

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())


@bot.tree.command(name="synccommands", description="Sync commands with discord")
async def sync_commands(interaction: discord.Interaction):
    if str(interaction.user.id) != ADMIN_USER_ID:
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


@bot.tree.command(
    name="ask", description="Ask a question, schedule an event, perform tasks"
)
@discord.app_commands.describe(
    question="The question you want to ask",
    image1="Image 1",
    image2="Image 2",
    image3="Image 3",
    image4="Image 4",
    image5="Image 5",
)
async def ask_command(
    interaction: discord.Interaction,
    question: str,
    image1: discord.Attachment = None,
    image2: discord.Attachment = None,
    image3: discord.Attachment = None,
    image4: discord.Attachment = None,
    image5: discord.Attachment = None,
):
    files = [image1, image2, image3, image4, image5]
    await interaction.response.defer()
    user_name = str(interaction.user)

    context = ""
    if interaction.guild is not None:
        online_statuses = {
            discord.Status.online,
            discord.Status.idle,
            discord.Status.dnd,
        }

        online_users = [
            member.display_name
            for member in interaction.guild.members
            if not member.bot and member.status in online_statuses
        ]

        if online_users:
            context += f"Online users: {', '.join(online_users)}\n\n"

        messages = [msg async for msg in interaction.channel.history(limit=15)]
        messages.reverse()

        if messages:
            lines = [
                f"[{msg.author.display_name}] {msg.content}"
                for msg in messages
                if msg.content
            ]
            if lines:
                context += "Recent messages in this channel:\n" + "\n".join(lines)

    try:
        base64_images = []
        for file in files:
            if file is not None:
                file_data = await file.read()
                image_base64 = image_to_base64(file_data)
                base64_images.append(image_base64)

        ai = ChatGPT()
        prompt = question

        message = await ai.ask_with_tools(
            prompt,
            user_name=user_name,
            files=base64_images if len(base64_images) > 0 else None,
            context=context,
            tools=TOOL_DEFINITIONS,
        )

        tool_messages = []
        for _ in range(3):
            if not message.tool_calls:
                break
            tool_messages.append(message.to_dict())
            for tc in message.tool_calls:
                result = await execute_tool_call(
                    tc.function.name, tc.function.arguments, interaction.guild
                )
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            message = await ai.ask_with_tools(
                prompt,
                user_name=user_name,
                files=base64_images if len(base64_images) > 0 else None,
                context=context,
                tools=TOOL_DEFINITIONS,
                tool_messages=tool_messages,
            )

        response = str(message.content)
        await interaction.followup.send(response)

        try:
            await db_create_completion(user_name, prompt, response)
        except Exception as e:
            print(f"Failed to log completion: {e}")

    except httpx.HTTPStatusError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"API Error: {e}")

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=str(e))
        await interaction.followup.send(embed=embed)
        print(f"Error: {e}")


@bot.tree.command(name="imagine", description="Generate an image")
@discord.app_commands.describe(
    description="The description of the image you want to generate"
)
async def imagine(
    interaction: discord.Interaction,
    description: str,
):
    await interaction.response.defer()

    try:
        ai = ImageDallE()
        image_bytes = await ai.generate_image(description)

        file = discord.File(io.BytesIO(image_bytes), filename="image.png")
        await interaction.followup.send(file=file)

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"Unknown Error: {e}")


@bot.tree.command(
    name="price",
    description="Get the price and market capitalization of a cryptocurrency",
)
@discord.app_commands.describe(
    symbol="The cryptocurrency symbol you want to get the price for"
)
async def price(interaction: discord.Interaction, symbol: str):
    try:
        api_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
        crypto_symbol = symbol.upper()
        params = {
            "symbol": crypto_symbol,
            "convert": "USD",
            "CMC_PRO_API_KEY": CMC_API_KEY,
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, params=params)

        if response.status_code != 200:
            embed = create_embed(
                title="API Error",
                description=f"Could not get price and market capitalization for {crypto_symbol}",
            )

            return await interaction.channel.send(embed=embed)

        data = response.json()
        price = data["data"][crypto_symbol]["quote"]["USD"]["price"]
        market_cap = data["data"][crypto_symbol]["quote"]["USD"]["market_cap"]
        api_response = f"**Price:** ${price:.2f}\n**Market Cap:** ${market_cap:.2f}"
        embed = create_embed(title=crypto_symbol, description=api_response)

        await interaction.response.send_message(embed=embed)

    except KeyError as e:
        embed = create_embed(title=e, description="Invalid cryptocurrency symbol")
        await interaction.response.send_message(embed=embed)
        print(f"API Error: {e}, Invalid cryptocurrency symbol")

    except Exception as e:
        embed = create_embed(title="API Error", description=e)
        await interaction.response.send_message(embed=embed)
        print(f"API Error: {e}")


@bot.tree.command(name="joke", description="Get a Chuck Norris joke")
@discord.app_commands.describe(category="The joke category you want to get")
async def joke_command(interaction: discord.Interaction, category: str):
    categories_url = "https://api.chucknorris.io/jokes/categories"

    async with httpx.AsyncClient() as client:
        categories_response = await client.get(categories_url)
    categories_response.raise_for_status()
    categories_list = categories_response.json()
    categories = ", ".join(categories_list)

    if category not in categories_list:
        return await interaction.response.send_message(
            f"**Available categories:** {categories}"
        )

    try:
        joke_url = f"https://api.chucknorris.io/jokes/random?category={category}"

        async with httpx.AsyncClient() as client:
            joke_response = await client.get(joke_url)
        joke_response.raise_for_status()
        joke_json = joke_response.json()
        joke_content = joke_json.get("value")

        view = View()

        async def new_joke_callback(interaction: discord.Interaction):
            async with httpx.AsyncClient() as client:
                new_joke_response = await client.get(joke_url)
            new_joke_response.raise_for_status()
            new_joke_json = new_joke_response.json()
            new_joke_content = new_joke_json.get("value")
            await interaction.response.edit_message(content=new_joke_content)

        button = Button(label="Get Another Joke", style=discord.ButtonStyle.primary)
        button.callback = new_joke_callback
        view.add_item(button)

        await interaction.response.send_message(content=joke_content, view=view)

    except Exception as e:
        embed = create_embed(title="API Call Error:", description=str(e))
        await interaction.response.send_message(embed=embed)
        print(f"API Call Error: {e}")
