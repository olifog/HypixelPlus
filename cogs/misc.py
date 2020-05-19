from datetime import datetime

import discord
import humanize
from discord.ext import commands


class misc(commands.Cog):
    """Miscellaneous commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Bot info")
    async def info(self, ctx):
        """
        Check the bot's ping, latency and info.
        Usage: `h+info`
        """
        process_time = round(((datetime.utcnow() - ctx.message.created_at).total_seconds()) * 1000)

        e = discord.Embed(color=self.bot.theme)
        e.add_field(
            name="**Latency:**",
            value=f"{round(self.bot.latency * 1000)}ms"
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

    @commands.command(brief="Invite link")
    async def invite(self, ctx):
        """
        Sends the bot's invite link, if you want to invite it to other servers!
        Usage: `h+invite`
        """
        await ctx.send("https://discord.com/api/oauth2/authorize?client_id=706200834198732892&permissions=8&scope=bot")

    @commands.command(brief="Support us!")
    async def support(self, ctx):
        """
        Support the development of the bot!
        Usage: `h+support`
        """
        await ctx.send('give us money please (except not yet we haven\'t set it up yet)')


def setup(bot):
    bot.add_cog(misc(bot))
