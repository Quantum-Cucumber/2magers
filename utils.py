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
