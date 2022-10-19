import discord
from discord.ext import commands
import datetime as dt
from utils import BOOL_OPTIONS, create_bar
from config import SPOTIFY_EMOJI, BOOSTER_ROLE, GUILD_ID, PRIMARY
from math import floor
from db import db

# Maps to minutes
DATE_SCALE = {
    "minutes": 1,
    "hours": 60,
    "days": 60 * 24,
    "weeks": 60 * 24 * 7,
}

BREATHE_GIFS = {
    "circle": "https://media3.giphy.com/media/1xVc4s9oZrDhO9BOYt/source.gif",
    "geometric": "https://tenor.com/view/breathe-in-breathe-iout-calming-calm-down-gif-12208363",
    "gauge": "https://www.duffthepsych.com/wp-content/uploads/2016/07/478Breathe500x500c129revised.gif"
}

PRONOUNS_PAGE_URL = "https://en.pronouns.page/api/profile/get/{}?version=2"

PRONOUNS_PAGE_BASE_OPINIONS = {
    "yes": "❤️",
    "meh": "👍",
    "close": "🫂",
    "jokingly": "😛",
    "no": "👎",
}

PRONOUNS_PAGE_FLAG_SERVERS = [830277756058337341, 830294210371518474, 932944778801315880]


def duration_to_str(duration: dt.timedelta):
    duration = floor(duration.total_seconds())
    minutes, seconds = divmod(duration, 60)

    return f"{minutes}:{seconds:02}"


class SpotifyLink(discord.ui.View):
    def __init__(self, url: str):
        super().__init__()

        self.add_item(
            discord.ui.Button(label="Play", emoji=SPOTIFY_EMOJI, url=url)
        )


