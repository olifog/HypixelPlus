import copy

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
        member = self.server.get_member(user['discordid'])

        self.serverdata = await self.bot.db.servers.find_one({"discordid": self.discordid})

        guild_applicable_roles = []
        try:
            for role in self.serverdata['hypixelRoles']:
                guild_applicable_roles.append(role)
        except KeyError:
            pass

        try:
            for role in self.serverdata['guildRoles']:
                guild_applicable_roles.append(role)
        except KeyError:
            pass

        user_roles = copy.copy(member.roles)
        new_roles = []
        try:
            new_roles.append(self.server.get_role(self.serverdata['hypixelRoles'][user['hypixelRank']]))
        except KeyError:
            pass
        try:
            if user['guildid'] == self.serverdata['guildid']:
                new_roles.append(self.server.get_role(self.serverdata['guildRoles'][user['guildRank']]))
        except KeyError:
            pass

        for role in user_roles:
            if role.name not in guild_applicable_roles and role.name[
                                                           8:] not in guild_applicable_roles:  # TODO: remove after making Deprived bot
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
