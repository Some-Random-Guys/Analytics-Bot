import asyncio
import time
from discord.ext import commands
from backend import log, db_creds, is_admin
from srg_analytics import DB
from srg_analytics.schemas import DataTemplate
from discord import app_commands, TextChannel, Member, User
from backend import embed_template, error_template, remove_ignore_autocomplete
from asyncer import asyncify
import aiomysql
import warnings

warnings.filterwarnings('ignore', module=r"aiomysql")


class Admin(commands.GroupCog, name="admin"):
    def __init__(self, client):
        self.client = client
        self.db = DB(db_creds)

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Admin.py Loaded")

    @app_commands.command()
    @commands.guild_only()
    async def harvest(self, interaction):
        cmd_channel = interaction.channel

        channel_ignores = tuple(await self.db.get_ignore_list("channel", interaction.guild.id))
        user_ignores = tuple(await self.db.get_ignore_list("user", interaction.guild.id))
        aliased_users = await self.db.get_user_aliases(guild_id=interaction.guild.id)
        aliases = set([alias for alias_list in aliased_users.values() for alias in alias_list])

        total_msgs = 0
        total_time = 0

        db = await aiomysql.create_pool(
            host=db_creds.host, port=db_creds.port, user=db_creds.user, password=db_creds.password, db=db_creds.name,
            autocommit=True, loop=self.client.loop
        )

        query = f"""
                INSERT IGNORE INTO `{interaction.guild.id}` (author_id, is_bot, has_embed, channel_id, epoch, num_attachments, mentions, ctx_id, message_content, message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """

        batch_size = 7
        concurrent_limit = 7
        semaphore = asyncio.Semaphore(concurrent_limit)

        # async with db.acquire() as conn:
        #     async with conn.cursor() as cur:
        #         await cur.execute(f"SELECT message_id from `{interaction.guild.id}`;")
        #
        #         existing_messages = tuple(set([msg[0] for msg in await cur.fetchall()]))

        async def process_messages(channel):
            nonlocal total_msgs, total_time

            await asyncio.sleep(2)

            msg_data = []

            if channel.id in channel_ignores:
                return

            start_time = time.time()
            num_msgs = 0

            async with semaphore:  # Acquire the semaphore before processing
                async for message in channel.history(limit=None):
                    # if message.id in existing_messages:
                    #     continue
                    if message.author.id in user_ignores:
                        continue

                    mentions = [str(mention.id) for mention in message.mentions]
                    author = message.author.id

                    if author in aliases:
                        for alias, alias_list in aliased_users.items():
                            if author in alias_list:
                                author = alias
                                break

                    num_msgs += 1
                    if num_msgs % 10000 == 0:
                        log.info(f"Processed {num_msgs} messages")

                    # Create a message data object without saving to the database
                    msg = (
                        author,
                        bool(message.author.bot),
                        len(message.embeds) > 0,
                        int(message.channel.id),
                        int(message.created_at.timestamp()),
                        len(message.attachments),
                        ",".join(mentions) if mentions else None,
                        int(message.reference.message_id) if message.reference is not None and isinstance(
                            message.reference.message_id, int) else None,
                        str(message.content),
                        int(message.id)
                    )

                    # Collect the message data for batch insertion
                    msg_data.append(msg)

            elapsed_time = time.time() - start_time
            total_time += elapsed_time
            total_msgs += num_msgs

            try:
                # run executemany to insert the batch of messages in a different thread to avoid blocking,
                # it is a synchronous function
                async with db.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.executemany(query, msg_data)

                        # No need to commit since we are using autocommit

            except Exception as e:
                raise e
                # log.error(str(e))

            # Send progress embed for the channel
            embed = embed_template()
            embed.title = f"Harvested Channel | {interaction.guild.text_channels.index(channel) + 1}/{len(interaction.guild.text_channels)}"
            embed.description = f"Successfully harvested the messages in {channel.mention}"
            embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)
            embed.add_field(name="Total Harvested (Channel)", value=f"`{num_msgs}`", inline=False)
            embed.add_field(name="Total Harvested (Server)", value=f"`{total_msgs}`", inline=False)
            embed.add_field(name="Time Taken", value=f"`{elapsed_time:.2f} seconds`", inline=False)

            try:
                await cmd_channel.send(embed=embed)
            except Exception as e:
                log.error(str(e))

        # Fetch messages from channels in batches
        tasks = []
        channels = interaction.guild.text_channels

        # Divide channels into batches
        channel_batches = [channels[i:i + batch_size] for i in range(0, len(channels), batch_size)]

        for batch in channel_batches:
            batch_tasks = [process_messages(channel) for channel in batch]
            tasks.extend(batch_tasks)

        await asyncio.gather(*tasks)

        # Calculate timing statistics
        total_time_str = f"{total_time:.2f} seconds"
        msgs_per_sec = total_msgs / total_time
        msgs_per_100k = msgs_per_sec * 100000
        per_100k_str = f"{msgs_per_100k:.2f} seconds"

        # Send completion embed
        embed = embed_template()
        embed.title = "Harvest Complete"
        embed.description = f"Successfully harvested all channels in {interaction.guild.name}"
        embed.add_field(name="Total Harvested", value=f"`{total_msgs}`", inline=False)
        embed.add_field(name="Total Time", value=f"`{total_time_str}`", inline=False)
        embed.add_field(name="Time per 100,000 Messages", value=f"`{per_100k_str}`", inline=False)
        await cmd_channel.send(embed=embed)

    @app_commands.command()
    @commands.guild_only()
    async def add_ignore(self, interaction, channel: TextChannel = None, user: Member = None):
        if user is None:
            if channel is None:
                channel = interaction.channel

        if user is not None:
            await self.db.add_ignore(guild_id=interaction.guild.id, user_id=user.id)
            await interaction.response.send_message(f"Ignoring {user.mention}", ephemeral=True)
        elif channel is not None:
            await self.db.add_ignore(guild_id=interaction.guild.id, channel_id=channel.id)
            await interaction.response.send_message(f"Ignoring {channel.mention}", ephemeral=True)

    # @app_commands.command()
    # @app_commands.choices(type_=[
    #     app_commands.Choice(name="Channel", value="channel"),
    #     app_commands.Choice(name="User", value="user"),
    # ])
    # @app_commands.autocomplete(value_=remove_ignore_autocomplete)
    # async def remove_ignore(self, interaction, type_: app_commands.Choice[str], value_: str):
    #     pass

    @app_commands.command()
    @commands.guild_only()
    async def add_user_alias(self, interaction, user: Member, alias: User):
        await self.db.add_user_alias(guild_id=interaction.guild.id, user_id=user.id, alias_id=alias.id)
        await interaction.response.send_message(f"Added alias {alias} for {user.mention}", ephemeral=True)

    @commands.Cog.listener()
    async def cog_check(self, ctx):
        return await is_admin(ctx)


async def setup(client):
    await client.add_cog(Admin(client))
