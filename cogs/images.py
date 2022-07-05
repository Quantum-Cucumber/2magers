import discord
from discord.ext import commands
from os import listdir
from PIL import Image, ImageDraw, ImageFilter
from io import BytesIO
from utils import BOOL_OPTIONS

FLAGS = []
for file in listdir("flags/"):
    if file.endswith(".png"):
        FLAGS.append(file[:-4])

PFP_SIZE = 1024
PFP_BLUR = 40
PFP_BORDER = 50

SEPARATORS = {
    "vertical": ((PFP_SIZE / 2, 0), (PFP_SIZE, 0), (PFP_SIZE, PFP_SIZE), (PFP_SIZE / 2), PFP_SIZE),
    "horizontal": ((0, PFP_SIZE / 2), (PFP_SIZE, PFP_SIZE / 2), (PFP_SIZE, PFP_SIZE), (0, PFP_SIZE)),
    "diagonal /": ((PFP_SIZE, 0), (PFP_SIZE, PFP_SIZE), (0, PFP_SIZE)),
    "diagonal \\": ((0, 0), (PFP_SIZE, 0), (PFP_SIZE, PFP_SIZE)),
}


def circle_crop(image: Image):
    # A transparent layer to place the image onto
    base = Image.new("RGBA", image.size, color=0)
    # Ensure the image is also RGBA
    image = image.convert("RGBA")

    # Create B&W image to be used as the composite mask
    mask_img = Image.new("L", image.size, color=0)
    mask_draw = ImageDraw.Draw(mask_img)
    # Create the circular mask in white
    mask_draw.ellipse((0, 0, image.size[0], image.size[1]), fill=255)

    # Apply the composite
    return Image.composite(image, base, mask_img)


class Images(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command()
    @discord.option("flag", choices=FLAGS)
    @discord.option("seperator", description="How your two flags will be positioned",
                    choices=SEPARATORS.keys(), default=None)
    @discord.option("flag_2", choices=FLAGS, default=None)
    @discord.option("blur", choices=BOOL_OPTIONS, default=0)
    async def pride(self, ctx: discord.ApplicationContext, flag: str, seperator: str, flag_2: str, blur: int):
        """
        Generate a pride pfp
        """
        if flag_2 and not seperator:
            await ctx.respond("To use 2 flags, you must specify the `seperator`", ephemeral=True)
            return

        # Load profile picture as a gif
        pfp = await ctx.user.display_avatar.with_static_format("png").read()
        # Load the pfp into PIL
        pfp = Image.open(BytesIO(pfp))
        # Resize pfp to standardised size, taking into account the border width
        pfp = pfp.resize((PFP_SIZE - PFP_BORDER * 2, PFP_SIZE - PFP_BORDER * 2))
        # Prevent colour mode errors
        pfp = pfp.convert("RGBA")

        # Load and resize the flags
        background = Image.open("flags/" + flag + ".png")
        background = background.resize((PFP_SIZE, PFP_SIZE))

        if flag_2:
            overlay_flag = Image.open("flags/" + flag_2 + ".png")
            overlay_flag = overlay_flag.resize((PFP_SIZE, PFP_SIZE))

            # Produce mask
            # Create B&W image to be used as the composite mask
            mask_img = Image.new("L", (PFP_SIZE, PFP_SIZE), color=0)
            mask_draw = ImageDraw.Draw(mask_img)

            # Draw the selected seperator in white onto the mask
            mask_poly = SEPARATORS[seperator]
            mask_draw.polygon(mask_poly, fill=255)

            # Apply the mask
            background = Image.composite(overlay_flag, background, mask_img)

        # Apply blur
        if blur:
            background = background.filter(ImageFilter.GaussianBlur(PFP_BLUR))

        # Crop profile picture to a circle
        pfp = circle_crop(pfp)

        # Combine images
        background.paste(pfp, (PFP_BORDER, PFP_BORDER, PFP_SIZE - PFP_BORDER, PFP_SIZE - PFP_BORDER), pfp)

        # Save the byte stream and send in chat
        output = BytesIO()
        background.save(output, format="png")
        output.seek(0)
        await ctx.respond(file=discord.File(output, filename="pride.png"))


def setup(bot):
    bot.add_cog(Images(bot))
