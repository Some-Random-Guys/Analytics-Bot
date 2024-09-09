"""Functions for interacting with the database."""

import asyncio
import aiomysql


class DB:
    """Class for interaction with the database."""

    def __init__(self, db_creds, maxsize: int = 10):
        self.con = None
        self.db_creds = db_creds
        self.maxsize = maxsize

        asyncio.create_task(self.connect())  # this doesn't work

    async def connect(self):
        if self.con is not None:
            return

        self.con = await aiomysql.create_pool(**self.db_creds, autocommit=True, maxsize=self.maxsize)

        await self._create_data_tables()

    async def _create_data_tables(self):
        # check if the "data" table exists, if not, create it

        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ignores (
                        type_ TEXT NOT NULL, 
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL
                    );
                    """
                )

                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS timezones (
                        guild_id BIGINT NOT NULL,
                        timezone INT NOT NULL
                    );
                    """
                )

                await cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS aliases (
                        guild_id BIGINT NOT NULL,
                        user_id BIGINT NOT NULL
                    );
                    """
                )

    async def add_guild(self, guild_id):
        """Adds a guild (database), with boilerplate table."""
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                CREATE TABLE IF NOT EXISTS `{guild_id}` (
                message_id BIGINT NOT NULL,
                channel_id BIGINT NOT NULL,
                author_id BIGINT NOT NULL,
                aliased_author_id BIGINT,
                message_length BIGINT,
                epoch BIGINT NOT NULL,
                has_embed BOOLEAN NOT NULL,                       
                num_attachments SMALLINT NOT NULL DEFAULT 0,
                PRIMARY KEY (message_id)
                );
                """
                )

    async def remove_guild(self, guild_id):
        """Removes the guild from the database."""
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"DROP TABLE IF EXISTS `{guild_id}`;")

                # await cur.execute(f"DELETE FROM config WHERE data1 = '{guild_id}';") # TODO

    async def execute(self, query, args=None, fetch=None):
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query.replace("?", "%s"), args)
                if fetch is None:
                    return
                if fetch == "all":
                    return await cur.fetchall()
                elif fetch == "one":
                    return await cur.fetchone()

            await conn.commit()

    async def get(self, guild_id, selected: list = None):
        """Retrieves the guild from the database."""

        if selected is None:
            selected = ["*"]
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT {', '.join(selected)} FROM `{guild_id}`;")

                return await cur.fetchall()

    async def get_guilds(self):  # TODO TEST
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES;")

                return await cur.fetchall()

    async def add_message(self, guild_id: int, data: dict):
        """Adds a message to the database."""
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                        INSERT IGNORE INTO `{guild_id}` (message_id, channel_id, author_id, aliased_author_id, message_length, epoch, 
                        has_embed, num_attachments)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        str(data['message_id']),
                        str(data['channel_id']),
                        str(data['author_id']),
                        str(data['aliased_author_id']),
                        str(data['message_length']),
                        str(data['epoch']),
                        str(data['has_embed']),
                        str(data['num_attachments']),
                    ),

                )

    async def add_messages_bulk(self, guild_id, message_ids, channel_ids, author_ids, aliased_author_ids,
                                message_lengths, epoches, has_embeds, num_attachments):
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    f"""
                        INSERT IGNORE INTO `{guild_id}` (message_id, channel_id, author_id, message_length, epoch, 
                        has_embed, num_attachments)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        message_ids,
                        channel_ids,
                        author_ids,
                        aliased_author_ids,
                        message_lengths,
                        epoches,
                        has_embeds,
                        num_attachments,
                    )
                )

    async def delete_message(self, guild_id: int, message_id: int):
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"DELETE FROM `{guild_id}` WHERE message_id = {message_id};")

    async def edit_message(
            self, guild_id: int, message_id: int, message_length: int, has_embed: bool, num_attachments: int,
    ):
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE `{guild_id}` SET message_length = %s, has_embed = %s, num_attachments = %s WHERE message_id = %s;",
                    (
                        message_length,
                        has_embed,
                        num_attachments,
                        message_id,
                    ),
                )

    async def add_user_alias(self, guild_id: int, user_id: int, alias_id: int, update_existing: bool = True):
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT IGNORE INTO `config` (_key, data1, data2, data3) VALUES ('alias', %s, %s, %s);",
                    (guild_id, user_id, alias_id),
                )
                if update_existing:
                    # replace all existing aliases with the new one
                    await cur.execute(
                        f"UPDATE `{guild_id}` SET aliased_author_id = {user_id} WHERE author_id = {alias_id};"
                    )

    async def remove_user_alias(self, guild_id: int, user_id: int, alias_id: int, update_existing: bool = True):
        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "DELETE FROM `config` WHERE _key = 'alias' AND data1 = %s AND data2 = %s AND data3 = %s;",
                    (guild_id, user_id, alias_id),
                )
                if update_existing:
                    # replace all existing aliases with the new one
                    await cur.execute(
                        f"UPDATE `{guild_id}` SET aliased_author_id = NULL WHERE author_id = {alias_id};"
                    )

    async def get_user_aliases(self, guild_id: int = None):
        from collections import defaultdict
        final_dict = defaultdict(lambda: {})

        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                # data1 is guild_id, data2 is user_id, data3 is alias_id

                if guild_id is None:
                    await cur.execute(
                        "SELECT data1, data2, data3 FROM `config` WHERE _key = 'alias';",
                    )

                    res = await cur.fetchall()

                    # { guild_id: {alias_id: user_id} }
                    for guild_id, user_id, alias_id in res:
                        final_dict[alias_id]: user_id

                else:
                    await cur.execute(
                        "SELECT data2, data3 FROM `config` WHERE _key = 'alias' AND data1 = %;",
                        ()
                    )

                    res = await cur.fetchall()

                    # {alias_id: user_id}
                    for user_id, alias_id in res:
                        final_dict[alias_id]: user_id

        return final_dict

    async def set_timezone(self, guild_id: int, timezone: int):
        # timezone here is an offset from UTC

        if await self.execute(
                f"SELECT data2 FROM `config` WHERE _key = 'timezone' AND data1 = '%s';",
                (guild_id,), fetch="one"
        ) is None:
            await self.execute(
                "INSERT INTO `config` (_key, data1, data2) VALUES ('timezone', %s, %s);",
                (guild_id, timezone),
            )
            return

        await self.execute(
            "UPDATE `config` SET data2 = %s WHERE _key = 'timezone' AND data1 = %s;",
            (timezone, guild_id),
        )

    async def get_timezone(self, guild_id: int):
        res = await self.execute(f"SELECT data2 FROM `config` WHERE _key = 'timezone' AND data1 = '%s';",
                                 (guild_id,), fetch="one")

        if res is None:
            return None

        return res[0]

    # analysis functions
    async def get_message_count(self, guild_id: int, channel_id: int = None, user_id: int = None):

        query = f"SELECT COUNT(*) FROM `{guild_id}`"
        conditions = []
        params = []

        if channel_id is not None:
            conditions.append("channel_id = %s")
            params.append(channel_id)

        if user_id is not None:
            conditions.append("author_id = %s")
            params.append(user_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, tuple(params))
                return (await cur.fetchone())[0]

    async def get_character_count(self, guild_id: int, channel_id: int = None, user_id: int = None):

        query = f"SELECT sum(message_length) FROM `{guild_id}`"
        conditions = []
        params = []

        if channel_id is not None:
            conditions.append("channel_id = %s")
            params.append(channel_id)

        if user_id is not None:
            conditions.append("author_id = %s")
            params.append(user_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        async with self.con.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, tuple(params))
                return (await cur.fetchone())[0]
