import discord
import requests
from decouple import config
from discord.ext import commands
from httpx import ConnectError

from .ai.chat import ChatGPT, ImageClassify, Ollama
from .ai.image import ImageDallE
from .ai.moderation import check_moderate
from .api import (
    db_create_classification,
    db_create_completion,
    db_create_recipe,
    s3_save_image,
)
from .utils import create_embed
from .utils.settings import (
    CMC_API_KEY,
    CMC_API_URL,
    OLLAMA_MODEL,
    VISION_BRAIN_API_KEY,
    VISION_BRAIN_API_URL,
)

bot = commands.Bot(command_prefix=".", intents=discord.Intents.all())
admin_user_id = config("ADMIN_USER_ID")


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
        is_not_safe = await check_moderate(question)

        if is_not_safe:
            return await interaction.followup.send(
                "The question contains inappropriate content. Please try again with a different question."
            )

        ai = ChatGPT()
        prompt = question
        answer = ai.ask(prompt)

        await interaction.followup.send(
            f"***Answer for {interaction.user.mention}:***\n\n{answer}"
        )

        api_response = await db_create_completion(str(interaction.user), prompt, answer)
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
        is_not_safe = await check_moderate(question)

        if is_not_safe:
            return await interaction.followup.send(
                "The question contains inappropriate content. Please try again with a different question."
            )

        ai = Ollama(model=model)
        prompt = question
        response = ai.ask(prompt)

        await interaction.followup.send(
            f"***Answer for {interaction.user.mention}:***\n\n{response}"
        )

        api_response = await db_create_completion(
            str(interaction.user), prompt, response
        )
        print(api_response)

    except ConnectError as e:
        description = f"Connection to Model failed. Error: {e}"
        embed = create_embed(title="Model Connection Error:", description=description)
        await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="imagine", description="Generate an image with Dalle-E 3")
@discord.app_commands.describe(
    description="The description of the image you want to generate"
)
async def imagine(
    interaction: discord.Interaction,
    description: str,
):
    await interaction.response.defer()

    try:
        is_not_safe = await check_moderate(description)

        if is_not_safe:
            return await interaction.followup.send(
                "The prompt contains inappropriate content. Please try again with a different prompt."
            )

        ai = ImageDallE()
        image_url = ai.generate_image(description)

        await interaction.followup.send(image_url)

        saved_image = await s3_save_image(
            image_url=image_url, discord_user=str(interaction.user), prompt=description
        )
        print(saved_image)

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"Unknown Error: {e}")


@bot.tree.command(name="classify", description="Classify an image with GPT-4o")
@discord.app_commands.describe(
    image_url="The URL of the image you want to classify",
    prompt="Custom prompt for the classification",
)
async def classify_command(
    interaction: discord.Interaction,
    image_url: str,
    prompt: str = "Classify this image",
):
    await interaction.response.defer()

    try:
        is_not_safe = await check_moderate(prompt)

        if is_not_safe:
            return await interaction.followup.send(
                "The question contains inappropriate content. Please try again with a different question."
            )

        ai = ImageClassify(prompt=prompt)
        answer = ai.classify_image(image_url)

        await interaction.followup.send(
            f"***Image classification for {interaction.user.mention}:***\n\n{answer}"
        )

        api_response = await db_create_classification(
            str(interaction.user), image_url, answer
        )
        print(api_response)

        if api_response:
            print("Image classification saved to db.")

    except requests.exceptions.HTTPError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"API Error: {e}")

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
        crypto_symbol = symbol.upper()
        params = {
            "symbol": crypto_symbol,
            "convert": "USD",
            "CMC_PRO_API_KEY": CMC_API_KEY,
        }
        response = requests.get(CMC_API_URL, params=params)

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


@bot.tree.command(name="tts", description="Text-to-Speech")
@discord.app_commands.describe(
    text="The question you want to ask", voice="The voice you want to use"
)
async def tts_command(
    interaction: discord.Interaction, text: str, voice: str = "fable"
):
    headers = {
        "X-Api-Key": VISION_BRAIN_API_KEY,
    }

    data = {
        "text": text,
        "voice": voice,
    }

    await interaction.response.defer()

    try:
        is_not_safe = await check_moderate(text)

        if is_not_safe:
            return await interaction.followup.send(
                "The question contains inappropriate content. Please try again with a different question."
            )

        response = requests.post(VISION_BRAIN_API_URL, data=data, headers=headers)
        response.raise_for_status()
        data = response.json()
        md_encode = f"[Download File]({data.get('file')})"

        await interaction.followup.send(
            f"***Audio for {interaction.user.mention}:***\n\n***File:*** {md_encode}\n"
            f"***Text:*** {data.get('text')}"
        )

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")
        print(f"An error occurred: {e}")


@bot.tree.command(name="joke", description="Get a Chuck Norris joke")
@discord.app_commands.describe(category="The joke category you want to get")
async def joke_command(interaction: discord.Interaction, category: str):
    categories_url = "https://api.chucknorris.io/jokes/categories"
    get_categories = requests.get(categories_url)
    categories_list = get_categories.json()
    categories = ", ".join(categories_list)

    if category not in categories_list:
        return await interaction.response.send_message(
            f"**Available categories:** {categories}"
        )

    try:
        joke_url = f"https://api.chucknorris.io/jokes/random?category={category}"
        api_response = requests.get(joke_url)
        api_response.raise_for_status()

        if api_response.status_code != 200:
            embed = create_embed(
                title="Sorry",
                description="Could not retrieve joke from Chuck Norris API",
            )

            return await interaction.response.send_message(embed=embed)

        joke_json = api_response.json()
        joke_content = joke_json.get("value")

        await interaction.response.send_message(joke_content)

    except Exception as e:
        embed = create_embed(title="API Call Error:", description=e)
        await interaction.response.send_message(embed=embed)
        print(f"API Call Error: {e}")


@bot.tree.command(name="recipe", description="Generate a recipe based on ingredients")
@discord.app_commands.describe(ingredients="Ingeredients separated by commas")
async def recipe_command(interaction: discord.Interaction, ingredients: str):
    await interaction.response.defer()

    try:
        prompt = f"Write a recipe based on these ingredients:\n{ingredients}\n"

        ai = ChatGPT()
        recipe = ai.ask(prompt=prompt, max_tokens=500)

        await interaction.followup.send(
            f"***Recipe for {interaction.user.mention}:***\n\n{recipe}"
        )

        recipe_response = await db_create_recipe(
            str(interaction.user), ingredients, recipe
        )
        print(recipe_response)

    except requests.exceptions.HTTPError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"API Error: {e}")

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"Unknown Error: {e}")
