import discord
from config import SUGGESTIONS_ID, LIKE_EMOJI, DISLIKE_EMOJI, STAFF_LIST_MESSAGE, STAFF_ROLE, GUILD_ID


class Passive(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent_id == SUGGESTIONS_ID:
            history = thread.history(limit=1, oldest_first=True)
            first_message = await history.next()

            if first_message:
                await first_message.add_reaction(DISLIKE_EMOJI)
                await first_message.add_reaction(LIKE_EMOJI)  # Last emoji shows up on the post

    @discord.Cog.listener()
    async def on_member_update(self, old_member: discord.Member, new_member: discord.Member):
        if old_member.roles != new_member.roles:
            # Roles updated
            guild = self.bot.get_guild(GUILD_ID)
            staff_role = guild.get_role(STAFF_ROLE)

            if staff_role in old_member.roles or staff_role in new_member.roles:
                description = "\n".join([member.mention for member in staff_role.members])

                channel = self.bot.get_guild(STAFF_LIST_MESSAGE[0]).get_channel(STAFF_LIST_MESSAGE[1])
                message = await channel.fetch_message(STAFF_LIST_MESSAGE[2])
                embed = message.embeds[0].copy()

                embed.description = description

                await message.edit(embed=embed)


def setup(bot):
    bot.add_cog(Passive(bot))
