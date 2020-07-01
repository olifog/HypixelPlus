
import json

from discord.ext import commands

from extras import checks


class dev(commands.Cog):
    """Miscellaneous commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @checks.is_owner()
    async def query(self, ctx, collection, *, query):
        async for data in self.bot.db[collection].find(json.loads(query)):
            await ctx.send(str(data)[:1999])

    @commands.command()
    @checks.is_owner()
    async def remove_element(self, ctx, collection, *, query):
        coll = self.bot.db[collection]
        n = await coll.count_documents({})
        await ctx.send(f'{n} documents before calling delete_many()')
        await self.bot.db[collection].delete_many(json.loads(query))
        await ctx.send(f'{await coll.count_documents({})} documents after')

    @commands.command()
    @checks.is_owner()
    async def devstats(self, ctx):
        players = await self.bot.db.players.count_documents({})
        guilds = await self.bot.db.guilds.count_documents({})
        await ctx.send(f'Tracking {players} players')
        await ctx.send(f'Tracking {guilds} guilds')

        await ctx.send(f'Each player is updated every {players / 1.5} seconds')
        await ctx.send(f'Each guild is updated every {guilds * 10} seconds')

    @commands.command()
    @checks.is_owner()
    async def getrank(self, ctx, name):
        player = await self.bot.hypixelapi.getPlayer(name=name)
        await ctx.send(player.getRank())

    @commands.command()
    @checks.is_owner()
    async def leave(self, ctx):
        await ctx.guild.leave()


def setup(bot):
    bot.add_cog(dev(bot))