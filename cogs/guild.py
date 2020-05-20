import typing
from datetime import datetime, timedelta

import discord
from discord.ext import commands


class guild(commands.Cog):
    """Guild commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Guild top Exp")
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def top(self, ctx, timeframe: typing.Optional[str] = "0"):
        """
        Displays the guild's top Exp earners. You can view top exp from any day in the past week, or the entire week.
        Usage: `h+top [optional timeframe]`

        Running the command without any timeframe will show the current top GEXP leaderboard.

        **Options for the timeframe:**
        - `week` - displays the leaderboard for GEXP earned in the entire last week
        - `average` - displays the leaderboard for average GEXP earned per day
        - days ago, a number from `1`-`6` - displays the GEXP leaderboard for the specified day
        """

        serv = await self.bot.server_verified(ctx.guild.id)
        gid = serv.get('guildid')
        if serv is None or gid is None:
            return await ctx.send("Please sync and setup your guild first by running `h+setup`!")

        titles = {
            "week": "Top GEXP earned over the entire week",
            "average": "Average GEXP earned per day"
        }

        guild_data = await self.bot.db.guilds.find_one({"guildid": gid})

        try:
            d = datetime.now(tz=self.bot.est) - timedelta(days=int(timeframe))
            timeframe = d.strftime("%Y-%m-%d")
            dispday = d.strftime("%m/%d/%Y")
        except Exception:
            dispday = None

        topdata = guild_data['top'][timeframe]

        desc = ""

        x = 0
        for player in topdata:
            x += 1
            desc += str(x) + ") "
            desc += "*" + player['player']

            discordid = player.get('discord')
            if discordid:
                desc += " (" + ctx.guild.get_member(discordid).mention + ")"

            desc += "* - **"
            desc += str(round(player['xp']))
            desc += "** Guild EXP\n"

        await ctx.send(timeframe)
        await ctx.send(titles)
        await ctx.send(titles.get(timeframe, 'couldn\'t match'))

        embed = discord.Embed(timestamp=datetime.now(tz=self.bot.est), description=desc)
        embed.set_author(name=titles.get(timeframe, "Guild top EXP for " + dispday),
                         icon_url="https://cdns.iconmonstr.com/wp-content/assets/preview/2013/240/iconmonstr-trophy-6.png")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(guild(bot))
