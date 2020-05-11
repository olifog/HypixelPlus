from discord.ext import commands


class LinkedServer:  # Object that references a linked Discord server. Basically handles updating the next user
    def __init__(self, bot, discordid):
        self.bot = bot
        self.discordid = discordid
        self.server = self.bot.get_guild(self.discordid)
        self.queue = []

    async def update_next_user(self):
        if self.server is None:
            self.server = self.bot.get_guild(self.discordid)

        if len(self.queue) == 0:
            return  # Get list of users to update, put it in queue

        player = self.queue[0]


class server(commands.Cog):
    """Server commands"""

    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(server(bot))
