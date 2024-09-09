import asyncio
import os
import sys
from backend import client, discord_token, log, presence, mode
import discord.utils


# This is what gets run when the bot stars
@client.event
async def on_ready():
    log.info(f"Bot is ready. Logged in as {client.user}")
    log.info("Ping: " + str(round(client.latency * 1000, 2)) + "ms")
    await client.change_presence(activity=discord.Game(name=presence))


async def load_cogs(mode):
    if mode != "listener":
        for file in os.listdir("./cogs"):
            if file.endswith(".py"):
                await client.load_extension(f"cogs.{file[:-3]}")
    else:
        await client.load_extension(f"cogs.Listeners")


asyncio.run(load_cogs(mode))


# Run the actual bot
try:
    client.run(discord_token)
except discord.LoginFailure:
    log.critical("Invalid Discord Token. Please check your config file.")
    sys.exit()
except Exception as err:
    log.critical(f"Error while connecting to Discord. Error: {err}")
    sys.exit()
