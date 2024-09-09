import os
import discord
import time
from discord.ext import commands
from discord import app_commands
from backend import get_db_creds
from srg_analytics import (
    DB,
    get_top_users_visual,
    get_top_channels_visual,
    build_profile,
    Profile,
    get_user_top_date,
    get_server_top_date,
)

# Importing our custom variables/functions from backend.py
from backend import log, embed_template, error_template


class Main(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Main.py Loaded")
        # sync commands
        # await self.client.tree.sync()

    @app_commands.command(name="top")
    @app_commands.choices(
        type_=[
            app_commands.Choice(name="User", value="user"),
            app_commands.Choice(name="Channel", value="channel"),
        ]
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="Messages", value="messages"),
            app_commands.Choice(name="Words", value="words"),
            app_commands.Choice(name="Characters", value="characters"),
        ]
    )
    @app_commands.choices(
        timeperiod=[
            app_commands.Choice(name="Today", value="day"),
            app_commands.Choice(name="Past Week", value="week"),
            app_commands.Choice(name="This Month", value="month"),
            app_commands.Choice(name="This Year", value="year"),
        ]
    )
    @app_commands.rename(type_="type")
    async def top(
        self,
        interaction,
        type_: app_commands.Choice[str],
        category: app_commands.Choice[str],
        timeperiod: app_commands.Choice[str] = None,
        amount: int = 10,
    ):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        # if amount isn't in the range 1-20, set it to 10
        if not 1 <= amount < 21:
            amount = 10

        embed = embed_template()
        embed.title = f"Top {amount} {type_.name}s"
        timeperiod = timeperiod.value if timeperiod else None

        if type_.value == "channel":
            res = await get_top_channels_visual(
                db, interaction.guild.id, self.client, category.value, amount
            )  # no timeperiod for channels
            embed.description = f"Top {amount} channels in this guild"

        elif type_.value == "user":
            res = await get_top_users_visual(
                db,
                interaction.guild.id,
                self.client,
                category.value,
                timeperiod,
                amount,
            )
            embed.description = f"Top {amount} users in this guild"

        else:
            return

        embed.set_image(url="attachment://image.png")

        # open res as a file and send it
        await interaction.followup.send(
            embed=embed, file=discord.File(res, filename="image.png")
        )

        os.remove(res)

    @app_commands.command()
    async def profile(self, interaction, member: discord.Member = None):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        if not member:
            member = interaction.user

        # Get the file from package
        profile = await build_profile(
            db=db, guild_id=interaction.guild.id, user_id=member.id
        )

        # Create embed
        embed = embed_template()
        embed.title = f"Profile for {member}"
        embed.description = f"Here is the profile for {member.mention}. Took {round(profile['time_taken'], 2)} seconds to generate."

        embed.add_field(name="Messages", value=profile['messages'], inline=False)
        embed.add_field(name="Characters", value=profile['characters'], inline=False)
        embed.add_field(
            name="Average Message Length",
            value=f"{round(profile['average_message_length'], 2)} Characters",
            inline=False,
        )
        embed.add_field(
            name="Total Attachments", value=profile['total_attachments'], inline=False
        )
        if member.bot:
            embed.add_field(
                name="Total Embeds", value=profile['total_embeds'], inline=False
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command()
    async def topdate(self, interaction, member: discord.Member = None):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        if member:
            res = await get_user_top_date(db, interaction.guild.id, member.id)
        else:
            res = await get_server_top_date(db, interaction.guild.id)

        embed = embed_template()
        embed.title = "Top Messages in a Day"
        embed.description = f"For {member.mention if member else 'this server'}"

        if member:
            for item in res:
                embed.add_field(
                    name=f"<t:{str(item[0])[:-7]}:D>", value=f"{item[1]} ({round((item[1] / item[2]) * 100)}% of that day)", inline=False
                )
        else:
            for item in res:
                embed.add_field(
                    name=f"<t:{str(item[0])[:-7]}:D>", value=item[1], inline=False
                )

        await interaction.followup.send(embed=embed)

    @app_commands.command()
    async def help(self, interaction):
        await interaction.response.defer()

        embed = embed_template()
        embed.title = "Help"
        embed.description = "Here are the commands for this bot"

        embed.add_field(
            name="Activity",
            value="</activity:1116797580752474232> | Get server activity",
            inline=False,
        )
        embed.add_field(
            name="Profile",
            value="</profile:1116739144929001473> | Get a user's profile",
            inline=False,
        )
        embed.add_field(
            name="Top",
            value="</top:1109066788358082621> | Get the top users or channels",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    # error handler
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error: discord.DiscordException):
        # if it's command is not found, skip
        if isinstance(error, commands.CommandNotFound):
            return

    # app command error handler
    @commands.Cog.listener()
    async def on_application_command_error(self, ctx, error: discord.DiscordException):
        log.error(error)


async def setup(client):
    await client.add_cog(Main(client))
