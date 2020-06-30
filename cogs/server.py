import typing
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext import menus

from extras import checks


class LinkedServer:  # Object that references a linked Discord server. Basically handles updating the next user
    def __init__(self, bot, object):
        self.bot = bot
        self.discordid = object['discordid']
        self.server = self.bot.get_guild(self.discordid)
        self.serverdata = object
        self.queue = []
        self.timeout = 0

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
            if user['guildid'] == self.serverdata['guildid']:
                return self.serverdata["nameFormat"].format(guildRank=user.get('guildRank', ""),
                                                            guildTag=user.get('guildRankTag', ""),
                                                            ign=user['displayname'],
                                                            level=str(round(user['level'], 2)),
                                                            rank=str(user.get("hypixelRank", "")),
                                                            username=member.name)
            else:
                return self.serverdata["nameFormat"].format(guildRank="",
                                                            guildTag="",
                                                            ign=user['displayname'],
                                                            level=str(round(user['level'], 2)),
                                                            rank=str(user.get("hypixelRank", "")),
                                                            username=member.name)
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
            async for user in self.bot.db.players.find({"urgentUpdate": self.discordid}):
                self.queue.append(user)

        try:
            user = self.queue[0]
        except IndexError:
            self.timeout = 60
            return

        self.queue.pop(0)
        return user

    async def update_next_user(self):
        if self.timeout > 0:
            self.timeout -= 1
            return

        self.serverdata = await self.bot.db.guilds.find_one({'_id': self.serverdata['_id']})

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
        except discord.errors.Forbidden:
            pass
        except Exception as e:
            raise e

        await self.bot.db.players.update_one({"_id": user['_id']}, {'$pull': {"urgentUpdate": self.discordid}})


class DummyRole:
    def __init__(self):
        self.mention = "*Not set*"
        self.id = 0


class Roles(menus.Menu):
    def __init__(self, roles):
        super().__init__(timeout=30.0)
        self.roles = roles
        self.index = 0

    async def send_initial_message(self, ctx, channel):
        self.message = await channel.send("*Loading...*")
        await self.render()
        return self.message

    def reaction_check(self, payload):
        if payload.event_type == "REACTION_REMOVE":
            return False
        if payload.message_id != self.message.id:
            return False
        if payload.user_id not in (self.bot.owner_id, self._author_id):
            return False

        return payload.emoji in self.buttons

    async def render(self):
        desc = ""

        x = 0
        for role in self.roles:
            desc += "\n"

            if x == 0:
                desc += "**Hypixel ranks:**\n"
            elif x == 9:
                desc += "\n**Verified role:**\n"
            elif x == 10:
                desc += "\n**Guild ranks:**\n"

            if x == self.index:
                desc += "<:next:711993456356098049>"
            else:
                desc += ":heavy_minus_sign:"

            desc += role[0] + "- " + role[1].mention
            x += 1

        embed = discord.Embed(colour=discord.Colour(15120192), description=desc)
        embed.set_author(name="Role config", icon_url="https://i.imgur.com/7PlbbFL.png")

        return await self.message.edit(content="", embed=embed)

    @menus.button('<:up:711993208220942428>')
    async def do_up(self, payload):
        self.index = (self.index - 1) % len(self.roles)
        await self.render()
        await self.message.remove_reaction(payload.emoji, self.ctx.author)

    @menus.button('<:down:711993054613078036>')
    async def do_down(self, payload):
        self.index = (self.index + 1) % len(self.roles)
        await self.render()
        await self.message.remove_reaction(payload.emoji, self.ctx.author)

    @menus.button('<:add:711993256585461791>')
    async def do_add(self, payload):
        current_role = self.roles[self.index]

        if current_role[1].mention == "*Not set*":
            colour = self.bot.rolecolours.get(current_role[0], discord.Colour.default())
            newrole = await self.ctx.guild.create_role(name=current_role[0], colour=colour)
            current_role[1] = newrole
        else:
            await self.ctx.send("There's already a role synced for that selection!", delete_after=5)

        await self.render()
        await self.message.remove_reaction(payload.emoji, self.ctx.author)

    @menus.button('<:remove:711993000976449557>')
    async def do_remove(self, payload):
        current_role = self.roles[self.index]

        if current_role[1].mention == "*Not set*":
            await self.ctx.send("There's no role synced there to remove!", delete_after=5)
        else:
            await current_role[1].delete()
            current_role[1] = DummyRole()

        await self.render()
        await self.message.remove_reaction(payload.emoji, self.ctx.author)

    @menus.button('<:yes:712303922764578886>')
    async def do_done(self, payload):
        self.stop()

    async def message_input(self, message):
        await message.delete()

        if self.roles[self.index][1].mention == "*Not set*":
            try:
                self.roles[self.index][1] = message.role_mentions[0]
                await self.render()
            except KeyError:
                pass
        else:
            await self.ctx.send("There's already a role synced for that selection!", delete_after=5)

    async def prompt(self, ctx):
        await self.start(ctx, wait=True)
        await self.message.edit(content="*Session ended*")
        return self.roles


