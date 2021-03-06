import asyncio
import json
import logging
import os
import traceback
from datetime import datetime
from urllib import parse

import discord
import motor.motor_asyncio
from discord.ext import commands, tasks
from pytz import timezone

from cogs.server import LinkedServer
from extras.hypixel import HypixelAPI, PlayerNotFoundException
from extras.requesthandler import RequestHandler

logging.basicConfig(
    format="[%(asctime)s] [%(levelname)s:%(name)s] %(message)s", level=logging.INFO
)


class HypixelPlus(commands.AutoShardedBot):

    def __init__(self):
        super().__init__(
            command_prefix=["h+"],
            case_insensitive=True,
            reconnect=True
        )

        with open('./data/settings.json') as settings:
            self.settings = json.load(settings)
            settings.close()

        uri = "mongodb://bot:" + parse.quote_plus(self.settings['bot_motor_password']) + "@51.81.32.153:27017/admin"
        self.motor_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.motor_client.hypixelPlusDB
        self.handler = RequestHandler(asyncio.get_event_loop())
        self.hypixelapi = HypixelAPI(self.settings['bot_api_key'], self.handler)
        self.logger = logging.getLogger(__name__)
        self.servers = {}
        self.logchannel = None
        self.est = timezone("US/Eastern")

        self.owner = 404244659024429056
        self.uptime = datetime.now()

        self.theme = discord.Colour(15120192)
        self.rolecolours = {
            "VIP": discord.Colour(5635925),
            "VIP+": discord.Colour(5635925),
            "MVP": discord.Colour(5636095),
            "MVP+": discord.Colour(5636095),
            "MVP++": discord.Colour(16755200),
            "Hypixel Helper": discord.Colour(5592575),
            "Youtuber": discord.Colour(16733525),
            "Hypixel Moderator": discord.Colour(43520),
            "Hypixel Admin": discord.Colour(11141120)
        }

    async def log(self, msg):
        timestamp = datetime.now()
        await self.db.logs.insert_one({"log": msg, "timestamp": timestamp})

    async def on_message(self, message):
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def handle_error(self, ctx, error):
        newerror = getattr(error, 'original', error)

        ignored = (commands.CommandNotFound)
        if isinstance(newerror, ignored):
            return
        elif isinstance(newerror, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'`{ctx.command.name}` cannot be used in Private Messages.')
            except:
                pass
        elif isinstance(newerror, commands.CommandOnCooldown):
            return await ctx.send(f'You can use that command again in `{round(error.retry_after, 2)}` seconds.')
        elif isinstance(newerror, PlayerNotFoundException):
            return await ctx.send('Player not found on Hypixel!')
        elif isinstance(newerror, commands.MissingRequiredArgument):
            msg = f"*You're missing the parameter `{newerror.param}`!*"
            embed, pic = await self.cogs['help'].get_command_help_embed(ctx.command.qualified_name)
            return await ctx.send(content=msg, embed=embed, file=pic)
        elif isinstance(newerror, commands.CheckFailure):
            return await ctx.send("Sorry, you aren't allowed to use that command.")

        await self.log(str(newerror) + "\n" + traceback.format_exc())
        await ctx.send("Internal error found. Sorry, please try again later! The developer has been notified.")

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            return

        await self.handle_error(ctx, error)

    async def setup_servers(self):
        async for server in self.db.guilds.find():
            self.servers[server['discordid']] = LinkedServer(self, server)

    async def server_verified(self, discordid):
        return self.servers.get(discordid)

    async def on_ready(self):
        self.remove_command('help')
        if not self.cogs:
            await self.load_mods()

        await self.setup_servers()
        self.update_next_users.start()

        self.logger.info("Bot ready")
        await self.log("Restarted")
        self.logging.start()

        watch = discord.Activity(type=discord.ActivityType.watching, name="h+help | hyp.plus")
        await self.change_presence(status=discord.Status.idle, activity=watch)

    async def load_mods(self):
        for ext in os.listdir('cogs'):
            try:
                if not ext.endswith(".py"):
                    continue
                self.load_extension(f"cogs.{ext.replace('.py', '')}")
                self.logger.info(f"Loaded {ext}")
            except:
                self.logger.critical(f"{ext} failed:\n{traceback.format_exc()}")

    @tasks.loop(seconds=1)
    async def update_next_users(self):
        for server in self.servers.values():
            try:
                await server.update_next_user()
            except Exception:
                await self.log(traceback.format_exc())

    @tasks.loop(seconds=3.0)
    async def logging(self):
        log = None
        async for g in self.db.logs.find().sort([("timestamp", 1)]).limit(1):
            log = g

        if log is None:
            return

        if self.logchannel is None:
            self.logchannel = await self.fetch_channel(710829103003205764)

        e = discord.Embed(color=discord.Color.darker_grey(), description=str(log['log'])[:1800],
                          timestamp=log['timestamp'])
        await self.logchannel.send(embed=e)
        await self.db.logs.delete_many({'_id': log['_id']})

    def run(self):
        super().run(self.settings['discord_token'])


HypixelPlus().run()
