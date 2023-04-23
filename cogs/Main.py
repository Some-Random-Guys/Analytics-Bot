import discord
from discord.ext import commands
from discord import app_commands

# Importing our custom variables/functions from backend.py
from backend import log, embed_template, error_template


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Main.py Loaded")

    


async def setup(client):
    await client.add_cog(Main(client))
