import discord
from discord.ext import tasks
from db import db
import datetime as dt
from config import QOTD_ID

COLOUR = 0x0ff00
EMBED_DESCRIPTION_MAX = 4096

MIDNIGHT_UTC = dt.time(tzinfo=dt.timezone.utc)


class QOTD(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.sender.start()

    qotd_group = discord.SlashCommandGroup(name="qotd", description="QOTD Management Commands")

    @qotd_group.command()
    @discord.default_permissions(manage_messages=True)
    async def add(self, ctx: discord.ApplicationContext, qotd: str,
                  credit: discord.Option(discord.Member, required=False,
                                         description="The user to give credit to for the question")
                  ):
        """Add a QOTD"""
        if not credit:
            credit = ctx.author

        await ctx.defer()

        await db.qotds.insert_one({
            "question": qotd,
            "credit": str(credit.id),
        })

        embed = discord.Embed(colour=COLOUR, title="QOTD Added", description=qotd)
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text=credit.display_name, icon_url=credit.display_avatar.url)

        await ctx.respond(embed=embed)

    @qotd_group.command()
    @discord.default_permissions(manage_messages=True)
    async def list(self, ctx: discord.ApplicationContext):
        """Shows the queue of QOTDs"""
        await ctx.defer()

        cursor = db.qotds.find()

        embed = discord.Embed(colour=COLOUR, title="QOTD Queue:", description="")

        i = 1
        async for qotd in cursor:
            question = qotd["question"]
            line = f"**{i}.** {question}\n\n"
            if len(embed.description) + len(line) <= EMBED_DESCRIPTION_MAX:
                embed.description += line
            else:
                break

            i += 1

        await ctx.respond(embed=embed)

    @tasks.loop(time=MIDNIGHT_UTC)
    async def sender(self):
        channel = self.bot.get_channel(QOTD_ID)

        qotd = await db.qotds.find_one_and_delete({})

        if not qotd:
            embed = discord.Embed(colour=COLOUR, title="There are no new questions in the queue",
                                  description="Go annoy someone to add more.")
            await channel.send(embed=embed)
            return

        question = qotd["question"]
        user_id = int(qotd["credit"])

        embed = discord.Embed(colour=COLOUR, title="Question of the Day")
        embed.description = f"**{question}**"

        member = channel.guild.get_member(user_id)
        if member:
            embed.set_footer(text="By " + member.display_name, icon_url=member.display_avatar.url)

        embed.timestamp = discord.utils.utcnow()

        await channel.send(embed=embed)


def setup(bot):
    bot.add_cog(QOTD(bot))
