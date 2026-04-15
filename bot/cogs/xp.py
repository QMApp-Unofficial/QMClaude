"""
xp.py — XP, levels, ranks, and profile card
Commands: rank, xptop, profile, setbio, xpgive
"""
import discord
from discord.ext import commands

from storage import load_data, save_data, load_coins
from cogs.economy import ensure_user
from ui_utils import C, E, embed, error, success, progress_bar

XP_BIO_KEY = "bios"


def calculate_level(xp: int) -> int:
    return int(int(xp) ** 0.5)

def xp_for_next_level(level: int) -> int:
    return (level + 1) ** 2

def _xp_bar(xp: int, level: int) -> str:
    current_floor = level ** 2
    next_floor = (level + 1) ** 2
    span = next_floor - current_floor
    progress = xp - current_floor
    return progress_bar(progress, span)


class XP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="rank", description="Check your XP rank.")
    async def rank(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        data = load_data()
        gid = str(ctx.guild.id) if ctx.guild else "0"
        guild_data = data.get(gid, {})
        uid = str(member.id)
        xp = int(guild_data.get(uid, {}).get("xp", 0))
        level = calculate_level(xp)
        next_xp = xp_for_next_level(level)
        bar = _xp_bar(xp, level)

        sorted_users = sorted(
            [(k, v) for k, v in guild_data.items() if isinstance(v, dict) and "xp" in v],
            key=lambda x: int(x[1].get("xp", 0)), reverse=True)
        rank_pos = next((i + 1 for i, (u, _) in enumerate(sorted_users) if u == uid), "?")

        rows = [("Level", str(level)), ("XP", f"{xp:,}"), ("Next Lv", f"{next_xp:,}"),
                ("Rank", f"#{rank_pos}/{len(sorted_users)}")]
        col_w = max(len(r[0]) for r in rows)
        table = "\n".join(f"{r[0].ljust(col_w)}  {r[1]}" for r in rows)

        e = embed(f"📊  {member.display_name}'s Rank", f"```\n{table}\n```\n{bar}", C.TRIVIA,
            footer="Earn XP by chatting · 10 XP/message")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="xptop", description="Server XP leaderboard.")
    async def xptop(self, ctx):
        if not ctx.guild:
            return await ctx.send(embed=error("XP", "Server only."))
        data = load_data()
        gid = str(ctx.guild.id)
        guild_data = data.get(gid, {})
        board = []
        for uid, udata in guild_data.items():
            if not isinstance(udata, dict): continue
            xp = int(udata.get("xp", 0))
            if xp <= 0: continue
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            board.append((name, xp, calculate_level(xp), int(uid)))
        board.sort(key=lambda x: x[1], reverse=True)
        board = board[:10]
        if not board:
            return await ctx.send(embed=embed(f"{E.TROPHY}  XP Leaderboard", "No data yet.", C.TRIVIA))

        name_w = max(len(r[0]) for r in board)
        medals = ["🥇", "🥈", "🥉"]
        header = f"{'#':>2}  {'Name'.ljust(name_w)}  {'XP':>8}  {'Lv':>4}"
        sep = "─" * len(header)
        lines = [header, sep]
        for i, (name, xp, level, uid) in enumerate(board):
            you = " *" if uid == ctx.author.id else ""
            medal = medals[i] if i < 3 else f"{i+1:>2}."
            lines.append(f"{medal}  {(name + you).ljust(name_w)}  {xp:>8,}  {level:>4}")
        lines += [sep, "* = you"]
        await ctx.send(embed=embed(f"{E.TROPHY}  XP Leaderboard", f"```\n{chr(10).join(lines)}\n```", C.TRIVIA))

    @commands.hybrid_command(name="profile", description="View a rich profile card.")
    async def profile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        uid, gid = str(member.id), str(ctx.guild.id) if ctx.guild else "0"
        data = load_data()
        coins = load_coins()
        xp = int(data.get(gid, {}).get(uid, {}).get("xp", 0))
        level = calculate_level(xp)
        uc = ensure_user(coins, member.id)
        wallet, bank, stars, debt = uc.get("wallet",0), uc.get("bank",0), uc.get("stars",0), uc.get("debt",0)
        bio = data.get(gid, {}).get(XP_BIO_KEY, {}).get(uid, "_No bio set. Use `/setbio`._")

        guild_data = data.get(gid, {})
        sorted_users = sorted(
            [(k, v) for k, v in guild_data.items() if isinstance(v, dict) and "xp" in v],
            key=lambda x: int(x[1].get("xp", 0)), reverse=True)
        rank_pos = next((i + 1 for i, (u, _) in enumerate(sorted_users) if u == uid), "?")

        bar = _xp_bar(xp, level)
        rows = [("Level", str(level)), ("XP", f"{xp:,}"), ("Rank", f"#{rank_pos}"),
                ("Wallet", f"{wallet:,}"), ("Bank", f"{bank:,}"), ("Stars", f"{stars:,}")]
        if debt > 0:
            rows.append(("Debt", f"{debt:,}"))
        col_w = max(len(r[0]) for r in rows)
        table = "\n".join(f"{r[0].ljust(col_w)}  {r[1]}" for r in rows)

        e = embed(f"{E.CROWN}  {member.display_name}", f"{bio}\n\n```\n{table}\n```\n**XP:** {bar}",
            C.ECONOMY, footer=f"Member since {member.joined_at.strftime('%d %b %Y') if member.joined_at else 'Unknown'}")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="setbio", description="Set your profile bio.")
    async def setbio(self, ctx, *, bio: str):
        if len(bio) > 150:
            return await ctx.send(embed=error("Bio", "Max 150 characters."))
        data = load_data()
        gid = str(ctx.guild.id) if ctx.guild else "0"
        data.setdefault(gid, {}).setdefault(XP_BIO_KEY, {})[str(ctx.author.id)] = bio
        save_data(data)
        await ctx.send(embed=success("Bio Updated!", f"Your bio: _{bio}_"))

    @commands.hybrid_command(name="xpgive", description="Give XP to a user (admin).")
    @commands.has_permissions(administrator=True)
    async def xpgive(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send(embed=error("XP", "Amount must be positive."))
        data = load_data()
        gid = str(ctx.guild.id) if ctx.guild else "0"
        data.setdefault(gid, {}).setdefault(str(member.id), {"xp": 0})
        data[gid][str(member.id)]["xp"] = int(data[gid][str(member.id)].get("xp", 0)) + amount
        save_data(data)
        new_xp = data[gid][str(member.id)]["xp"]
        await ctx.send(embed=success("XP Given!", f"+**{amount:,}** XP to {member.mention}. Total: **{new_xp:,}** (Lv {calculate_level(new_xp)})"))

    async def cog_command_error(self, ctx, err):
        if isinstance(err, commands.MissingPermissions):
            await ctx.send(embed=error("Permission", "Admin only."))


async def setup(bot):
    await bot.add_cog(XP(bot))
