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

    @discord.slash_command()
    async def approve(self, ctx: discord.ApplicationContext, user: discord.Member):
        """Approve a board joiner"""
        # Replace board unverified role with new member role
        role = ctx.guild.get_role(BOARD_UNVERIFIED_ROLE)
        await user.remove_roles(role)

        role = ctx.guild.get_role(NEW_MEMBER_ROLE)
        await user.add_roles(role)

        embed = discord.Embed(title="User Verified")
        embed.set_footer(text=user.display_name, icon_url=user.display_avatar.url)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Verification(bot))
