import discord
from config import SUGGESTIONS_ID, LIKE_EMOJI, DISLIKE_EMOJI


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


def setup(bot):
    bot.add_cog(Passive(bot))
