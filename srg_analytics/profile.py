import time
from collections import Counter
from typing import Tuple, Any

from srg_analytics.DB import DB
from srg_analytics.schemas import Profile


async def total_message_count(db: DB, guild_id: int, user_id: int) -> int:
    """Returns the total number of messages in a guild."""
    return await db.get_message_count(guild_id=guild_id, user_id=user_id)





async def get_character_count(db_or_msgs: DB | list[str], guild_id: int, user_id: int) -> int:
    """Returns the number of characters in a guild."""
    if isinstance(db_or_msgs, DB):
        message_content: list[str] = await db_or_msgs.get_message_content(guild_id, user_id or None)
    else:
        message_content = db_or_msgs

    # get the number of characters in each message
    all_messages = "".join(message_content)

    return len(all_messages)


async def get_total_attachments(db: DB, guild_id: int, user_id: int) -> int:
    """Returns the total number of attachments in a guild."""
    return (
        await db.execute(
            # select sum of all values in sum_attachments column
            f"SELECT SUM(num_attachments) FROM `{guild_id}` WHERE author_id = ?",
            (str(user_id),), fetch="one"
        )
    )[0]


async def get_total_embeds(db: DB, guild_id: int, user_id: int) -> int:
    return (
        await db.execute(
            f"SELECT COUNT(has_embed) FROM `{guild_id}` WHERE author_id = ?",
            (str(user_id),), fetch="one"
        )
    )[0]


async def is_bot(db: DB, guild_id: int, user_id: int) -> bool:
    """Returns whether a user is a bot or not."""
    return (
        await db.execute(
            f"SELECT is_bot FROM `{guild_id}` WHERE author_id = ? LIMIT 1", 
            (str(user_id),), fetch="one"
        )
    )[0]

async def get_notnull_message_count(db: DB, guild_id: int, user_id: int):
    return (
        await db.execute(
            f"SELECT count(*) FROM `{guild_id}` WHERE author_id = ? AND message_content IS NOT NULL AND message_content != ''",
            (str(user_id),), fetch="one"
        )
    )[0]
    

async def build_profile(db: DB, guild_id: int, user_id: int) -> Profile:
    """Builds the profile for a certain user, in a certain guild."""
    start_time = time.time()

    profile = Profile()

    profile.user_id = user_id
    profile.guild_id = guild_id
    profile.is_bot = await is_bot(db, guild_id, user_id)


    profile.messages = await total_message_count(db, guild_id, user_id)
    profile.characters = await get_character_count(msg_list, guild_id, user_id)
    profile.average_msg_length = profile.characters / await get_notnull_message_count(db, guild_id, user_id)

    profile.total_embeds = await get_total_embeds(db, guild_id, user_id)

    profile.total_attachments = int(await get_total_attachments(db, guild_id, user_id))

    # most_mentioned_ = await most_mentioned(db, guild_id, user_id)
    # profile.total_mentions = len(most_mentioned_)

    # profile.most_mentioned = most_mentioned_[0]
    # profile.no_of_times_most_mentioned = most_mentioned_[1]

    # most_mentioned_by_ = await most_mentioned_by(db, guild_id, user_id)
    # profile.most_mentioned_by = most_mentioned_by_[0]
    # profile.no_of_times_most_mentioned_by = most_mentioned_by_[1]

    profile.time_taken = time.time() - start_time

    return profile
