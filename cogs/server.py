from discord.ext import commands


class LinkedServer(object):  # Object that references a linked Discord server. Basically handles updating the next user
    def __init__(self, bot, discordid):
        self.bot = bot
        self.discordid = discordid
        self.server = self.bot.get_guild(self.discordid)
        self.serverdata = None
        self.queue = []

    async def update_next_user(self):
        if self.server is None:
            self.server = await self.bot.fetch_guild(self.discordid)

        if len(self.queue) == 0:
            async for user in self.bot.db.players.find({"servers": self.discordid}):
                self.queue.append(user)

        user = self.queue[0]
        self.queue.pop(0)
        member = self.server.get_member(user['discordid'])

        self.serverdata = await self.bot.db.servers.find_one({"discordid": self.discordid})

        guild_applicable_roles = []
        new_roles = []
        try:
            for role, id in self.serverdata['hypixelRoles'].items():
                guild_applicable_roles.append(id)

            new_roles.append(self.server.get_role(self.serverdata['hypixelRoles'][user['hypixelRank']]))
        except KeyError:
            pass

        try:
            guild_applicable_roles.append(self.serverdata['unverifiedRole'])
        except KeyError:
            pass

        try:
            new_roles.append(self.server.get_role(self.serverdata['verifiedRole']))
            guild_applicable_roles.append(self.serverdata['verifiedRole'])
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

        nick = self.serverdata["nameFormat"].format(ign=user['displayname'], level=str(round(user['level'], 2)))

        try:
            await member.edit(roles=new_roles, nick=nick)
        except Exception as e:
            pass


class server(commands.Cog):
    """Server commands"""

    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(server(bot))
