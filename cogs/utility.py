import asyncio
import html
import os
import random
from time import time

import aiohttp
import arrow
import discord
import orjson
from bs4 import BeautifulSoup
from discord.ext import commands, tasks

from modules import emojis, exceptions, log, queries, util

GOOGLE_API_KEY = os.environ.get("GOOGLE_KEY")
DARKSKY_API_KEY = os.environ.get("DARK_SKY_KEY")
TIMEZONE_API_KEY = os.environ.get("TIMEZONEDB_API_KEY")
OXFORD_APPID = os.environ.get("OXFORD_APPID")
OXFORD_TOKEN = os.environ.get("OXFORD_TOKEN")
NAVER_APPID = os.environ.get("NAVER_APPID")
NAVER_TOKEN = os.environ.get("NAVER_TOKEN")
WOLFRAM_APPID = os.environ.get("WOLFRAM_APPID")
GFYCAT_CLIENT_ID = os.environ.get("GFYCAT_CLIENT_ID")
GFYCAT_SECRET = os.environ.get("GFYCAT_SECRET")
STREAMABLE_USER = os.environ.get("STREAMABLE_USER")
STREAMABLE_PASSWORD = os.environ.get("STREAMABLE_PASSWORD")
THESAURUS_KEY = os.environ.get("THESAURUS_KEY")
FINNHUB_TOKEN = os.environ.get("FINNHUB_TOKEN")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

command_logger = log.get_command_logger()

papago_pairs = [
    "ko/en",
    "ko/ja",
    "ko/zh-cn",
    "ko/zh-tw",
    "ko/vi",
    "ko/id",
    "ko/de",
    "ko/ru",
    "ko/es",
    "ko/it",
    "ko/fr",
    "en/ja",
    "ja/zh-cn",
    "ja/zh-tw",
    "zh-cn/zh-tw",
    "en/ko",
    "ja/ko",
    "zh-cn/ko",
    "zh-tw/ko",
    "vi/ko",
    "id/ko",
    "th/ko",
    "de/ko",
    "ru/ko",
    "es/ko",
    "it/ko",
    "fr/ko",
    "ja/en",
    "zh-cn/ja",
    "zh-tw/ja",
    "zh-tw/zh-tw",
]

weather_icons = {
    "clear-day": ":sunny:",
    "clear-night": ":night_with_stars:",
    "fog": ":foggy:",
    "hail": ":cloud_snow:",
    "sleet": ":cloud_snow:",
    "snow": ":cloud_snow:",
    "partly-cloudy-day": ":partly_sunny:",
    "cloudy": ":cloud:",
    "partly-cloudy-night": ":cloud:",
    "tornado": ":cloud_tornado:",
    "wind": ":wind_blowing_face:",
}

logger = log.get_logger(__name__)


