import discord
from db import db
import datetime as dt
from utils import seconds_to_pretty
from config import GUILD_ID

EMBED_FIELD_LIMIT = 25
COLOUR = 0xff0000

TIER_EXPIRATION = dt.timedelta(days=90)  # 3 Months


def mod_case_embed(ctx: discord.ApplicationContext, case: dict) -> discord.Embed:
    # TODO: Colour
    embed = discord.Embed(colour=COLOUR)
    embed.title = "Case #{} | {}:".format(case["case"], case["type"].title())
    embed.description = case["reason"]

    member = ctx.guild.get_member(int(case["user"]))
    name = member.display_name if member else "User left guild"
    icon = member.display_avatar.url if member else discord.Embed.Empty
    embed.set_author(name=name, icon_url=icon)

    embed.add_field(name="Moderator", value="<@{}>".format(case["mod"]))

    if case["duration"]:
        embed.add_field(name="Duration", value=seconds_to_pretty(case["duration"]))

    if dt.datetime.utcnow() - case["timestamp"] > TIER_EXPIRATION:
        embed.set_footer(text="Case Expired")

    embed.timestamp = case["timestamp"]

    return embed


def user_case_embed(ctx: discord.ApplicationContext, case: dict) -> discord.Embed:
    type_verb = {
        "timeout": "muted in",
        "ban": "banned from",
        "warn": "warned in",
    }

    embed = discord.Embed(colour=COLOUR)
    embed.title = f"You have been {type_verb[case['type']]} {ctx.guild.name}"

    if case["type"] == "note":
        embed.add_field(name="Note", value=case["reason"], inline=False)
    else:
        embed.add_field(name="Reason", value=case["reason"], inline=False)

    if case["duration"]:
        embed.add_field(name="Duration", value=seconds_to_pretty(case["duration"]))

    embed.timestamp = case["timestamp"]
    embed.set_footer(text="Case #" + str(case["case"]))

    return embed


def can_moderate_user(ctx: discord.ApplicationContext, target_user: discord.Member):
    if target_user.bot or ctx.user.id == target_user.id:
        return False
    elif ctx.user.top_role <= target_user.top_role and ctx.user.id != ctx.guild.owner_id:
        return False
    else:
        return True


async def insert_modlog(user: discord.Member, mod: discord.Member, log_type: str, reason: str,
                        duration: dt.timedelta = None):
    if duration:
        duration = duration.total_seconds()

    # Get case number and increment it for the next modlog
    counter = await db.counters.find_one_and_update({"_id": "mod_logs_case"}, {"$inc": {"value": 1}})
    case_number = counter["value"]

    data = {
        "case": case_number,
        "user": str(user.id),
        "mod": str(mod.id),
        "type": log_type,
        "duration": duration,
        "reason": reason,
        "timestamp": discord.utils.utcnow(),
    }

    await db.mod_logs.insert_one(data)

    return data


