import datetime
import random

import matplotlib.pyplot as plt
import mplcyberpunk
from collections import Counter

from srg_analytics.DB import DB


async def get_top_users(db: DB, guild_id: int, type_: str, amount: int = 10, timeperiod: str = None,
                        count_others: bool = True):
    # type_ can be either "messages" or "words" or "characters"
    # time_duration can be either "day" or "week" or "month" or "year" or None

    if timeperiod not in ["day", "week", "month", "year", None]:
        raise ValueError("time_duration must be either 'day' or 'week' or 'month' or 'year' or None")
    else:
        timezone = await db.get_timezone(guild_id=guild_id)
        if not timezone:
            timezone = datetime.timezone(datetime.timedelta(hours=3))
        else:
            timezone = datetime.timezone(datetime.timedelta(hours=int(timezone)))

    # get the earliest epoch start time for the time duration with timezone utc+3
    if timeperiod == "day":
        # get epoch of starting of the current day (consider timezone)
        epoch_start = datetime.datetime.now(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    elif timeperiod == "week":
        # get epoch of starting of the current week (consider timezone)
        epoch_start = datetime.datetime.now(timezone) - datetime.timedelta(days=7)
    elif timeperiod == "month":
        # get epoch of starting of the current month (consider timezone)
        epoch_start = datetime.datetime.now(timezone).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif timeperiod == "year":
        # get epoch of starting of the current year (consider timezone)
        epoch_start = datetime.datetime.now(timezone).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        epoch_start = None

    if type_ == "messages":
        query = f"""
                SELECT aliased_author_id, COUNT(aliased_author_id) AS count
                FROM `{guild_id}`
                WHERE is_bot = 0
            """
        if epoch_start is not None:
            query += f"AND epoch >= {epoch_start.timestamp()}"

        query += """
                GROUP BY aliased_author_id
                ORDER BY count DESC
                """

        if not count_others:
            query += f"LIMIT {amount}"

        top = await db.execute(query, fetch="all")

        if count_others:
            return [*top[:amount], ('others', sum([i[1] for i in top[amount:]]))]
        else:
            return top[:amount]


    elif type_ == "characters":
        query = f"""
                SELECT aliased_author_id, SUM(CHAR_LENGTH(message_content)) AS count
                FROM `{guild_id}`
                WHERE is_bot = 0
            """

        if timeperiod is not None:
            query += f"AND epoch >= {epoch_start.timestamp()}"

        query += """
                GROUP BY aliased_author_id
                ORDER BY count DESC
                """

        top = await db.execute(query, fetch="all")

        return top[:amount]


async def get_top_users_visual(db: DB, guild_id: int, client, type_: str, timeperiod: str, amount: int = 10) -> str:
    res = await get_top_users(db=db, guild_id=guild_id, type_=type_, timeperiod=timeperiod, amount=amount)
    plt.style.use("cyberpunk")

    # get member object from id and get their nickname, if not found, use "Deleted User"
    labels = []
    guild = await client.fetch_guild(guild_id)

    for i in res:
        if i == res[-1]:
            labels.append(f"Others | {i[1]}")
            continue
        try:
            # get member
            member = await guild.fetch_member(i[0])
            # get nickname
            labels.append(f"{member.nick or member.display_name} | {i[1]}")

        except Exception:
            labels.append(f"Unknown ({i[0]}) | {i[1]}")

    pie, texts, autotexts = plt.pie([value for _, value in res], labels=labels, autopct="%1.1f%%")

    for text in autotexts:
        text.set_color('black')

    for text in texts:
        text.set_color('white')

    if timeperiod is None:
        timeperiod = "All Time"
    elif timeperiod == "day":
        timeperiod = "today"
    elif timeperiod == "week":
        timeperiod = "this Week"
    elif timeperiod == "month":
        timeperiod = "this Month"
    elif timeperiod == "year":
        timeperiod = "this Year"

    plt.title(f"Top {amount} Members by {type_.capitalize()} {timeperiod}")

    mplcyberpunk.add_glow_effects()

    # save image
    name = f"{random.randint(1, 100000000)}.png"
    try:
        plt.savefig(name, format='png', dpi=600)
    except Exception as e:
        print(e)

    plt.close()

    return name


async def get_top_channels(db: DB, guild_id: int, type_: str, amount: int = 10):
    if type_ == "messages":
        return await db.execute(
            f"""
                SELECT channel_id, COUNT(aliased_author_id) AS count
                FROM `{guild_id}` WHERE is_bot = 0
                AND message_content IS NOT NULL
                GROUP BY channel_id
                ORDER BY count DESC
                LIMIT {amount};
            """, fetch="all"
        )

    elif type_ == "characters":
        # get all messages
        res = await db.execute(
            f"""
                        SELECT channel_id, message_content
                        FROM `{guild_id}` WHERE is_bot = 0 AND message_content IS NOT NULL
                    """, fetch="all"
        )

        # Count characters for each user
        char_counts = Counter()

        for channel_id, message in res:
            char_counts[channel_id] += len(message)

        # Get the top users and their character counts
        top_channels = char_counts.most_common()

        return top_channels[:amount]


async def get_top_channels_visual(db: DB, guild_id: int, client, type_: str, amount: int = 10) -> str:
    res = await get_top_channels(db=db, guild_id=guild_id, type_=type_, amount=amount)
    plt.style.use("cyberpunk")

    labels = []
    guild = await client.fetch_guild(guild_id)

    for i in res:
        try:
            channel = await guild.fetch_channel(i[0])

            # get channel name
            labels.append(f"{channel.name} | {i[1]}")

        except Exception as e:
            labels.append(f"Unknown Channel | {i[1]}")

    pie, texts, autotexts = plt.pie([value for _, value in res], labels=labels, autopct="%1.1f%%")

    for text in autotexts:
        text.set_color('black')

    for text in texts:
        text.set_color('white')

    plt.title(f"Top {amount} Channels by {type_}")

    mplcyberpunk.add_glow_effects()

    # save image
    name = f"{random.randint(1, 100000000)}.png"
    try:
        plt.savefig(name, format='png', dpi=600)
    except Exception as e:
        print(e)

    plt.close()

    return name


async def get_user_top_date(db: DB, guild_id: int, user_id: int, amount: int = 10):
    res = await db.execute(
        f"""
            SELECT
                UNIX_TIMESTAMP(CONCAT(DATE_FORMAT(FROM_UNIXTIME(epoch), '%Y-%m-%d'), ' 00:00:00')) AS start_of_day_epoch,
                COUNT(CASE WHEN aliased_author_id = {user_id} THEN 1 ELSE NULL END) AS count,
                COUNT(*) AS total_count
            FROM
                `{guild_id}`
            WHERE
                epoch <= UNIX_TIMESTAMP()
            GROUP BY
                start_of_day_epoch
            ORDER BY
                count DESC
            LIMIT {amount};
    """, fetch="all"
    )
    return res


async def get_server_top_date(db: DB, guild_id: int, amount: int = 10):
    res = await db.execute(
        f"""
    SELECT
        UNIX_TIMESTAMP(CONCAT(DATE_FORMAT(FROM_UNIXTIME(epoch), '%Y-%m-%d'), ' 00:00:00')) AS start_of_day_epoch,
        COUNT(*) AS count
    FROM
        `{guild_id}`
    WHERE
        epoch <= UNIX_TIMESTAMP()
    GROUP BY
        start_of_day_epoch
    ORDER BY
        count DESC
    LIMIT {amount};
    """, fetch="all"
    )

    return res
