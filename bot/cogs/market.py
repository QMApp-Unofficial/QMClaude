"""
market.py — Stock market system with anti-exploit protections
Commands: stocks, stockvalue, portfolio, buy, sell, resetmarket
Improvements: transaction tax, trade cooldowns, daily limits, max holdings cap
"""
import io
import time

import discord
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands

from storage import load_coins, save_coins, load_stocks, save_stocks
from config import (
    STOCKS, STOCK_TRANSACTION_TAX, STOCK_TRADE_COOLDOWN,
    STOCK_DAILY_TRADE_LIMIT, STOCK_MAX_SHARES_PER_STOCK,
)
from cogs.economy import ensure_user, parse_amount
from ui_utils import C, E, embed, error, success, warn, cooldown_str, ConfirmView


def _today_key() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _stock_lookup(name: str) -> str | None:
    """Case-insensitive stock name lookup."""
    lookup = {s.lower(): s for s in STOCKS}
    return lookup.get(name.lower().strip())


def _check_trade_cooldown(user: dict, stock_name: str) -> int:
    """Returns seconds remaining on cooldown, or 0 if clear."""
    meta = user.setdefault("trade_meta", {})
    last_ts = meta.setdefault("last_trade_ts", {})
    last = float(last_ts.get(stock_name, 0))
    remaining = STOCK_TRADE_COOLDOWN - (time.time() - last)
    return max(0, int(remaining))


def _check_daily_limit(user: dict) -> bool:
    """Returns True if under daily limit."""
    meta = user.setdefault("trade_meta", {})
    daily = meta.setdefault("daily", {"day": "", "count": 0})
    today = _today_key()
    if daily.get("day") != today:
        daily["day"] = today
        daily["count"] = 0
    return daily["count"] < STOCK_DAILY_TRADE_LIMIT


def _record_trade(user: dict, stock_name: str):
    """Mark a trade timestamp and increment daily counter."""
    meta = user.setdefault("trade_meta", {})
    meta.setdefault("last_trade_ts", {})[stock_name] = time.time()
    daily = meta.setdefault("daily", {"day": _today_key(), "count": 0})
    if daily.get("day") != _today_key():
        daily["day"] = _today_key()
        daily["count"] = 0
    daily["count"] = daily.get("count", 0) + 1


