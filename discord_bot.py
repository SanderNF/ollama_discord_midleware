import discord
from discord.ext import commands
from chat import send_prompt_http
import os
from pathlib import Path

# Create .env file if it doesn't exist
env_file = Path('.env')
if not env_file.exists():
    with open(env_file, 'w') as f:
        f.write('BOT_TOKEN=YOUR_BOT_TOKEN_HERE\n')
    print("Created .env file. Please add your bot token and restart the bot.")
    exit()

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get bot token from environment
bot_token = os.getenv('BOT_TOKEN')

# Validate token
if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
    print("Error: BOT_TOKEN not found or not set in .env file")
    print("Please add your bot token to the .env file and restart the bot.")
    exit()

# Create bot instance with command tree support
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Global variables for streaming
generating_msg = None
temp_response = ""
class Streaming:
    edit_msg = None
    temp_response = ""

def streamingCallback(chunk):
    print(chunk)
    print(Streaming.temp_response)
    print(Streaming.edit_msg)
    Streaming.temp_response += chunk
    if Streaming.edit_msg:
        Streaming.edit_msg(content=f'{Streaming.temp_response}')

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    # Register slash commands
    try:
        await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author == bot.user:
        return

    # Check if message starts with @grok
    if message.content.startswith('@grok '):
        await handle_grok_command(None, message=message, is_slash=False)

@bot.tree.command(name="grok", description="Ask Grok a question")
async def grok_command(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    await handle_grok_command(prompt, interaction=interaction, is_slash=True)

async def handle_grok_command(prompt, message=None, is_slash=False, interaction=None):
    #print(prompt, message)
    # For slash commands, get the channel and user from interaction
    if is_slash:
        channel = interaction.channel
        user = interaction.user
    else:
        channel = message.channel
        user = message.author
        prompt = message.content[5:].strip()  # Remove "@grok "

    # Get the message being replied to (only for normal messages)
    if not is_slash and message.reference and message.reference.message_id:
        try:
            replied_to_message = await channel.fetch_message(message.reference.message_id)
            prompt = f"Context: {replied_to_message.content}\n\nPrompt: {prompt}"
        except discord.NotFound:
            pass

    # Send "generating response" message
    if is_slash:
        generating_msg = await interaction.followup.send("Generating response...")
    else:
        generating_msg = await channel.send("Generating response...")

    Streaming.temp_response = ""

    try:
        response = await send_prompt_http(prompt, callback=lambda content: generating_msg.edit(content=content))
        text = response.get('text', '')
        evalTime = response.get('seconds_eval', 0)
        promptEvalTime = response.get('seconds_prompt_eval', 0)
        loadTime = response.get('seconds_load', 0)
        totalTime = response.get('seconds_total', 0)
        words = response.get('words', 0)
        tokens = response.get('tokens', 0)
        wpm = response.get('wpm', 0)
        tps = response.get('tps', 0)

        formatted_response = (
            f"{text}\n\n\n"
            f"> Total time: {totalTime:.2f}\n"
            f"> Model load time: {loadTime:.2f}\n"
            f"> Read prompt time: {promptEvalTime:.2f}\n"
            f"> Generation time: {evalTime:.2f}\n"
            f"> Words: {words}\n"
            f"> Tokens: {tokens}\n"
            f"> WPM: {wpm:.2f}\n"
            f"> TPS: {tps:.2f}\n"
            f"> Device: CPU\n"
            f"> Model: qwen3-coder:30b\n"
        )

        await generating_msg.edit(content=formatted_response)
    except Exception as e:
        print(e)
        # Handle any errors
        await generating_msg.edit(content=f"# Error: \n```\n{str(e)}\n```")

# Run the bot with your token
bot.run(bot_token)