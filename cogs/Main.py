import os
import discord
from discord.ext import commands
from discord import app_commands
from backend import db_creds
from srg_analytics import wordcloud, DB, get_top_users_visual, get_top_channels_visual, export_html, build_profile, \
    Profile

# Importing our custom variables/functions from backend.py
from backend import log, embed_template, error_template


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Main.py Loaded")
        # sync commands
        await self.client.tree.sync()

    @app_commands.command()
    async def wordcloud_(self, interation, member: discord.Member):
        await interation.response.defer()
        db: DB = DB(db_creds)
        cloud = await wordcloud(db, interation.guild.id, member.id)

        embed = embed_template()
        embed.title = "Word Cloud"
        embed.description = f"Here is the wordcloud for {member.mention if member else 'this server'}"
        embed.set_image(url="attachment://image.png")

        await interation.followup.send(embed=embed, file=discord.File(cloud, filename="image.png"))

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
    @app_commands.rename(type_='type')
    async def top(self, interaction, type_: app_commands.Choice[str], category: app_commands.Choice[str],
                  amount: int = 10):
        await interaction.response.defer()
        db = DB(db_creds)

        embed = embed_template()
        embed.title = f"Top {amount} {type_.name}s"

        if type_.value == "channel":
            res = await get_top_channels_visual(db, interaction.guild.id, self.client, category.value, amount)
            embed.description = f"Top {amount} channels in this guild"

        elif type_.value == "user":
            res = await get_top_users_visual(db, interaction.guild.id, self.client, category.value, amount)
            embed.description = f"Top {amount} users in this guild"

        embed.set_image(url="attachment://image.png")

        # open res as a file and send it
        await interaction.followup.send(embed=embed, file=discord.File(res, filename="image.png"))

        os.remove(res)

    @app_commands.command()
    @app_commands.choices(export_format=[
        app_commands.Choice(name="HTML", value="html"),
        # app_commands.Choice(name="JSON", value="json"),
    ])
    async def export(self, interation, channel: discord.TextChannel,
                     export_format: app_commands.Choice[str], message_limit: int = None):

        # Return if the user is not an admin
        if not interation.user.guild_permissions.administrator:
            await interation.response.send_message(
                embed=error_template("You must be an admin to use this command"),
                ephemeral=True
            )
            return

        await interation.response.defer()

        # HTML Export
        if export_format.value == "html":
            # Get the file from package
            file = await export_html(client=self.client, channel=channel, limit=message_limit)

            # Create embed
            embed = embed_template()
            embed.title = "Exported HTML"
            embed.description = f"Here is the exported HTML file for {channel.mention}"
            embed.set_image(url=f"attachment://export.html")

            # Send the embed and file
            await interation.followup.send(
                embed=embed, file=discord.File(file, filename=f"{channel.id}.html")
            )

    # error handler
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error: discord.DiscordException):
        log.error(error)


async def setup(client):
    await client.add_cog(Main(client))
