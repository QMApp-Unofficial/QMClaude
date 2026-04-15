"""
swearjar.py — Swear tracking system
Commands: swearjar, swearleaderboard, swearreset
Merged: swearfine (your personal count) now shown inline with swearjar
"""
import discord
from discord.ext import commands

from storage import load_swear_jar, save_swear_jar
from ui_utils import C, E, embed, error, success


class SwearJar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="swearjar", description="View the swear jar stats.")
    async def swearjar(self, ctx):
        jar = load_swear_jar()
        total = jar.get("total", 0)
        your_count = jar.get("users", {}).get(str(ctx.author.id), {}).get("count", 0)
        e = embed("🫙  Swear Jar",
            f"**Server total:** `{total:,}` swears\n"
            f"**Your count:** `{your_count:,}` swears\n\n"
            f"Every swear costs **10 coins** from your wallet.",
            C.SWEAR, footer="Logged automatically")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="swearleaderboard", description="Who swears the most?")
    async def swearleaderboard(self, ctx):
        jar = load_swear_jar()
        users = jar.get("users", {})
        if not users:
            return await ctx.send(embed=embed("🧼  Swear Leaderboard", "No swears recorded. Impressive.", C.SWEAR))
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("count", 0), reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(sorted_users):
            try:
                user = await self.bot.fetch_user(int(uid))
                name = user.display_name
            except Exception:
                name = f"User {uid}"
            count = data.get("count", 0)
            medal = medals[i] if i < 3 else f"{i+1}."
            you = "  ← you" if str(uid) == str(ctx.author.id) else ""
            lines.append(f"{medal}  **{name}** — `{count:,}` swears{you}")
        await ctx.send(embed=embed("🧼  Swear Leaderboard", "\n".join(lines), C.SWEAR))

    @commands.hybrid_command(name="swearreset", description="Reset the swear jar (admin).")
    @commands.has_permissions(administrator=True)
    async def swearreset(self, ctx):
        save_swear_jar({"total": 0, "users": {}})
        await ctx.send(embed=success("Swear Jar Reset", "🧹 The jar has been emptied."))

    async def cog_command_error(self, ctx, err):
        if isinstance(err, commands.MissingPermissions):
            await ctx.send(embed=error("Permission", "Admin only."))


async def setup(bot):
    await bot.add_cog(SwearJar(bot))
