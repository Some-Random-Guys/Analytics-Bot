import os
import discord
from discord.ext import commands
from discord import app_commands
from backend import db_creds
from srg_analytics import wordcloud, DB, get_top_users_visual

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

        await interation.response.send(embed=embed, file=discord.File(cloud, filename="image.png"))

        os.remove(cloud)

    @app_commands.command(name="top")
    @app_commands.choices(type_=[
        app_commands.Choice(name="Channel", value="channel"),
        app_commands.Choice(name="User", value="user"),
    ])
    @app_commands.choices(category=[
        app_commands.Choice(name="Messages", value="messages"),
        app_commands.Choice(name="Words", value="words"),
        app_commands.Choice(name="Characters", value="characters"),
    ])
    async def top(self, interaction, type_: app_commands.Choice[str], category: app_commands.Choice[str],
                  amount: int = 10):

        await interaction.response.defer()

        embed = embed_template()
        embed.title = f"Top {amount} {category.value.capitalize()}"

        if type_.value == "channel":
            pass

        elif type_.value == "user":
            res = await get_top_users_visual(self.db, interaction.guild.id, self.client, category.value, amount)
            embed.description = f"Top {amount} users by in this guild"

        embed.set_image(url="attachment://image.png")

        # open res as a file and send it
        await interaction.followup.send(embed=embed, file=discord.File(res, filename="image.png"))

        os.remove(res)

    # error handler
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error: discord.DiscordException):
        log.error(error)


async def setup(client):
    await client.add_cog(Main(client))
