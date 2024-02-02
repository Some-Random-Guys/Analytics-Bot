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

warnings.filterwarnings("ignore", module=r"aiomysql")


class Admin(commands.GroupCog, name="admin"):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Admin.py Loaded")

    @app_commands.command()
    @commands.guild_only()
    async def harvest(
        self,
        interaction,
        channel: discord.TextChannel | discord.ForumChannel = None,
        amount: int = None,
    ):
        cmd_channel = interaction.channel
        db = DB(db_creds)
        await db.connect()

        channel_ignores = tuple(
            await db.get_ignore_list("channel", interaction.guild.id)
        )
        user_ignores = tuple(await db.get_ignore_list("user", interaction.guild.id))
        aliased_users = await db.get_user_aliases(guild_id=interaction.guild.id)
        aliases = tuple(
            set(
                [alias for alias_list in aliased_users.values() for alias in alias_list]
            )
        )
        harvested_channel_ids = {i[0] for i in await db.get(interaction.guild.id, selected=['message_id'])}

        total_msgs = 0
        harvest_start_time = time.time()
        harvest_stats = [0.0]

        query = f"""
                INSERT IGNORE INTO `{interaction.guild_id}` (message_id, channel_id, author_id, aliased_author_id, message_content, epoch, 
                edit_epoch, is_bot, has_embed, num_attachments, ctx_id, user_mentions, channel_mentions, role_mentions, reactions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """

        def message_exists(message_id):
            old_length = len(harvested_channel_ids)
            harvested_channel_ids.add(message_id)
            return old_length == len(harvested_channel_ids)
            
        async def process_channel(channel, amount: int = 9999999):
            await asyncio.sleep(1)

            start = time.time()
            nonlocal total_msgs, harvest_start_time
            channel_msgs = 0

            messages = []
            tasks = []

            async for message in channel.history(limit=amount, oldest_first=False):
                if message.author.id in user_ignores:
                    continue
                if message.channel.id in channel_ignores:
                    continue
                if message_exists(message.id):
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
            embed.description = (
                f"Harvested messages in {channel.name} in {time.time() - start} seconds"
            )
            embed.add_field(name="Total Messages", value=total_msgs)
            embed.add_field(name="Channel Messages", value=channel_msgs)
            await cmd_channel.send(embed=embed)

            print(f"Took {time.time() - start} seconds to process {channel.name}")

        async def process_messages(messages):
            nonlocal harvest_stats, total_msgs

            msg_data = []

            for message in messages:
                total_msgs += 1
                author = message.author.id

                if author in aliases:
                    for alias, alias_list in aliased_users.items():
                        if author in alias_list:
                            author = alias
                            break

                # Get reactions and their counts
                # reactions = {}
                # if message.reactions:
                #     for reaction in message.reactions:
                #         key = reaction.emoji.id if reaction.is_custom_emoji() else reaction.emoji
                #         reactions[key] = reaction.count

                msg = (
                    int(message.id),
                    int(message.channel.id),
                    int(message.author.id),
                    int(author),
                    str(message.content) if message.content != "" else None,
                    int(message.created_at.timestamp()),
                    int(message.edited_at.timestamp())
                    if message.edited_at is not None
                    else None,
                    int(message.author.bot),
                    bool(message.embeds != []),
                    len(message.attachments),
                    int(message.reference.message_id)
                    if message.reference is not None
                    and isinstance(message.reference.message_id, int)
                    else None,
                    None if message.raw_mentions == [] else str(message.raw_mentions),
                    None
                    if message.raw_channel_mentions == []
                    else str(message.raw_channel_mentions),
                    None
                    if message.raw_role_mentions == []
                    else str(message.raw_role_mentions),
                    None,  # if str(reactions) == '{}' else str(reactions)
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
            if type(channel) == discord.TextChannel:
                await process_channel(channel, amount)
            elif type(channel) == discord.ForumChannel:
                for thread in channel.threads:
                    await process_channel(thread)
                tasks = []
                async for thread in channel.archived_threads():
                    if not thread.permissions_for(interaction.guild.me).read_messages:
                        embed = error_template(
                            f"Missing permissions to read messages in {thread.mention}"
                        )
                        await cmd_channel.send(embed=embed)

                    tasks.append(process_channel(thread))
                await asyncio.gather(*tasks)
        else:
            tasks = []
            # for each text channel
            for channel in interaction.guild.text_channels:
                # check if the bot has permissions to read messages in the channel
                if not channel.permissions_for(interaction.guild.me).read_messages:
                    embed = error_template(
                        f"Missing permissions to read messages in {channel.mention}"
                    )
                    await cmd_channel.send(embed=embed)

                for thread in channel.threads:
                    if not thread.permissions_for(interaction.guild.me).read_messages:
                        embed = error_template(
                            f"Missing permissions to read messages in {thread.mention}"
                        )
                        await cmd_channel.send(embed=embed)

                    tasks.append(process_channel(thread))
                async for thread in channel.archived_threads(private=False):
                    if not thread.permissions_for(interaction.guild.me).read_messages:
                        embed = error_template(
                            f"Missing permissions to read messages in {thread.mention}"
                        )
                        await cmd_channel.send(embed=embed)

                    tasks.append(process_channel(thread))
                async for thread in channel.archived_threads(private=True):
                    if not thread.permissions_for(interaction.guild.me).read_messages:
                        embed = error_template(
                            f"Missing permissions to read messages in {thread.mention}"
                        )
                        await cmd_channel.send(embed=embed)

                    tasks.append(process_channel(thread))
                tasks.append(process_channel(channel))

            for channel in interaction.guild.forums:
                for forum in channel.threads:
                    if not forum.permissions_for(interaction.guild.me).read_messages:
                        embed = error_template(
                            f"Missing permissions to read messages in {forum.mention}"
                        )
                        await cmd_channel.send(embed=embed)

                    tasks.append(process_channel(forum))
                async for thread in channel.archived_threads():
                    if not thread.permissions_for(interaction.guild.me).read_messages:
                        embed = error_template(
                            f"Missing permissions to read messages in {thread.mention}"
                        )
                        await cmd_channel.send(embed=embed)

                    tasks.append(process_channel(thread))
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
    async def add_ignore(
        self,
        interaction,
        channel: TextChannel = None,
        user: Member = None,
        update_existing: bool = False,
    ):
        db = DB(db_creds)
        await db.connect()

        if user is None:
            if channel is None:
                channel = interaction.channel

        if user is not None:
            await db.add_ignore(
                guild_id=interaction.guild.id,
                user_id=user.id,
                update_existing=update_existing,
            )
            await interaction.response.send_message(
                f"Ignoring {user.mention}", ephemeral=True
            )
        elif channel is not None:
            await db.add_ignore(
                guild_id=interaction.guild.id,
                channel_id=channel.id,
                update_existing=update_existing,
            )
            await interaction.response.send_message(
                f"Ignoring {channel.mention}", ephemeral=True
            )

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
    async def add_user_alias(
        self, interaction, user: Member, alias: User, update_existing: bool = True
    ):
        db = DB(db_creds)
        await db.connect()

        await db.add_user_alias(
            guild_id=interaction.guild.id,
            user_id=user.id,
            alias_id=alias.id,
            update_existing=update_existing,
        )
        await interaction.response.send_message(
            f"Added alias {alias} for {user.mention}", ephemeral=update_existing
        )

    @app_commands.command()
    async def show_aliases(self, interaction, user: Member = None):
        if user is None:
            user = interaction.user

        db = DB(db_creds)
        await db.connect()

        aliases = await db.get_user_aliases(guild_id=interaction.guild.id)

        print(aliases)

        # filter aliases to only those for the user
        aliases = [alias for alias in aliases if alias.user_id == user.id]

        embed = embed_template()
        embed.title = f"Aliases for {user}"
        embed.description = (
            f"Aliases: {', '.join([f'{alias.mention}' for alias in aliases])}"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def set_timezone(self, interaction):
        embed = embed_template()

        db = DB(db_creds)
        await db.connect()

        timezones = [
            "UTC-11",
            "UTC-10",
            "UTC-09",
            "UTC-08",
            "UTC-07",
            "UTC-06",
            "UTC-05",
            "UTC-04",
            "UTC-03",
            "UTC-02",
            "UTC-01",
            "UTC±00",
            "UTC+01",
            "UTC+02",
            "UTC+03",
            "UTC+04",
            "UTC+05",
            "UTC+06",
            "UTC+07",
            "UTC+08",
            "UTC+09",
            "UTC+10",
            "UTC+11",
            "UTC+12",
            "UTC+13",
        ]

        values = [
            "-11",
            "-10",
            "-09",
            "-08",
            "-07",
            "-06",
            "-05",
            "-04",
            "-03",
            "-02",
            "-01",
            "00",
            "+01",
            "+02",
            "+03",
            "+04",
            "+05",
            "+06",
            "+07",
            "+08",
            "+09",
            "+10",
            "+11",
            "+12",
            "+13",
        ]

        options = []
        for timezone in timezones:
            options.append(
                discord.SelectOption(
                    label=timezone, value=values[timezones.index(timezone)]
                )
            )

        # create a dropdown with the timezones
        class MyView(discord.ui.View):
            def __init__(self, db, interaction_):
                super().__init__(timeout=60)
                self.value = None
                self.db = db
                self.interaction_ = interaction_
                print(self.interaction_)

            @discord.ui.select(  # the decorator that lets you specify the properties of the select menu
                placeholder="Choose a Timezone!",
                min_values=1,
                max_values=1,
                options=options,
            )
            async def select_callback(self, interaction, select):
                print(select.values)
                self.value = select.values[0]
                print(self.value)

                await self.db.set_timezone(
                    guild_id=interaction.guild.id, timezone=int(self.value)
                )

                embed = embed_template()
                embed.title = "Timezone Set!"
                embed.description = (
                    f"Timezone set to {timezones[values.index(self.value)]}"
                )

                await self.interaction_.edit_original_response(embed=embed, view=None)

            async def on_timeout(self):
                # await interaction.response.send_message("Timed out...", ephemeral=True)
                # grey out the options
                self.children[0].disabled = True

        # send a response, get the message object, edit it with the view
        msg = await interaction.response.send_message(
            "Choose a Timezone!", view=MyView(db, interaction)
        )
        print(msg)

    @commands.Cog.listener()
    async def check(self, ctx):
        return await is_admin(ctx)


async def setup(client):
    await client.add_cog(Admin(client))
