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

    async def server_verified(self, discordid):
        async for serv in self.bot.db.servers.find({"discordid": discordid}):
            return serv

    @commands.group(invoke_without_command=True, brief="Server setup")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    async def setup(self, ctx):
        """
        This command will walk you through setting up the Discord server, syncing it with Hypixel.
        Usage: `h+setup`

        To set up individual parts of the server's config, use one of the following subcommands:
            `h+setup names [format]` - specifies how the bot will sync usernames
            `...`
            `...`
        """
        # TODO: Create bot-wide embed system, with timestamp/author icon + formatting + reaction menus
        # TODO: Ask the user whether they want a setup walk-through or whether they just want to setup one thing
        await ctx.send("Placeholder")

    @setup.command(brief="Name config", usage="https://i.ibb.co/t2k7D6f/Screenshot-2020-05-17-at-15-05-45.png")
    @commands.guild_only()
    async def names(self, ctx):
        """
        This specifies how Hypixel+ will format members' names.
        Usage: `h+setup names [format]`

        **Options:**
            `{ign}` - is replaced with the user's MC username
            `{level}` - is replaced with the user's Hypixel level, rounded
            `{rank}` - is replaced with the user's Hypixel rank, without surrounding brackets
            `{guildRank}` - is replaced with the user's guild rank

        For example, using the command like this-
        `h+setup names [{rank}] {ign}, {guildRank} | {level}`
        Will result in players being formatted like this-
        """

        serv = await self.server_verified(ctx.guild.id)
        if serv is None:
            return await ctx.send("Please sync and setup your server first by running `h+setup`!")

        curformat = serv.get('nameFormat', "")
        msg = "Your current name config is set as `" + curformat + "`." if curformat is not None else ""

        menu = discord.Embed(color=discord.Color.darker_grey())

        await ctx.send(msg, embed=menu)


def setup(bot):
    bot.add_cog(server(bot))
