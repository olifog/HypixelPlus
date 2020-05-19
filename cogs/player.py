import asyncio
import base64
import datetime

from discord.ext import commands


class player(commands.Cog):
    """Player commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(brief="Verifying your account")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def verify(self, ctx, ign):
        """
        This command verifies your Minecraft account within Discord, enabling the bot to sync your name/rank across servers.
        Usage: `h+verify [mc username]`
        """
        pdata = await self.bot.db.players.find_one({'discordid': ctx.author.id})

        if pdata is not None:
            await ctx.send("You're already verified as `" + pdata['displayname'] +
                           "`! Use `h+unverify` to unverify.")
            return

        # Check for illegal characters
        allowed_chars = "abcdefghijklmnopqrstuvwxyz"
        allowed_chars += allowed_chars.upper()

        target = str(ctx.author)
        for char in ctx.author.name:
            if char not in allowed_chars:
                target = (base64.b64encode(str(ctx.author).encode()).decode('utf-8')[:5] + '#6969').strip('+/=-')
                break

        player = await self.bot.hypixelapi.getPlayer(name=ign)

        try:
            daccount = player.JSON['socialMedia']['links']['DISCORD']
        except KeyError:  # They have no linked Discord account
            daccount = None

        if daccount == target or daccount == str(ctx.author):
            member = {'discordid': ctx.author.id, 'displayname': ign, 'uuid': player.UUID,
                      'lastModifiedData': datetime.datetime(2000, 1, 1, 1, 1, 1, 1)}
            servers = []

            for server in self.bot.servers.values():
                for m in server.server.members:
                    if m.id == ctx.author.id:
                        server.empty = False
                        servers.append(server.discordid)

            member['servers'] = servers

            await self.bot.db.players.insert_one(member)
            return await ctx.send(f"**{ctx.author.mention} Verified as {ign}! The bot will now take a few minutes to" +
                                  " sync your roles/ign across Discord.**")

        vmessage = "> Please follow the steps below to verify your current Discord account!"
        vmessage += "\n\n**How to verify:**\n\t*- Connect to* `mc.hypixel.net`"
        vmessage += "\n\t*- Go into your profile (right click on your head)"
        vmessage += "\n\t- Click on \'Social Media\', the Twitter logo"
        vmessage += "\n\t- Click on the Discord logo"
        vmessage += f"\n\t- Copy and paste* `{target}` *into chat"
        vmessage += f"\n\t- Come back to Discord and run* `{ctx.prefix + ctx.command.qualified_name} {ign}` *again!*"

        await ctx.send(vmessage)

    @commands.command(brief="Unverify")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def unverify(self, ctx):
        """
        Unverifies your account on the bot. You can always verify again with `h+verify`.
        Usage: `h+unverify`
        """
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
