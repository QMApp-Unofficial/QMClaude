"""
admin.py — Admin utilities, info commands, suggestions, announcements
Commands: suggest, announcement, package, ping, uptime, botinfo, serverinfo, userinfo, timer
Merged from: admin.py + extras.py (removed gif command, messagecount merged into profile)
"""
import asyncio
import time

import discord
from discord.ext import commands

from config import (
    SUGGESTION_CHANNEL_ID, ANNOUNCEMENT_CHANNEL_ID, PACKAGE_USER_ID, XP_PER_MESSAGE,
)
from storage import load_suggestions, save_suggestions, load_data
from ui_utils import C, E, embed, error, success, warn


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()

    # ── SUGGEST ────────────────────────────────────────────────

    @commands.hybrid_command(name="suggest", description="Submit a suggestion for the server.")
    async def suggest(self, ctx, *, suggestion: str):
        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID)
        if not channel:
            return await ctx.send(embed=error("Suggest", "Suggestion channel not configured."))
        suggestions = load_suggestions()
        suggestions.append({"user": ctx.author.id, "text": suggestion})
        save_suggestions(suggestions)
        e = embed("💡  New Suggestion", suggestion, C.TRIVIA, footer=f"From {ctx.author.display_name}")
        msg = await channel.send(embed=e)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        await ctx.send(embed=success("Suggestion Submitted!", "Your idea has been sent. ✅"))

    # ── ANNOUNCEMENT ───────────────────────────────────────────

    @commands.hybrid_command(name="announcement", description="Send a server announcement.")
    @commands.has_permissions(manage_guild=True)
    async def announcement(self, ctx, *, message: str):
        channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if not channel:
            return await ctx.send(embed=error("Announcement", "Channel not configured."))
        e = embed("📢  Announcement", message, C.ADMIN, footer=f"Posted by {ctx.author.display_name}")
        await channel.send(embed=e)
        await ctx.send(embed=success("Announcement Posted!", "Message sent. 📣"))

    # ── PACKAGE ────────────────────────────────────────────────

    @commands.hybrid_command(name="package", description="Send a manual data backup.")
    async def package(self, ctx):
        if ctx.author.id != PACKAGE_USER_ID:
            return await ctx.send(embed=error("Backup", "Not authorised."))
        from cogs.tasks import dm_package_to_user
        ok = await dm_package_to_user(self.bot, PACKAGE_USER_ID, reason="Manual backup")
        if ok:
            await ctx.send(embed=success("Backup Sent!", "Delivered to your DMs. 📦"))
        else:
            await ctx.send(embed=error("Backup Failed", "Something went wrong."))

    # ── INFO COMMANDS (merged from extras.py) ──────────────────

    @commands.hybrid_command(name="ping", description="Check bot latency.")
    async def ping(self, ctx):
        latency = round(self.bot.latency * 1000)
        color = C.WIN if latency < 100 else (C.WARN if latency < 200 else C.LOSE)
        await ctx.send(embed=embed("🏓  Pong!", f"Latency: `{latency}ms`", color))

    @commands.hybrid_command(name="uptime", description="Show bot uptime.")
    async def uptime(self, ctx):
        seconds = int(time.time() - self.start_time)
        h, r = divmod(seconds, 3600)
        m, s = divmod(r, 60)
        await ctx.send(embed=embed("⏱️  Uptime", f"`{h}h {m}m {s}s`", C.NEUTRAL))

    @commands.hybrid_command(name="botinfo", description="Bot information.")
    async def botinfo(self, ctx):
        e = embed("🤖  QMBOT v2",
            f"**Servers:** `{len(self.bot.guilds)}`\n"
            f"**Users:** `{len(self.bot.users)}`\n"
            f"**Latency:** `{round(self.bot.latency * 1000)}ms`\n"
            f"**Commands:** `{len([c for c in self.bot.tree.walk_commands()])}`",
            C.ADMIN)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="serverinfo", description="Server information.")
    async def serverinfo(self, ctx):
        g = ctx.guild
        if not g:
            return await ctx.send(embed=error("Server Info", "Server only."))
        rows = [
            ("Name", g.name), ("ID", str(g.id)), ("Owner", str(g.owner)),
            ("Members", str(g.member_count)), ("Channels", str(len(g.channels))),
            ("Roles", str(len(g.roles))), ("Created", g.created_at.strftime("%d %b %Y")),
        ]
        col_w = max(len(r[0]) for r in rows)
        table = "\n".join(f"{r[0].ljust(col_w)}  {r[1]}" for r in rows)
        e = embed(f"🏠  {g.name}", f"```\n{table}\n```", C.ADMIN)
        if g.icon:
            e.set_thumbnail(url=g.icon.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="userinfo", description="User information.")
    async def userinfo(self, ctx, member: discord.Member = None):
        m = member or ctx.author
        rows = [
            ("Name", str(m)), ("Display", m.display_name), ("ID", str(m.id)),
            ("Joined", m.joined_at.strftime("%d %b %Y") if m.joined_at else "Unknown"),
            ("Created", m.created_at.strftime("%d %b %Y")),
            ("Roles", str(len(m.roles) - 1)),
            ("Top Role", m.top_role.name if m.top_role else "None"),
        ]
        col_w = max(len(r[0]) for r in rows)
        table = "\n".join(f"{r[0].ljust(col_w)}  {r[1]}" for r in rows)
        e = embed(f"👤  {m.display_name}", f"```\n{table}\n```", C.ADMIN)
        e.set_thumbnail(url=m.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="timer", description="Start a countdown timer (max 300s).")
    async def timer(self, ctx, seconds: int):
        if not 1 <= seconds <= 300:
            return await ctx.send(embed=error("Timer", "Must be 1–300 seconds."))
        await ctx.send(embed=embed("⏳  Timer Started", f"Counting down **{seconds}** seconds...", C.NEUTRAL))
        await asyncio.sleep(seconds)
        await ctx.send(f"⏰ {ctx.author.mention} Time's up!")

    async def cog_command_error(self, ctx, err):
        if isinstance(err, commands.MissingPermissions):
            await ctx.send(embed=error("Permission Denied", "You need **Manage Server**."))


async def setup(bot):
    await bot.add_cog(Admin(bot))
