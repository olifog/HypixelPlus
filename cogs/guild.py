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
        Displays the guild's top Exp earners. You can view top exp from any day in the past week, the entire week, or average per day.
        Usage: `h+top [optional timeframe]`

        Running the command without any timeframe will show the current top GEXP leaderboard.

        **Options for the timeframe:**
        - `week` - displays the leaderboard for GEXP earned in the entire last week
        - `average` - displays the leaderboard for average GEXP earned per day
        - days ago, a number from `1`-`6` - displays the GEXP leaderboard for the specified day
        """

        try:
            serv = await self.bot.server_verified(ctx.guild.id)
            gid = serv.serverdata.get('guildid')
            if gid is None:
                raise AttributeError
        except AttributeError:
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
            dispday = "ERROR"

        topdata = guild_data['top'][timeframe]

        desc = ""

        x = 0
        for player in topdata:
            x += 1
            desc += str(x) + ") "
            desc += "*" + player['player']

            discordid = player.get('discord')
            try:
                if discordid:
                    member = ctx.guild.get_member(int(discordid))
                    desc += " (" + member.mention + ")"
            except AttributeError:
                pass

            desc += "* - **"
            desc += str(round(player['xp']))
            desc += "** Guild EXP\n"

        embed = discord.Embed(timestamp=datetime.now(tz=self.bot.est), description=desc)
        embed.set_author(name=titles.get(timeframe, "Guild top EXP for " + dispday),
                         icon_url="https://i.imgur.com/5OA6dzg.png")
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(guild(bot))
