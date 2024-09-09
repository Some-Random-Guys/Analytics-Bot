from discord.ext import commands, tasks
from backend import log, get_db_creds
from srg_analytics import DB


class Listeners(commands.Cog):
    def __init__(self, client):
        self.db = DB(db_creds=get_db_creds('onsite'))  # TODO change to offsite
        self.client = client

        self.channel_ignores = {}
        self.user_ignores = {}
        self.aliased_users = {}

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Listeners.py Loaded")
        await self.db.connect()

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if self.db.con is None:
            await self.db.connect()
            return log.warning("Listeners: self.db is None")

        has_embed = after.embeds != []

        await self.db.edit_message(
            guild_id=before.guild.id, message_id=before.id, message_length=len(after.content),
            num_attachments=len(after.attachments), has_embed=has_embed
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        log.info(f"Joined guild {guild.id}")

        if self.db.con is None:
            await self.db.connect()
            return log.warning("Listeners: self.db is None")

        await self.db.add_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        log.info(f"Removed from guild {guild.id}")

        if self.db.con is None:
            await self.db.connect()
            return log.warning("Listeners: self.db is None")

        # When the bot is removed from a guild, delete all data associated with that guild
        await self.db.remove_guild(guild.id)
        await self.db.execute(f"DELETE FROM `config` WHERE `data1` = {guild.id}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if self.db.con is None:
            await self.db.connect()
            return log.warning("Listeners: self.db is None")

        await self.db.delete_message(guild_id=message.guild.id, message_id=message.id)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        channel_id = channel.id
        guild_id = channel.guild.id

        # delete all messages in that channel from database
        await self.db.execute(f"DELETE FROM `{guild_id}` WHERE `channel_id` = {channel_id}")

    @commands.Cog.listener()
    async def on_message(self, message):

        if not message.guild:
            return
        if message.is_system():
            return

        if self.db.con is None:
            await self.db.connect()

        # If the message's channel is ignored, return
        try:
            if message.channel.id in self.channel_ignores[message.channel.guild.id]:
                return
        except KeyError:
            pass

        # If the message's author is ignored, return
        try:
            if message.author.id in self.user_ignores[message.channel.guild.id]:
                return
        except KeyError:
            pass

        author_id = message.author.id

        # if message.author.id is an alias, set author to the alias' id
        guild_id = message.channel.guild.id

        try:
            author_id = self.aliased_users[guild_id][author_id]
        except KeyError:
            pass

        msg = {
            'message_id': message.id,
            'channel_id': message.channel.id,
            'author_id': message.author.id,
            'aliased_author_id': author_id,
            'message_length': len(message.content),
            'epoch': message.created_at.timestamp(),
            'has_embed': message.embeds != [],
            'num_attachments': len(message.attachments),
        }

        try:
            await self.db.add_message(guild_id=message.guild.id, data=msg)
            log.debug(f"Added message: {msg['message_id']}")

        except Exception as e:
            log.error(f"Error while adding message: {e}")

    @tasks.loop(seconds=60)
    async def cache(self):
        # Connect the DB if it isn't already connected
        if self.db.con is None:
            await self.db.connect()

        # Attempt to get channel ignores and user ignores
        try:
            # self.channel_ignores = await self.db.get_ignore_list("channel")
            # self.user_ignores = await self.db.get_ignore_list("user")

            self.aliased_users = await self.db.get_user_aliases()
            log.debug(self.aliased_users)

        except Exception as e:
            log.error(f"Error while fetching cache: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        raise error


async def setup(client):
    await client.add_cog(Listeners(client))
