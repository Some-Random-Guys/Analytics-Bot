import asyncio
import configparser
import sys
import threading

import discord
import logging
from discord.ext import commands
from colorlog import ColoredFormatter
from srg_analytics import DbCreds, DB

intents = discord.Intents()
intents.message_content = True
intents.guilds = True
intents.members = True



# Initializing the logger
def colorlogger(name: str = 'my-discord-bot') -> logging.log:
    logger = logging.getLogger(name)
    stream = logging.StreamHandler()

    stream.setFormatter(ColoredFormatter("%(reset)s%(log_color)s%(levelname)-8s%(reset)s | %(log_color)s%(message)s"))
    logger.addHandler(stream)
    return logger  # Return the logger


log = colorlogger()

# Loading config.ini
config = configparser.ConfigParser()

try:
    config.read('./data/config.ini')
except Exception as e:
    log.critical("Error reading the config.ini file. Error: " + str(e))
    sys.exit()

# Getting variables from config.ini
try:
    # Getting the variables from `[general]`
    log_level: str = config.get('general', 'log_level')
    presence: str = config.get('general', 'presence')
    owner_ids = config.get('general', 'owner_ids').split(',')
    owner_ids = [int(i) for i in owner_ids]
    owner_guilds = config.get('general', 'owner_guilds').split(',')
    owner_guilds = [int(i) for i in owner_guilds]

    # Getting the variables from `[secret]`
    discord_token: str = config.get('secret', 'discord_token')
    db_host: str = config.get('secret', 'db_host')
    db_port: int = config.getint('secret', 'db_port')
    db_user: str = config.get('secret', 'db_user')
    db_password: str = config.get('secret', 'db_password')
    db_name: str = config.get('secret', 'db_name')

    # Getting the variables from `[discord]`
    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_url: str = config.get('discord', 'embed_url')


except Exception as err:
    log.critical("Error getting variables from the config file. Error: " + str(err))
    sys.exit()

# Set the logger's log level to the one in the config file
if log_level.upper().strip() in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    log.setLevel(log_level.upper().strip())
else:
    log.setLevel("INFO")
    log.warning(f"Invalid log level `{log_level.upper().strip()}`. Defaulting to INFO.")

# Initializing the client
client = commands.Bot(intents=intents, command_prefix="!")  # Setting prefix

_embed_template = discord.Embed(
    title="Error!",
    color=embed_color,
    url=embed_url
)
_embed_template.set_footer(text=embed_footer)

embed_template = lambda: _embed_template.copy()


def error_template(description: str) -> discord.Embed:
    _error_template = discord.Embed(
        title="Error!",
        description=description,
        color=0xff0000,
        url=embed_url
    )
    _error_template.set_footer(text=embed_footer)

    return _error_template.copy()


db_creds: DbCreds = DbCreds(db_host, db_port, db_user, db_password, db_name)

async def is_admin(interaction) -> bool:
    if interaction.guild is None:
        return False

    if interaction.user.id in owner_ids:
        return True

    if interaction.guild.owner_id == interaction.user.id:
        return True

    if interaction.user.guild_permissions.administrator:
        return True

    return False


# Confirm Button Discord View
class ConfirmButton(discord.ui.View):  # Confirm Button Class
    def __init__(self, author):
        super().__init__()
        self.value = None
        self.author = author

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def confirm_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.id == self.author.id:
            await interaction.response.send_message("This button is not for you", ephemeral=True)
            return

        self.value = True

        for child in self.children:  # Disable all buttons
            child.disabled = True

        await interaction.response.send_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.id == self.author.id:
            return await interaction.response.send_message("This button is not for you", ephemeral=True)

        self.value = False

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_original_message(view=self)
        self.stop()