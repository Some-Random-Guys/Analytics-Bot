from discord.ext import commands
from discord import app_commands
from srg_analytics import DB
from backend import (
    log,
    embed_template,
    error_template,
    owner_ids,
    owner_guilds, get_db_creds,
)



class Owners(
    commands.GroupCog, group_name="owners"
):  # TODO use owner_guilds to restrict commands to owner guilds
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Owners.py Loaded")

    @app_commands.command()
    async def sync(self, interation):
        if interation.user.id not in owner_ids:
            return

        await self.client.tree.sync()
        await interation.response.send_message("Synced commands", ephemeral=True)

    @app_commands.command()
    async def reload(self, interation, cog: str):
        if interation.user.id not in owner_ids:
            return

        try:
            self.client.reload_extension(f"cogs.{cog}")
        except Exception as e:
            await interation.response.send_message(
                f"Failed to reload {cog}", ephemeral=True
            )
            return

        await interation.response.send_message(f"Reloaded {cog}", ephemeral=True)

    @app_commands.command()
    async def load(self, interation, cog: str):
        if interation.user.id not in owner_ids:
            return

        try:
            self.client.load_extension(f"cogs.{cog}")
        except Exception as e:
            await interation.response.send_message(
                f"Failed to load {cog}", ephemeral=True
            )
            return

        await interation.response.send_message(f"Loaded {cog}", ephemeral=True)

    @app_commands.command()
    async def unload(self, interation, cog: str):
        if interation.user.id not in owner_ids:
            return

        try:
            self.client.unload_extension(f"cogs.{cog}")
        except Exception as e:
            await interation.response.send_message(
                f"Failed to unload {cog}", ephemeral=True
            )
            return

        await interation.response.send_message(f"Unloaded {cog}", ephemeral=True)

    @app_commands.command()
    async def add_guild(self, interation, guild_id: str):
        if interation.user.id not in owner_ids:
            return

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        await db.add_guild(guild_id)

        await interation.response.send_message(
            f"Added guild {guild_id}", ephemeral=True
        )

    @app_commands.command()
    async def remove_guild(self, interation, guild_id: str):
        if interation.user.id not in owner_ids:
            return

        db = DB(db_creds=get_db_creds('onsite'))
        await db.connect()

        await db.remove_guild(guild_id)

        await interation.response.send_message(
            f"Removed guild {guild_id}", ephemeral=True
        )


async def setup(client):
    await client.add_cog(Owners(client))
