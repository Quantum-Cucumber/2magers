import discord
from discord.ext import tasks
from config import GUILD_ID, MODMAIL_GUILD_ID, MODMAIL_CATEGORY_ID, RED, YELLOW, GREEN, PRIMARY
from db import db, use_counter
from typing import Optional

MODMAIL_SENT_EMOJI = "📨"


class ModMail(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        # Will act like a mirror of the DB, just in memory
        # channel ID -> user ID
        self.mail_cache = {}

        # Run once on startup
        self.load_view.start()
        self.load_active_modmails.start()

    async def get_or_fetch_user(self, user_id: int) -> Optional[discord.User]:
        user = self.bot.get_user(user_id)

        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except discord.NotFound:
                return None

        return user

    @discord.slash_command(guild_ids=[GUILD_ID])
    async def attachmailbutton(self, ctx: discord.ApplicationContext, message: discord.Message):
        """Attach the ModMail button to a message"""
        if message.author.id != self.bot.user.id:
            await ctx.respond("Not a bot message", ephemeral=True)
            return

        await message.edit(view=ModMailButton(self))
        await ctx.respond("Done", ephemeral=True)

    @tasks.loop(count=1)
    async def load_view(self):
        self.bot.add_view(ModMailButton(self))

    @tasks.loop(count=1)
    async def load_active_modmails(self):
        cursor = db.modmails.find()
        async for modmail in cursor:
            self.mail_cache.update({
                int(modmail["channel"]): int(modmail["user"]),
            })

    @discord.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            return

        for channel_id, user_id in self.mail_cache.items():
            if user_id == message.author.id:
                # Author has an active modmail

                channel = self.bot.get_channel(channel_id)

                embed = discord.Embed(colour=PRIMARY, description=message.content)

                # Get files
                files = []
                for attachment in message.attachments:
                    files.append(await attachment.to_file())

                await channel.send(embed=embed if message.content else None,
                                   files=files if files else None)

                await message.add_reaction(MODMAIL_SENT_EMOJI)

                break

    @discord.slash_command(guild_ids=[MODMAIL_GUILD_ID])
    async def reply(self, ctx: discord.ApplicationContext, message: str,
                    file: discord.Option(discord.Attachment, required=False)):
        """Reply to the active mod mail"""
        if ctx.channel_id not in self.mail_cache:
            await ctx.respond("This channel is not an active mod mail channel", ephemeral=True)
            return

        user_id = self.mail_cache[ctx.channel_id]

        await ctx.defer()

        # Get user
        user = await self.get_or_fetch_user(user_id)
        if not user:
            embed = discord.Embed(colour=RED, title="User not found",
                                  description=f"You may want to close this mod mail - {self.close.mention}")
            await ctx.respond(embed=embed)
            return

        # Create embed
        embed = discord.Embed(colour=PRIMARY, description=message)

        # Attach main server's info as the author
        guild = self.bot.get_guild(GUILD_ID)
        embed.set_author(name=guild.name + " Mod Team", icon_url=guild.icon.url)

        # Get file if set
        if file:
            # File needs to be copied, so it can be sent to the user and the mods
            file_copy = await file.to_file()
            file = await file.to_file()
        else:
            # ApplicationContext.respond gets cranky if its None so yeah
            file_copy = discord.utils.MISSING

        try:
            # Respond to user
            await user.send(embed=embed, file=file)

        except discord.Forbidden:
            error_embed = discord.Embed(colour=YELLOW, title="Unable to DM user",
                                        description="They may have direct messages disabled for the server.")

            await ctx.respond(embed=error_embed)
        else:
            # Respond to mods
            # Not using .respond() to be verbose about discord.utils.MISSING above
            await ctx.send_followup(embed=embed, file=file_copy)

    @discord.slash_command(guild_ids=[MODMAIL_GUILD_ID])
    async def close(self, ctx: discord.ApplicationContext):
        """Close the active mod mail"""
        if ctx.channel_id not in self.mail_cache:
            await ctx.respond("This channel is not an active mod mail channel", ephemeral=True)
            return

        user_id = int(self.mail_cache[ctx.channel_id])

        await ctx.defer()

        # Inform user
        user = await self.get_or_fetch_user(user_id)
        if user:
            user_embed = discord.Embed(colour=RED, title="Your mod mail has been closed")

            try:
                await user.send(embed=user_embed)
            except discord.Forbidden:
                pass

        # Clear records
        del self.mail_cache[ctx.channel_id]
        await db.modmails.delete_one({"channel": str(ctx.channel_id), "user": str(user_id)})

        # Inform mods
        mod_embed = discord.Embed(colour=RED, title="Mod Mail Closed")
        await ctx.respond(embed=mod_embed)

        # Change channel name
        await ctx.channel.edit(name=f"closed-{ctx.channel.name}")


class ModMailButton(discord.ui.View):
    def __init__(self, cog: ModMail):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(emoji="💬", label="Create Mod Mail", custom_id="start_modmail", style=discord.ButtonStyle.blurple)
    async def start_mail(self, _button: discord.Button, interaction: discord.Interaction):
        # Ensure no mod mails currently exist
        existing_modmail = await db.modmails.find_one({"user": str(interaction.user.id)})
        if existing_modmail:
            embed = discord.Embed(colour=YELLOW, title="You already have a mod mail open",
                                  description="If you wish to create a new one, ask the mods to close the old mod mail")

            try:
                await interaction.user.send(embed=embed)
            except discord.Forbidden:
                await interaction.response.send_message(embed=embed, ephemeral=True)

            return

        await interaction.response.send_modal(PromptModal(self.cog))


class PromptModal(discord.ui.Modal):
    def __init__(self, cog: ModMail):
        super().__init__(title="Create Mod Mail")

        self.cog = cog

        self.add_item(
            discord.ui.InputText(label="Message", placeholder="The message to send to the mod team",
                                 style=discord.InputTextStyle.long, required=False)
        )

    async def callback(self, interaction: discord.Interaction):
        # Get modmail data
        category = self.cog.bot.get_channel(MODMAIL_CATEGORY_ID)
        mail_number = await use_counter("modmail")

        # Create channel
        # noinspection PyUnresolvedReferences
        channel = await category.create_text_channel(f"mail-{mail_number}")
        # Notify mods
        embed = None
        if self.children[0].value:
            embed = discord.Embed(colour=PRIMARY, description=self.children[0].value)

        await channel.send("@here New mod mail created", embed=embed,
                           allowed_mentions=discord.AllowedMentions(everyone=True))

        # Create records
        await db.modmails.insert_one({
            "channel": str(channel.id),
            "user": str(interaction.user.id),
        })
        self.cog.mail_cache.update({channel.id: interaction.user.id})

        # Respond to user
        try:
            embeds = [
                discord.Embed(colour=GREEN, title="Mod Mail Created",
                              description="Send messages here to talk to the mod team")
            ]

            if self.children[0].value:
                embeds.append(
                    discord.Embed(colour=GREEN, description=self.children[0].value)
                )

            await interaction.user.send(embeds=embeds)
            await interaction.response.defer(invisible=True)

        except discord.Forbidden:
            await interaction.response.send_message(
                "The mod mail has been setup, but I am unable to DM you to pass on messages. Please ensure DMs are "
                "enabled for this server - https://support.discord.com/hc/en-us/articles/217916488",
                ephemeral=True,
            )


def setup(bot):
    bot.add_cog(ModMail(bot))
