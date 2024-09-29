import time
from collections import Counter
from typing import Tuple, Any

from srg_analytics.DB import DB
from srg_analytics.schemas import Profile




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


async def get_notnull_message_count(db: DB, guild_id: int, user_id: int):
    return (
        await db.execute(
            f"SELECT count(*) FROM `{guild_id}` WHERE author_id = ? AND message_length IS NOT NULL AND message_length != ''",
            (str(user_id),), fetch="one"
        )
    )[0]


async def build_profile(db: DB, guild_id: int, user_id: int) -> dict:
    """Builds the profile for a certain user, in a certain guild."""
    start_time = time.time()

    return_dict = {
        'user_id': user_id, 'guild_id': guild_id,
        'messages': await db.get_message_count(guild_id=guild_id, user_id=user_id) or 0,
        'characters': await db.get_character_count(guild_id=guild_id, user_id=user_id) or 0,
        'total_embeds': await get_total_embeds(db, guild_id, user_id) or 0,
        'total_attachments': await get_total_attachments(db, guild_id, user_id) or 0
    }

    return_dict['average_message_length'] = return_dict['characters'] / (await get_notnull_message_count(db, guild_id, user_id) or 1)
    return_dict['time_taken'] = time.time() - start_time

    print(return_dict)

    return return_dict
