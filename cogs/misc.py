import discord
from discord.ext import commands
from datetime import datetime
import humanize

class misc(commands.Cog):
    """Miscellaneous commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def info(self, ctx):
        """Check bot ping, latency and info"""
        process_time = round(((datetime.utcnow()-ctx.message.created_at).total_seconds())*1000)

        e = discord.Embed(color=discord.Color.gold())
        e.add_field(
            name="**Latency:**",
            value=f"{round(self.bot.latency*1000)}ms"
        )
        e.add_field(
            name="**Process time:**",
            value=f"{process_time}ms",
            inline=False
        )

        uptime = humanize.naturaltime(self.bot.uptime)
        e.add_field(name="Owner:", value="Moose#0064")
        e.add_field(name="Uptime:", value=f"Been up since {uptime}")
        e.add_field(name="WILL BE MORE INFORMATION HERE EVENTUALLY", value="aaaaaaaaaaa")

        e.set_thumbnail(url=ctx.me.avatar_url)
        await ctx.send(embed=e)

    #@commands.command()
    #async def help(self, ctx):
    #    """Help command"""
    #    await ctx.send('Placeholder help command')

    @commands.command()
    async def support(self, ctx):
        """Support the development of the bot!"""
        await ctx.send('give us money please (except not yet we haven\'t set it up yet)')

def setup(bot):
    bot.add_cog(misc(bot))