class General(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.option("unit", choices=DATE_SCALE.keys())
    async def selfmute(self, ctx: discord.ApplicationContext, time: discord.Option(int), unit: str):
        """Temporarily mute yourself"""
        delta = dt.timedelta(minutes=time * DATE_SCALE[unit])
        if delta.days > 28:
            await ctx.respond("The max timeout is 28 days", ephemeral=True)
        else:
            try:
                await ctx.user.timeout_for(delta, reason="Selfmute")
            except discord.Forbidden:
                await ctx.respond(f"I do not have permission to apply a timeout to you", ephemeral=True)
            else:
                self.self_mutes.append(ctx.user.id)

                timeout_end = discord.utils.format_dt(dt.datetime.now() + delta)
                await ctx.respond(f"Ok, I will mute you until {timeout_end}")

    @discord.slash_command()
    @discord.option("gif", choices=BREATHE_GIFS.keys(), description="Which breathing gif to display")
    @discord.option("hide", choices=BOOL_OPTIONS, default=0,
                    description="Whether to display the image to only you, or to the whole channel")
    async def breathe(self, ctx: discord.ApplicationContext, gif: str, hide: int):
        """Sends a gif to help you breathe slowly"""
        await ctx.respond(BREATHE_GIFS[gif], ephemeral=bool(hide))

    @discord.slash_command()
    async def np(self, ctx: discord.ApplicationContext):
        """
        Display your current spotify status
        """
        # ApplicationContext.user.activities doesn't appear to ever contain anything, so get the member object
        activities = ctx.guild.get_member(ctx.user.id).activities

        spotify = None
        for activity in activities:
            if isinstance(activity, discord.Spotify):
                spotify = activity

        if spotify is None:
            await ctx.respond("No spotify status found", ephemeral=True)
            return

        embed = discord.Embed(colour=spotify.colour, title=spotify.title,
                              description=f"By {spotify.artist} on {spotify.album}")
        embed.set_thumbnail(url=spotify.album_cover_url)

        duration = spotify.duration
        progress = discord.utils.utcnow() - spotify.start  # Calculate how long it has been since the start
        progress = max(dt.timedelta(0), min(progress, duration))  # Constrain timestamp to be between 0 and duration
        progress_bar = create_bar(progress.seconds, duration.seconds)

        progress_time = duration_to_str(progress) + "/" + duration_to_str(duration)
        embed.description += f"\n\n{progress_bar} {progress_time}"

        await ctx.respond(embed=embed, view=SpotifyLink(spotify.track_url))

    @discord.slash_command(guild_ids=[GUILD_ID])
    @discord.option("url", description="The link to a .png .jpg or .gif file. Must be less than 256KB in size")
    async def boostbadge(self, ctx: discord.ApplicationContext, url: str):
        """
        Give yourself a custom icon next to your name!
        """
        # Prevent interaction from timing out
        await ctx.defer()

        async with self.bot.session.get(url) as response:
            # Verify contents of file
            if response.content_type not in ["image/jpeg", "image/png", "image/gif"]:
                await ctx.respond("Invalid file type")
                return
            if response.content_length > 256000:  # Max 256KB
                await ctx.respond("Max image size is 256KB")
                return

            # Get file
            image = await response.read()

            # Create role
            booster_role = ctx.guild.get_role(BOOSTER_ROLE)
            new_role = await ctx.guild.create_role(name="Boost Badge")
            await new_role.edit(position=booster_role.position + 1, icon=image)

            # Remove current boost badge, if one exists
            roles = ctx.user.roles
            badge_role = discord.utils.find(lambda role: role.name == "Boost Badge", roles)

            if badge_role:
                await badge_role.delete()

            # Assign role to user
            await ctx.user.add_roles(new_role)

            await ctx.respond("Created!")

    @discord.slash_command()
    async def whois(self, ctx: discord.ApplicationContext, user: discord.Member):
        """Show information about a user"""
        embed = discord.Embed(colour=user.colour, description=user.mention)
        embed.set_author(name=str(user), icon_url=user.avatar.url)
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Joined", value=discord.utils.format_dt(user.joined_at))
        embed.add_field(name="Registered", value=discord.utils.format_dt(user.created_at))

        # Skip the 1st role (@everyone) then reverse the order so the highest role is first. Weird syntax lol
        roles = " ".join([role.mention for role in user.roles[:0:-1]])
        embed.add_field(name=f"Roles [{len(user.roles) - 1}]", value=roles, inline=False)

        embed.set_footer(text=f"User ID: {user.id}")

        await ctx.respond(embed=embed)

    pronouns = discord.SlashCommandGroup(name="pronouns")

    @pronouns.command()
    async def set(self, ctx: discord.ApplicationContext, username: str):
        """Set your pronouns.page username"""
        url = f"https://en.pronouns.page/api/profile/get/{username}?version=2"

        await ctx.defer()

        async with self.bot.session.get(url) as response:
            status_code = response.status

            if status_code != 200:
                await ctx.respond("pronouns.page cannot be reached", ephemeral=True)
                return

        await db.settings.update_one({"_id": str(ctx.user.id)}, {"$set": {"pronouns_page": username}}, upsert=True)

        await ctx.respond("Username set", ephemeral=True)

    @pronouns.command()
    async def view(self, ctx: discord.ApplicationContext, user: discord.Option(discord.Member, required=False)):
        """Display the user's pronouns.page profile"""
        ephemeral = True
        if not user:
            user = ctx.user
            ephemeral = False

        await self.send_pronouns_profile(ctx, user, ephemeral)

    @discord.user_command(name="View Pronouns")
    async def user_pronouns(self, ctx: discord.ApplicationContext, member: discord.Member):
        await self.send_pronouns_profile(ctx, member)

    async def send_pronouns_profile(self, ctx: discord.ApplicationContext, user: discord.Member, ephemeral=True):
        await ctx.defer(ephemeral=ephemeral)

        entry = await db.settings.find_one({"_id": str(user.id), "pronouns_page": {"$ne": None}},
                                           projection={"pronouns_page": True})

        if not entry:
            if ctx.user.id == user.id:
                # TODO: When slash group mention fixed:
                #  embed = discord.Embed(colour=PRIMARY, description=self.set.mention)
                await ctx.respond("You have not setup your pronouns.page profile")
            else:
                await ctx.respond("That user has not setup their pronouns.page profile")
            return

        # At this point, the user does have a pronouns.page username set
        username = entry["pronouns_page"]

        async with self.bot.session.get(PRONOUNS_PAGE_URL.format(username)) as response:
            status_code = response.status

            if status_code != 200:
                await ctx.respond("pronouns.page cannot be reached")
                return

            data = await response.json()

        if "en" not in data["profiles"]:
            await ctx.respond("That user does not have an english profile set up")
            return

        embed = self.pronouns_page_embed(data)

        await ctx.respond(embed=embed)

    def pronouns_page_embed(self, data: dict):
        profile = data["profiles"]["en"]

        src_username = data["username"]
        avatar = data["avatar"]
        page_url = "https://en.pronouns.page/@" + src_username

        embed = discord.Embed(colour=PRIMARY)
        embed.set_author(name=src_username + "🔗", icon_url=avatar, url=page_url)

        if profile["description"] != "":
            embed.description = profile["description"]

        opinions = PRONOUNS_PAGE_BASE_OPINIONS.copy()

        for key, values in profile["opinions"].items():
            opinions.update({
                key: "[{}]".format(values["description"])
            })

        names = ""
        for entry in profile["names"]:
            name = entry["value"]
            opinion = opinions[entry["opinion"]]
            names += f"{opinion} {name}\n"

        if names:
            embed.add_field(name="Names", value=names)

        pronouns = ""
        for entry in profile["pronouns"]:
            name = entry["value"]
            opinion = opinions[entry["opinion"]]
            pronouns += f"{opinion} {name}\n"

        if pronouns:
            embed.add_field(name="Pronouns", value=pronouns)

        if profile["flags"]:
            # Grab all flag emojis
            flag_emojis = []
            for guild_id in PRONOUNS_PAGE_FLAG_SERVERS:
                flag_emojis += self.bot.get_guild(guild_id).emojis

            flags = []
            for flag in profile["flags"]:
                emoji = discord.utils.get(flag_emojis, name=flag.replace(" ", ""))
                if emoji:
                    flags.append(str(emoji))
            for entry in profile["customFlags"]:
                flags.append("[{}]".format(entry["name"]))

            if flags:
                embed.add_field(name="Flags", value=" ".join(flags))

        if profile["links"]:
            embed.add_field(name="Links", value="\n".join(profile["links"]), inline=False)

        embed.set_footer(text="pronouns.page")

        return embed


def setup(bot: discord.Bot):
    bot.add_cog(General(bot))
