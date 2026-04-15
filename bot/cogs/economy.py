"""
economy.py — Core economy system
Commands: balance, deposit, withdraw, daily, beg, career, work, pay, tax, debt,
          repaydebt, star, stars, starleaderboard, baltop, rob, bankrob,
          weeklypay, reseteconomy
"""
import discord
from discord.ext import commands
import random
import time
from datetime import datetime, timedelta, timezone

from storage import load_coins, save_coins
from config import (
    ALWAYS_BANKROB_USER_ID,
    BANKROB_STEAL_MIN_PCT, BANKROB_STEAL_MAX_PCT,
    BANKROB_MIN_STEAL, BANKROB_MAX_STEAL_PCT_CAP,
    TAX_BRACKETS, CAREER_FIELDS, WORK_COOLDOWN, PROMOTION_THRESHOLDS,
    DEBT_INTEREST_RATE, DEBT_INTEREST_INTERVAL,
)
from ui_utils import C, E, embed, success, error, warn, cooldown_str, ConfirmView


# ═══════════════════════════════════════════════════════════════
# Shared Economy Helpers (imported by other cogs)
# ═══════════════════════════════════════════════════════════════

def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def _week_key() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year}-W{now.isocalendar()[1]}"


def ensure_user(coins: dict, user_id) -> dict:
    """Canonical ensure_user — all cogs should import from here."""
    uid = str(user_id)
    defaults = {
        "wallet": 100, "bank": 0, "debt": 0, "debt_since": 0,
        "stars": 0, "last_daily": 0, "last_beg": 0,
        "last_rob": 0, "last_bankrob": 0, "last_work": 0,
        "active_effects": {},
        "star_meta": {"day": _today_key(), "given": {}},
        "career_field": None, "career_tier": 0, "career_shifts": 0,
        "career_week_key": "", "career_week_shifts": 0,
        "portfolio": {}, "trade_meta": {},
    }
    if uid not in coins:
        coins[uid] = dict(defaults)
    else:
        for k, v in defaults.items():
            coins[uid].setdefault(k, v)
        # Reset daily star tracking
        meta = coins[uid].get("star_meta")
        if not isinstance(meta, dict) or meta.get("day") != _today_key():
            coins[uid]["star_meta"] = {"day": _today_key(), "given": {}}
    return coins[uid]


def has_effect(user: dict, effect: str) -> bool:
    effects = user.get("active_effects", {})
    return effect in effects and effects[effect] > time.time()


def calculate_tax(amount: int) -> tuple[int, float]:
    for threshold, rate in TAX_BRACKETS:
        if amount <= threshold:
            return int(amount * rate), rate
    return int(amount * 0.45), 0.45


def accrue_debt_interest(user: dict) -> int:
    debt = int(user.get("debt", 0))
    if debt <= 0:
        return 0
    debt_since = float(user.get("debt_since", 0))
    full_hours = int((time.time() - debt_since) / DEBT_INTEREST_INTERVAL)
    if full_hours < 1:
        return debt
    new_debt = int(debt * ((1 + DEBT_INTEREST_RATE) ** full_hours))
    user["debt"] = new_debt
    user["debt_since"] = debt_since + full_hours * DEBT_INTEREST_INTERVAL
    return new_debt


def parse_amount(text: str, maximum: int) -> int | None:
    """Parse 'all', '50%', or a number. Returns None on invalid."""
    text = text.strip().lower()
    if text == "all":
        return maximum
    if text.endswith("%"):
        try:
            pct = float(text[:-1])
            return max(1, int(maximum * pct / 100))
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        return None


def _career_tier(user: dict) -> int:
    shifts = int(user.get("career_shifts", 0))
    tier = 0
    for i, threshold in enumerate(PROMOTION_THRESHOLDS):
        if shifts >= threshold:
            tier = i
    return min(tier, len(PROMOTION_THRESHOLDS) - 1)


# ═══════════════════════════════════════════════════════════════
# Career Pick View
# ═══════════════════════════════════════════════════════════════

