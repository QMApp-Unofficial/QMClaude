"""
QMBOT v2 — Main entry point
Clean modular bot with slash commands, economy, social, market, and moderation.
"""
import discord
from discord.ext import commands
from config import TOKEN


INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.voice_states = True
INTENTS.members = True


COGS = [
    "cogs.listeners",
    "cogs.economy",
    "cogs.market",
    "cogs.shop",
    "cogs.games",
    "cogs.trivia",
    "cogs.social",
    "cogs.fun",
    "cogs.xp",
    "cogs.modtools",
    "cogs.swearjar",
    "cogs.logs",
    "cogs.admin",
    "cogs.tasks",
    "cogs.mc",
]


class QMULBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS)

    async def setup_hook(self):
        print("─── QMBOT v2 Starting ───")
        for ext in COGS:
            try:
                await self.load_extension(ext)
                print(f"  ✓ {ext}")
            except Exception as e:
                print(f"  ✗ {ext}: {type(e).__name__}: {e}")

        try:
            synced = await self.tree.sync()
            print(f"  ⚡ Synced {len(synced)} slash commands")
        except Exception as e:
            print(f"  ✗ Sync failed: {e}")
        print("─── Ready ───")


bot = QMULBot()


@bot.event
async def on_ready():
    print(f"  🤖 {bot.user} is online")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="/help · QMBOT v2")
    )


def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set")
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
