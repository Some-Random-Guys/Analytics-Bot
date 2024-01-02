import discord
from discord.ext import commands
from discord import app_commands
from backend import log, embed_template, error_template, db_creds
from srg_analytics import letter_leaderboard, DB


class Leaderboard(commands.GroupCog, group_name="leaderboard"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print("Cog: Leaderboard.py Loaded")

    @app_commands.command()
    async def letter(self, interaction, user: discord.Member = None):
        await interaction.response.defer()

        db = DB(db_creds)
        await db.connect()

        embed = embed_template()
        embed.title = "Leaderboard"
        embed.description = (
            "This is a leaderboard of all the letters sent in the server"
        )

        res = await letter_leaderboard(
            db=db, guild_id=interaction.guild.id, user_id=user.id if user else None
        )

        if not res:
            await interaction.response.send_message(
                "No letters have been sent in this server", ephemeral=True
            )
            return

        # res is a Counter object with letter: count
        for letter, count in res.most_common():
            embed.add_field(name=letter, value=count, inline=True)

        await interaction.followup.send(embed=embed)


async def setup(client):
    await client.add_cog(Leaderboard(client))