class CareerPickView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        for key, data in CAREER_FIELDS.items():
            btn = discord.ui.Button(
                label=f"{data['icon']}  {data['name']}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"career_{key}",
            )
            btn.callback = self._make_cb(key)
            self.add_item(btn)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=error("Career", "This isn't your career choice."), ephemeral=True)
            return False
        return True

    def _make_cb(self, field_key: str):
        async def callback(interaction: discord.Interaction):
            coins = load_coins()
            user = ensure_user(coins, interaction.user.id)
            if user.get("career_field"):
                return await interaction.response.send_message(
                    embed=warn("Career", f"You already work in **{CAREER_FIELDS[user['career_field']]['name']}**."),
                    ephemeral=True)
            user["career_field"] = field_key
            user["career_tier"] = 0
            user["career_shifts"] = 0
            save_coins(coins)
            field = CAREER_FIELDS[field_key]
            for c in self.children:
                c.disabled = True
            await interaction.response.edit_message(
                embed=success("Career Started!",
                    f"You're now a **{field['icon']} {field['tiers'][0]['title']}** in **{field['name']}**!\n\n"
                    f"Use `/work` every hour to earn coins and climb the ranks.\n"
                    f"**10 shifts** earns your first promotion."),
                view=self)
            self.stop()
        return callback


