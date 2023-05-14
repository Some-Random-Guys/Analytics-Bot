import time

from discord.ext import commands
from backend import log, db_creds, is_admin
from srg_analytics import DB
from srg_analytics.schemas import DataTemplate
from discord import app_commands, TextChannel, Member, User
from backend import embed_template, error_template, remove_ignore_autocomplete


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
        # go through all channels and add them to the db
        cmd_channel = interaction.channel
        guild = interaction.guild

        channel_ignores = await self.db.get_ignore_list("channel", interaction.guild.id)
        user_ignores = await self.db.get_ignore_list("user", interaction.guild.id)
        aliased_users = await self.db.get_user_aliases(guild_id=interaction.guild.id)
        aliases = set([alias for alias_list in aliased_users.values() for alias in alias_list])

        print(channel_ignores)
        print(user_ignores)
        print(aliased_users)

        total_msgs = 0

        for channel in interaction.guild.text_channels:
            start_time = time.time()
            num_msgs = 0
            if channel.id in channel_ignores:
                continue

            # for every message in the channel
            async for message in channel.history(limit=None):
                if message.author.id in user_ignores:
                    continue

                mentions = [str(mention.id) for mention in message.mentions]
                author = message.author.id

                # if the author is an alias, set author to the alias' id
                if author in aliases:
                    for alias, alias_list in aliased_users.items():
                        if author in alias_list:
                            author = alias
                            break

                num_msgs += 1

                msg = DataTemplate(
                    author_id=author,
                    is_bot=message.author.bot,
                    has_embed=len(message.embeds) > 0,
                    channel_id=message.channel.id,
                    epoch=message.created_at.timestamp(),
                    num_attachments=len(message.attachments),
                    mentions=",".join(mentions) if mentions else None,
                    ctx_id=int(message.reference.message_id) if message.reference is not None and
                                                                type(message.reference.message_id) == int else None,
                    message_content=message.content,
                    message_id=message.id
                )

                await self.db.add_message(guild_id=guild.id, data=msg)

            total_msgs += num_msgs

            embed = embed_template()
            embed.title = f"Harvested Channel | " \
                          f"{interaction.guild.text_channels.index(channel) + 1}/{len(interaction.guild.text_channels)}"
            embed.description = f"Successfully harvested the messages in {channel.mention}"
            embed.add_field(name="Channel", value=f"{channel.mention}", inline=False)
            embed.add_field(name="Time Taken", value=f"`{round(time.time() - start_time, 4)}s`",
                            inline=False)  # todo time formatting
            embed.add_field(name="Total Harvested (Channel)", value=f"`{num_msgs}`", inline=False)
            embed.add_field(name="Total Harvested (Server)", value=f"`{total_msgs}`", inline=False)

            try:
                await cmd_channel.send(embed=embed)
            except Exception as e:
                log.error(str(e))

        embed = embed_template()
        embed.title = "Harvest Complete"
        embed.description = f"Successfully harvested all channels in {interaction.guild.name}"

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
    async def add_user_alias(self, interaction, user: Member, alias: Member):
        await self.db.add_user_alias(guild_id=interaction.guild.id, user_id=user.id, alias_id=alias.id)
        await interaction.response.send_message(f"Added alias {alias} for {user.mention}", ephemeral=True)


async def setup(client):
    await client.add_cog(Admin(client))