import discord
from discord.ext import commands
import asyncio
import base64
import datetime


class player(commands.Cog):
    """Player commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def verify(self, ctx, ign):
        """Verify your Minecraft account in Discord!"""
        pdata = await self.bot.db.players.find_one({'discordid': ctx.author.id})

        if pdata is not None:
            await ctx.send("You're already verified as `" + pdata['displayname'] +
                           "`! Use `h+unverify` to unverify.")
            return

        # Check for illegal characters
        allowed_chars = "abcdefghijklmnopqrstuvwxyz"
        allowed_chars += allowed_chars.upper()
        allowed_chars += "!@#$%^&*()-=_+`~[]{}\\|;:\'\",<.>/?"

        target = str(ctx.author)
        gamer = False
        for char in ctx.author.name:
            if char not in allowed_chars:
                target = base64.b64encode(str(ctx.author))[:3] + '#6969'
                gamer = True
                break

        player = await self.bot.hypixelapi.getPlayer(name=ign)

        try:
            if player.JSON['socialMedia']['links']['DISCORD'] != target:
                raise KeyError

            member = {'discordid': ctx.author.id, 'displayname': ign, 'uuid': player.UUID, 'lastModifiedData': datetime.datetime(2000, 1, 1, 1, 1, 1, 1)}
            await self.bot.db.players.insert_one(member)
            return await ctx.send(f"**{ctx.author.mention} Verified as {ign}! The bot will now take a few minutes to" +
                                  " sync your roles/ign across Discord.**")

        except KeyError:
            pass # If they're a gamer, tell them to verify with the weird thing

        await ctx.send("Go away i haven't written that code yet dumbass")

    @commands.command()
    async def unverify(self, ctx):
        msg = await ctx.send("*Finding user...*")
        player = await self.bot.db.players.find_one({'discordid': ctx.author.id})

        if player is None:
            await msg.edit(content="**You aren't verified! Verify with `h+verify`.**")
            return

        await msg.edit(content=f"*Unverifying your linked account, `{player['displayname']}`...*")

        if player['updating']:
            await asyncio.sleep(0.8)

        await self.bot.db.players.delete_one({'_id': player['_id']})
        await msg.edit(content=f"**Unverified your account, `{player['displayname']}`!**")


def setup(bot):
    bot.add_cog(player(bot))
