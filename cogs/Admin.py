import asyncio
import time
import discord
from discord.ext import commands
from backend import log, db_creds, is_admin, ConfirmButton
from srg_analytics import DB
from discord import app_commands, TextChannel, Member, User
from backend import embed_template, error_template  # , remove_ignore_autocomplete
import warnings
import multiprocessing

warnings.filterwarnings('ignore', module=r"aiomysql")


query = f"""
                INSERT IGNORE INTO `{interaction.guild_id}` (message_id, channel_id, author_id, aliased_author_id, message_content, epoch, 
                edit_epoch, is_bot, has_embed, num_attachments, ctx_id, user_mentions, channel_mentions, role_mentions, reactions)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """


class Admin(commands.GroupCog, name="admin"):
    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Cog: Admin.py Loaded")

    async def process_messages(self, raw_messages, db):

        cache = {123: None, }


        msgs = []

        msg_count = 0
        for message in raw_messages:
            msg_count += 1

            author = message.author.id
            
            if author not in cache:
                if author in aliases:
                    for alias, alias_list in aliased_users.items():
                        if author in alias_list:
                            cache[alias] = author
                                                        
                            author = alias
                            break
                else:
                    cache[author] = None

            author = cache[author] or author

            reactions = "stuff"

            msgs.append((
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
                ))
            
            try:
                async with db.con.acquire() as conn:
                    async with conn.cursor() as cur:
                        # print(msg_data[-1])
                        await cur.executemany(query, msgs)
        

            except Exception as e:
                raise e
            

            

        return msg_count


    async def process_channel(self, channel, db):
        
        messages, tasks = [], []

        count = 0
        async for message in channel.history(limit=None):
            # todo: add skip ignore
            messages.append(message)

            count += 1
            if count == 5000:
                tasks.append(messages)
                count = 0
                messages.clear()

        with multiprocessing.Pool() as pool:
            data = pool.map(self.process_messages, [(t, db) for t in tasks])w

        total_count = sum(data)
            
                



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

        async for channel in interaction.guild.text_channels:
            if channel.id not in channel_ignores:
                self.process_channel(channel, db)
        
                # `todo forum channel and text in voice channel
            


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

        aliases = await db.get_user_aliases(guild_id=interaction.guild.id)

        print(aliases)

        # filter aliases to only those for the user
        aliases = [alias for alias in aliases if alias.user_id == user.id]


        embed = embed_template()
        embed.title = f"Aliases for {user}"
        embed.description = f"Aliases: {', '.join([f'{alias.mention}' for alias in aliases])}"

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command()
    async def set_timezone(self, interaction):
        embed = embed_template()

        db = DB(db_creds)
        await db.connect()


        timezones = ["UTC-11", "UTC-10", "UTC-09", "UTC-08", "UTC-07", "UTC-06", "UTC-05", "UTC-04", "UTC-03", "UTC-02", "UTC-01", "UTC±00", "UTC+01", "UTC+02",
                        "UTC+03", "UTC+04", "UTC+05", "UTC+06", "UTC+07", "UTC+08", "UTC+09", "UTC+10", "UTC+11", "UTC+12", "UTC+13"]

        values = ["-11", "-10", "-09", "-08", "-07", "-06", "-05", "-04", "-03", "-02", "-01", "00", "+01", "+02",
                        "+03", "+04", "+05", "+06", "+07", "+08", "+09", "+10", "+11", "+12", "+13"]

        options = []
        for timezone in timezones:
            options.append(discord.SelectOption(label=timezone, value=values[timezones.index(timezone)]))

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
                options=options
            )
            async def select_callback(self, interaction, select):
                print(select.values)
                self.value = select.values[0]
                print(self.value)

                await self.db.set_timezone(guild_id=interaction.guild.id, timezone=int(self.value))

                embed = embed_template()
                embed.title = "Timezone Set!"
                embed.description = f"Timezone set to {timezones[values.index(self.value)]}"


                await self.interaction_.edit_original_response(embed=embed, view=None)


            async def on_timeout(self):
                # await interaction.response.send_message("Timed out...", ephemeral=True)
                # grey out the options
                self.children[0].disabled = True

        # send a response, get the message object, edit it with the view
        msg = await interaction.response.send_message("Choose a Timezone!", view=MyView(db, interaction))
        print(msg)





    @commands.Cog.listener()
    async def check(self, ctx):
        return await is_admin(ctx)


async def setup(client):
    await client.add_cog(Admin(client))
