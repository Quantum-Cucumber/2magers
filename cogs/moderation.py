import discord
from db import db
import datetime as dt

EMBED_FIELD_LIMIT = 25
COLOUR = 0xff0000


def seconds_to_pretty(seconds: int):
    # Approximations - Meant to be readable for humans so making sense is better than accuracy
    units = {
        "year": 365 * 24 * 60 * 60,
        "month": 30 * 24 * 60 * 60,
        "day": 24 * 60 * 60,
        "hour": 60 * 60,
        "minute": 60,
        "second": 1,
    }

    output = ""

    remainder = seconds
    for unit, duration in units.items():
        value, remainder = divmod(remainder, duration)

        if value > 1:
            output += f"{value} {unit}s, "
        elif value == 1:
            output += f"{value} {unit}, "

    return output.rstrip(", ")


def case_to_embed(ctx: discord.ApplicationContext, case: dict) -> discord.Embed:
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
        embed.add_field(name="Duration", value="{}s".format(seconds_to_pretty(case["duration"])))

    embed.timestamp = case["timestamp"]

    return embed


class Moderation(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command()
    @discord.default_permissions(kick_members=True)
    async def getcase(self, ctx: discord.ApplicationContext, case_number: int):
        """
        Displays the modlog entry with the corresponding number
        """
        await ctx.defer()
        case = await db.mod_logs.find_one({"case": case_number})

        if not case:
            await ctx.respond("Case not found")
            return

        embed = case_to_embed(ctx, case)
        await ctx.respond(embed=embed)

    @discord.slash_command()
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
        embed.title = f"Modlogs for {user.display_name}:"

        embed.set_author(name=user.name, icon_url=user.display_avatar.url)

        if case_count > 0:
            async for case in cases:
                title = "Case {}: {}".format(case["case"], case["type"].title())
                description = "**Reason:** {}\n".format(case["reason"])

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

    @discord.slash_command()
    @discord.default_permissions(kick_members=True)
    async def removecase(self, ctx: discord.ApplicationContext, case_number: int):
        """Remove a modlog by its case number"""
        await ctx.defer()

        case = await db.mod_logs.find_one({"case": case_number})

        if not case:
            await ctx.respond("Case not found")
            return

        # Could use the case no. here by this is what _ids are for lol
        await db.mod_logs.delete_one({"_id": case["_id"]})

        embed = case_to_embed(ctx, case)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Moderation(bot))
