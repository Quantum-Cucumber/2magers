import discord
from db import db
from cogs.moderation import mod_case_embed, can_moderate_user, TIER_EXPIRATION
from utils import seconds_to_pretty
import datetime as dt
from config import GUILD_ID

EMBED_FIELD_LIMIT = 25
COLOUR = 0xff0000


LOG_TYPE_PRETTY = {
    "timeout": "mute",
    "warn": "warning",
    "ban": "ban",
    "note": "note",
}


class Modlogs(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def modlogs(self, ctx: discord.ApplicationContext, user: discord.Member):
        """Displays a user's modlogs"""
        await ctx.defer()

        case_count = await db.mod_logs.count_documents({"user": str(user.id)})
        cases = db.mod_logs.find({"user": str(user.id)}).sort("case", 1)

        # Only get the last 25 entries
        if case_count > EMBED_FIELD_LIMIT:
            cases = cases.skip(case_count - EMBED_FIELD_LIMIT)

        embed = discord.Embed(colour=COLOUR)
        embed.title = f"Modlogs for {user.name}:"

        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)

        if case_count > 0:
            async for case in cases:
                title = "Case #{} | {}".format(case["case"], LOG_TYPE_PRETTY[case["type"]].title())
                description = ""

                if case["type"] != "note":
                    timestamp = case["timestamp"]
                    if dt.datetime.utcnow() - timestamp >= TIER_EXPIRATION:
                        description += "**--EXPIRED--**\n"

                if case["type"] == "note":
                    description += "**Note:** {}\n".format(case["reason"])
                else:
                    description += "**Reason:** {}\n".format(case["reason"])

                if case["duration"]:
                    description += "**Length:** {}\n".format(seconds_to_pretty(case["duration"]))

                description += "**Date:** {}\n".format(discord.utils.format_dt(case["timestamp"], "F"))
                description += "**Moderator:** <@{}>\n".format(case["mod"])

                embed.add_field(name=title, value=description, inline=False)

            if case_count > EMBED_FIELD_LIMIT:
                # TODO - Paginate?
                embed.set_footer(text=f"{case_count - EMBED_FIELD_LIMIT} older cases were omitted")
        else:
            embed.description = "This user has no associated logs"

        await ctx.respond(embed=embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def viewnotes(self, ctx: discord.ApplicationContext, user: discord.User):
        """View all mod notes associated with a user"""
        await ctx.defer()

        query = {
            "user": str(user.id),
            "type": "note",
        }

        case_count = await db.mod_logs.count_documents(query)
        cases = db.mod_logs.find(query).sort("case", 1)

        # Only get the last 25 entries
        if case_count > EMBED_FIELD_LIMIT:
            cases = cases.skip(case_count - EMBED_FIELD_LIMIT)

        embed = discord.Embed(colour=COLOUR)
        embed.title = f"Mod Notes for {user.name}:"

        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)

        if case_count > 0:
            async for case in cases:
                title = "Case #" + str(case["case"])

                description = "**Note:** {}\n".format(case["reason"])

                description += "**Date:** {}\n".format(discord.utils.format_dt(case["timestamp"], "F"))
                description += "**Moderator:** <@{}>\n".format(case["mod"])

                embed.add_field(name=title, value=description, inline=False)

            if case_count > EMBED_FIELD_LIMIT:
                # TODO - Paginate?
                embed.set_footer(text=f"{case_count - EMBED_FIELD_LIMIT} older notes were omitted")
        else:
            embed.description = "This user has no associated notes"

        await ctx.respond(embed=embed)

    @discord.slash_command()
    async def mymodlogs(self, ctx: discord.ApplicationContext):
        """Display the tiers you have received"""
        await ctx.defer()

        query = {
            "user": str(ctx.author.id),
            "type": {"$ne": "note"},
        }

        case_count = await db.mod_logs.count_documents(query)
        cases = db.mod_logs.find(query).sort("case", 1)

        # Only get the last 25 entries
        if case_count > EMBED_FIELD_LIMIT:
            cases = cases.skip(case_count - EMBED_FIELD_LIMIT)

        embed = discord.Embed(colour=COLOUR)
        embed.title = f"Modlogs for {ctx.author.name}:"

        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        if case_count > 0:
            async for case in cases:
                title = "Case #{} | {}".format(case["case"], LOG_TYPE_PRETTY[case["type"]].title())
                description = ""

                timestamp = case["timestamp"]
                if dt.datetime.utcnow() - timestamp >= TIER_EXPIRATION:
                    description += "**--EXPIRED--**\n"

                description += "**Reason:** {}\n".format(case["reason"])

                if case["duration"]:
                    description += "**Length:** {}\n".format(seconds_to_pretty(case["duration"]))

                description += "**Date:** {}\n".format(discord.utils.format_dt(timestamp, "F"))

                embed.add_field(name=title, value=description, inline=False)

            if case_count > EMBED_FIELD_LIMIT:
                # TODO - Paginate?
                embed.set_footer(text=f"{case_count - EMBED_FIELD_LIMIT} older cases were omitted")
        else:
            embed.description = "This user has no associated logs"

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def getcase(self, ctx: discord.ApplicationContext, case_number: int):
        """
        Displays the modlog entry with the corresponding number
        """
        await ctx.defer()
        case = await db.mod_logs.find_one({"case": case_number})

        if not case:
            await ctx.respond("Case not found", ephemeral=True)
            return

        embed = mod_case_embed(ctx, case)
        await ctx.respond(embed=embed)

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.default_permissions(kick_members=True)
    async def removecase(self, ctx: discord.ApplicationContext, case_number: int):
        """Remove a modlog by its case number"""
        await ctx.defer()

        case = await db.mod_logs.find_one({"case": case_number})

        if not case:
            await ctx.respond("Case not found", ephemeral=True)
            return

        member = ctx.guild.get_member(case["user"])
        if member and not can_moderate_user(ctx, member):
            await ctx.respond("You cannot moderate that user", ephemeral=True)
            return

        # Could use the case no. here by this is what _ids are for lol
        await db.mod_logs.delete_one({"_id": case["_id"]})

        embed = mod_case_embed(ctx, case)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Modlogs(bot))
