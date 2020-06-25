import asyncio

import discord
from discord.ext import commands

from extras import checks


class LinkedServer:  # Object that references a linked Discord server. Basically handles updating the next user
    def __init__(self, bot, object):
        self.bot = bot
        self.discordid = object['discordid']
        self.server = self.bot.get_guild(self.discordid)
        self.serverdata = object
        self.queue = []
        self.empty = False

    async def get_member(self, id):
        member = self.server.get_member(id)
        if member is None:
            try:
                member = await self.server.fetch_member(id)
            except discord.errors.NotFound:
                pass

        return member

    async def get_name(self, user, member):
        try:
            return self.serverdata["nameFormat"].format(ign=user['displayname'],
                                                        level=str(round(user['level'], 2)),
                                                        guildRank=user.get('guildRank', ""),
                                                        rank=str(user.get("hypixelRank", "")),
                                                        username=member.name,
                                                        guildTag=user.get('guildRankTag', ""))
        except KeyError:
            return member.nick

    async def get_roles(self, user, member):
        guild_applicable_roles = []
        new_roles = []

        roles = self.serverdata.get('roles')

        if roles is None:
            return member.roles

        hyproles = roles.get('hypixelRoles')

        for role, id in hyproles.items():
            if id != 0:
                guild_applicable_roles.append(id)

        try:
            new_roles.append(self.server.get_role(hyproles[user['hypixelRank']]))
        except KeyError:
            pass

        guild_applicable_roles.append(roles.get('verifiedRole'))

        try:
            new_roles.append(self.server.get_role(roles.get('verifiedRole')))
        except KeyError:
            pass

        try:
            for role, id in roles['guildRoles'].items():
                guild_applicable_roles.append(id)

            if user['guildid'] == self.serverdata['guildid']:
                new_roles.append(self.server.get_role(roles['guildRoles'][user['guildRank']]))
        except KeyError:
            pass

        for role in member.roles:
            if role.id not in guild_applicable_roles:
                new_roles.append(role)

        return new_roles

    async def get_next_user(self):
        if self.server is None:
            self.server = await self.bot.fetch_guild(self.discordid)

        if len(self.queue) == 0:
            async for user in self.bot.db.players.find({"servers": self.discordid, "urgentUpdate": True}):
                self.queue.append(user)

        try:
            user = self.queue[0]
        except IndexError:
            self.empty = True
            return

        self.queue.pop(0)
        return user

    async def update_next_user(self):
        if self.empty:
            return

        user = await self.get_next_user()
        if user is None:
            return

        member = await self.get_member(user['discordid'])
        if member is None:
            return

        roles = await self.get_roles(user, member)
        nick = await self.get_name(user, member)

        try:
            await member.edit(roles=[x for x in roles if x is not None], nick=nick[:32])
            await self.bot.db.players.update_one({"_id": user['_id']}, {'$set': {"urgentUpdate": False}})
        except discord.errors.Forbidden:
            pass
        except Exception as e:
            raise e


class DummyRole:
    def __init__(self):
        self.mention = "*Not set*"
        self.id = 0


