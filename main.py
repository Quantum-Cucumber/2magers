import discord
from dotenv import dotenv_values
from os import listdir
from config import GUILD_ID

intents = discord.Intents.default()
bot = discord.Bot(command_prefix="++", case_insensitive=True, owner_id=349070664684142592, intents=intents,
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


token = dotenv_values()["BOT_TOKEN"]
bot.run(token)