class Moderation(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def warn(self, ctx: discord.ApplicationContext, user: discord.Member, reason: str):
        """Warn a user"""
        if not can_moderate_user(ctx, user):
            await ctx.respond("You cannot moderate that user", ephemeral=True)
            return

        await ctx.defer()
        case = await insert_modlog(user, ctx.user, "warn", reason)

        # DM User
        user_embed = discord.Embed(colour=COLOUR)
        user_embed.title = f"You have been warned in {ctx.guild.name}"
        user_embed.add_field(name="Reason", value=reason)
        user_embed.timestamp = case["timestamp"]
        user_embed.set_footer(text="Case #" + str(case["case"]))

        try:
            await user.send(embed=user_embed)
            can_dm = True
        except discord.Forbidden:
            can_dm = False

        # Send confirmation
        mod_embed = mod_case_embed(ctx, case)

        if not can_dm:
            mod_embed.set_footer(text="Cannot DM User")

        await ctx.respond(embed=mod_embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def addnote(self, ctx: discord.ApplicationContext, user: discord.Member, note: str):
        """Warn a user"""
        await ctx.defer()
        case = await insert_modlog(user, ctx.user, "note", note)

        mod_embed = mod_case_embed(ctx, case)
        await ctx.respond(embed=mod_embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    @discord.option("units", description="The unit the duration is in", choices=[
        discord.OptionChoice(name="Minutes", value=60),
        discord.OptionChoice(name="Hours", value=60 * 60),
        discord.OptionChoice(name="Days", value=24 * 60 * 60),
    ])
    async def mute(self, ctx: discord.ApplicationContext, user: discord.Member,
                   duration: discord.Option(int, "The duration of the mute"), units: int,
                   reason: discord.Option(required=False)):
        """Mute a user for a period of time"""
        if not can_moderate_user(ctx, user):
            await ctx.respond("You cannot moderate that user", ephemeral=True)
            return

        if duration < 1:
            await ctx.respond("Invalid duration", ephemeral=True)
            return

        duration *= units
        duration = dt.timedelta(seconds=duration)

        if duration > dt.timedelta(days=28):
            await ctx.respond("The max mute length is 28 days", ephemeral=True)
            return

        await ctx.defer()

        # Timeout user
        try:
            await user.timeout_for(duration)
        except discord.Forbidden:
            await ctx.respond("Unable to timeout user")
            return

        case = await insert_modlog(user, ctx.user, "timeout", reason, duration)

        # Send message to user
        user_embed = user_case_embed(ctx, case)

        try:
            await user.send(embed=user_embed)
            can_dm = True
        except discord.Forbidden:
            can_dm = False

        # Send confirmation
        mod_embed = mod_case_embed(ctx, case)

        if not can_dm:
            mod_embed.set_footer(text="Cannot DM User")

        await ctx.respond(embed=mod_embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def unmute(self, ctx: discord.ApplicationContext, user: discord.Member):
        """Unmute a user"""
        if not can_moderate_user(ctx, user):
            await ctx.respond("You cannot moderate that user", ephemeral=True)
            return

        try:
            await user.timeout(None)
        except discord.Forbidden:
            await ctx.respond("Unable to unmute that user")
            return

        embed = discord.Embed(colour=COLOUR, title="User Unmuted")
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        embed.add_field(name="Moderator", value=ctx.author.mention)

        await ctx.respond(embed=embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def unban(self, ctx: discord.ApplicationContext, user_id: str):
        """Unban a user"""
        try:
            user_id = int(user_id)
        except ValueError:
            await ctx.respond("Invalid user ID", ephemeral=True)
            return

        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await ctx.respond("User not found", ephemeral=True)
            return

        try:
            await ctx.guild.unban(user)
        except discord.NotFound:
            embed = discord.Embed(colour=COLOUR, title="User is not banned")
            embed.set_author(name=user.name, icon_url=user.display_avatar.url)
            await ctx.respond(embed=embed)
            return

        embed = discord.Embed(colour=COLOUR, title="User Unbanned")
        embed.set_author(name=user.name, icon_url=user.display_avatar.url)
        embed.add_field(name="Moderator", value=ctx.author.mention)

        await ctx.respond(embed=embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(manage_messages=True)
    async def purge(self, ctx: discord.ApplicationContext, number: int):
        """
        Purge messages in this channel
        """
        if number < 1:
            await ctx.respond("Invalid number of messages", ephemeral=True)
            return

        await ctx.channel.purge(limit=number)

        embed = discord.Embed(colour=COLOUR, title=f"Purged {number} messages")
        embed.timestamp = discord.utils.utcnow()
        await ctx.respond(embed=embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(ban_members=True)
    @discord.option("delete_messages", required=False, choices=[
        discord.OptionChoice("1 Hour", 60 * 60),
        discord.OptionChoice("6 Hours", 6 * 60 * 60),
        discord.OptionChoice("1 Day", 24 * 60 * 60),
        discord.OptionChoice("7 Days", 7 * 24 * 60 * 60),
    ])
    async def ban(self, ctx: discord.ApplicationContext, user: discord.Member,
                  reason: discord.Option(str, required=False), delete_messages: int = 0):
        """Ban a user"""
        if not can_moderate_user(ctx, user):
            await ctx.respond("You cannot moderate that user", ephemeral=True)
            return
        # When banning, the DM will need to be sent first, so perform more checks on the ability to ban
        elif ctx.me.top_role <= user.top_role:
            await ctx.respond("Unable to ban user", ephemeral=True)
            return

        await ctx.defer()

        case = await insert_modlog(user, ctx.user, "ban", reason)

        # DM User

        user_embed = user_case_embed(ctx, case)
        try:
            await user.send(embed=user_embed)
            can_dm = True
        except discord.Forbidden:
            can_dm = False

        # Generate embed here, so we can get the member object once the user has left
        mod_embed = mod_case_embed(ctx, case)

        # Ban user

        try:
            # This is indeed gross, waiting for the library to release a fix
            await ctx.guild.ban(user, delete_message_seconds=delete_messages, delete_message_days=0)
        except discord.Forbidden:
            await ctx.respond("Unable to ban user")
            return

        # Send confirmation

        if not can_dm:
            mod_embed.set_footer(text="Cannot DM User")

        await ctx.respond(embed=mod_embed)


def setup(bot):
    bot.add_cog(Moderation(bot))
