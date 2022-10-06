import discord
from discord.ext import tasks
from config import UNVERIFIED_ROLE, BOARD_UNVERIFIED_ROLE, NEW_MEMBER_ROLE, MEMBER_ROLE, GUILD_ID, BUDDY_ROLE, MAIN_ID
from utils import seconds_to_pretty
import asyncio
from db import db
import datetime as dt

MEMBER_TIMEOUT = 24 * 60 * 60  # 24h

PENDING_TYPE = "member_role"

# IDs of users whose invitees will be considered to be board joiners
BOARD_INVITERS = [
    302050872383242240,  # Disboard Bot
]


async def assign_member_role(member: discord.Member):
    # The guild should be verified by anything that calls this
    new_member_role = member.guild.get_role(NEW_MEMBER_ROLE)
    member_role = member.guild.get_role(MEMBER_ROLE)

    await member.remove_roles(new_member_role)
    await member.add_roles(member_role)


class Verification(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        # Run once on startup. Loops are the best option at the moment
        self.member_role_restore.start()

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

        await self.safe_schedule_member_timeout(ctx.author)

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

        await self.safe_schedule_member_timeout(user)

    async def safe_schedule_member_timeout(self, member: discord.Member):
        # Log to database to ensure role is added if bot shuts down
        result = await db.pending.insert_one({
            "type": PENDING_TYPE,
            "user": str(member.id),
            "timestamp": discord.utils.utcnow() + dt.timedelta(seconds=MEMBER_TIMEOUT)
        })
        pending_entry_id = result.inserted_id

        await self.member_role_timeout(member, MEMBER_TIMEOUT)

        # Clear the pending entry as roles have been modified
        await db.pending.delete_one({"_id": pending_entry_id})

    async def member_role_timeout(self, member: discord.Member, timeout: int):
        await asyncio.sleep(timeout)
        await self.bot.wait_until_ready()

        await assign_member_role(member)

    @tasks.loop(count=1)
    async def member_role_restore(self):
        """Load all pending member role assignments and process them"""
        cursor = db.pending.find({
            "type": PENDING_TYPE,
        })

        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(GUILD_ID)

        async for entry in cursor:
            member = guild.get_member(int(entry["user"]))

            if not member:  # User has likely left the guild, so remove entry and move on
                await db.pending.delete_one({"_id": entry["_id"]})

            elif entry["timestamp"] <= dt.datetime.utcnow():  # Timestamp is in the past
                await assign_member_role(member)
                await db.pending.delete_one({"_id": entry["_id"]})

            else:  # Timestamp is in the future
                # Schedule
                # Create its own function to delete the entry when the timeout completes
                asyncio.create_task(self.schedule_completion(entry, member))

    async def schedule_completion(self, entry: dict, member: discord.Member):
        """Runs the timeout for the remaining time, then deletes the pending entry"""
        timeout = entry["timestamp"] - dt.datetime.utcnow()
        await self.member_role_timeout(member, timeout.total_seconds())

        await db.pending.delete_one({"_id": entry["_id"]})


def setup(bot):
    bot.add_cog(Verification(bot))
