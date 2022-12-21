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
    # The member object could be outdated depending on what method calls this, so verify the member exists
    member = member.guild.get_member(member.id)
    if not member:
        return

    # The guild should be verified by anything that calls this
    new_member_role = member.guild.get_role(NEW_MEMBER_ROLE)
    member_role = member.guild.get_role(MEMBER_ROLE)

    await member.remove_roles(new_member_role)
    await member.add_roles(member_role)


class Verification(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        # invite_id: #uses
        self.invite_cache = {}

        # Run once on startup. Loops are the best option at the moment
        self.member_role_restore.start()

    async def send_welcome(self, member: discord.Member):
        channel = self.bot.get_channel(MAIN_ID)
        await channel.send(f"Everyone say welcome to {member.mention}! <@&{BUDDY_ROLE}>")

    @discord.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return

        if await self.is_board_joiner():
            role = member.guild.get_role(BOARD_UNVERIFIED_ROLE)
        else:
            role = member.guild.get_role(NEW_MEMBER_ROLE)

        await member.add_roles(role)

    @discord.Cog.listener()
    async def on_member_update(self, old_member: discord.Member, new_member: discord.Member):
        # If user has passed membership screening
        if old_member.pending is True and new_member.pending is False:
            # Ensure user has not been sent to board joiner hell
            role = new_member.guild.get_role(BOARD_UNVERIFIED_ROLE)
            if role not in new_member.roles:
                await self.send_welcome(new_member)
                await self.safe_schedule_member_timeout(new_member)

    @discord.slash_command(guild_ids=[GUILD_ID])
    async def verify(self, ctx: discord.ApplicationContext):
        """Get access to the rest of Teamagers"""
        # Replace unverified role with new member role
        role = ctx.guild.get_role(UNVERIFIED_ROLE)
        await ctx.user.remove_roles(role)

        role = ctx.guild.get_role(NEW_MEMBER_ROLE)
        await ctx.user.add_roles(role)

        time_spent = seconds_to_pretty((discord.utils.utcnow() - ctx.user.joined_at).total_seconds())
        embed = discord.Embed(description="Successfully verified - " + time_spent)
        await ctx.respond(embed=embed)

        await self.send_welcome(ctx.user)

        await self.safe_schedule_member_timeout(ctx.user)

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

    async def get_invite_dict(self) -> dict:
        guild = self.bot.get_guild(GUILD_ID)
        invites = await guild.invites()

        cache = {}
        for invite in invites:
            # Only need to track board inviters
            if invite.inviter.id in BOARD_INVITERS:
                cache.update({str(invite.id): invite.uses})

        return cache

    @discord.Cog.listener()
    async def on_ready(self):
        self.invite_cache = await self.get_invite_dict()

    async def is_board_joiner(self) -> bool:
        current_invites = await self.get_invite_dict()

        try:
            for invite, uses in current_invites.items():
                if invite in current_invites:
                    if uses == self.invite_cache[invite] + 1:
                        return True
                else:
                    if uses == 1:
                        return True

            return False
        finally:
            self.invite_cache = current_invites


def setup(bot):
    bot.add_cog(Verification(bot))
