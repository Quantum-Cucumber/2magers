import discord
from dotenv import dotenv_values
from os import listdir
from config import GUILD_ID
import aiohttp


class Bot(discord.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # Override start() to create an aiohttp session
    async def start(self, token: str, *, reconnect: bool = True):
        async with aiohttp.ClientSession(loop=self.loop) as self.session:
            await super().start(token, reconnect=reconnect)


intents = discord.Intents.default()
intents.presences = True
intents.members = True

bot = Bot(command_prefix="++", case_insensitive=True, owner_id=349070664684142592, intents=intents,
          debug_guilds=[GUILD_ID])

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