# ═══════════════════════════════════════════════════════════════
# Economy Cog
# ═══════════════════════════════════════════════════════════════

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── BALANCE ────────────────────────────────────────────────

    @commands.hybrid_command(name="balance", description="Check your coin balance.")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        coins = load_coins()
        user = ensure_user(coins, member.id)
        debt = accrue_debt_interest(user)
        save_coins(coins)
        total = user["wallet"] + user["bank"]

        rows = [
            ("Wallet", f"{user['wallet']:,}"),
            ("QMBank", f"{user['bank']:,}"),
            ("Stars",  f"{user['stars']:,}"),
            ("Total",  f"{total:,}"),
        ]
        if debt > 0:
            rows.append(("Debt", f"{debt:,}  (3%/hr)"))

        col_w = max(len(r[0]) for r in rows)
        table = "\n".join(f"{r[0].ljust(col_w)}  {r[1]}" for r in rows)

        e = embed(
            f"{E.CROWN}  {member.display_name}",
            f"```\n{table}\n```",
            C.ECONOMY,
            footer=f"{'Your' if member == ctx.author else member.display_name + chr(39) + 's'} account",
        )
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    # ── DEPOSIT / WITHDRAW ────────────────────────────────────

    @commands.hybrid_command(name="deposit", description="Deposit coins into your bank.")
    async def deposit(self, ctx, amount: str):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        amt = parse_amount(amount, user["wallet"])
        if amt is None or amt <= 0:
            return await ctx.send(embed=error("Deposit", "Enter a valid number, `all`, or a percentage like `50%`."))
        if amt > user["wallet"]:
            return await ctx.send(embed=error("Deposit", f"You only have `{user['wallet']:,}` in your wallet."))
        user["wallet"] -= amt
        user["bank"] += amt
        save_coins(coins)
        e = success("Deposited!", f"Moved **{amt:,}** coins into {E.BANK} QMBank.")
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=True)
        e.add_field(name=f"{E.BANK} QMBank", value=f"`{user['bank']:,}`", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="withdraw", description="Withdraw coins from your bank.")
    async def withdraw(self, ctx, amount: str):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        amt = parse_amount(amount, user["bank"])
        if amt is None or amt <= 0:
            return await ctx.send(embed=error("Withdraw", "Enter a valid number, `all`, or a percentage."))
        if amt > user["bank"]:
            return await ctx.send(embed=error("Withdraw", f"You only have `{user['bank']:,}` in the bank."))
        user["bank"] -= amt
        user["wallet"] += amt
        save_coins(coins)
        e = success("Withdrawn!", f"Moved **{amt:,}** coins to your {E.WALLET} wallet.")
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=True)
        e.add_field(name=f"{E.BANK} QMBank", value=f"`{user['bank']:,}`", inline=True)
        await ctx.send(embed=e)

    # ── DAILY ──────────────────────────────────────────────────

    @commands.hybrid_command(name="daily", description="Claim your daily coins.")
    async def daily(self, ctx):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        now = datetime.now(timezone.utc)
        last = datetime.fromtimestamp(user["last_daily"], timezone.utc)
        if last.date() == now.date():
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return await ctx.send(embed=warn("Already Claimed",
                f"{E.CLOCK} Come back in **{cooldown_str(int((tomorrow - now).total_seconds()))}**."))
        reward = random.randint(100, 500)
        user["wallet"] += reward
        user["last_daily"] = now.timestamp()
        save_coins(coins)
        e = success("Daily Reward!", f"{E.COIN} You received **{reward:,}** coins!")
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=False)
        e.set_footer(text="Come back tomorrow!")
        await ctx.send(embed=e)

    # ── BEG ────────────────────────────────────────────────────

    @commands.hybrid_command(name="beg", description="Beg for some coins.")
    async def beg(self, ctx):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        now = time.time()
        if now - user["last_beg"] < 120:
            return await ctx.send(embed=warn("Slow Down",
                f"Try again in **{cooldown_str(int(120 - (now - user['last_beg'])))}**."))
        responses = [
            "A kind stranger tossed you some change.",
            "Someone felt sorry for you.",
            "A passing NPC dropped their wallet.",
            "The universe took pity on you.",
            "A pigeon dropped coins. Somehow.",
        ]
        amount = random.randint(5, 50)
        user["wallet"] += amount
        user["last_beg"] = now
        save_coins(coins)
        e = embed(f"{E.BEG}  Begging Result",
            f"{random.choice(responses)}\n\n{E.COIN} You got **{amount}** coins.", C.ECONOMY)
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=False)
        await ctx.send(embed=e)

    # ── CAREER ─────────────────────────────────────────────────

    @commands.hybrid_command(name="career", description="View or choose your career field.")
    async def career(self, ctx):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        field_key = user.get("career_field")
        if field_key:
            field = CAREER_FIELDS[field_key]
            tier = _career_tier(user)
            tier_data = field["tiers"][tier]
            shifts = user.get("career_shifts", 0)
            next_thresh = PROMOTION_THRESHOLDS[tier + 1] if tier < len(PROMOTION_THRESHOLDS) - 1 else None

            desc = (
                f"{field['icon']}  **{field['name']}**\n"
                f"Title: **{tier_data['title']}**\n"
                f"Tier: **{tier + 1}/{len(field['tiers'])}**\n"
                f"Shifts: **{shifts}**\n"
            )
            if next_thresh:
                desc += f"Next promotion: **{next_thresh} shifts** ({next_thresh - shifts} to go)"
            else:
                desc += "**MAX RANK** {E.TROPHY}"
            return await ctx.send(embed=embed("💼  Your Career", desc, C.ECONOMY))

        e = embed(
            "💼  Choose Your Career",
            "Pick a field below. **This is permanent** — you cannot switch.\n"
            "Your title and pay improve as you work more shifts.",
            C.ECONOMY)
        await ctx.send(embed=e, view=CareerPickView(ctx.author.id))

    # ── WORK ───────────────────────────────────────────────────

    @commands.hybrid_command(name="work", description="Work a shift and earn coins.")
    async def work(self, ctx):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        now = time.time()

        if now - user["last_work"] < WORK_COOLDOWN:
            return await ctx.send(embed=warn("Too Tired",
                f"{E.CLOCK} Come back in **{cooldown_str(int(WORK_COOLDOWN - (now - user['last_work'])))}**."))

        field_key = user.get("career_field")
        if not field_key:
            return await ctx.send(embed=warn("No Career",
                "You don't have a job yet! Use `/career` to pick your field."))

        field = CAREER_FIELDS[field_key]
        old_tier = _career_tier(user)

        user["career_shifts"] = int(user.get("career_shifts", 0)) + 1
        wk = _week_key()
        if user.get("career_week_key") != wk:
            user["career_week_key"] = wk
            user["career_week_shifts"] = 0
        user["career_week_shifts"] = int(user.get("career_week_shifts", 0)) + 1

        new_tier = _career_tier(user)
        promoted = new_tier > old_tier
        tier_data = field["tiers"][new_tier]
        earned = random.randint(tier_data["min"], tier_data["max"])

        # Time multiplier
        hour = datetime.now(timezone.utc).hour
        if 9 <= hour < 17:
            time_label, multiplier = "regular hours", 1.0
        elif 17 <= hour < 22:
            time_label, multiplier = "evening shift", 1.15
        else:
            time_label, multiplier = "overnight shift", 1.30
        earned = int(earned * multiplier)

        tax, rate = calculate_tax(earned)
        net = earned - tax
        user["wallet"] += net
        user["last_work"] = now
        save_coins(coins)

        desc = (
            f"_{field['icon']} {tier_data['title']} · {field['name']}_\n\n"
            f"**Gross:** {earned:,} coins\n"
            f"**Tax ({int(rate*100)}%):** -{tax:,}\n"
            f"**Net Pay:** +{net:,} coins\n\n"
            f"*{time_label.capitalize()} ({int((multiplier-1)*100)}% bonus)*"
        )
        if promoted:
            desc += f"\n\n🎉 **PROMOTED to {field['tiers'][new_tier]['title']}!**"

        e = embed(f"{E.WORK}  Payday!", desc, C.WIN if promoted else C.ECONOMY)
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=True)
        e.add_field(name="Total Shifts", value=f"`{user['career_shifts']:,}`", inline=True)
        e.set_footer(text="Night +30% · Evening +15% · Hourly cooldown")
        await ctx.send(embed=e)

    # ── PAY ────────────────────────────────────────────────────

    @commands.hybrid_command(name="pay", description="Send coins to another user.")
    async def pay(self, ctx, member: discord.Member, amount: str):
        if member == ctx.author or member.bot:
            return await ctx.send(embed=error("Pay", "Invalid target."))
        coins = load_coins()
        sender = ensure_user(coins, ctx.author.id)
        receiver = ensure_user(coins, member.id)
        amt = parse_amount(amount, sender["wallet"])
        if amt is None or amt <= 0:
            return await ctx.send(embed=error("Pay", "Enter a valid amount."))
        if sender["wallet"] < amt:
            return await ctx.send(embed=error("Pay", f"You only have `{sender['wallet']:,}` coins."))
        sender["wallet"] -= amt
        receiver["wallet"] += amt
        save_coins(coins)
        e = success("Payment Sent!", f"{ctx.author.mention} sent **{amt:,}** {E.COIN} to {member.mention}.")
        e.add_field(name="Your Wallet", value=f"`{sender['wallet']:,}`", inline=True)
        e.add_field(name=f"{member.display_name}", value=f"`{receiver['wallet']:,}`", inline=True)
        await ctx.send(embed=e)

    # ── TAX ────────────────────────────────────────────────────

    @commands.hybrid_command(name="tax", description="Calculate the tax on an amount.")
    async def tax(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send(embed=error("Tax", "Amount must be positive."))
        tax_amt, rate = calculate_tax(amount)
        net = amount - tax_amt
        brackets = []
        prev, found = 0, False
        for threshold, r in TAX_BRACKETS:
            label = f"up to {int(threshold):,}" if threshold != float("inf") else f"{prev:,}+"
            mark = " ◄" if not found and amount <= threshold else ""
            if mark:
                found = True
            brackets.append(f"`{label}` → {int(r*100)}%{mark}")
            prev = int(threshold) if threshold != float("inf") else prev
        e = embed(f"{E.TAX}  Tax Calculator",
            f"**Amount:** {amount:,}\n**Rate:** {int(rate*100)}%\n"
            f"**Tax:** -{tax_amt:,}\n**Net:** {net:,}\n\n" + "\n".join(brackets),
            C.ECONOMY)
        await ctx.send(embed=e)

    # ── DEBT / REPAY ───────────────────────────────────────────

    @commands.hybrid_command(name="debt", description="Check your debt balance.")
    async def debt(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        coins = load_coins()
        user = ensure_user(coins, member.id)
        debt = accrue_debt_interest(user)
        save_coins(coins)
        if debt <= 0:
            return await ctx.send(embed=success("Debt Free!", f"{member.display_name} owes nothing. 🎉"))
        e = embed(f"{E.DEBT}  {member.display_name}'s Debt",
            f"Current debt: **{debt:,}** coins\nInterest: **3%/hr** compound\nUse `/repaydebt` to pay.", C.DEBT)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="repaydebt", description="Repay your debt (or part of it).")
    async def repaydebt(self, ctx, amount: str = "all"):
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        debt = accrue_debt_interest(user)
        if debt <= 0:
            return await ctx.send(embed=success("No Debt!", "Nothing to repay. 🎉"))
        pay = parse_amount(amount, min(debt, user["wallet"]))
        if pay is None or pay <= 0:
            return await ctx.send(embed=error("Repay", "Enter a valid amount."))
        pay = min(pay, user["wallet"], debt)
        if pay == 0:
            return await ctx.send(embed=error("Repay", "You have no coins to repay with."))
        user["wallet"] -= pay
        user["debt"] = max(0, debt - pay)
        if user["debt"] == 0:
            user["debt_since"] = 0
        save_coins(coins)
        remaining = user["debt"]
        if remaining == 0:
            e = success("Debt Cleared! 🎉", f"Paid **{pay:,}** coins — debt free!")
        else:
            e = embed(f"{E.DEBT}  Partial Repayment",
                f"Paid **{pay:,}** coins.\nRemaining: **{remaining:,}**.", C.WARN)
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=False)
        await ctx.send(embed=e)

    # ── STARS ──────────────────────────────────────────────────

    @commands.hybrid_command(name="star", description="Give someone a golden star.")
    async def star(self, ctx, member: discord.Member):
        if member == ctx.author or member.bot:
            return await ctx.send(embed=error("Star", "Invalid target."))
        coins = load_coins()
        giver = ensure_user(coins, ctx.author.id)
        receiver = ensure_user(coins, member.id)
        key = str(member.id)
        given_today = int(giver["star_meta"]["given"].get(key, 0))
        if given_today >= 2:
            return await ctx.send(embed=warn("Limit", f"You've given {member.mention} 2 stars today already."))
        giver["star_meta"]["given"][key] = given_today + 1
        receiver["stars"] += 1
        save_coins(coins)
        e = embed(f"{E.STAR}  Star Given!",
            f"{ctx.author.mention} gifted {member.mention} a golden star!\n"
            f"They now have **{receiver['stars']:,}** {E.STAR}", C.TRIVIA)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="stars", description="Check golden stars.")
    async def stars(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        coins = load_coins()
        user = ensure_user(coins, member.id)
        e = embed(f"{E.STAR}  {member.display_name}'s Stars",
            f"**{user['stars']:,}** golden stars", C.TRIVIA)
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="baltop", description="Richest users leaderboard.")
    async def baltop(self, ctx):
        coins = load_coins()
        board = sorted(coins.items(),
            key=lambda x: x[1].get("wallet", 0) + x[1].get("bank", 0), reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        rows = []
        for i, (uid, data) in enumerate(board):
            total = data.get("wallet", 0) + data.get("bank", 0)
            member = ctx.guild.get_member(int(uid)) if ctx.guild else None
            name = (member.display_name if member else f"User {uid}")[:16]
            you = " *" if int(uid) == ctx.author.id else ""
            medal = medals[i] if i < 3 else f"{i+1:>2}."
            rows.append((medal, name + you, f"{data.get('wallet',0):,}", f"{data.get('bank',0):,}", f"{total:,}"))

        if not rows:
            return await ctx.send(embed=embed(f"{E.TROPHY}  Balance Leaderboard", "No data yet.", C.ECONOMY))

        name_w = max(len(r[1]) for r in rows)
        header = f"{'':3}  {'Name'.ljust(name_w)}  {'Wallet':>8}  {'Bank':>8}  {'Total':>8}"
        sep = "─" * len(header)
        lines = [header, sep]
        for medal, name, wallet, bank, total in rows:
            lines.append(f"{medal}  {name.ljust(name_w)}  {wallet:>8}  {bank:>8}  {total:>8}")
        lines += [sep, f"{'':3}  {'* = you'.ljust(name_w)}"]
        e = embed(f"{E.TROPHY}  Balance Leaderboard", f"```\n{chr(10).join(lines)}\n```", C.ECONOMY)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="starleaderboard", description="Star leaderboard.")
    async def starleaderboard(self, ctx):
        coins = load_coins()
        board = sorted(coins.items(), key=lambda x: int(x[1].get("stars", 0)), reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(board):
            member = ctx.guild.get_member(int(uid)) if ctx.guild else None
            name = (member.display_name if member else f"User {uid}")[:20]
            you = "  ← you" if int(uid) == ctx.author.id else ""
            medal = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{medal}  **{name}** — `{data.get('stars',0):,}` {E.STAR}{you}")
        e = embed(f"{E.TROPHY}  Star Leaderboard", "\n".join(lines) or "No data.", C.TRIVIA)
        await ctx.send(embed=e)

    # ── ROB ────────────────────────────────────────────────────

    @commands.hybrid_command(name="rob", description="Attempt to rob someone's wallet.")
    async def rob(self, ctx, member: discord.Member):
        if member == ctx.author or member.bot:
            return await ctx.send(embed=error("Rob", "Invalid target."))
        coins = load_coins()
        robber = ensure_user(coins, ctx.author.id)
        victim = ensure_user(coins, member.id)
        now = time.time()
        cd = 60 if has_effect(robber, "kachow_clock_until") else 300
        if now - robber["last_rob"] < cd:
            return await ctx.send(embed=warn("Cooldown",
                f"{E.CLOCK} Try again in **{cooldown_str(int(cd-(now-robber['last_rob'])))}**."))
        if int(victim.get("wallet", 0)) <= 0:
            return await ctx.send(embed=warn("Rob Failed", f"{member.display_name} is broke."))
        robber["last_rob"] = now

        if random.random() < (0.20 if has_effect(victim, "comfort_until") else 0.40):
            steal = random.randint(10, min(200, victim["wallet"]))
            victim["wallet"] -= steal
            robber["wallet"] += steal
            save_coins(coins)
            e = embed(f"{E.ROB}  Robbery Success!", f"You swiped **{steal:,}** coins from {member.mention}.", C.WIN)
            e.add_field(name=f"{E.WALLET} Wallet", value=f"`{robber['wallet']:,}`", inline=True)
        else:
            debt_added = random.randint(30, 100)
            old_debt = int(robber.get("debt", 0))
            robber["debt"] = old_debt + debt_added
            if old_debt == 0:
                robber["debt_since"] = now
            hit = min(robber["wallet"], int(debt_added * 0.03))
            robber["wallet"] = max(0, robber["wallet"] - hit)
            save_coins(coins)
            e = embed(f"{E.LOSE}  Busted!",
                f"Caught trying to rob {member.mention}.\n\n"
                f"{E.DEBT} Debt added: `{debt_added:,}`\n"
                f"{E.COIN} Fine: `-{hit:,}`", C.LOSE)
            e.add_field(name=f"{E.WALLET} Wallet", value=f"`{robber['wallet']:,}`", inline=True)
            e.add_field(name=f"{E.DEBT} Debt", value=f"`{robber['debt']:,}`", inline=True)
        await ctx.send(embed=e)

    # ── BANK ROB ───────────────────────────────────────────────

    @commands.hybrid_command(name="bankrob", description="Attempt to rob someone's bank.")
    async def bankrob(self, ctx, member: discord.Member):
        if member == ctx.author or member.bot:
            return await ctx.send(embed=error("Bank Rob", "Invalid target."))
        coins = load_coins()
        robber = ensure_user(coins, ctx.author.id)
        victim = ensure_user(coins, member.id)
        now = time.time()
        cd = 180 if has_effect(robber, "kachow_clock_until") else 600
        if now - robber["last_bankrob"] < cd:
            return await ctx.send(embed=warn("Cooldown",
                f"{E.CLOCK} Try again in **{cooldown_str(int(cd-(now-robber['last_bankrob'])))}**."))
        if int(victim.get("bank", 0)) <= 0:
            return await ctx.send(embed=warn("Bank Rob Failed", f"{member.display_name} has no savings."))
        robber["last_bankrob"] = now

        if random.random() < (0.05 if has_effect(victim, "comfort_until") else 0.20):
            pct = random.uniform(BANKROB_STEAL_MIN_PCT, BANKROB_STEAL_MAX_PCT)
            amount = max(BANKROB_MIN_STEAL, int(victim["bank"] * pct))
            amount = min(amount, int(victim["bank"] * BANKROB_MAX_STEAL_PCT_CAP), victim["bank"])
            victim["bank"] -= amount
            robber["wallet"] += amount
            save_coins(coins)
            e = embed(f"{E.BANK}  Heist Success!",
                f"Cracked {member.mention}'s vault for **{amount:,}** coins!", C.WIN)
            e.add_field(name=f"{E.WALLET} Wallet", value=f"`{robber['wallet']:,}`", inline=True)
        else:
            debt_added = random.randint(80, 200)
            old_debt = int(robber.get("debt", 0))
            robber["debt"] = old_debt + debt_added
            if old_debt == 0:
                robber["debt_since"] = now
            hit = min(robber["wallet"], int(debt_added * 0.03))
            robber["wallet"] = max(0, robber["wallet"] - hit)
            save_coins(coins)
            e = embed(f"{E.LOSE}  Heist Failed!",
                f"Security caught you at {member.mention}'s vault.\n\n"
                f"{E.DEBT} Debt: `+{debt_added:,}`  {E.COIN} Fine: `-{hit:,}`", C.LOSE)
            e.add_field(name=f"{E.WALLET} Wallet", value=f"`{robber['wallet']:,}`", inline=True)
            e.add_field(name=f"{E.DEBT} Debt", value=f"`{robber['debt']:,}`", inline=True)
        await ctx.send(embed=e)

    # ── WEEKLY PAY (admin) ─────────────────────────────────────

    @commands.hybrid_command(name="weeklypay", description="Distribute weekly top-worker bonuses (admin).")
    @commands.has_permissions(administrator=True)
    async def weeklypay(self, ctx):
        wk = _week_key()
        coins = load_coins()
        field_top: dict[str, tuple[str, int]] = {}
        overall_top = None

        for uid, data in coins.items():
            if data.get("career_week_key") != wk:
                continue
            shifts = int(data.get("career_week_shifts", 0))
            fk = data.get("career_field")
            if not fk or not shifts:
                continue
            if fk not in field_top or shifts > field_top[fk][1]:
                field_top[fk] = (uid, shifts)
            if overall_top is None or shifts > overall_top[1]:
                overall_top = (uid, shifts)

        if not field_top:
            return await ctx.send(embed=warn("Weekly Pay", "No one worked this week."))

        lines = []
        for fk, (uid, shifts) in field_top.items():
            bonus = CAREER_FIELDS[fk]["tiers"][-1]["max"] * 2
            ensure_user(coins, uid)
            coins[uid]["wallet"] = int(coins[uid].get("wallet", 0)) + bonus
            member = ctx.guild.get_member(int(uid)) if ctx.guild else None
            name = member.display_name if member else f"<@{uid}>"
            lines.append(f"{CAREER_FIELDS[fk]['icon']} **{CAREER_FIELDS[fk]['name']}** → {name} ({shifts} shifts) +{bonus:,}")

        if overall_top:
            uid, shifts = overall_top
            coins[uid]["wallet"] = int(coins[uid].get("wallet", 0)) + 5000
            member = ctx.guild.get_member(int(uid)) if ctx.guild else None
            name = member.display_name if member else f"<@{uid}>"
            lines.append(f"\n👑 **Overall MVP:** {name} → +5,000 bonus!")

        save_coins(coins)
        await ctx.send(embed=success("Weekly Bonuses Paid! 💰", "\n".join(lines)))

    # ── RESET ECONOMY (admin) ──────────────────────────────────

    @commands.hybrid_command(name="reseteconomy", description="Reset all balances (admin).")
    @commands.has_permissions(administrator=True)
    async def reseteconomy(self, ctx):
        async def do_reset(interaction):
            from storage import load_data, save_data
            coins = load_coins()
            for uid in coins:
                coins[uid]["wallet"] = 100
                coins[uid]["bank"] = 0
                coins[uid]["debt"] = 0
                coins[uid]["debt_since"] = 0
            save_coins(coins)
            data = load_data()
            data["economy_reset_ts"] = time.time()
            save_data(data)
            await interaction.message.edit(
                embed=embed(f"{E.WARN_ACT}  Economy Reset",
                    "All wallets reset to **100** coins. Banks and debts cleared.\n"
                    "⚠️ Trivia prizes reduced by 75% for 24 hours.", C.WARN,
                    footer=f"Reset by {ctx.author.display_name}"),
                view=None)

        await ctx.send(
            embed=warn("Confirm Economy Reset",
                "This will reset **ALL** wallets to 100 and clear all banks/debts.\n"
                "This cannot be undone."),
            view=ConfirmView(author_id=ctx.author.id, on_confirm=do_reset))

    async def cog_command_error(self, ctx, err):
        if isinstance(err, commands.MissingPermissions):
            await ctx.send(embed=error("Permission Denied", "You need **Administrator**."))


async def setup(bot):
    await bot.add_cog(Economy(bot))
