import discord
from discord.ext import commands
from dotenv import dotenv_values
from os import listdir
import aiohttp


class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Override start() to create an aiohttp session
    async def start(self, token: str, *, reconnect: bool = True):
        async with aiohttp.ClientSession(loop=self.loop) as self.session:
            await super().start(token, reconnect=reconnect)


intents = discord.Intents.all()
allowed_mentions = discord.AllowedMentions(everyone=False)

bot = Bot(command_prefix="++", case_insensitive=True, owner_id=349070664684142592, intents=intents,
          allowed_mentions=allowed_mentions)

for cog in listdir("cogs/"):
    if cog.endswith(".py"):
        cog = cog[:-3]
        print(f"Loading extension: {cog}")
        bot.load_extension(f"cogs.{cog}")


@bot.event
async def on_ready():
    status = bot.user.name + " has started"
    print(status)
    print("-" * len(status))


TOKEN = dotenv_values()["BOT_TOKEN"]
bot.run(TOKEN)
