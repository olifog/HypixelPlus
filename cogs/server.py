from discord.ext import commands


class server(commands.Cog):
    """Server commands"""

    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(server(bot))