class server(commands.Cog):
    """Server commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):  # if server and new user are verified, add server id to their db entry
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):  # if server and user are verified, remove server id from their db entry
        pass

    @commands.Cog.listener()
    async def on_member_update(self, before,
                               after):  # check audit log- if it was by bot, ignore, if it wasn't nickname/roles, ignore, otherwise revert
        pass

    @commands.Cog.listener()
    async def on_user_update(self, before,
                             after):  # when a username/discrim updates, make sure to update user's discord name in db
        pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):  # if the guild was verified delete it from db
        pass

    @commands.group(invoke_without_command=True, brief="Server setup")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.guild_only()
    @checks.serverowner_or_permissions(manage_server=True)
    async def setup(self, ctx):
        """
        This command will walk you through setting up the Discord server, syncing it with Hypixel.
        Usage: `h+setup`

        To set up individual parts of the server's config, use one of the following subcommands:
        - `h+setup names [format]` - specifies how the bot will sync usernames
        - `h+setup roles` - sets up players' rank roles
        - `...`
        """

        # Make sure to create empty roles list, empty nameFormat

        await ctx.send("Placeholder")

    @setup.command(brief="Name config", usage="./data/name_config_help.png")
    @commands.guild_only()
    @checks.serverowner_or_permissions(manage_server=True)
    async def names(self, ctx, *, format):
        """
        This specifies how Hypixel+ will format members' names.
        Usage: `h+setup names [format]`

        **Options:**
        - `{ign}` - is replaced with the user's MC username
        - `{level}` - is replaced with the user's Hypixel level, rounded
        - `{rank}` - is replaced with the user's Hypixel rank, without surrounding brackets
        - `{guildRank}` - is replaced with the user's guild rank
        - `{guildTag}` - is replaced with the user's guild rank tag
        - `{username}` - is replaced with the user's discord username

        *Note- bots cannot change the nicknames of server owners, so if you own the server your name won't be synced*

        For example, using the command like this-
        `h+setup names [{rank}] {ign}, {guildRank} | {level}`
        Will result in players being formatted like this-
        """

        result = await self.bot.db.guilds.update_one({"discordid": ctx.guild.id}, {"$set": {"nameFormat": format}})

        if result.matched_count == 0:
            return await ctx.send("Please sync and setup your server first by running `h+setup`!")

        self.bot.servers[ctx.guild.id].serverdata['nameFormat'] = format
        result = await self.bot.db.players.update_many({"servers": ctx.guild.id}, {"$set": {"urgentUpdate": True}})

        await ctx.send(
            f"**Updated the format!**\nThe bot will take ~{result.matched_count} seconds to fully update all the names in this server.")

    @names.error
    async def names_error(self, ctx, error):
        serv = await self.bot.server_verified(ctx.guild.id)

        if serv is not None:
            newerror = getattr(error, 'original', error)
            curformat = serv.serverdata.get('nameFormat', "none")

            if isinstance(newerror, commands.MissingRequiredArgument):
                msg = f"Your current naming format is set as `{curformat}`.\n*To change it, please include the format with your command-*"
                embed, pic = await self.bot.cogs['help'].get_command_help_embed(ctx.command.qualified_name)
                return await ctx.send(content=msg, embed=embed, file=pic)

        await self.bot.handle_error(ctx, error)

    async def render_roles(self, roles, index, hypranks):
        ret = ""

        x = 0
        for name, role in roles.items():
            ret += "\n"

            if x == 0:
                ret += "**Hypixel ranks:**\n"
            elif x == hypranks:
                ret += "\n**Verified role:**\n"
            elif x == hypranks + 1:
                ret += "\n**Guild ranks:**\n"

            if x == index:
                ret += "<:next:711993456356098049>"
            else:
                ret += ":heavy_minus_sign:"

            ret += name + "- " + role.mention
            x += 1

        return ret

    async def get_optional_role(self, id, guild):
        role = guild.get_role(id)
        return role if role is not None else DummyRole()

    @setup.command(brief="Role config", usage="./data/role_config_help.png")
    @commands.guild_only()
    @checks.serverowner_or_permissions(manage_server=True)
    async def roles(self, ctx):
        """
        This command sets up what roles Hypixel+ will apply to users in your server.
        Usage: `h+setup roles`

        It will give you a menu with all the possible roles that Hypixel+ can apply, including Hypixel ranks, guild ranks, and a Verified role.

        **Menu navigation:**
        - *change the selected role with the* <:up:711993208220942428> *and* <:down:711993054613078036> *arrows*
        - *press the* <:add:711993256585461791> *button for the bot to create/sync that role automatically*
        - *press the* <:remove:711993000976449557> *button for the bot to unsync that role*
        - *to sync an existing role, send the @role in the same channel as the menu, with the right role selected in the menu.*

        For example, if you already have an 'MVP+' role, and you don't want the bot to create a new one, do the following:
        """
        serv = await self.bot.server_verified(ctx.guild.id)
        if serv is None:
            return await ctx.send("Please sync and setup your server first by running `h+setup`!")

        roles = serv.serverdata['roles']

        rolelist = {}
        for rank in roles['hypixelRoles']:
            rolelist[rank] = await self.get_optional_role(roles['hypixelRoles'][rank], ctx.guild)

        rolelist["Verified"] = await self.get_optional_role(roles['verifiedRole'], ctx.guild)

        update_roles = {}

        id = serv.serverdata.get("guildid")
        if id is not None:
            new_ranks = serv.serverdata['guildRanks']

            update_roles['guildRoles'] = {}

            for rank in new_ranks:
                try:
                    discid = roles['guildRoles'].get(rank['name'], 0)
                except KeyError:
                    discid = 0
                update_roles['guildRoles'][rank['name']] = discid
                rolelist[rank['name']] = await self.get_optional_role(discid, ctx.guild)

        rolekeys = list(rolelist.keys())
        rolevals = list(rolelist.values())

        message = await ctx.send("*Loading...*")
        await message.add_reaction(discord.PartialEmoji(name="up", id=711993208220942428))
        await message.add_reaction(discord.PartialEmoji(name="down", id=711993054613078036))
        await message.add_reaction(discord.PartialEmoji(name="add", id=711993256585461791))
        await message.add_reaction(discord.PartialEmoji(name="remove", id=711993000976449557))
        await message.add_reaction(discord.PartialEmoji(name="yes", id=712303922764578886))

        index = 0

        while True:
            desc = await self.render_roles(rolelist,
                                           index,
                                           9) + "\n\n*Do `h+help setup roles` for help with using this menu!*"
            embed = discord.Embed(colour=self.bot.theme, description=desc)
            embed.set_author(name="Role config",
                             icon_url="https://i.imgur.com/7PlbbFL.png")

            await message.edit(content="", embed=embed)

            def reaction_check(reaction, user):
                return user == ctx.author

            def message_check(m):
                return m.author == ctx.author and len(m.role_mentions) == 1

            done, pending = await asyncio.wait([
                self.bot.wait_for('message', check=message_check),
                self.bot.wait_for('reaction_add', check=reaction_check)
            ], timeout=20, return_when=asyncio.FIRST_COMPLETED)

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

            if isinstance(data, discord.Message):
                await data.delete()
                if rolevals[index].mention == "*Not set*":
                    role = data.role_mentions[0]
                    rolelist[rolekeys[index]] = role
                    rolekeys = list(rolelist.keys())
                    rolevals = list(rolelist.values())
                else:
                    await ctx.send("There's already a role synced for that selection!", delete_after=5)
            else:
                await message.remove_reaction(data[0], data[1])
                reaction = data[0]
                try:
                    reaction = reaction.emoji.name
                except AttributeError:
                    reaction = reaction.emoji

                if reaction == "up":
                    index -= 1
                elif reaction == "down":
                    index += 1
                elif reaction == "add":
                    if rolevals[index].mention == "*Not set*":
                        colour = self.bot.rolecolours.get(rolekeys[index], discord.Colour.default())
                        newrole = await ctx.guild.create_role(name=rolekeys[index], colour=colour)
                        rolelist[rolekeys[index]] = newrole
                        rolekeys = list(rolelist.keys())
                        rolevals = list(rolelist.values())
                    else:
                        await ctx.send("There's already a role synced for that selection!", delete_after=5)
                elif reaction == "remove":
                    if rolevals[index].mention == "*Not set*":
                        await ctx.send("There's no role synced there to remove!", delete_after=5)
                    else:
                        await rolelist[rolekeys[index]].delete()
                        rolelist[rolekeys[index]] = DummyRole()
                        rolekeys = list(rolelist.keys())
                        rolevals = list(rolelist.values())
                elif reaction == "yes":
                    await message.edit(content="*Session ended*")
                    break

                index %= len(rolelist)

        update_roles['verifiedRole'] = rolelist['Verified'].id

        hyproles = {}
        for rank in roles['hypixelRoles']:
            hyproles[rank] = rolelist[rank].id
        update_roles['hypixelRoles'] = hyproles

        if id is not None:
            for rank in update_roles['guildRoles']:
                update_roles['guildRoles'][rank] = rolelist[rank].id

        await self.bot.db.guilds.update_one({"_id": serv.serverdata["_id"]}, {"$set": {"roles": update_roles}})
        self.bot.servers[ctx.guild.id].serverdata['roles'] = update_roles
        result = await self.bot.db.players.update_many({"servers": ctx.guild.id}, {"$set": {"urgentUpdate": True}})

        await ctx.send(
            f"**Updated role settings!**\nThe bot will take ~{result.matched_count} seconds to fully update all the users in this server")


def setup(bot):
    bot.add_cog(server(bot))
