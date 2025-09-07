import discord
import httpx
import requests
from discord.ext import commands
from discord.ui import Button, View
from httpx import ConnectError

from .ai.chat import ChatGPT, Ollama
from .ai.image import ImageDallE
from .ai.moderation import check_moderate
from .api.crud import (
    check_ollama_server_health,
    db_create_completion,
    db_create_recipe,
    db_get_user_images,
    s3_save_image,
)
from .utils import create_embed, image_to_base64
from .utils.settings import (
    ADMIN_USER_ID,
    BACKEND_API_KEY,
    BACKEND_API_URL,
    CMC_API_KEY,
    OLLAMA_MODEL,
    SUPPORTED_OLLAMA_MODELS,
    UTILS_API_KEY,
    UTILS_API_URL,
)

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


@bot.tree.command(name="ask", description="Ask a question to ChatGPT")
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

    try:
        base64_images = []
        for file in files:
            if file is not None:
                file_data = await file.read()
                image_base64 = image_to_base64(file_data)
                base64_images.append(image_base64)

        ai = ChatGPT()
        prompt = question

        response = await ai.ask(
            prompt,
            user_name=user_name,
            files=base64_images if len(base64_images) > 0 else None,
        )

        await interaction.followup.send(response)
        await db_create_completion(user_name, prompt, response)

    except requests.exceptions.HTTPError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"API Error: {e}")

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"Error: {e}")


@bot.tree.command(name="ollama", description="Ask a question to Ollama")
@discord.app_commands.describe(
    question="The question you want to ask", model="The model you want to use"
)
async def ollama(
    interaction: discord.Interaction, question: str, model: str = OLLAMA_MODEL
):
    await interaction.response.defer()

    is_ollama_on = await check_ollama_server_health()

    if not is_ollama_on:
        return await interaction.followup.send(
            "Ollama server is not available at the moment. Please try again later."
        )

    if model not in SUPPORTED_OLLAMA_MODELS:
        return await interaction.followup.send(
            f"The model `{model}` is not supported. "
            f"Please choose from the following models: {', '.join(f'`{m}`' for m in SUPPORTED_OLLAMA_MODELS)}"
        )

    try:
        is_flagged = await check_moderate(question)

        if is_flagged:
            return await interaction.followup.send(
                "The question contains inappropriate content. Please try again with a different question."
            )

        ai = Ollama(model=model)
        prompt = question
        response = ai.ask(prompt)

        await interaction.followup.send(
            f"***Answer for {interaction.user.mention}:***\n\n{response}"
        )

        await db_create_completion(str(interaction.user), prompt, response)

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
        is_flagged = await check_moderate(description)

        if is_flagged:
            return await interaction.followup.send(
                "The prompt contains inappropriate content. Please try again with a different prompt."
            )

        ai = ImageDallE()
        image_url = await ai.generate_image(description)

        await interaction.followup.send(image_url)
        await s3_save_image(
            image_url=image_url, discord_user=str(interaction.user), prompt=description
        )

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
        response = requests.get(api_url, params=params)

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
    text="Text to convert", voice="voices: fable, alloy, shimmer"
)
async def tts_command(
    interaction: discord.Interaction, text: str, voice: str = "fable"
):
    headers = {
        "Authorization": f"Bearer {BACKEND_API_KEY}",
    }

    data = {
        "text": text,
        "discordUser": str(interaction.user),
        "voice": voice,
    }

    await interaction.response.defer()

    try:
        is_flagged = await check_moderate(text)

        if is_flagged:
            return await interaction.followup.send(
                "The question contains inappropriate content. Please try again with a different question."
            )

        api_url = f"{BACKEND_API_URL}/tts"

        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=data, headers=headers)
            response.raise_for_status()
            response_data = response.json()

        md_encode = f"[Download File]({response_data.get('audioUrl')})"

        await interaction.followup.send(
            f"***Audio for {interaction.user.mention}:***\n\n"
            f"***File:*** {md_encode}\n"
            f"***Text:*** {response_data.get('text')}"
        )

    except httpx.RequestError as e:
        await interaction.followup.send(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

    except Exception as e:
        await interaction.followup.send(f"An error occurred: {e}")
        print(f"An error occurred: {e}")


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


@bot.tree.command(name="recipe", description="Generate a recipe based on ingredients")
@discord.app_commands.describe(ingredients="Ingeredients separated by commas")
async def recipe_command(interaction: discord.Interaction, ingredients: str):
    await interaction.response.defer()

    try:
        ai = ChatGPT()
        prompt = f"Write a recipe based on these ingredients:\n{ingredients}\n"
        recipe = await ai.ask(prompt=prompt, user_name=str(interaction.user))

        await interaction.followup.send(
            f"***Recipe for {interaction.user.mention}:***\n\n{recipe}"
        )

        await db_create_recipe(str(interaction.user), ingredients, recipe)

    except requests.exceptions.HTTPError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"API Error: {e}")

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"Unknown Error: {e}")


@bot.tree.command(name="myimages", description="Get images generated by you")
async def get_images_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        user_images = await db_get_user_images(str(interaction.user))

        if not user_images:
            return await interaction.followup.send(
                f"No images found for {str(interaction.user)}",
                ephemeral=True,
            )

        for image in user_images[-10]:
            await interaction.followup.send(image["imageUrl"], ephemeral=True)

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"Unknown Error: {e}")


@bot.tree.command(name="barca", description="Get a upcoming FC Barcelona matches")
async def get_barca_matches_command(interaction: discord.Interaction):
    await interaction.response.defer()
    user_name = str(interaction.user)

    try:
        async with httpx.AsyncClient() as client:
            matches_response = await client.get(
                UTILS_API_URL, headers={"Authorization": f"Bearer {UTILS_API_KEY}"}
            )

        matches_response.raise_for_status()
        matches_list = matches_response.json()

        ai = ChatGPT(model="gpt-5-nano")
        prompt = f"Present this information to the user:\n{matches_list}\n"
        response = await ai.ask(prompt, user_name=user_name)

        await interaction.followup.send(
            f"***Upcoming Matches for {interaction.user.mention}:***\n\n{response}"
        )
    except requests.exceptions.HTTPError as e:
        embed = create_embed(title="API Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"API Error: {e}")

    except Exception as e:
        embed = create_embed(title="Unknown Error:", description=e)
        await interaction.followup.send(embed=embed)
        print(f"Unknown Error: {e}")
