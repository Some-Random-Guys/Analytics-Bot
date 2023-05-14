import os
import discord
from discord.ext import commands
from discord import app_commands
from backend import db_creds
from srg_analytics import wordcloud, DB

# Importing our custom variables/functions from backend.py
from backend import log, embed_template, error_template


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.db: DB = DB(db_creds)

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Main.py Loaded")
        # sync commands
        # await self.client.tree.sync()

    @app_commands.command()
    async def wordcloud_(self, interation, user_id: discord.Member):
        cloud = await wordcloud(self.db, interation.guild.id, user_id.id)

        embed = embed_template()
        embed.title = "Word Cloud"
        embed.description = f"Here is the wordcloud for {'<@' + str(user_id) + '>' if user_id else 'this server'}"
        embed.set_image(url="attachment://image.png")

        await self.client.tree.send(embed=embed, file=discord.File(cloud, filename="image.png"))

        os.remove(cloud)

    @app_commands.command()
    @app_commands.choices(type_=[
        app_commands.Choice(name="Channel", value="channel"),
        app_commands.Choice(name="User", value="user"),
    ])
    async def topusers(self, interaction, amount: int, type_: app_commands.Choice[str]):

        messages = await self.db.get_messages(interaction.guild.id, amount)





    # error handler
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error: discord.DiscordException):
        log.error(error)




async def setup(client):
    await client.add_cog(Main(client))