class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── STOCK LIST ─────────────────────────────────────────────

    @commands.hybrid_command(name="stocks", description="View all stock prices.")
    async def stocks(self, ctx):
        stocks = load_stocks()
        rows = []
        for name in STOCKS:
            s = stocks.get(name, {})
            price = int(s.get("price", 0))
            history = s.get("history", [])
            change = price - int(history[-2]) if len(history) >= 2 else 0
            arrow = "▲" if change > 0 else ("▼" if change < 0 else "─")
            rows.append(f"{name[:16].ljust(16)}  {str(price).rjust(6)}  {arrow}{abs(change):>+5}")

        table = (
            "```\n"
            f"{'Stock'.ljust(16)}  {'Price':>6}  {'Chg':>5}\n"
            f"{'─' * 32}\n"
            f"{chr(10).join(rows)}\n"
            "```"
        )
        e = embed(f"{E.CHART}  Market Overview", table, C.MARKET,
            footer=f"📊 Updated every 5 min · {STOCK_TRANSACTION_TAX*100:.0f}% transaction tax")
        await ctx.send(embed=e)

    # ── STOCK VALUE + CHART ────────────────────────────────────

    @commands.hybrid_command(name="stockvalue", description="Show a stock's price and chart.")
    async def stockvalue(self, ctx, stock: str):
        stock_name = _stock_lookup(stock)
        if not stock_name:
            return await ctx.send(embed=error("Market", f"Unknown stock. Available: {', '.join(STOCKS)}"))

        stocks = load_stocks()
        data = stocks.get(stock_name)
        if not data:
            return await ctx.send(embed=error("Market", "Stock data not found."))

        price = int(data.get("price", 0))
        history = data.get("history", []) or []
        change = price - int(history[-2]) if len(history) >= 2 else 0

        if len(history) < 2:
            e = embed(stock_name, f"**Price:** `{price}`  **Change:** `{change:+}`\nNot enough data for a chart yet.", C.MARKET)
            return await ctx.send(embed=e)

        # Generate chart
        x = np.arange(len(history))
        y = np.array(history, dtype=float)
        color = "#57dc82" if change >= 0 else "#f05050"

        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150)
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")
        ax.plot(x, y, color=color, linewidth=2.0, solid_capstyle="round")
        ax.fill_between(x, y, y.min(), color=color, alpha=0.08)
        ax.grid(True, which="major", linestyle="-", linewidth=0.35, alpha=0.12, color="#ffffff")
        for spine in ax.spines.values():
            spine.set_color("#3a4250")
            spine.set_linewidth(0.8)
        ax.tick_params(axis="x", colors="#aeb6c2", labelsize=8)
        ax.tick_params(axis="y", colors="#aeb6c2", labelsize=8)
        ax.set_title(f"{stock_name} · Price History", color="#e6edf3", fontsize=13, pad=10)
        ax.set_xlabel("Updates", color="#aeb6c2", fontsize=9)
        ax.set_ylabel("Price", color="#aeb6c2", fontsize=9)
        ymin, ymax = float(y.min()), float(y.max())
        pad = max(2.0, (ymax - ymin) * 0.10 if ymax > ymin else ymax * 0.06 + 2)
        ax.set_ylim(max(0, ymin - pad), ymax + pad)
        ax.scatter([x[-1]], [y[-1]], color=color, s=18, zorder=3)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)

        sign = "+" if change > 0 else ""
        e = embed(stock_name, "Current market snapshot", C.MARKET)
        e.add_field(name="Price", value=f"`{price:,}`", inline=True)
        e.add_field(name="Change", value=f"`{sign}{change}`", inline=True)
        e.add_field(name="History", value=f"`{len(history)} pts`", inline=True)
        e.set_image(url="attachment://stock.png")
        e.set_footer(text=f"📈 {STOCK_TRANSACTION_TAX*100:.0f}% tax on trades · Max {STOCK_MAX_SHARES_PER_STOCK} shares/stock")
        await ctx.send(embed=e, file=discord.File(buf, filename="stock.png"))

    # ── PORTFOLIO ──────────────────────────────────────────────

    @commands.hybrid_command(name="portfolio", description="View your stock portfolio.")
    async def portfolio(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        coins = load_coins()
        user = ensure_user(coins, member.id)
        pf = user.get("portfolio", {})
        stocks = load_stocks()

        rows = []
        total = 0
        for s in STOCKS:
            qty = int(pf.get(s, 0))
            if qty > 0:
                price = int(stocks.get(s, {}).get("price", 0))
                value = qty * price
                total += value
                rows.append(f"{s[:16].ljust(16)}  {str(qty).rjust(4)}  {str(value).rjust(8)}")

        if not rows:
            return await ctx.send(embed=embed(f"📊  {member.display_name}'s Portfolio",
                "No stocks owned.", C.MARKET))

        table = (
            f"```\n{'Stock'.ljust(16)}  {'Qty':>4}  {'Value':>8}\n{'─' * 32}\n"
            f"{chr(10).join(rows)}\n{'─' * 32}\n"
            f"{'Total'.ljust(16)}  {'':>4}  {str(total).rjust(8)}\n```"
        )
        e = embed(f"📊  {member.display_name}'s Portfolio", table, C.MARKET)
        e.add_field(name="Portfolio Value", value=f"`{total:,}` coins", inline=False)
        await ctx.send(embed=e)

    # ── BUY STOCK ──────────────────────────────────────────────

    @commands.hybrid_command(name="buy", description="Buy shares of a stock.")
    async def buy(self, ctx, stock: str, amount: str):
        stock_name = _stock_lookup(stock)
        if not stock_name:
            return await ctx.send(embed=error("Market", f"Unknown stock."))

        stocks = load_stocks()
        price = int(stocks.get(stock_name, {}).get("price", 0))
        if price <= 0:
            return await ctx.send(embed=error("Market", "No price data."))

        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)

        # Anti-exploit checks
        cd = _check_trade_cooldown(user, stock_name)
        if cd > 0:
            return await ctx.send(embed=warn("Trade Cooldown",
                f"Wait **{cooldown_str(cd)}** before trading {stock_name} again."))

        if not _check_daily_limit(user):
            return await ctx.send(embed=warn("Daily Limit",
                f"You've hit the daily trade limit ({STOCK_DAILY_TRADE_LIMIT} trades)."))

        # Parse quantity
        if amount.lower() == "all":
            # Account for tax: cost_per_share = price * (1 + tax)
            effective_price = int(price * (1 + STOCK_TRANSACTION_TAX))
            qty = user["wallet"] // max(1, effective_price)
        else:
            try:
                qty = int(amount)
            except ValueError:
                return await ctx.send(embed=error("Market", "Enter a number or `all`."))

        if qty <= 0:
            return await ctx.send(embed=error("Market", "Invalid amount."))

        # Holdings cap
        current_held = int(user.get("portfolio", {}).get(stock_name, 0))
        if current_held + qty > STOCK_MAX_SHARES_PER_STOCK:
            allowed = STOCK_MAX_SHARES_PER_STOCK - current_held
            return await ctx.send(embed=warn("Holdings Cap",
                f"Max {STOCK_MAX_SHARES_PER_STOCK} shares per stock. You can buy **{allowed}** more."))

        # Calculate cost with tax
        subtotal = price * qty
        tax = int(subtotal * STOCK_TRANSACTION_TAX)
        total_cost = subtotal + tax

        if user["wallet"] < total_cost:
            afford = user["wallet"] // max(1, int(price * (1 + STOCK_TRANSACTION_TAX)))
            return await ctx.send(embed=error("Market",
                f"Not enough coins. You can afford **{afford}** share(s) after tax."))

        user["wallet"] -= total_cost
        pf = user.setdefault("portfolio", {})
        pf[stock_name] = int(pf.get(stock_name, 0)) + qty
        _record_trade(user, stock_name)
        save_coins(coins)

        # Notify background tasks of trade flow
        tasks = self.bot.get_cog("BackgroundTasks")
        if tasks:
            tasks.record_trade(stock_name, "buy", qty)

        e = embed(f"{E.CHECK}  Order Filled — Buy",
            f"Bought **{qty}** shares of **{stock_name}**.", C.MARKET)
        e.add_field(name="Subtotal", value=f"`{subtotal:,}`", inline=True)
        e.add_field(name=f"Tax ({STOCK_TRANSACTION_TAX*100:.0f}%)", value=f"`{tax:,}`", inline=True)
        e.add_field(name="Total Cost", value=f"`{total_cost:,}`", inline=True)
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=False)
        await ctx.send(embed=e)

    # ── SELL STOCK ─────────────────────────────────────────────

    @commands.hybrid_command(name="sell", description="Sell shares of a stock.")
    async def sell(self, ctx, stock: str, amount: str):
        stock_name = _stock_lookup(stock)
        if not stock_name:
            return await ctx.send(embed=error("Market", "Unknown stock."))

        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)

        # Anti-exploit checks
        cd = _check_trade_cooldown(user, stock_name)
        if cd > 0:
            return await ctx.send(embed=warn("Trade Cooldown",
                f"Wait **{cooldown_str(cd)}** before trading {stock_name} again."))

        if not _check_daily_limit(user):
            return await ctx.send(embed=warn("Daily Limit",
                f"You've hit the daily trade limit ({STOCK_DAILY_TRADE_LIMIT})."))

        owned = int(user.get("portfolio", {}).get(stock_name, 0))

        if amount.lower() == "all":
            qty = owned
        else:
            try:
                qty = int(amount)
            except ValueError:
                return await ctx.send(embed=error("Market", "Enter a number or `all`."))

        if qty <= 0:
            return await ctx.send(embed=error("Market", "Invalid amount."))
        if owned < qty:
            return await ctx.send(embed=error("Market", f"You only own **{owned}** shares."))

        stocks = load_stocks()
        price = int(stocks.get(stock_name, {}).get("price", 0))
        gross = price * qty
        tax = int(gross * STOCK_TRANSACTION_TAX)
        revenue = gross - tax

        user["portfolio"][stock_name] = owned - qty
        user["wallet"] += revenue
        _record_trade(user, stock_name)
        save_coins(coins)

        tasks = self.bot.get_cog("BackgroundTasks")
        if tasks:
            tasks.record_trade(stock_name, "sell", qty)

        e = embed(f"{E.CHECK}  Order Filled — Sell",
            f"Sold **{qty}** shares of **{stock_name}**.", C.MARKET)
        e.add_field(name="Gross", value=f"`{gross:,}`", inline=True)
        e.add_field(name=f"Tax ({STOCK_TRANSACTION_TAX*100:.0f}%)", value=f"`-{tax:,}`", inline=True)
        e.add_field(name="Net Revenue", value=f"`{revenue:,}`", inline=True)
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=False)
        await ctx.send(embed=e)

    # ── RESET MARKET (admin) ───────────────────────────────────

    @commands.hybrid_command(name="resetmarket", description="Reset all stock prices (admin).")
    @commands.has_permissions(manage_guild=True)
    async def resetmarket(self, ctx):
        async def do_reset(interaction):
            from config import DEFAULT_STOCK_CONFIG
            stocks = load_stocks()
            for name in STOCKS:
                cfg = DEFAULT_STOCK_CONFIG.get(name, {})
                stocks[name] = {
                    "price": cfg.get("price", 100),
                    "fair_value": cfg.get("fair_value", 100.0),
                    "volatility": cfg.get("volatility", 0.015),
                    "drift": cfg.get("drift", 0.0001),
                    "liquidity": cfg.get("liquidity", 1200),
                    "history": [cfg.get("price", 100)],
                }
            save_stocks(stocks)
            await interaction.message.edit(
                embed=embed(f"{E.WARN_ACT}  Market Reset",
                    "All stock prices reset to defaults.", C.WARN,
                    footer=f"Reset by {ctx.author.display_name}"),
                view=None)

        await ctx.send(
            embed=warn("Confirm Market Reset", "This resets ALL stock prices to defaults."),
            view=ConfirmView(author_id=ctx.author.id, on_confirm=do_reset))


async def setup(bot):
    await bot.add_cog(Stocks(bot))
