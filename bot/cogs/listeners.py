"""
listeners.py — Event listeners for XP, swear jar, AFK, welcome, filters
"""
import time
import re
from datetime import datetime, timezone

import discord
from discord.ext import commands

from config import (
    XP_PER_MESSAGE, TOP_ROLE_NAME, WELCOME_CHANNEL_ID,
    LEVEL_ANNOUNCE_CHANNEL_ID, SWEAR_FINE_ENABLED, SWEAR_FINE_AMOUNT,
)
from storage import load_data, save_data, load_swear_jar, save_swear_jar, load_coins, save_coins
from ui_utils import C, E, embed as _ui_embed

EMBED_COLOR = C.NEUTRAL
STAR_REACTION_EMOJIS = {"⭐", "🌟"}
AFK_STATUS = {}

SWEAR_WORDS = {
    "fuck", "fucking", "shit", "bullshit", "bitch", "asshole", "bastard",
    "dick", "piss", "crap", "damn", "bloody", "wanker", "twat"
}
SWEAR_RE = re.compile(
    r"\b(" + "|".join(map(re.escape, sorted(SWEAR_WORDS, key=len, reverse=True))) + r")\b",
    re.IGNORECASE
)
SWEAR_COUNT_COOLDOWN = 2
_LAST_SWEAR_COUNT_AT = {}

_FAEEZ_PATTERN = re.compile(r"[fF][^a-zA-Z0-9]*[aA4@][^a-zA-Z0-9]*[eE3][^a-zA-Z0-9]*[eE3][^a-zA-Z0-9]*[zZ2$]")
_HUSNA_PATTERN = re.compile(r"[hH][^a-zA-Z0-9]*[uU][^a-zA-Z0-9]*[sS$5][^a-zA-Z0-9]*[nN][^a-zA-Z0-9]*[aA4@]")
BANNED_NAME_PATTERNS = [_FAEEZ_PATTERN, _HUSNA_PATTERN]


def contains_banned_name(text: str) -> bool:
    return any(p.search(text) for p in BANNED_NAME_PATTERNS)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _ensure_user_coins(user_id):
    from cogs.economy import ensure_user
    uid = str(user_id)
    coins = load_coins()
    ensure_user(coins, user_id)
    save_coins(coins)
    return coins


def calculate_level(xp: int) -> int:
    return int(int(xp) ** 0.5)


def add_swears(user_id: int, count: int):
    if count <= 0:
        return
    jar = load_swear_jar()
    jar.setdefault("total", 0)
    jar.setdefault("users", {})
    uid = str(user_id)
    jar["total"] = int(jar.get("total", 0)) + count
    jar["users"].setdefault(uid, {"count": 0})
    jar["users"][uid]["count"] = int(jar["users"][uid].get("count", 0)) + count
    save_swear_jar(jar)


async def update_top_exp_role(guild: discord.Guild):
    data = load_data()
    gid = str(guild.id)
    if gid not in data or not data[gid]:
        return
    # Filter to only dict entries (skip string keys like "bios")
    user_entries = [(k, v) for k, v in data[gid].items() if isinstance(v, dict) and "xp" in v]
    if not user_entries:
        return
    top_uid, _ = max(user_entries, key=lambda x: int(x[1].get("xp", 0)))
    top_member = guild.get_member(int(top_uid))
    if not top_member:
        return
    role = discord.utils.get(guild.roles, name=TOP_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=TOP_ROLE_NAME)
        except discord.Forbidden:
            return
    for member in guild.members:
        if role in member.roles and member != top_member:
            try: await member.remove_roles(role)
            except Exception: pass
    if role not in top_member.roles:
        try: await top_member.add_roles(role)
        except Exception: pass


async def update_xp(bot, user_id: int, guild_id: int, xp_amount: int):
    data = load_data()
    gid, uid = str(guild_id), str(user_id)
    data.setdefault(gid, {})
    user = data[gid].setdefault(uid, {"xp": 0})
    prev_xp = int(user.get("xp", 0))
    prev_level = calculate_level(prev_xp)
    user["xp"] = prev_xp + int(xp_amount)
    new_level = calculate_level(user["xp"])
    user["level"] = new_level
    save_data(data)

    guild = bot.get_guild(int(gid))
    if not guild:
        return

    if new_level > prev_level and new_level % 5 == 0:
        channel = bot.get_channel(LEVEL_ANNOUNCE_CHANNEL_ID)
        if channel:
            try:
                user_obj = await bot.fetch_user(user_id)
                await channel.send(embed=_ui_embed("🎉  Level Up!",
                    f"{user_obj.mention} just reached level **{new_level}**! 🚀", C.WIN))
            except Exception: pass

    if new_level > prev_level and new_level % 10 == 0:
        role_name = f"Level {new_level}"
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try: role = await guild.create_role(name=role_name)
            except discord.Forbidden: role = None
        member = guild.get_member(int(uid))
        if role and member:
            try: await member.add_roles(role)
            except Exception: pass

    await update_top_exp_role(guild)


class Listeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return
        e = _ui_embed(f"👋  Welcome to {member.guild.name}!",
            f"{member.mention}, we're glad to have you here.\n"
            "Read through the channels, introduce yourself, and have fun! 🎉",
            EMBED_COLOR)
        e.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=e)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot or str(reaction.emoji) not in STAR_REACTION_EMOJIS:
            return
        msg = reaction.message
        if not msg.guild or msg.author.bot or msg.author.id == user.id:
            return
        coins = _ensure_user_coins(user.id)
        _ensure_user_coins(msg.author.id)
        coins = load_coins()
        giver = coins[str(user.id)]
        receiver = coins[str(msg.author.id)]

        giver.setdefault("star_meta", {"day": _today_key(), "given": {}})
        if giver["star_meta"].get("day") != _today_key():
            giver["star_meta"] = {"day": _today_key(), "given": {}}

        target_key = str(msg.author.id)
        given_today = int(giver["star_meta"]["given"].get(target_key, 0))
        if given_today >= 2:
            return
        giver["star_meta"]["given"][target_key] = given_today + 1
        receiver["stars"] = int(receiver.get("stars", 0)) + 1
        save_coins(coins)

        try:
            await msg.channel.send(
                embed=_ui_embed(f"{E.STAR}  Golden Star",
                    f"{msg.author.mention} got a star from {user.mention}! ✦ **{receiver['stars']}**",
                    C.TRIVIA),
                delete_after=3)
        except Exception: pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Banned name filter
        if message.guild and contains_banned_name(message.content or ""):
            try: await message.delete()
            except discord.Forbidden: pass
            await message.channel.send(
                embed=_ui_embed("🚫  Filtered", f"{message.author.mention} that name is not allowed.", C.LOSE),
                delete_after=5)
            return

        # Swear jar
        if message.guild:
            try:
                now_ts = time.time()
                if now_ts - _LAST_SWEAR_COUNT_AT.get(message.author.id, 0) >= SWEAR_COUNT_COOLDOWN:
                    matches = SWEAR_RE.findall(message.content or "")
                    if matches:
                        _LAST_SWEAR_COUNT_AT[message.author.id] = now_ts
                        add_swears(message.author.id, len(matches))
                        if SWEAR_FINE_ENABLED and SWEAR_FINE_AMOUNT > 0:
                            coins = _ensure_user_coins(message.author.id)
                            uid = str(message.author.id)
                            fine = SWEAR_FINE_AMOUNT * len(matches)
                            wallet = int(coins[uid].get("wallet", 0))
                            coins[uid]["wallet"] = max(0, wallet - min(wallet, fine))
                            save_coins(coins)
                        jar = load_swear_jar()
                        await message.channel.send(
                            embed=_ui_embed("🫙  Swear Jar",
                                f"{message.author.mention} +**{len(matches)}** to the jar. Total: **{jar.get('total',0):,}**",
                                C.SWEAR),
                            delete_after=5)
            except Exception as e:
                print(f"[SwearJar] {e}")

        # "rigged" filter
        if message.guild and "rigged" in (message.content or "").lower():
            try: await message.delete()
            except discord.Forbidden: pass
            await message.channel.send(
                embed=_ui_embed("🔪  Filtered", f"{message.author.mention} its fair 🔪", C.LOSE),
                delete_after=5)
            return

        # AFK system
        if message.guild:
            key = f"{message.guild.id}-{message.author.id}"
            if key in AFK_STATUS:
                del AFK_STATUS[key]
                await message.channel.send(embed=_ui_embed("✅  Back Online",
                    f"{message.author.mention} is no longer AFK.", C.WIN))
            for user in message.mentions:
                mk = f"{message.guild.id}-{user.id}"
                if mk in AFK_STATUS:
                    await message.channel.send(embed=_ui_embed("💤  User is AFK",
                        f"{user.display_name} is AFK: {AFK_STATUS[mk]}", EMBED_COLOR))

            # XP
            try:
                await update_xp(self.bot, message.author.id, message.guild.id, XP_PER_MESSAGE)
            except Exception as e:
                print(f"[XP] {e}")

    @commands.hybrid_command(name="afk", description="Set your AFK status.")
    async def afk(self, ctx, *, reason: str = "💤  AFK"):
        if not ctx.guild:
            return await ctx.send(embed=_ui_embed("AFK", "Server only.", C.LOSE))
        AFK_STATUS[f"{ctx.guild.id}-{ctx.author.id}"] = reason
        await ctx.send(embed=_ui_embed("💤  AFK Set",
            f"{ctx.author.mention} is now AFK: {reason}", EMBED_COLOR))


async def setup(bot):
    await bot.add_cog(Listeners(bot))
