import asyncio
import time
import discord
from discord.ext import commands
from backend import log, db1_creds, db2_creds, is_admin, ConfirmButton, get_db_creds
from discord import app_commands, TextChannel, Member, User
from backend import embed_template, error_template  # , remove_ignore_autocomplete
import warnings
import threading

from srg_analytics import DB

warnings.filterwarnings("ignore", module=r"aiomysql")


class Admin(commands.Cog, name="admin"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Admin.py Loaded")
        # await self.client.tree.sync()

    async def save_channel(self, channel):
        guild_id = channel.guild.id

        message_ids = []
        channel_ids = []
        author_ids = []
        aliased_author_ids = []
        message_lengths = []
        epoches = []
        has_embeds = []
        num_attachments = []

        async for message in channel.history(limit=None):
            message_ids.append(message.id)
            channel_ids.append(message.channel.id)
            author_ids.append(message.author.id)
            message_lengths.append(len(message.content))
            epoches.append(message.created_at.timestamp())
            has_embeds.append(message.embeds != [])
            num_attachments.append(len(message.attachments))

        db = DB(get_db_creds('onsite'))
        await db.add_messages_bulk(guild_id, message_ids, channel_ids, author_ids, aliased_author_ids, message_lengths, epoches, has_embeds, num_attachments)

    @app_commands.command()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def guild_harvest(
            self,
            interaction,
            channel: discord.TextChannel | discord.ForumChannel = None,
            amount: int = None,
    ):
        start_time = time.time()
        guild = interaction.guild

        for channel in guild.channels:
            # guild.channel contains:
            # TextChannel, VoiceChannel, CategoryChannel, StageChannel, ForumChannel
            print(channel)

            if isinstance(channel, discord.TextChannel):
                await self.save_channel(channel)

                for thread in channel.threads:
                    await self.save_channel(thread)

                async for thread in channel.archived_threads():
                    await self.save_channel(thread)

            elif isinstance(channel, discord.ForumChannel):
                for thread in channel.threads:
                    await self.save_channel(thread)

                async for thread in channel.archived_threads():
                    await self.save_channel(thread)

            elif isinstance(channel, discord.VoiceChannel):
                await self.save_channel(channel)

    @commands.Cog.listener()
    async def check(self, ctx):
        return await is_admin(ctx)


async def setup(client):
    await client.add_cog(Admin(client))
