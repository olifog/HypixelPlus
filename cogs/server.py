import discord
from discord.ext import commands


class LinkedServer(object):  # Object that references a linked Discord server. Basically handles updating the next user
    def __init__(self, bot, discordid):
        self.bot = bot
        self.discordid = discordid
        self.server = self.bot.get_guild(self.discordid)
        self.serverdata = None
        self.queue = []

    async def get_member(self, id):
        member = self.server.get_member(id)
        if member is None:
            try:
                member = await self.server.fetch_member(id)
            except discord.errors.NotFound:
                pass

        return member

    async def update_next_user(self):
        if self.server is None:
            self.server = await self.bot.fetch_guild(self.discordid)

        if len(self.queue) == 0:
            async for user in self.bot.db.players.find({"servers": self.discordid}):
                self.queue.append(user)

        user = self.queue[0]
        self.queue.pop(0)

        member = await self.get_member(user['discordid'])
        if member is None:
            await self.bot.db.players.update_one({'_id': user['_id']}, {"$pull": {"servers": self.server.id}})
            return

        self.serverdata = await self.bot.db.servers.find_one({"discordid": self.discordid})

        guild_applicable_roles = []
        new_roles = []

        hyproles = self.serverdata.get('hypixelRoles')

        if hyproles:
            for role, id in hyproles.items():
                guild_applicable_roles.append(id)

            try:
                new_roles.append(self.server.get_role(hyproles[user['hypixelRank']]))
            except KeyError:
                pass

        guild_applicable_roles.append(self.serverdata.get('unverifiedRole'))
        guild_applicable_roles.append(self.serverdata.get('verifiedRole'))

        try:
            new_roles.append(self.server.get_role(self.serverdata['verifiedRole']))
        except KeyError:
            pass

        try:
            for role, id in self.serverdata['guildRoles'].items():
                guild_applicable_roles.append(id)

            if user['guildid'] == self.serverdata['guildid']:
                new_roles.append(self.server.get_role(self.serverdata['guildRoles'][user['guildRank']]))
        except KeyError:
            pass

        for role in member.roles:
            if role.id not in guild_applicable_roles:
                new_roles.append(role)

        nick = self.serverdata["nameFormat"].format(ign=user['displayname'],
                                                    level=str(round(user['level'], 2)),
                                                    guildRank=user.get('guildRank', ""),
                                                    rank=str(user.get("hypixelRank", "")))

        try:
            await member.edit(roles=new_roles, nick=nick)
        except Exception as e:
            raise e


class server(commands.Cog):
    """Server commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    async def setup(self, ctx):
        # TODO: Create bot-wide embed system, with timestamp/author icon + formatting + reaction menus
        # TODO: Ask the user whether they want a setup walk-through or whether they just want to setup one thing
        await ctx.send("Placeholder")

def setup(bot):
    bot.add_cog(server(bot))
