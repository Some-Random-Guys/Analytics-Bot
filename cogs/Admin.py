import asyncio
import time
import discord
from discord.ext import commands
from backend import log, db_creds, is_admin, ConfirmButton
from srg_analytics import DB
from discord import app_commands, TextChannel, Member, User
from backend import embed_template, error_template  # , remove_ignore_autocomplete
import warnings
import threading

warnings.filterwarnings('ignore', module=r"aiomysql")


class Admin(commands.GroupCog, name="admin"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Admin.py Loaded")


    @app_commands.command()
    @commands.guild_only()
    async def harvest(self, interaction, channel: discord.TextChannel = None):
        cmd_channel = interaction.channel
        db = DB(db_creds)
        await db.connect()

        channel_ignores = tuple(await db.get_ignore_list("channel", interaction.guild.id))
        user_ignores = tuple(await db.get_ignore_list("user", interaction.guild.id))
        aliased_users = await db.get_user_aliases(guild_id=interaction.guild.id)
        aliases = tuple(set([alias for alias_list in aliased_users.values() for alias in alias_list]))

        total_msgs = 0
        harvest_start_time = time.time()
        harvest_stats = [0.0]

        query = f"""
                INSERT IGNORE INTO `{interaction.guild_id}` (message_id, channel_id, author_id, aliased_author_id, message_content, epoch, 
                edit_epoch, is_bot, has_embed, num_attachments, ctx_id, user_mentions, channel_mentions, role_mentions, reactions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """

        async def process_channel(channel):
            await asyncio.sleep(1)

            start = time.time()
            nonlocal total_msgs, harvest_start_time
            channel_msgs = 0

            messages = []
            tasks = []

            async for message in channel.history(limit=None):
                if message.author.id in user_ignores:
                    continue
                if message.channel.id in channel_ignores:
                    continue

                messages.append(message)

                if len(messages) == 10000:
                    channel_msgs += len(messages)
                    tasks.append(process_messages(messages))

                    messages = []

            if messages:
                channel_msgs += len(messages)
                tasks.append(process_messages(messages))
            await asyncio.gather(*tasks)

            del messages

            embed = embed_template()
            embed.title = f"Harvested {channel.name} | {len(tasks)} tasks"
            embed.description = f"Harvested messages in {channel.name} in {time.time() - start} seconds"
            embed.add_field(name="Total Messages", value=total_msgs)
            embed.add_field(name="Channel Messages", value=channel_msgs)
            await cmd_channel.send(embed=embed)

            print(f"Took {time.time() - start} seconds to process {channel.name}")

        async def get_reaction(message):

            reactions = {}
            if not message.reactions:
                return None
            for reaction in message.reactions:
                key = reaction.emoji.id if reaction.is_custom_emoji() else reaction.emoji
                reactions[key] = reaction.count

            return reactions

        async def process_messages(messages):
            nonlocal harvest_stats, total_msgs

            start = time.time()
            msg_data = []


            for message in messages:
                total_msgs += 1
                author = message.author.id

                if author in aliases:
                    for alias, alias_list in aliased_users.items():
                        if author in alias_list:
                            author = alias
                            break

                reactions = await get_reaction(message)

                msg = (
                    int(message.id),
                    int(message.channel.id),
                    int(message.author.id),
                    int(author),
                    str(message.content),
                    int(message.created_at.timestamp()),
                    int(message.edited_at.timestamp()) if message.edited_at is not None else None,
                    int(message.author.bot),
                    bool(message.embeds != []),
                    len(message.attachments),
                    int(message.reference.message_id) if message.reference is not None and isinstance(
                        message.reference.message_id, int) else None,
                    None if message.raw_mentions == [] else str(message.raw_mentions),
                    None if message.raw_channel_mentions == [] else str(message.raw_channel_mentions),
                    None if message.raw_role_mentions == [] else str(message.raw_role_mentions),
                    None if str(reactions) == {} else str(reactions)
                )

                msg_data.append(msg)

                if total_msgs % 10000 == 0:
                    harvest_stats.append(time.time() - harvest_start_time)
                    print(harvest_stats)

            del messages

            try:
                async with db.con.acquire() as conn:
                    async with conn.cursor() as cur:
                        # print(msg_data[-1])
                        await cur.executemany(query, msg_data)

                        # No need to commit since we are using autocommit

            except Exception as e:
                raise e

            del msg_data

        if channel:
            await process_channel(channel)
        else:
            tasks = []
            for channel in interaction.guild.text_channels:
                # check if the bot has permissions to read messages in the channel
                if not channel.permissions_for(interaction.guild.me).read_messages:
                    embed = error_template(f"Missing permissions to read messages in {channel.mention}")
                    await cmd_channel.send(embed=embed)


                tasks.append(process_channel(channel))

            await asyncio.gather(*tasks)

        embed = embed_template()
        embed.title = "Harvest Complete"
        embed.description = f"Harvested {total_msgs} messages in {time.time() - harvest_start_time} seconds"
        await cmd_channel.send(embed=embed)

        import matplotlib.pyplot as plt
        import mplcyberpunk

        plt.style.use("cyberpunk")

        # create a plot with harvest stats
        # harvest_stats has y axis values
        # x axis is the index of the value * 10000 in the list

        plt.plot([i * 10000 for i in range(len(harvest_stats))], harvest_stats)

        plt.xlabel("Messages")
        plt.ylabel("Time (s)")

        plt.savefig("harvest.png")

        plt.close()

        await cmd_channel.send(file=discord.File("harvest.png"))


    @app_commands.command()
    @commands.guild_only()
    async def clear_data(self, interaction):
        db = DB(db_creds)
        await db.connect()

        button = ConfirmButton(author=interaction.user)

        embed = embed_template()
        embed.title = "Clear Data"
        embed.description = "Are you sure you want to clear all data for this server?"

        await interaction.response.send_message(embed=embed, view=button)

        await button.wait()

        if button.value is True:
            await db.remove_guild(interaction.guild.id)

        else:
            await interaction.response.send_message("Cancelled", ephemeral=True)

        embed = embed_template()
        embed.title = "Clear Data"
        embed.description = "Successfully cleared all data"
        await interaction.response.send_message("Cleared all data")

    @app_commands.command()
    @commands.guild_only()
    async def add_ignore(self, interaction, channel: TextChannel = None, user: Member = None, update_existing: bool = False):

        db = DB(db_creds)
        await db.connect()

        if user is None:
            if channel is None:
                channel = interaction.channel

        if user is not None:
            await db.add_ignore(guild_id=interaction.guild.id, user_id=user.id, update_existing=update_existing)
            await interaction.response.send_message(f"Ignoring {user.mention}", ephemeral=True)
        elif channel is not None:
            await db.add_ignore(guild_id=interaction.guild.id, channel_id=channel.id, update_existing=update_existing)
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
    async def add_user_alias(self, interaction, user: Member, alias: User, update_existing: bool = True):
        db = DB(db_creds)
        await db.connect()

        await db.add_user_alias(guild_id=interaction.guild.id, user_id=user.id, alias_id=alias.id, update_existing=update_existing)
        await interaction.response.send_message(f"Added alias {alias} for {user.mention}", ephemeral=update_existing)

    @app_commands.command()
    async def show_aliases(self, interaction, user: Member = None):
        if user is None:
            user = interaction.user

        db = DB(db_creds)
        await db.connect()

        aliases = await db.get_user_aliases(guild_id=interaction.guild.id, user_id=user.id)

        embed = embed_template()
        embed.title = f"Aliases for {user}"
        embed.description = f"Aliases: {', '.join([f'{alias.mention}' for alias in aliases])}"

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def check(self, ctx):
        return await is_admin(ctx)


async def setup(client):
    await client.add_cog(Admin(client))
