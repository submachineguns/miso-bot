from modules import log

logger = log.get_logger(__name__)


class Cache:
    def __init__(self, bot):
        self.bot = bot
        self.log_emoji = False
        self.prefixes = {}
        self.rolepickers = set()
        self.votechannels = set()
        self.autoresponse = {}
        self.blacklist = {}
        self.logging_settings = {}
        self.autoroles = {}
        self.marriages = set()
        self.starboard_settings = {}
        self.starboard_blacklisted_channels = set()

    async def cache_starboard_settings(self):
        data = await self.bot.db.execute(
            """
            SELECT guild_id, is_enabled, channel_id, reaction_count,
                emoji_name, emoji_id, emoji_type, log_channel_id
            FROM starboard_settings
            """
        )
        if not data:
            return
        for (
            guild_id,
            is_enabled,
            channel_id,
            reaction_count,
            emoji_name,
            emoji_id,
            emoji_type,
            log_channel_id,
        ) in data:
            self.starboard_settings[str(guild_id)] = [
                is_enabled,
                channel_id,
                reaction_count,
                emoji_name,
                emoji_id,
                emoji_type,
                log_channel_id,
            ]

        self.starboard_blacklisted_channels = set(
            await self.bot.db.execute(
                "SELECT channel_id FROM starboard_blacklist",
                as_list=True,
            )
        )

    async def cache_logging_settings(self):
        logging_settings = await self.bot.db.execute(
            """
            SELECT guild_id, member_log_channel_id, ban_log_channel_id, message_log_channel_id
            FROM logging_settings
            """
        )
        for (
            guild_id,
            member_log_channel_id,
            ban_log_channel_id,
            message_log_channel_id,
        ) in logging_settings:
            self.logging_settings[str(guild_id)] = {
                "member_log_channel_id": member_log_channel_id,
                "ban_log_channel_id": ban_log_channel_id,
                "message_log_channel_id": message_log_channel_id,
            }

    async def cache_autoroles(self):
        for guild_id, role_id in await self.bot.db.execute(
            "SELECT guild_id, role_id FROM autorole"
        ):
            try:
                self.autoroles[str(guild_id)].add(role_id)
            except KeyError:
                self.autoroles[str(guild_id)] = set([role_id])

    async def initialize_settings_cache(self):
        logger.info("Caching settings...")
        prefixes = await self.bot.db.execute("SELECT guild_id, prefix FROM guild_prefix")
        for guild_id, prefix in prefixes:
            self.prefixes[str(guild_id)] = prefix

        self.rolepickers = set(
            await self.bot.db.execute("SELECT channel_id FROM rolepicker_settings", as_list=True)
        )

        self.votechannels = set(
            await self.bot.db.execute("SELECT channel_id FROM voting_channel", as_list=True)
        )

        guild_settings = await self.bot.db.execute(
            "SELECT guild_id, autoresponses FROM guild_settings"
        )
        for guild_id, autoresponses in guild_settings:
            self.autoresponse[str(guild_id)] = autoresponses

        self.blacklist = {
            "global": {
                "user": set(
                    await self.bot.db.execute("SELECT user_id FROM blacklisted_user", as_list=True)
                ),
                "guild": set(
                    await self.bot.db.execute(
                        "SELECT guild_id FROM blacklisted_guild", as_list=True
                    )
                ),
                "channel": set(
                    await self.bot.db.execute(
                        "SELECT channel_id FROM blacklisted_channel", as_list=True
                    )
                ),
            }
        }

        self.marriages = [
            set(pair)
            for pair in await self.bot.db.execute(
                "SELECT first_user_id, second_user_id FROM marriage"
            )
        ]

        for guild_id, user_id in await self.bot.db.execute(
            "SELECT guild_id, user_id FROM blacklisted_member"
        ):
            try:
                self.blacklist[str(guild_id)]["member"].add(user_id)
            except KeyError:
                self.blacklist[str(guild_id)] = {"member": {user_id}, "command": set()}

        for guild_id, command_name in await self.bot.db.execute(
            "SELECT guild_id, command_name FROM blacklisted_command"
        ):
            try:
                self.blacklist[str(guild_id)]["command"].add(command_name.lower())
            except KeyError:
                self.blacklist[str(guild_id)] = {
                    "member": set(),
                    "command": {command_name.lower()},
                }

        await self.cache_starboard_settings()
        await self.cache_logging_settings()
        await self.cache_autoroles()
