import configparser
import sys
import discord
import logging
from discord.ext import commands
from colorlog import ColoredFormatter
import aiohttp

intents = discord.Intents.default()


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

    # Getting the variables from `[secret]`
    discord_token: str = config.get('secret', 'discord_token')

    # Getting the variables from `[discord]`
    embed_footer: str = config.get('discord', 'embed_footer')
    embed_color: int = int(config.get('discord', 'embed_color'), base=16)
    embed_url: str = config.get('discord', 'embed_url')

    base_api_url: str = config.get('api', 'base_api_url')
    view_key: str = config.get("api", "view_key")
    edit_key: str = config.get("api", "edit_key")
    admin_key: str = config.get("api", "admin_key")


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


class DataTemplate:
    author_id: list[str or int]
    is_bot: list[bool]
    has_embed: list[bool]
    channel_id: list[str or int]
    timestamp: list[str]
    num_attachments: list[str or int]
    mentions: list[list[str or int]]
    context: list[str]
    message_content: list[str or None]
    message_id: list[str or int]


#
#   API Functions
#

async def request(endpoint: str, api_key: str, method: str = "GET", **kwargs) -> dict:
    url = base_api_url + endpoint
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.request(method, url, **kwargs) as resp:
            if resp.status != 200:
                raise Exception(resp.status)

            return await resp.json()


async def get_all_guilds() -> dict:
    guilds = await request("/db/guilds", view_key)
    return guilds


async def clear_db() -> bool:
    await request("/db/guilds", admin_key, method="DELETE")
    return True


async def add_guild(guild_id: int) -> dict:
    res = await request(f"/db/guilds", edit_key, method="POST", params={"guild_id": guild_id})
    return res


async def remove_guild(guild_id: int) -> dict:
    res = await request(f"/db/guilds/{guild_id}", edit_key, method="DELETE")
    return res


async def get_guild(guild_id: int) -> dict:
    res = await request(f"/db/guilds/{guild_id}", view_key)
    return res


async def add_data(guild_id: int, data: DataTemplate) -> dict:
    res = await request(f"/db/guilds/{guild_id}", edit_key, method="PATCH", json=data)
    return res

