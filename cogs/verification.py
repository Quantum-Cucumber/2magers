import discord
from config import UNVERIFIED_ROLE, BOARD_UNVERIFIED_ROLE, NEW_MEMBER_ROLE, MEMBER_ROLE, GUILD_ID, BUDDY_ROLE, MAIN_ID
from utils import seconds_to_pretty

# IDs of users whose invitees will be considered to be board joiners
BOARD_INVITERS = [302050872383242240]


class Verification(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    async def send_welcome(self, member: discord.Member):
        channel = self.bot.get_channel(MAIN_ID)
        await channel.send(f"Everyone say welcome to {member.mention}! <@&{BUDDY_ROLE}>")

    @discord.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        role = member.guild.get_role(UNVERIFIED_ROLE)
        await member.add_roles(role)

    @discord.slash_command(guild_ids=[GUILD_ID])
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

        await self.send_welcome(ctx.user)

    @discord.slash_command(guild_ids=[GUILD_ID])
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

        await self.send_welcome(user)


def setup(bot):
    bot.add_cog(Verification(bot))