class Utility(commands.Cog):
    """Utility commands"""

    def __init__(self, bot):
        self.bot = bot
        self.icon = "🔧"
        self.reminder_list = []
        self.cache_needs_refreshing = True

    async def cog_load(self):
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @tasks.loop(seconds=5.0)
    async def reminder_loop(self):
        try:
            await self.check_reminders()
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")

    @reminder_loop.before_loop
    async def task_waiter(self):
        await self.bot.wait_until_ready()

    async def check_reminders(self):
        """Check all current reminders"""
        if self.cache_needs_refreshing:
            self.cache_needs_refreshing = False
            self.reminder_list = await self.bot.db.execute(
                """
                SELECT user_id, guild_id, created_on, reminder_date, content, original_message_url
                FROM reminder
                """
            )

        if not self.reminder_list:
            return

        now_ts = arrow.utcnow().timestamp()
        for (
            user_id,
            guild_id,
            created_on,
            reminder_date,
            content,
            original_message_url,
        ) in self.reminder_list:
            reminder_ts = reminder_date.timestamp()
            if reminder_ts > now_ts:
                continue

            user = self.bot.get_user(user_id)
            if user is not None:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    guild = "Unknown guild"

                date = arrow.get(created_on)
                if now_ts - reminder_ts > 21600:
                    logger.info(
                        f"Deleting reminder set for {date.format('DD/MM/YYYY HH:mm:ss')} for being over 6 hours late"
                    )
                else:
                    embed = discord.Embed(
                        color=int("d3a940", 16),
                        title=":alarm_clock: Reminder!",
                        description=content,
                    )
                    embed.add_field(
                        name="context",
                        value=f"[Jump to message]({original_message_url})",
                        inline=True,
                    )
                    embed.set_footer(text=f"{guild}")
                    embed.timestamp = created_on
                    try:
                        await user.send(embed=embed)
                        logger.info(f'Reminded {user} to "{content}"')
                    except discord.errors.Forbidden:
                        logger.warning(f"Unable to remind {user}, missing DM permissions!")
            else:
                logger.info(f"Deleted expired reminder by unknown user {user_id}")

            await self.bot.db.execute(
                """
                DELETE FROM reminder
                    WHERE user_id = %s AND guild_id = %s AND original_message_url = %s
                """,
                user_id,
                guild_id,
                original_message_url,
            )
            self.cache_needs_refreshing = True

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        """only for CommandNotFound"""
        error = getattr(error, "original", error)
        if isinstance(error, commands.CommandNotFound) and ctx.message.content.startswith(
            f"{ctx.prefix}!"
        ):
            ctx.timer = time()
            ctx.iscallback = True
            ctx.command = self.bot.get_command("!")
            await ctx.command.callback(self, ctx)

    async def resolve_bang(self, ctx: commands.Context, bang, args):
        params = {"q": "!" + bang + " " + args, "format": "json", "no_redirect": 1}
        url = "https://api.duckduckgo.com"
        async with self.bot.session.get(url, params=params) as response:
            data = await response.json(content_type=None)
            location = data.get("Redirect")
            if location == "":
                return await ctx.send(":warning: Unknown bang or found nothing!")

            while location:
                async with self.bot.session.get(url, params=params) as deeper_response:
                    response = deeper_response
                    location = response.headers.get("location")

            content = response.url
        await ctx.send(content)

    @commands.command(name="!", usage="<bang> <query...>")
    async def bang(self, ctx: commands.Context):
        """
        DuckDuckGo bangs https://duckduckgo.com/bang

        Usage:
            >!<bang> <query...>

        Example:
            >!w horses
        """
        if not hasattr(ctx, "iscallback"):
            return await ctx.send_help(ctx.command)

        try:
            await ctx.trigger_typing()
        except discord.errors.Forbidden:
            pass

        command_logger.info(log.log_command(ctx))
        await queries.save_command_usage(ctx)
        try:
            bang, args = ctx.message.content[len(ctx.prefix) + 1 :].split(" ", 1)
            if len(bang) != 0:
                await self.resolve_bang(ctx, bang, args)
        except ValueError:
            await ctx.send("Please provide a query to search")

    @commands.command(usage="<'in' | 'on'> <time | YYYY/MM/DD [HH:mm:ss]> to <something>")
    async def remindme(self, ctx: commands.Context, pre, *, arguments):
        """
        Set a reminder

        Usage:
            >remindme in <some time> to <something>
            >remindme on <YYYY/MM/DD> [HH:mm:ss] to <something>
        """
        try:
            reminder_time, content = arguments.split(" to ", 1)
        except ValueError:
            return await util.send_command_help(ctx)

        now = arrow.utcnow()

        if pre == "on":
            # user inputs date
            date = arrow.get(reminder_time)
            seconds = date.int_timestamp - now.int_timestamp

        elif pre == "in":
            # user inputs time delta
            seconds = util.timefromstring(reminder_time)
            date = now.shift(seconds=+seconds)

        else:
            return await ctx.send(
                f"Invalid operation `{pre}`\nUse `on` for date and `in` for time delta"
            )

        if seconds < 1:
            raise exceptions.CommandInfo(
                "You must give a valid time at least 1 second in the future!"
            )

        await self.bot.db.execute(
            """
            INSERT INTO reminder (user_id, guild_id, created_on, reminder_date, content, original_message_url)
                VALUES(%s, %s, %s, %s, %s, %s)
            """,
            ctx.author.id,
            ctx.guild.id,
            now.datetime,
            date.datetime,
            content,
            ctx.message.jump_url,
        )

        self.cache_needs_refreshing = True
        await ctx.send(
            embed=discord.Embed(
                color=int("ccd6dd", 16),
                description=(
                    f":pencil: I'll message you on **{date.to('utc').format('DD/MM/YYYY HH:mm:ss')}"
                    f" UTC** to remind you of:\n```{content}```"
                ),
            )
        )

    @commands.command(usage="['save'] <location>")
    async def weather(self, ctx: commands.Context, *, address=None):
        """
        Get weather of given location.

        Usage:
            >weather
            >weather <location>
            >weather save <location>
        """
        if address is None:
            # use saved location
            location = await self.bot.db.execute(
                "SELECT location_string FROM user_settings WHERE user_id = %s",
                ctx.author.id,
                one_value=True,
            )
            if not location:
                return await util.send_command_help(ctx)
        else:
            # check if user wants to save location
            try:
                cmd, saved_address = address.split(" ", 1)
                cmd = cmd.lower()
            except ValueError:
                cmd = None

            if cmd == "save":
                await self.bot.db.execute(
                    """
                    INSERT INTO user_settings (user_id, location_string)
                        VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE
                        location_string = VALUES(location_string)
                    """,
                    ctx.author.id,
                    saved_address,
                )
                return await util.send_success(ctx, f"Saved your location as `{saved_address}`")
            # use given string as temporary location
            location = address

        params = {"address": location, "key": GOOGLE_API_KEY}
        async with self.bot.session.get(
            "https://maps.googleapis.com/maps/api/geocode/json", params=params
        ) as response:
            geocode_data = await response.json()
        try:
            geocode_data = geocode_data["results"][0]
        except IndexError:
            raise exceptions.CommandWarning("Could not find that location!")

        formatted_name = geocode_data["formatted_address"]
        lat = geocode_data["geometry"]["location"]["lat"]
        lon = geocode_data["geometry"]["location"]["lng"]

        # we have lat and lon now, plug them into dark sky
        async with self.bot.session.get(
            url=f"https://api.darksky.net/forecast/{DARKSKY_API_KEY}/{lat},{lon}?units=si"
        ) as response:
            weather_data = await response.json()
        current = weather_data["currently"]
        hourly = weather_data["hourly"]

        localtime = await get_timezone(self.bot.session, {"lat": lat, "lon": lon})

        country = "N/A"
        for comp in geocode_data["address_components"]:
            if "country" in comp["types"]:
                country = comp["short_name"].lower()

        weather_icon = weather_icons.get(current["icon"], "")
        try:
            summary = hourly["summary"]
        except KeyError:
            summary = "No weather forecast found."

        information_rows = [
            f":thermometer: Currently **{current['temperature']} °C** ({to_f(current['temperature']):.2f} °F)",
            f":neutral_face: Feels like **{current['apparentTemperature']} °C** ({to_f(current['apparentTemperature']):.2f} °F)",
            f":dash: Wind speed **{current['windSpeed']} m/s** with gusts of **{current['windGust']} m/s**",
            f":sweat_drops: Humidity **{int(current['humidity'] * 100)}%**",
            f":map: [See on map](https://www.google.com/maps/search/?api=1&query={lat},{lon})",
        ]

        content = discord.Embed(
            color=int("e1e8ed", 16), title=f":flag_{country}: {formatted_name}"
        )
        content.add_field(name=f"{weather_icon} {summary}", value="\n".join(information_rows))
        content.set_footer(text=f"🕐 Local time {localtime}")
        await ctx.send(embed=content)

    @commands.command()
    async def define(self, ctx: commands.Context, *, word):
        """Get definitions for a given word"""
        API_BASE_URL = "wordsapiv1.p.rapidapi.com"
        COLORS = ["226699", "f4900c", "553788"]

        headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": API_BASE_URL}
        url = f"https://{API_BASE_URL}/words/{word}"
        async with self.bot.session.get(url, headers=headers) as response:
            data = await response.json(loads=orjson.loads)

        if data.get("results") is None:
            raise exceptions.CommandWarning(f"No definitions found for `{word}`")

        content = discord.Embed(
            title=f":books: {word.capitalize()}",
            color=int(random.choice(COLORS), 16),
        )

        if data.get("pronunciation") is not None:
            if isinstance(data["pronunciation"], str):
                content.description = f"`{data['pronunciation']}`"
            elif data["pronunciation"].get("all") is not None:
                content.description = f"`{data['pronunciation'].get('all')}`"
            else:
                content.description = "\n".join(
                    f"{wt}: `{pro}`" for wt, pro in data["pronunciation"].items()
                )

        results = {}
        for result in data["results"]:
            word_type = result["partOfSpeech"]
            try:
                results[word_type].append(result)
            except KeyError:
                results[word_type] = [result]

        for category, definitions in results.items():
            category_definitions = []
            for n, category_result in enumerate(definitions, start=1):
                parts = [f"**{n}.** {category_result['definition'].capitalize()}"]

                if category_result.get("examples") is not None:
                    parts.append(f'> *"{category_result.get("examples")[0]}"*')

                if category_result.get("synonyms") is not None:
                    quoted_synonyms = [f"`{x}`" for x in category_result["synonyms"]]
                    parts.append(f"> Similar: {' '.join(quoted_synonyms)}")

                category_definitions.append("\n".join(parts))

            content.add_field(
                name=category.upper(),
                value="\n".join(category_definitions)[:1024],
                inline=False,
            )

        await ctx.send(embed=content)

    @commands.command()
    async def urban(self, ctx: commands.Context, *, word):
        """Get Urban Dictionary entries for a given word"""
        API_BASE_URL = "https://api.urbandictionary.com/v0/define"
        async with self.bot.session.get(API_BASE_URL, params={"term": word}) as response:
            data = await response.json(loads=orjson.loads)

        pages = []
        if data["list"]:
            for entry in data["list"]:
                definition = entry["definition"].replace("]", "**").replace("[", "**")
                example = entry["example"].replace("]", "**").replace("[", "**")
                timestamp = entry["written_on"]
                content = discord.Embed(colour=discord.Colour.from_rgb(254, 78, 28))
                content.description = f"{definition}"

                if not example == "":
                    content.add_field(name="Example", value=example)

                content.set_footer(
                    text=f"by {entry['author']} • "
                    f"{entry.get('thumbs_up')} 👍 {entry.get('thumbs_down')} 👎"
                )
                content.timestamp = arrow.get(timestamp).datetime
                content.set_author(
                    name=entry["word"],
                    icon_url="https://i.imgur.com/yMwpnBe.png",
                    url=entry.get("permalink"),
                )
                pages.append(content)

            await util.page_switcher(ctx, pages)

        else:
            await ctx.send(f"No definitions found for `{word}`")

    @commands.command(aliases=["tr", "trans"], usage="[source_lang]/[target_lang] <text>")
    async def translate(self, ctx: commands.Context, *, text):
        """
        Papago and Google translator

        You can specify language pairs or let them be automatically detected.
        Default target language is english.

        Usage:
            >translate <sentence>
            >translate xx/yy <sentence>
            >translate /yy <sentence>
            >translate xx/ <sentence>
        """
        if len(text) > 1000:
            raise exceptions.CommandWarning(
                "Sorry, the maximum length of text i can translate is 1000 characters!"
            )

        languages = text.partition(" ")[0]
        if "/" in languages or "->" in languages:
            if "/" in languages:
                source, target = languages.split("/")
            elif "->" in languages:
                source, target = languages.split("->")
            text = text.partition(" ")[2]
            if source == "":
                source = await detect_language(self.bot.session, text)
            if target == "":
                target = "en"
        else:
            source = await detect_language(self.bot.session, text)
            if source == "en":
                target = "ko"
            else:
                target = "en"
        language_pair = f"{source}/{target}"

        # we have language and query, now choose the appropriate translator

        if language_pair in papago_pairs:
            # use papago
            url = "https://openapi.naver.com/v1/papago/n2mt"
            params = {"source": source, "target": target, "text": text}
            headers = {
                "X-Naver-Client-Id": NAVER_APPID,
                "X-Naver-Client-Secret": NAVER_TOKEN,
            }

            async with self.bot.session.post(url, headers=headers, data=params) as response:
                translation = (await response.json(loads=orjson.loads))["message"]["result"][
                    "translatedText"
                ]

        else:
            # use google
            url = "https://translation.googleapis.com/language/translate/v2"
            params = {
                "key": GOOGLE_API_KEY,
                "model": "nmt",
                "target": target,
                "source": source,
                "q": text,
            }

            async with self.bot.session.get(url, params=params) as response:
                data = await response.json(loads=orjson.loads)

            try:
                translation = html.unescape(data["data"]["translations"][0]["translatedText"])
            except KeyError:
                return await ctx.send("Sorry, I could not translate this :(")

        await ctx.send(f"`{source}->{target}` {translation}")

    @commands.command(aliases=["wolf", "w"])
    async def wolfram(self, ctx: commands.Context, *, query):
        """Ask something from wolfram alpha"""
        url = "http://api.wolframalpha.com/v1/result"
        params = {
            "appid": WOLFRAM_APPID,
            "i": query,
            "output": "json",
            "units": "metric",
        }

        async with self.bot.session.get(url, params=params) as response:
            if response.status == 200:
                content = await response.text()
                await ctx.send(f":mag_right: {content}")
            else:
                await ctx.send(":shrug:")

    @commands.command()
    async def creategif(self, ctx: commands.Context, media_url):
        """Create a gfycat gif from video url"""
        starttimer = time()
        auth_headers = await gfycat_oauth(self.bot.session)
        url = "https://api.gfycat.com/v1/gfycats"
        params = {"fetchUrl": media_url.strip("`")}
        async with self.bot.session.post(url, json=params, headers=auth_headers) as response:
            data = await response.json(loads=orjson.loads)

        try:
            gfyname = data["gfyname"]
        except KeyError:
            raise exceptions.CommandWarning("Unable to create gif from this link!")

        message = await ctx.send(f"Encoding {emojis.LOADING}")

        i = 1
        url = f"https://api.gfycat.com/v1/gfycats/fetch/status/{gfyname}"
        await asyncio.sleep(5)
        while True:
            async with self.bot.session.get(url, headers=auth_headers) as response:
                data = await response.json(loads=orjson.loads)
                task = data["task"]

            if task == "encoding":
                pass

            elif task == "complete":
                await message.edit(
                    content=f"Gif created in **{util.stringfromtime(time() - starttimer, 2)}**"
                    f"\nhttps://gfycat.com/{data['gfyname']}"
                )
                break

            else:
                await message.edit(content="There was an error while creating your gif :(")
                break

            await asyncio.sleep(i)
            i += 1

    @commands.command()
    async def streamable(self, ctx: commands.Context, media_url):
        """Create a streamable video from media/twitter/ig url"""
        starttimer = time()

        url = "https://api.streamable.com/import"
        params = {"url": media_url.strip("`")}
        auth = aiohttp.BasicAuth(STREAMABLE_USER, STREAMABLE_PASSWORD)

        async with self.bot.session.get(url, params=params, auth=auth) as response:
            if response.status != 200:
                try:
                    data = await response.json(loads=orjson.loads)
                    messages = []
                    for category in data["messages"]:
                        for msg in data["messages"][category]:
                            messages.append(msg)
                    messages = " | ".join(messages)
                    errormsg = f"ERROR {response.status_code}: {messages}"
                except (aiohttp.ContentTypeError, KeyError):
                    errormsg = await response.text()

                logger.error(errormsg)
                return await ctx.send(f"```{errormsg.split(';')[0]}```")

            data = await response.json(loads=orjson.loads)
            link = "https://streamable.com/" + data.get("shortcode")
            message = await ctx.send(f"Processing Video {emojis.LOADING}")

        i = 1
        await asyncio.sleep(5)
        while True:
            async with self.bot.session.get(link) as response:
                soup = BeautifulSoup(await response.text(), "html.parser")
                meta = soup.find("meta", {"property": "og:url"})

                if meta:
                    timestring = util.stringfromtime(time() - starttimer, 2)
                    await message.edit(
                        content=f"Streamable created in **{timestring}**\n{meta.get('content')}"
                    )
                    break

                status = soup.find("h1").text
                if status != "Processing Video":
                    await message.edit(content=f":warning: {status}")
                    break

                await asyncio.sleep(i)
                i += 1

    @commands.command()
    async def stock(self, ctx: commands.Context, *, symbol):
        """
        Get price data for the US stock market

        Example:
            >stock $TSLA
        """
        FINNHUB_API_QUOTE_URL = "https://finnhub.io/api/v1/quote"
        FINNHUB_API_PROFILE_URL = "https://finnhub.io/api/v1/stock/profile2"

        symbol = symbol.upper()
        params = {"symbol": symbol.strip("$"), "token": FINNHUB_TOKEN}
        async with self.bot.session.get(FINNHUB_API_QUOTE_URL, params=params) as response:
            quote_data = await response.json(loads=orjson.loads)

        error = quote_data.get("error")
        if error:
            raise exceptions.CommandError(error)

        if quote_data["c"] == 0:
            raise exceptions.CommandWarning("Company not found")

        async with self.bot.session.get(FINNHUB_API_PROFILE_URL, params=params) as response:
            company_profile = await response.json(loads=orjson.loads)

        change = float(quote_data["c"]) - float(quote_data["pc"])
        GAINS = change > 0

        arrow_emoji = emojis.GREEN_UP if GAINS else emojis.RED_DOWN
        percentage = ((float(quote_data["c"]) / float(quote_data["pc"])) - 1) * 100
        market_cap = int(company_profile["marketCapitalization"])

        def get_money(key):
            return f"${quote_data[key]}"

        if company_profile.get("name") is not None:
            content = discord.Embed(
                title=f"${company_profile['ticker']} | {company_profile['name']}",
            )
            content.set_thumbnail(url=company_profile.get("logo"))
            content.set_footer(text=company_profile["exchange"])
        else:
            content = discord.Embed(title=f"${symbol}")

        content.add_field(
            name="Change",
            value=f"{'+' if GAINS else '-'}${abs(change):.2f}{arrow_emoji}\n({percentage:.2f}%)",
        )
        content.add_field(name="Open", value=get_money("o"))
        content.add_field(name="Previous close", value=get_money("pc"))
        content.add_field(name="Current price", value=get_money("c"))
        content.add_field(name="Today's high", value=get_money("h"))
        content.add_field(name="Today's low", value=get_money("l"))
        content.add_field(name="Market capitalization", value=f"${market_cap:,}", inline=False)

        content.colour = discord.Color.green() if GAINS else discord.Color.red()
        content.timestamp = arrow.get(quote_data["t"]).datetime

        await ctx.send(embed=content)

    @commands.group(aliases=["tz", "timezones"])
    async def timezone(self, ctx: commands.Context):
        """See the current time for your friends across the globe"""
        await util.command_group_help(ctx)

    @timezone.command(name="now")
    async def tz_now(self, ctx: commands.Context, member: discord.Member = None):
        """Get current time for a member"""
        if member is None:
            member = ctx.author

        tz_str = await self.bot.db.execute(
            "SELECT timezone FROM user_settings WHERE user_id = %s",
            member.id,
            one_value=True,
        )
        if tz_str:
            dt = arrow.now(tz_str)
            await ctx.send(f":clock2: **{dt.format('MMM Do HH:mm')}**")
        else:
            raise exceptions.CommandWarning(f"{member} has not set their timezone yet!")

    @timezone.command(name="set")
    async def tz_set(self, ctx: commands.Context, your_timezone):
        """
        Set your timezone
        Give timezone as a tz database name (case sensitive):
        https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

        Example:
            >timezone set Europe/Helsinki
        """
        try:
            ts = arrow.now(your_timezone)
        except arrow.ParserError as e:
            raise exceptions.CommandWarning(str(e), help_footer=True)
        await ctx.bot.db.execute(
            """
            INSERT INTO user_settings (user_id, timezone)
                VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                timezone = VALUES(timezone)
            """,
            ctx.author.id,
            your_timezone,
        )
        await util.send_success(
            ctx,
            f"Saved your timezone as **{your_timezone}**\n:clock2: Current time: **{ts.ctime()}**",
        )

    @timezone.command(name="unset")
    async def tz_unset(self, ctx: commands.Context):
        """Unset your timezone"""
        await ctx.bot.db.execute(
            """
            INSERT INTO user_settings (user_id, timezone)
                VALUES (%s, NULL)
            ON DUPLICATE KEY UPDATE
                timezone = VALUES(timezone)
            """,
            ctx.author.id,
        )
        await util.send_success(ctx, "Your timezone is no longer saved.")

    @timezone.command(name="list")
    async def tz_list(self, ctx: commands.Context):
        """List current time of all server members who have it saved"""
        content = discord.Embed(
            title=f":clock2: Current time in {ctx.guild}",
            color=int("3b88c3", 16),
        )
        rows = []
        user_ids = [user.id for user in ctx.guild.members]
        data = await self.bot.db.execute(
            "SELECT user_id, timezone FROM user_settings WHERE user_id IN %s AND timezone IS NOT NULL",
            user_ids,
        )
        if not data:
            raise exceptions.CommandWarning("No one on this server has set their timezone yet!")

        dt_data = []
        for user_id, tz_str in data:
            dt_data.append((arrow.now(tz_str), ctx.guild.get_member(user_id)))

        for dt, member in sorted(dt_data, key=lambda x: int(x[0].format("Z"))):
            if member is None:
                continue
            rows.append(f"{dt.format('MMM Do HH:mm')} - **{util.displayname(member)}**")

        await util.send_as_pages(ctx, content, rows)


