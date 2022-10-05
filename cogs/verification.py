import discord
from config import UNVERIFIED_ROLE, BOARD_UNVERIFIED_ROLE, NEW_MEMBER_ROLE, MEMBER_ROLE
from utils import seconds_to_pretty

# IDs of users whose invitees will be considered to be board joiners
BOARD_INVITERS = [302050872383242240]


class Verification(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role = member.guild.get_role(UNVERIFIED_ROLE)
        await member.add_roles(role)

    @discord.slash_command()
    async def verify(self, ctx: discord.ApplicationContext):
        """Get access to the rest of Teamagers"""
        # Replace unverified role with new member role
        role = ctx.guild.get_role(UNVERIFIED_ROLE)
        await ctx.author.remove_roles(role)

        role = ctx.guild.get_role(NEW_MEMBER_ROLE)
        await ctx.author.add_roles(role)

        time_spent = seconds_to_pretty((discord.utils.utcnow() - ctx.user.joined_at).total_seconds())
        embed = discord.Embed(description="Successfully verified - " + time_spent)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Verification(bot))
