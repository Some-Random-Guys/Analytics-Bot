import datetime
import discord
from discord.ext import commands
from backend import log, embed_template, error_template, get_db_creds
from discord import app_commands
from srg_analytics import (
    DB,
    get_top_users_visual,
    get_top_users,
    activity_server
)
import os

timeperiod_choices = [
    app_commands.Choice(name="Today", value="1d"),
    app_commands.Choice(name="Past 1 Week", value="1w"),
    app_commands.Choice(name="Past 2 Weeks", value="2w"),
    app_commands.Choice(name="Past 1 Month", value="1m"),
    app_commands.Choice(name="Past 6 Months", value="6m"),
    app_commands.Choice(name="Past 1 Year", value="1y"),
    app_commands.Choice(name="Past 2 Years", value="2y"),
    app_commands.Choice(name="Past 5 Years", value="5y"),
    app_commands.Choice(name="All Time", value="all"),
]


async def format_datarange(start_date: str, end_date: str):
    # parameter validation
    dates: list[str] = [start_date, end_date]

    for i in range(len(dates)):
        dates[i] = dates[i].strip()
        dates[i] = dates[i].replace("/", "-")
        dates[i] = dates[i].replace("\\", "-")
        dates[i] = dates[i].replace(".", "-")
        dates[i] = dates[i].replace(" ", "-")

    # if datetime.datetime.strptime(dates[1], date_format).timestamp() - datetime.datetime.strptime(dates[0], date_format).timestamp() < 60*60*24:
    #    print("TODO thing too small")
    #    return

    # Check if both the dates are in the same format
    if len(dates[0].split("-")) != len(dates[1].split("-")):
        raise ValueError

    # 10-11-22 -> 10-11-2022
    for i in range(len(dates)):
        parts = dates[i].split("-")

        # If the year is `yy` instead of `yyyy`, convert to `20yy`
        if not len(parts[-1]) == 4:
            dates[i] = f"{dates[i][0:-3]}-20{dates[i][-2:]}"

    # if the date is in the format mm/yyyy
    if len(dates[0].split("-")) == 2:
        date_format = '%m-%Y'

        for i in range(len(dates)):
            datetime.datetime.strptime(dates[i], date_format)

    # if the date is in the format dd/mm/yyyy
    elif len(dates[0].split("-")) == 3:
        date_format = '%d-%m-%Y'

        for i in range(len(dates)):
            datetime.datetime.strptime(dates[i], date_format)

    return dates


