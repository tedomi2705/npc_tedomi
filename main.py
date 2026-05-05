import os
from dotenv import load_dotenv

import discord
from discord.ext import commands
import asyncio

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='t', intents=intents)

async def load_cogs():
    await bot.load_extension('cogs.general')
    await bot.load_extension('cogs.voice')

# Use uv to run this bot:
#   uv run main.py
if __name__ == '__main__':
    asyncio.run(load_cogs())
    bot.run(TOKEN)