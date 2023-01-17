import discord
from discord.ext import tasks
from db import db
import datetime as dt
from config import QOTD_ID, GUILD_ID, QOTD_ROLE

COLOUR = 0x0ff00
EMBED_DESCRIPTION_MAX = 4096

MIDNIGHT_UTC = dt.time(tzinfo=dt.timezone.utc)


class QOTD(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.sender.start()

    qotd_group = discord.SlashCommandGroup(name="qotd", description="QOTD Management Commands",
                                           guild_ids=[GUILD_ID],
                                           default_member_permissions=discord.Permissions(manage_messages=True))

    @qotd_group.command()
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
        remaining = await db.qotds.count_documents({})

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
            embed.set_footer(text=f"By {member.display_name} | {remaining} questions in queue",
                             icon_url=member.display_avatar.url)

        embed.timestamp = discord.utils.utcnow()

        await channel.send(f"<@&{QOTD_ROLE}>", embed=embed)

    @qotd_group.command(guild_ids=[GUILD_ID])
    async def force(self, ctx: discord.ApplicationContext):
        """Force a QOTD to send"""
        try:
            await self.sender()
        except discord.DiscordException as e:
            await ctx.respond(f"QOTD failed with the following error:\n```{e}```\n<@{self.bot.owner_id}>")
        else:
            self.sender.restart()

            next_iter = discord.utils.format_dt(self.sender.next_iteration, "F")
            embed = discord.Embed(title="--Debug--",
                                  description=f"Task running: {self.sender.is_running()}\n"
                                              f"Task failed: {self.sender.failed}\nNext QOTD: {next_iter}")
            await ctx.respond("Sent", embed=embed)


def setup(bot):
    bot.add_cog(QOTD(bot))
