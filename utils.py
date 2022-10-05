import discord

PROGRESS = "▰"
REMAINDER = "▱"

BOOL_OPTIONS = [
    discord.OptionChoice("Yes", 1),
    discord.OptionChoice("No", 0),
]


def create_bar(progress: int, total: int, size=15) -> str:
    progress = max(0, min(progress, total))  # Ensure progress > 0 and progress < total

    completed = int(progress / total * size)
    remaining = size - completed

    return completed * PROGRESS + remaining * REMAINDER


def seconds_to_pretty(seconds: float):
    # Approximations - Meant to be readable for humans so making sense is better than accuracy
    units = {
        "year": 365 * 24 * 60 * 60,
        "month": 30 * 24 * 60 * 60,
        "day": 24 * 60 * 60,
        "hour": 60 * 60,
        "minute": 60,
        "second": 1,
    }

    output = ""

    remainder = seconds
    for unit, duration in units.items():
        value, remainder = divmod(remainder, duration)

        if value > 1:
            output += f"{int(value)} {unit}s, "
        elif value == 1:
            output += f"{int(value)} {unit}, "

    return output.rstrip(", ")