class Activity(commands.GroupCog, name="activity"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Activity.py Loaded")

    @app_commands.command(name="server")
    @app_commands.choices(timeperiod=timeperiod_choices)
    async def activity_server(self, interaction, timeperiod: app_commands.Choice[str]):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        timezone = await db.get_timezone(guild_id=interaction.guild.id)
        if not timezone:
            timezone = 3

        match timeperiod.value:
            case "1d":
                start_date = datetime.datetime.now() - datetime.timedelta(days=1)
                end_date = datetime.datetime.now()
            case "1w":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=1)
                end_date = datetime.datetime.now()
            case "2w":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=2)
                end_date = datetime.datetime.now()
            case "1m":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=4)
                end_date = datetime.datetime.now()
            case "6m":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=24)
                end_date = datetime.datetime.now()
            case "1y":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=52)
                end_date = datetime.datetime.now()
            case "2y":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=104)
                end_date = datetime.datetime.now()
            case "5y":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=260)
                end_date = datetime.datetime.now()
            case "all":
                start_date = datetime.datetime.now() - datetime.timedelta(weeks=2600)
                end_date = datetime.datetime.now()
            case _:
                return

        e = await activity_server(
            start_date=start_date,
            end_date=end_date,
            timezone_offset=timezone
        )

        embed = embed_template()
        embed.title = "Server Activity"
        embed.description = \
            f"For the guild `{interaction.guild.name}`\n" \
            f"Showing activity for the {timeperiod.name}"
        embed.set_image(url="attachment://activity.png")

        await interaction.followup.send(
            embed=embed, file=discord.File(e, filename="activity.png")
        )


    @app_commands.command(name="user")
    @app_commands.choices(timeperiod=timeperiod_choices)
    async def activity_user(
            self, interaction,
            timeperiod: app_commands.Choice[str],
            user_1: discord.User,
            user_2: discord.User = None,
            user_3: discord.User = None,
            user_4: discord.User = None,
            user_5: discord.User = None,
    ):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        timezone = await db.get_timezone(guild_id=interaction.guild.id)
        if not timezone:
            timezone = 3

        # user_list format - [(name, id), (name, id), (name, id), (name, id), (name, id)]
        user_list = [
            (user.nick if hasattr(user, 'nick') else user.display_name or user.name, user.id)
            for user in [user_1, user_2, user_3, user_4, user_5]
            if user is not None
        ]

        # res = await activity_user_visual(
        #     db=db,
        #     guild_id=interaction.guild.id,
        #     user_list=user_list,
        #     timeperiod_or_daterange=timeperiod.value,
        #     timezone=timezone,
        # )
        #
        # if res is None:
        #     embed = error_template(
        #         "There was an error generating the graph. Please try again later."
        #     )
        #     await interaction.followup.send(embed=embed)
        #     return
        #
        # embed = embed_template()
        # embed.title = f"User Activity"
        # embed.description = \
        #     f"For users {' '.join([user.mention for user in [user_1, user_2, user_3, user_4, user_5] if user is not None])}\n" \
        #     f"Showing activity for the {timeperiod.name}"
        # embed.set_image(url="attachment://activity.png")
        #
        # await interaction.followup.send(
        #     # embed=embed, file=discord.File(res, filename="activity.png")
        # )

        # os.remove(res)

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

        db = DB(db_creds=get_db_creds('onsite'))
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

            nick = user.nick if hasattr(user, 'nick') else user.display_name or user.name

            user_list.append((nick, user.id))

        # file = await activity_user_visual(
        #     db=db,
        #     guild_id=interaction.guild.id,
        #     user_list=user_list,
        # )
        #
        # embed = embed_template()
        # embed.title = f"Today's Activity"
        # embed.description = f"Showing top users by {category.value}"
        # embed.set_image(url="attachment://activity.png")
        #
        # await interaction.followup.send(
        #     embed=embed, file=discord.File(file, filename="activity.png")
        # )
        #
        # # remove file
        # os.remove(file)

    @app_commands.command(name="serverpast")
    async def activity_serverpast(self, interaction, start_date: str, end_date: str):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        # Timezone logic
        timezone = await db.get_timezone(guild_id=interaction.guild.id)
        if not timezone:
            timezone = 3

        timezone = datetime.timezone(
            datetime.timedelta(hours=int(timezone) if timezone else 3)
        )

        try:
            dates = await format_datarange(start_date, end_date)
            assert dates is not None
        except ValueError:
            await interaction.followup.send("Invalid date or date format")
            return
        except AssertionError:
            await interaction.followup.send("Unknown error")  # TODO
            return
        #
        # e = await activity_guild_visual(
        #     db=db,
        #     guild_id=interaction.guild.id,
        #     timeperiod_or_daterange=dates,
        #     timezone=timezone,
        # )
        #
        # embed = embed_template()
        # embed.title = "Server Activity"
        # embed.description = \
        #     f"For the guild `{interaction.guild.name}`\n" \
        #     f"Showing activity from {start_date} to {end_date}"
        # embed.set_image(url="attachment://activity.png")
        #
        # await interaction.followup.send(
        #     embed=embed, file=discord.File(e, filename="activity.png")
        # )
        #
        # os.remove(e)

    @app_commands.command(name="userpast")
    async def activity_userpast(
            self, interaction: discord.Interaction, start_date: str, end_date: str,
            user_1: discord.User,
            user_2: discord.User = None,
            user_3: discord.User = None,
            user_4: discord.User = None,
            user_5: discord.User = None,
    ):
        await interaction.response.defer()

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        timezone = await db.get_timezone(guild_id=interaction.guild.id)
        if not timezone:
            timezone = 3

        timezone = datetime.timezone(datetime.timedelta(hours=int(timezone)))

        # user_list format - [(name, id), (name, id), (name, id), (name, id), (name, id)]
        user_list = [
            (user.nick if hasattr(user, 'nick') else user.display_name or user.name, user.id)
            for user in [user_1, user_2, user_3, user_4, user_5]
            if user is not None
        ]

        try:
            dates = await format_datarange(start_date, end_date)
            assert dates is not None
        except ValueError:
            await interaction.followup.send("Invalid date or date format")
            return
        except AssertionError:
            await interaction.followup.send("Unknown error") #TODO
            return
        #
        # res = await activity_user_visual(
        #     db=db,
        #     guild_id=interaction.guild.id,
        #     user_list=user_list,
        #     timeperiod_or_daterange=dates,
        #     timezone=timezone,
        # )
        #
        # if res is None:
        #     embed = error_template(
        #         "There was an error generating the graph. Please try again later."
        #     )
        #     await interaction.followup.send(embed=embed)
        #     return
        #
        # embed = embed_template()
        # embed.title = f"User Activity"
        # embed.description = \
        #     f"For users {' '.join([user.mention for user in [user_1, user_2, user_3, user_4, user_5] if user is not None])}\n" \
        #     f"Showing activity from {start_date} to {end_date}"
        # embed.set_image(url="attachment://activity.png")
        #
        # await interaction.followup.send(
        #     embed=embed, file=discord.File(res, filename="activity.png")
        # )
        #
        # os.remove(res)


async def setup(client):
    await client.add_cog(Activity(client))
