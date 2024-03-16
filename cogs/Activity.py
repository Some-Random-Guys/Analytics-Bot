import datetime
import discord
from discord.ext import commands
from backend import log, db_creds, embed_template, error_template
from discord import app_commands
from srg_analytics import (
    activity_guild_visual,
    DB,
    activity_user_visual,
    get_top_users_visual,
    get_top_users,
)
import os

timeperiod_choices = [
            app_commands.Choice(name="Today", value="1d"),
            app_commands.Choice(name="Past 5 days", value="5d"),
            app_commands.Choice(name="Past 1 Week", value="1w"),
            app_commands.Choice(name="Past 2 Weeks", value="2w"),
            app_commands.Choice(name="Past 1 Month", value="1m"),
            app_commands.Choice(name="Past 6 Months", value="6m"),
            app_commands.Choice(name="Past 1 Year", value="1y"),
            app_commands.Choice(name="Past 2 Years", value="2y"),
            app_commands.Choice(name="Past 5 Years", value="5y"),
            app_commands.Choice(name="All Time", value="all"),
        ]


class Activity(commands.GroupCog, name="activity"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Activity.py Loaded")

    @app_commands.command(name="server")
    @app_commands.choices(timeperiod=timeperiod_choices)
    async def activity_server(self, interation, timeperiod: app_commands.Choice[str]):
        await interation.response.defer()

        db = DB(db_creds)
        await db.connect()

        timezone = await db.get_timezone(guild_id=interation.guild.id)
        if not timezone:
            timezone = 3

        timezone = datetime.timezone(
            datetime.timedelta(hours=int(timezone) if timezone else 3)
        )

        e = await activity_guild_visual(
            db=db,
            guild_id=interation.guild.id,
            time_period=timeperiod.value,
            timezone=timezone,
        )

        embed = embed_template()
        embed.title = "Server Activity"
        embed.description = \
        f"For the guild `{interaction.guild.name}`\n" \
        f"Showing activity for the {timeperiod.name}"
        embed.set_image(url="attachment://activity.png")

        await interation.followup.send(
            embed=embed, file=discord.File(e, filename="activity.png")
        )

        os.remove(e)

    @app_commands.command(name="user")
    @app_commands.choices(timeperiod=timeperiod_choices)
    async def activity_user(
        self,
        interation,
        timeperiod: app_commands.Choice[str],
        user_1: discord.Member,
        user_2: discord.Member = None,
        user_3: discord.Member = None,
        user_4: discord.Member = None,
        user_5: discord.Member = None,
        include_server_activity: bool = False,
    ):
        await interation.response.defer()

        db = DB(db_creds)
        await db.connect()

        timezone = await db.get_timezone(guild_id=interation.guild.id)
        if not timezone:
            timezone = 3

        timezone = datetime.timezone(datetime.timedelta(hours=int(timezone)))

        # user_list format - [(name, id), (name, id), (name, id), (name, id), (name, id)]
        user_list = [
            (user.nick or user.display_name or user.name, user.id)
            for user in [user_1, user_2, user_3, user_4, user_5]
            if user is not None
        ]

        if include_server_activity:
            user_list.append(("Server", "Server"))

        res = await activity_user_visual(
            db=db,
            guild_id=interation.guild.id,
            user_list=user_list,
            time_period=timeperiod.value,
            include_server=include_server_activity,
            timezone=timezone,
        )

        if res is None:
            embed = error_template(
                "There was an error generating the graph. Please try again later."
            )
            await interation.followup.send(embed=embed)
            return

        embed = embed_template()
        embed.title = f"User Activity"
        embed.description = \
        f"For users {' '.join([user.mention for user in [user_1, user_2, user_3, user_4, user_5] if user is not None])}\n" \
        f"Showing activity for the {timeperiod.name}"
        embed.set_image(url="attachment://activity.png")

        await interation.followup.send(
            embed=embed, file=discord.File(res, filename="activity.png")
        )

        os.remove(res)

    @app_commands.command(name="today")
    @app_commands.choices(
        category=[
            app_commands.Choice(name="Messages", value="messages"),
            app_commands.Choice(name="Words", value="words"),
            app_commands.Choice(name="Characters", value="characters"),
        ]
    )
    async def today(
        self, interaction, category: app_commands.Choice[str], amount: int = 5
    ):
        await interaction.response.defer()

        db = DB(db_creds)
        await db.connect()

        # get top users today
        top = await get_top_users(
            db, interaction.guild.id, category.value, amount, "day", count_others=False
        )

        if top is None:
            embed = error_template(
                "There was an error generating the graph due to inadequate data. Please try again later."
            )
            await interaction.followup.send(embed=embed)
            return

        top = [i[0] for i in top]

        user_list = []

        for user in top:
            # get user object
            user = await interaction.guild.fetch_member(user)

            if user is None:
                continue

            nick = user.nick or user.display_name or user.name

            user_list.append((nick, user.id))

        file = await activity_user_visual(
            db=db,
            guild_id=interaction.guild.id,
            user_list=user_list,
            include_server=False,
            time_period="1d",
        )

        embed = embed_template()
        embed.title = f"Today's Activity"
        embed.description = f"Showing top users by {category.value}"
        embed.set_image(url="attachment://activity.png")

        await interaction.followup.send(
            embed=embed, file=discord.File(file, filename="activity.png")
        )

        # remove file
        os.remove(file)


async def setup(client):
    await client.add_cog(Activity(client))
