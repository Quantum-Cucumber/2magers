import discord
from discord.ext import commands
from utils import BOOL_OPTIONS


class Embed(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command()
    async def embed(self, ctx: discord.ApplicationContext,
                    channel: discord.Option(discord.TextChannel, required=False),
                    title: discord.Option(str, required=False),
                    description: discord.Option(str, required=False),
                    image_url: discord.Option(str, required=False),
                    colour: discord.Option(str, required=False),
                    timestamp: discord.Option(int, required=False, choices=BOOL_OPTIONS) = 0
                    ):
        """Send an embed"""
        if not channel:
            channel = ctx.channel

        embed = discord.Embed(title=title, description=description.replace("\\n", "\n"))
        if colour:
            try:
                # ctx is literally unused, so it doesn't matter
                # noinspection PyTypeChecker
                embed.colour = await commands.ColourConverter().convert(None, colour)
            except commands.BadArgument:
                await ctx.respond("Unknown colour", ephemeral=True)
                return

        if image_url:
            embed.set_image(url=image_url)

        if timestamp:
            embed.timestamp = discord.utils.utcnow()

        try:
            await channel.send(embed=embed)
        except discord.DiscordException as e:
            await ctx.respond(f"Unable to send embed\n```{e}```", ephemeral=True)
        else:
            await ctx.respond("Sent", ephemeral=True)


def setup(bot):
    bot.add_cog(Embed(bot))
