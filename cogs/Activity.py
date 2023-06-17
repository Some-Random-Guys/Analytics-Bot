import discord
from discord.ext import commands
from backend import log, db_creds, embed_template, error_template
from discord import app_commands
from srg_analytics import activity_guild_visual, DB


class Activity(commands.GroupCog, name="activity"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Activity.py Loaded")


    @app_commands.command(name="server")
    # @app_commands.choices(type_=[
    #     app_commands.Choice(name="1 Day", value="channel"),
    #     app_commands.Choice(name="3 Days", value="user"),
    #     todo
    # ])
    async def activity_user(self, interation, timeperiod: int):
        await interation.response.defer()

        db = DB(db_creds)
        await db.connect()

        e = await activity_guild_visual(db=db, guild_id=interation.guild.id, time_period=timeperiod)

        embed = embed_template()
        embed.title = f"Activity for {interation.guild.name}"
        embed.description = f"Showing activity for the last {timeperiod} day(s)"
        embed.set_image(url="attachment://activity.png")

        await interation.followup.send(embed=embed, file=discord.File(e, filename="activity.png"))




async def setup(client):
    await client.add_cog(Activity(client))
