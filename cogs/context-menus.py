import discord


class ContextMenus(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.user_command(name="Get Profile Picture")
    async def user_pfp(self, ctx: discord.ApplicationContext, member: discord.Member):
        embed = discord.Embed(title=member.display_name, colour=member.colour, url=member.display_avatar.url)
        embed.set_image(url=member.display_avatar.url)
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.message_command(name="Get sticker")
    async def message_sticker(self, ctx: discord.ApplicationContext, message: discord.Message):
        if message.stickers:
            sticker = message.stickers[0]

            embed = discord.Embed(title=sticker.name, url=sticker.url)
            embed.set_image(url=sticker.url)
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond("This message doesn't contain any stickers", ephemeral=True)


def setup(bot):
    bot.add_cog(ContextMenus(bot))
