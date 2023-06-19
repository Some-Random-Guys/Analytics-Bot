import datetime

import discord
from discord.ext import commands
from backend import log, db_creds, embed_template, error_template
from discord import app_commands
from srg_analytics import activity_guild_visual, DB
import os


class Activity(commands.GroupCog, name="activity"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Activity.py Loaded")

    @app_commands.command(name="server")
    @app_commands.choices(timeperiod=[
        app_commands.Choice(name="1 Day", value="1d"),
        app_commands.Choice(name="5 Days", value="5d"),
        app_commands.Choice(name="1 Week", value="1w"),
        app_commands.Choice(name="2 Weeks", value="2w"),
        app_commands.Choice(name="1 Month", value="1m"),
        app_commands.Choice(name="3 Months", value="3m"),
        app_commands.Choice(name="6 Months", value="6m"),
        app_commands.Choice(name="9 Months", value="9m"),
        app_commands.Choice(name="1 Year", value="1y"),
        app_commands.Choice(name="2 Year", value="2y"),
        app_commands.Choice(name="3 Year", value="3y"),
        app_commands.Choice(name="All Time", value="all")
    ])
    @app_commands.choices(interval=[
        app_commands.Choice(name="Hour", value="hours"),
        app_commands.Choice(name="Day", value="days"),
        app_commands.Choice(name="Week", value="weeks"),
        app_commands.Choice(name="Month", value="months"),
        app_commands.Choice(name="Year", value="years")
    ])
    @app_commands.choices(timezone=[
        app_commands.Choice(name="UTC-11", value="-11"),
        app_commands.Choice(name="UTC-10", value="-10"),
        app_commands.Choice(name="UTC-9", value="-9"),
        app_commands.Choice(name="UTC-8", value="-8"),
        app_commands.Choice(name="UTC-7", value="-7"),
        app_commands.Choice(name="UTC-6", value="-6"),
        app_commands.Choice(name="UTC-5", value="-5"),
        app_commands.Choice(name="UTC-4", value="-4"),
        app_commands.Choice(name="UTC-3", value="-3"),
        app_commands.Choice(name="UTC-2", value="-2"),
        app_commands.Choice(name="UTC-1", value="-1"),
        app_commands.Choice(name="UTC", value="0"),
        app_commands.Choice(name="UTC+1", value="1"),
        app_commands.Choice(name="UTC+2", value="2"),
        app_commands.Choice(name="UTC+3", value="3"),
        app_commands.Choice(name="UTC+4", value="4"),
        app_commands.Choice(name="UTC+5", value="5"),
        app_commands.Choice(name="UTC+6", value="6"),
        app_commands.Choice(name="UTC+7", value="7"),
        app_commands.Choice(name="UTC+8", value="8"),
        app_commands.Choice(name="UTC+9", value="9"),
        app_commands.Choice(name="UTC+10", value="10"),
        app_commands.Choice(name="UTC+11", value="11"),
        app_commands.Choice(name="UTC+12", value="12"),
        app_commands.Choice(name="UTC+13", value="13"),

    ])
    async def activity_server(self, interation, timeperiod: app_commands.Choice[str], interval: app_commands.Choice[str] = None, timezone: app_commands.Choice[str] = None):
        await interation.response.defer()

        db = DB(db_creds)
        await db.connect()

        print(int(timezone.value) if timezone else 3)

        timezone = datetime.timezone(
            datetime.timedelta(
                hours=int(timezone.value) if timezone else 3
            )
        )

        e = await activity_guild_visual(db=db, guild_id=interation.guild.id, time_period=timeperiod.value, interval=interval.value if interval else None,
                                        timezone=timezone)

        embed = embed_template()
        embed.title = f"Activity for {interation.guild.name}"
        embed.description = f"Showing activity for the last {timeperiod}"
        embed.set_image(url="attachment://activity.png")

        await interation.followup.send(embed=embed, file=discord.File(e, filename="activity.png"))

        os.remove(e)


async def setup(client):
    await client.add_cog(Activity(client))
