import asyncio

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
                                                    rank=str(user.get("hypixelRank", "")),
                                                    username=member.name)

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
        - `h+setup names [format]` - specifies how the bot will sync usernames
        - `h+setup roles` - sets up players' rank roles
        - `...`
        """
        await ctx.send("Placeholder")

    @setup.command(brief="Name config", usage="https://i.ibb.co/t2k7D6f/Screenshot-2020-05-17-at-15-05-45.png")
    @commands.guild_only()
    async def names(self, ctx, *, format):
        """
        This specifies how Hypixel+ will format members' names.
        Usage: `h+setup names [format]`

        **Options:**
        - `{ign}` - is replaced with the user's MC username
        - `{level}` - is replaced with the user's Hypixel level, rounded
        - `{rank}` - is replaced with the user's Hypixel rank, without surrounding brackets
        - `{guildRank}` - is replaced with the user's guild rank
        - `{discord}` - is replaced with the user's discord username

        *Note- bots cannot change the nicknames of server owners, so if you own the server your name won't be synced*

        For example, using the command like this-
        `h+setup names [{rank}] {ign}, {guildRank} | {level}`
        Will result in players being formatted like this-
        """

        result = await self.bot.db.servers.update_one({"discordid": ctx.guild.id}, {"$set": {"nameFormat": format}})

        if result.matched_count == 0:
            return await ctx.send("Please sync and setup your server first by running `h+setup`!")

        count = self.bot.db.players.count_documents({"servers": ctx.guild.id})

        await ctx.send(
            f"**Updated the format!**\nThe bot will take ~{count} seconds to fully update all the names in this server.")

    @names.error
    async def names_error(self, ctx, error):
        serv = await self.server_verified(ctx.guild.id)

        if serv is not None:
            newerror = getattr(error, 'original', error)
            curformat = serv.get('nameFormat', "none")

            if isinstance(newerror, commands.MissingRequiredArgument):
                msg = f"Your current naming format is set as `{curformat}`.\n*To change it, please include the format with your command-*"
                embed, pic = await self.bot.cogs['help'].get_command_help_embed(ctx.command.qualified_name)
                return await ctx.send(content=msg, embed=embed, file=pic)

        await self.bot.handle_error(ctx, error)

    async def render_roles(self, roles, index):
        ret = ""

        x = 0
        for name, data in roles.items():
            ret += "\n"

            if x == 0:
                ret += "**Hypixel ranks:**\n"
            elif x == 5:
                ret += "\n**General roles:**\n"
            elif x == 7:
                ret += "\n**Guild ranks:**\n"

            if x == index:
                ret += "<:next:711993456356098049>"
            else:
                ret += ":heavy_minus_sign:"

            ret += name + "- " + data
            x += 1

        return ret

    async def get_mention(self, id, guild):
        role = guild.get_role(id)
        return role.mention if role is not None else "*Not set*"

    @setup.command(brief="Role config")
    @commands.guild_only()
    async def roles(self, ctx):
        """
        This command sets up what roles Hypixel+ will apply to users in your server.
        Usage: `h+setup roles`

        It will give you a menu with all the possible roles that Hypixel+ can apply, including Hypixel ranks, guild ranks, and Verified/Unverified roles.

        **Menu navigation:**
        - *change the selected role with the* <:up:711993208220942428> *and* <:down:711993054613078036> *arrows*
        - *press the* <:add:711993256585461791> *button for the bot to create/sync that role automatically*
        - *press the* <:remove:711993000976449557> *button for the bot to unsync that role*
        - *to sync an existing role, send the @role in the same channel as the menu, with the right role selected in the menu.*
        For example, if you already have an 'MVP+' role, and you don't want the bot to create a new one, do the following:

        *(image here eventually)*
        """
        serv = await self.server_verified(ctx.guild.id)
        if serv is None:
            return await ctx.send("Please sync and setup your server first by running `h+setup`!")

        rolelist = {}
        for rank in serv['hypixelRoles']:
            rolelist[rank] = await self.get_mention(serv['hypixelRoles'][rank], ctx.guild)

        rolelist["Verified"] = await self.get_mention(serv['verifiedRole'], ctx.guild)
        rolelist["Unverified"] = await self.get_mention(serv['unverifiedRole'], ctx.guild)

        id = serv.get("guildid")
        if id is not None:
            guild_data = await self.bot.guilds.find_one({"guildid": id})
            new_ranks = guild_data['ranks']
            update_roles = {}

            for rank in new_ranks:
                discid = serv['guildRoles'].get(rank['name'], 0)
                update_roles[rank['name']] = discid
                rolelist[rank['name']] = discid

            await self.bot.guilds.update_one({"guildid": id}, {"$set": {"guildRoles": update_roles}})

        message = await ctx.send("*Loading...*")
        await message.add_reaction(discord.PartialEmoji(name="up", id=711993208220942428))
        await message.add_reaction(discord.PartialEmoji(name="down", id=711993054613078036))
        await message.add_reaction(discord.PartialEmoji(name="add", id=711993256585461791))
        await message.add_reaction(discord.PartialEmoji(name="remove", id=711993000976449557))

        index = 0

        while True:
            desc = await self.render_roles(rolelist,
                                           index) + "\n\n*Do `h+help setup roles` for help with using this menu!*"
            embed = discord.Embed(colour=self.bot.theme, description=desc)
            embed.set_author(name="Role config",
                             icon_url="https://upload-icon.s3.us-east-2.amazonaws.com/uploads/icons/png/2674342741552644384-512.png")

            await message.edit(content="", embed=embed)

            def reaction_check(reaction, user):
                return user == ctx.author

            def message_check(m):
                return m.author == ctx.author

            done, pending = await asyncio.wait([
                self.bot.wait_for('message', check=message_check),
                self.bot.wait_for('reaction_add', check=reaction_check)
            ], timeout=10, return_when=asyncio.FIRST_COMPLETED)

            data = None

            try:
                data = done.pop().result()
            except Exception:
                pass

            for future in pending:
                future.cancel()

            if data is None:
                await message.edit(content="*Session ended*")
                break

            await ctx.send(data)


def setup(bot):
    bot.add_cog(server(bot))
