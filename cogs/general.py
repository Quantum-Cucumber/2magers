import discord
from discord.ext import commands
import datetime as dt
from utils import BOOL_OPTIONS, create_bar
from config import SPOTIFY_EMOJI, BOOSTER_ROLE
from math import floor

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

    @discord.slash_command(guild_only=True)
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

    @discord.slash_command()
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


def setup(bot: discord.Bot):
    bot.add_cog(General(bot))