class server(commands.Cog):
    """Server commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):  # if server and new user are verified, add server id to their db entry
        if member.guild.id in self.bot.servers:
            await self.bot.db.players.update_one({'discordid': member.id}, {
                '$push': {"urgentUpdate": member.guild.id, "servers": member.guild.id}})

    @commands.Cog.listener()
    async def on_member_remove(self, member):  # if server and user are verified, remove server id from their db entry
        if member.guild.id in self.bot.servers:
            await self.bot.db.players.update_one({'discordid': member.id}, {
                '$pull': {"urgentUpdate": member.guild.id, "servers": member.guild.id}})

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles or before.nick != after.nick:
            await self.bot.db.players.update_one({'discordid': after.id}, {"$push": {"urgentUpdate": after.guild.id}})

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        if str(before) != str(after):
            await self.bot.db.players.update_one({'discordid': after.id}, {"$set": {"discordName": str(after)}})

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):  # if the guild was verified delete it from db
        await self.bot.db.guilds.delete_many({'discordid': guild.id})
        del self.bot.servers[guild.id]

    @commands.group(invoke_without_command=True, brief="Server setup")
    @commands.cooldown(1, 10, commands.BucketType.user)
    @checks.serverowner_or_permissions(manage_guild=True)
    async def setup(self, ctx):
        """
        This command will walk you through setting up the Discord server, syncing it with Hypixel.
        Usage: `h+setup`

        To set up individual parts of the server's config, use one of the following subcommands:
        - `h+setup names [format]` - specifies how the bot will sync usernames
        - `h+setup roles` - sets up players' rank roles
        - `h+setup guild [Guild name] - links a Hypixel guild to the Discord server`
        """
        current_guild = await self.bot.db.guilds.find_one({'discordid': ctx.guild.id})

        if current_guild is not None:
            return await ctx.send("This Discord server has already been setup!")

        msg = await ctx.send("*Setting up...*")

        insert = {'guildid': None,
                  'updating': False,
                  'lastModifiedData': datetime(2000, 1, 1, 1, 1, 1, 1),
                  'discordid': ctx.guild.id,
                  'nameFormat': None,
                  'roles': {'verifiedRole': 0,
                            'hypixelRoles': {
                                'VIP': 0,
                                'VIP+': 0,
                                'MVP': 0,
                                'MVP+': 0,
                                'MVP++': 0,
                                'Hypixel Helper': 0,
                                'Youtuber': 0,
                                'Hypixel Moderator': 0,
                                'Hypixel Admin': 0
                            }}}

        await self.bot.db.guilds.insert_one(insert)
        self.bot.servers[ctx.guild.id] = LinkedServer(self.bot, insert)

        await msg.edit(content="Done!")
        await ctx.send("To set up the bot's linking features, use the rest of the setup subcommands:\n" +
                       "- `h+setup names [format]` - specifies how the bot will sync usernames\n" +
                       "- `h+setup roles` - sets up players' rank roles\n" +
                       "- `h+setup guild [Guild name]` - links a Hypixel guild to the Discord server")

    @setup.command(brief="Name config", usage="./data/name_config_help.png")
    @checks.serverowner_or_permissions(manage_guild=True)
    async def names(self, ctx, *, format):
        """
        This specifies how Hypixel+ will format members' names.
        Usage: `h+setup names [format]`

        **Options:**
        - `{ign}` - is replaced with the user's MC username
        - `{level}` - is replaced with the user's Hypixel level, rounded
        - `{rank}` - is replaced with the user's Hypixel rank, without surrounding brackets
        - `{guildRank}` - is replaced with the user's guild rank (if th)
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

        result = await self.bot.db.players.update_many({"servers": ctx.guild.id},
                                                       {"$push": {"urgentUpdate": ctx.guild.id}})
        self.bot.servers[ctx.guild.id].timeout = 0

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

    async def get_optional_role(self, id, guild):
        role = guild.get_role(id)
        return role if role is not None else DummyRole()

    @setup.command(brief="Role config", usage="./data/role_config_help.png")
    @checks.serverowner_or_permissions(manage_guild=True)
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

        roleindexes = []

        rolelist = []
        for rank in roles['hypixelRoles']:
            rolelist.append([rank, await self.get_optional_role(roles['hypixelRoles'][rank], ctx.guild)])
            roleindexes.append(rank)

        rolelist.append(["Verified", await self.get_optional_role(roles['verifiedRole'], ctx.guild)])
        roleindexes.append("Verified")

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
                rolelist.append([rank['name'], await self.get_optional_role(discid, ctx.guild)])
                roleindexes.append(rank['name'])

        rolelist = await Roles(rolelist).prompt(ctx)

        update_roles['verifiedRole'] = rolelist[roleindexes.index('Verified')][1].id

        hyproles = {}
        for rank in roles['hypixelRoles']:
            hyproles[rank] = rolelist[roleindexes.index(rank)][1].id
        update_roles['hypixelRoles'] = hyproles

        if id is not None:
            for rank in update_roles['guildRoles']:
                update_roles['guildRoles'][rank] = rolelist[roleindexes.index(rank)][1].id

        await self.bot.db.guilds.update_one({"_id": serv.serverdata["_id"]}, {"$set": {"roles": update_roles}})
        result = await self.bot.db.players.update_many({"servers": ctx.guild.id},
                                                       {"$push": {"urgentUpdate": ctx.guild.id}})
        self.bot.servers[ctx.guild.id].timeout = 0

        await ctx.send(
            f"**Updated role settings!**\nThe bot will take ~{result.matched_count} seconds to fully update all the users in this server")

    async def get_guild_owner(self, guild):
        for member in guild.JSON['members']:
            if member['rank'] == "Guild Master" or member['rank'] == "GUILDMASTER":
                return member

    @setup.command(brief="Link your Hypixel Guild")
    @checks.serverowner_or_permissions(manage_guild=True)
    async def guild(self, ctx, guildname: typing.Optional[str]):
        """
        This command links your Hypixel guild to the Discord server this command is sent in- you have to own the guild + be an admin in the server to link/unlink it!
        Usage: `h+setup guild [Guild name]`

        Linking your Hypixel guild enables things like synced guild roles, guild ranks in name format, viewing top GEXP, and many more future features.

        To unlink your Hypixel guild, use this command without any guild name, just `h+setup guild`
        """

        user = await self.bot.db.players.find_one({'discordid': ctx.author.id})

        if user is None:
            return await ctx.send("Please link your account first with `h+link`!")

        current_guild = await self.bot.db.guilds.find_one({'discordid': ctx.guild.id})

        if guildname is None:
            if current_guild is None:
                return await ctx.send("This server hasn't been setup yet! Set it up with `h+setup`!")

            try:
                if current_guild['guildid'] is None:
                    raise KeyError
            except KeyError:
                return await ctx.send(
                    "This server doesn't have any guild linked to unlink!\nLink one by using the command like this: `h+setup guild [Guild name]`")

            hypguild = await self.bot.hypixelapi.getGuild(id=current_guild['guildid'])
            owner = await self.get_guild_owner(hypguild)

            if owner['uuid'] == user['uuid']:
                await self.bot.db.guilds.update_one({'discordid': ctx.guild.id}, {
                    "$set": {"guildid": None, "guildName": None, "guildRanks": [], "top": [], "members": []}})
                await ctx.send("Guild unlinked!")
            else:
                return await ctx.send("You aren't the Guild Master of that guild, so you can't unlink it. Sorry!")
        else:
            test_guild = await self.bot.db.guilds.find_one({'guildName': guildname})

            if test_guild is not None:
                return await ctx.send(
                    "That guild is already linked to a server. Unlink it by using this command without any guild name!")

            hypguild = await self.bot.hypixelapi.getGuild(name=guildname)

            try:
                owner = await self.get_guild_owner(hypguild)
            except Exception:
                return await ctx.send("Sorry, I couldn't find that guild name on Hypixel.")

            if owner['uuid'] == user['uuid']:
                await self.bot.db.guilds.update_one({'discordid': ctx.guild.id},
                                                    {"$set": {"guildid": hypguild.JSON['_id']}})
                await ctx.send("Guild linked!")
            else:
                await ctx.send("You aren't the Guild Master of that guild, so you can't link it. Sorry!")


def setup(bot):
    bot.add_cog(server(bot))