async def setup(bot):
    await bot.add_cog(Utility(bot))


def profile_ticker(ticker):
    subs = {"GOOG": "GOOGL"}
    return subs.get(ticker) or ticker


async def get_timezone(session, coord, clocktype="12hour"):
    url = "http://api.timezonedb.com/v2.1/get-time-zone"
    params = {
        "key": TIMEZONE_API_KEY,
        "format": "json",
        "by": "position",
        "lat": str(coord["lat"]),
        "lng": str(coord["lon"]),
    }
    async with session.get(url, params=params) as response:
        if response.status != 200:
            return f"HTTP ERROR {response.status}"

        timestring = (await response.json()).get("formatted").split(" ")
        try:
            hours, minutes = [int(x) for x in timestring[1].split(":")[:2]]
        except IndexError:
            return "N/A"

        if clocktype == "12hour":
            if hours > 12:
                suffix = "PM"
                hours -= 12
            else:
                suffix = "AM"
                if hours == 0:
                    hours = 12
            return f"{hours}:{minutes:02d} {suffix}"
        return f"{hours}:{minutes:02d}"


async def detect_language(session, string):
    url = "https://translation.googleapis.com/language/translate/v2/detect"
    params = {"key": GOOGLE_API_KEY, "q": string[:1000]}

    async with session.get(url, params=params) as response:
        data = await response.json(loads=orjson.loads)
        language = data["data"]["detections"][0][0]["language"]

    return language


async def gfycat_oauth(session):
    url = "https://api.gfycat.com/v1/oauth/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": GFYCAT_CLIENT_ID,
        "client_secret": GFYCAT_SECRET,
    }

    async with session.post(url, json=params) as response:
        data = await response.json(loads=orjson.loads)
        access_token = data["access_token"]

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    return auth_headers


def to_f(c):
    return c * (9.0 / 5.0) + 32
