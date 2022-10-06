import discord
from discord.ext import commands
from os import listdir
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from io import BytesIO
from utils import BOOL_OPTIONS
from config import WELCOME_ID, GUILD_ID

FLAG_DIR = "images/flags/"

FLAGS = []
for file in listdir(FLAG_DIR):
    if file.endswith(".png"):
        FLAGS.append(file[:-4])

FLAG_PFP_SIZE = 1024
FLAG_BLUR = 40
FLAG_BORDER = 50

FLAG_SEPARATORS = {
    "vertical": ((FLAG_PFP_SIZE / 2, 0), (FLAG_PFP_SIZE, 0), (FLAG_PFP_SIZE, FLAG_PFP_SIZE), (FLAG_PFP_SIZE / 2),
                 FLAG_PFP_SIZE),
    "horizontal": ((0, FLAG_PFP_SIZE / 2), (FLAG_PFP_SIZE, FLAG_PFP_SIZE / 2), (FLAG_PFP_SIZE, FLAG_PFP_SIZE),
                   (0, FLAG_PFP_SIZE)),
    "diagonal /": ((FLAG_PFP_SIZE, 0), (FLAG_PFP_SIZE, FLAG_PFP_SIZE), (0, FLAG_PFP_SIZE)),
    "diagonal \\": ((0, 0), (FLAG_PFP_SIZE, 0), (FLAG_PFP_SIZE, FLAG_PFP_SIZE)),
}

FONT = "Roboto-Regular.ttf"
FONT_BOLD = "Roboto-Bold.ttf"
WELCOME_BG = "images/welcomeBG.jpg"
LEAVE_BG = "images/goodbyeBG.jpg"


def image_to_file(image: Image, filename: str) -> discord.File:
    output = BytesIO()
    image.save(output, format="png")
    output.seek(0)

    return discord.File(output, filename=filename)


def make_welcome_image(background: str, pfp: BytesIO, header: str, body: str, footer: str, text_colour: tuple) -> Image:
    background_img = Image.open(background)

    pfp_img = Image.open(pfp)
    pfp_img = pfp_img.convert("RGBA")
    pfp_img = pfp_img.resize((200, 200))
    pfp_img = circle_crop(pfp_img)

    background_img.paste(pfp_img, (25, 25, 225, 225), pfp_img)

    canvas = ImageDraw.Draw(background_img)

    # PFP Border
    # Size is pfp_img's size + the width
    canvas.ellipse((21, 21, 229, 228), outline=(255, 255, 255), width=4)

    # Background border
    # idk why the border end is -1px off the size
    canvas.rectangle((0, 0, 699, 249), outline=(0, 0, 0), width=3)

    # Draw text

    header_font = ImageFont.truetype(FONT_BOLD, 35)
    canvas.text((700 / 1.5, 250 / 3.5), header, text_colour, header_font, "mm")

    body_font = fit_font_width(FONT_BOLD, 60, body, 400)
    canvas.text((700 / 1.5, 250 / 2), body, text_colour, body_font, "mm")

    footer_font = ImageFont.truetype(FONT, 25)
    canvas.text((700 / 1.5, 250 / 1.35), footer, text_colour, footer_font, "mm")

    return background_img


def fit_font_width(font_path: str, start_size: int, text: str, width: int, step=10) -> ImageFont:
    """Shrinks the font so the width fits in the given size"""
    font = ImageFont.truetype(font_path, start_size)
    size = start_size

    while font.getsize(text)[0] > width:
        size -= step
        font = ImageFont.truetype(font_path, size)

    return font


def num_suffix(n: int) -> str:
    """
    Format a number into a string and prepend "nd" "st" "rd" etc
    """
    return str(n) + ("th" if 4 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


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
                    choices=FLAG_SEPARATORS.keys(), default=None)
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
        pfp = pfp.resize((FLAG_PFP_SIZE - FLAG_BORDER * 2, FLAG_PFP_SIZE - FLAG_BORDER * 2))
        # Prevent colour mode errors
        pfp = pfp.convert("RGBA")

        # Load and resize the flags
        background = Image.open(FLAG_DIR + flag + ".png")
        background = background.resize((FLAG_PFP_SIZE, FLAG_PFP_SIZE))

        if flag_2:
            overlay_flag = Image.open(FLAG_DIR + flag_2 + ".png")
            overlay_flag = overlay_flag.resize((FLAG_PFP_SIZE, FLAG_PFP_SIZE))

            # Produce mask
            # Create B&W image to be used as the composite mask
            mask_img = Image.new("L", (FLAG_PFP_SIZE, FLAG_PFP_SIZE), color=0)
            mask_draw = ImageDraw.Draw(mask_img)

            # Draw the selected seperator in white onto the mask
            mask_poly = FLAG_SEPARATORS[seperator]
            mask_draw.polygon(mask_poly, fill=255)

            # Apply the mask
            background = Image.composite(overlay_flag, background, mask_img)

        # Apply blur
        if blur:
            background = background.filter(ImageFilter.GaussianBlur(FLAG_BLUR))

        # Crop profile picture to a circle
        pfp = circle_crop(pfp)

        # Combine images
        background.paste(pfp, (FLAG_BORDER, FLAG_BORDER, FLAG_PFP_SIZE - FLAG_BORDER, FLAG_PFP_SIZE - FLAG_BORDER), pfp)

        # Save the byte stream and send in chat
        await ctx.respond(file=image_to_file(background, filename="pride.png"))

    @discord.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return

        pfp = BytesIO(await member.display_avatar.read())

        image = make_welcome_image(WELCOME_BG, pfp, "Welcome", member.display_name,
                                   f"You are our {num_suffix(member.guild.member_count)} member!", (0, 0, 0))

        channel = self.bot.get_channel(WELCOME_ID)
        await channel.send(file=image_to_file(image, "welcome.png"))

    @discord.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild.id != GUILD_ID:
            return

        pfp = BytesIO(await member.display_avatar.read())

        image = make_welcome_image(LEAVE_BG, pfp, "Goodbye", member.display_name, f"We will miss you :(",
                                   (255, 255, 255))

        channel = self.bot.get_channel(WELCOME_ID)
        await channel.send(file=image_to_file(image, "goodbye.png"))


def setup(bot):
    bot.add_cog(Images(bot))
