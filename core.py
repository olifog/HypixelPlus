import discord
from discord.ext import commands
import asyncio
import os
import traceback
import logging
from datetime import datetime
import json
from extras.hypixel import HypixelAPI, PlayerNotFoundException
from extras.requesthandler import RequestHandler
import motor.motor_asyncio
from urllib import parse


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

        self.owner = 404244659024429056
        self.uptime = datetime.now()

    async def on_message(self, message):
        if message.author.bot:
            return

        ctx = await self.get_context(message)
        await self.invoke(ctx)

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, 'on_error'):
            print('has handler')
            return

        newerror = getattr(error, 'original', error)

        ignored = (commands.CommandNotFound)
        if isinstance(newerror, ignored):
            return
        elif isinstance(newerror, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'`{ctx.command}` can not be used in Private Messages.')
            except:
                pass
        elif isinstance(newerror, PlayerNotFoundException):
            return await ctx.send('Player not found on Hypixel!')
        elif isinstance(newerror, commands.MissingRequiredArgument):
            usage = '```%s%s %s```' % (ctx.prefix, ctx.command.qualified_name, ctx.command.signature)
            msg = f"*You're missing the parameter {newerror.param}!*\nUsage of `{ctx.command}`:\n> {usage}"
            return await ctx.send(msg)

        traceback.print_exc()
        print(error)


    async def on_ready(self):
        #self.remove_command('help')
        if not self.cogs:
            await self.load_mods()
        self.logger.info("Bot ready")

        watch = discord.Activity(type=discord.ActivityType.watching, name="Hypixel plus++ (Plus)️")
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

    def run(self):
        super().run(self.settings['discord_token'])


HypixelPlus().run()
