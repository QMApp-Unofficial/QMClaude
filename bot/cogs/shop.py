"""
shop.py — Item shop system with coin and star shops
Commands: shop, starshop, buyitem, buystaritem, inventory, iteminfo, claim, claimcrash, claimusb
"""
import asyncio
import random
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

import storage
from storage import (
    load_coins, save_coins, load_inventory, save_inventory,
    load_shop_stock, save_shop_stock, load_stocks, save_stocks,
)
from config import COIN_SHOP_ITEMS, STAR_SHOP_ITEMS, SHOP_RESTOCK_MINUTES
from cogs.economy import ensure_user
from ui_utils import C, E, embed as _embed, error, success, warn, ConfirmView

EMBED_COLOR = C.SHOP


def ensure_inventory(inv: dict, user_id) -> dict:
    uid = str(user_id)
    if uid not in inv:
        inv[uid] = {}
    return inv[uid]


def _item_lookup(name: str) -> str | None:
    target = name.lower().strip()
    for item in list(COIN_SHOP_ITEMS) + list(STAR_SHOP_ITEMS):
        if item.lower() == target:
            return item
    return None


def generate_stock(items: dict) -> dict:
    prices = [items[item]["price"] for item in items]
    min_p, max_p = min(prices), max(prices)
    stock = {}
    for item, meta in items.items():
        price = meta["price"]
        score = 1 - ((price - min_p) / (max_p - min_p)) if max_p != min_p else 1.0
        score = max(0, min(1, score))
        appear_chance = 0.15 + (score * 0.85)
        if random.random() > appear_chance:
            stock[item] = 0
            continue
        upper = max(1, int(round(1 + score * (meta["max_stock"] - 1))))
        stock[item] = random.randint(1, upper)
    return stock


def _default_stock_data() -> dict:
    return {"coin_shop": generate_stock(COIN_SHOP_ITEMS), "star_shop": generate_stock(STAR_SHOP_ITEMS)}


def ensure_shop_stock(stock: dict) -> dict:
    if not isinstance(stock, dict):
        stock = _default_stock_data()
    for key, items in [("coin_shop", COIN_SHOP_ITEMS), ("star_shop", STAR_SHOP_ITEMS)]:
        if key not in stock or not isinstance(stock.get(key), dict):
            stock[key] = generate_stock(items)
        for item in items:
            stock[key].setdefault(item, 0)
        for item in list(stock[key]):
            if item not in items:
                stock[key].pop(item)
    save_shop_stock(stock)
    return stock


BANK_NOTE_WHEEL = [1, 5, 10, 20, 50, 100, 200, 250, 1000, 1500, 2000, "JACKPOT"]

def _bank_note_reward() -> int:
    weighted = [1,1,1, 5,5, 10,10, 20,20, 50,50, 100,100, 200, 250, 1000, 1500, 2000, "JACKPOT"]
    choice = random.choice(weighted)
    return 10000 if choice == "JACKPOT" else int(choice)

def _spinner_text(values: list) -> str:
    line = " | ".join(str(v) for v in values)
    middle = str(values[2])
    left = " | ".join(str(v) for v in values[:2])
    prefix_len = len(left) + 3 if left else 0
    center_pos = prefix_len + (len(middle) // 2)
    arrow_line = " " * center_pos + "▲"
    return f"```\n{line}\n{arrow_line}\n```"

def _future_ts(hours: int = 0) -> float:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).timestamp()

def _reset_all_json_except_actions():
    reset_map = {
        storage.DATA_FILE: {}, storage.COOLDOWN_FILE: {}, storage.COIN_DATA_FILE: {},
        storage.SHOP_FILE: _default_stock_data(), storage.INVENTORY_FILE: {},
        storage.MARRIAGE_FILE: {}, storage.PLAYLIST_FILE: {}, storage.QUEST_FILE: {},
        storage.EVENT_FILE: {}, storage.STOCK_FILE: {}, storage.SUGGESTION_FILE: [],
        storage.TRIVIA_STATS_FILE: {}, storage.TRIVIA_STREAKS_FILE: {},
        storage.BEG_STATS_FILE: {},
        storage.SWEAR_JAR_FILE: {"total": 0, "users": {}},
        storage.STICKER_FILE: {"total": 0, "users": {}, "daily": {}},
    }
    for path, default in reset_map.items():
        storage._save_json(path, default)


def _format_shop(items_dict: dict, stock_map: dict, currency: str = "coins") -> str:
    lines = []
    for item, meta in sorted(items_dict.items(), key=lambda x: x[1]["price"]):
        qty = stock_map.get(item, 0)
        emoji = meta.get("emoji", "📦")
        status = f"`{qty}` left" if qty > 0 else "~~sold out~~"
        lines.append(f"{emoji} **{item}** — `{meta['price']:,}` {currency}  ({status})")
    return "\n".join(lines) or "Shop is empty."


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.restock.start()

    def cog_unload(self):
        self.restock.cancel()

    @tasks.loop(minutes=SHOP_RESTOCK_MINUTES)
    async def restock(self):
        save_shop_stock(_default_stock_data())

    @restock.before_loop
    async def before_restock(self):
        await self.bot.wait_until_ready()

    # ── SHOP ───────────────────────────────────────────────────

    @commands.hybrid_command(name="shop", description="View the coin shop.")
    async def shop(self, ctx):
        stock = ensure_shop_stock(load_shop_stock())
        desc = _format_shop(COIN_SHOP_ITEMS, stock["coin_shop"], "coins")
        e = _embed(f"{E.BAG}  Coin Shop", desc, EMBED_COLOR,
            footer=f"🔄 Restocks every {SHOP_RESTOCK_MINUTES} min · /buyitem <name>")
        await ctx.send(embed=e)

    @commands.hybrid_command(name="starshop", description="View the star shop.")
    async def starshop(self, ctx):
        stock = ensure_shop_stock(load_shop_stock())
        desc = _format_shop(STAR_SHOP_ITEMS, stock["star_shop"], "stars")
        e = _embed(f"{E.STAR}  Star Shop", desc, EMBED_COLOR,
            footer=f"🔄 Restocks every {SHOP_RESTOCK_MINUTES} min · /buystaritem <name>")
        await ctx.send(embed=e)

    # ── BUY ITEM ───────────────────────────────────────────────

    @commands.hybrid_command(name="buyitem", description="Buy from the coin shop.")
    async def buyitem(self, ctx, *, item: str):
        real = _item_lookup(item)
        if not real or real not in COIN_SHOP_ITEMS:
            return await ctx.send(embed=error("Shop", "Item not found in coin shop."))
        stock = ensure_shop_stock(load_shop_stock())
        if stock["coin_shop"].get(real, 0) <= 0:
            return await ctx.send(embed=error("Shop", "Out of stock."))
        price = COIN_SHOP_ITEMS[real]["price"]
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        if user["wallet"] < price:
            return await ctx.send(embed=error("Shop", "Not enough coins."))
        inv = load_inventory()
        user_inv = ensure_inventory(inv, ctx.author.id)
        user["wallet"] -= price
        user_inv[real] = user_inv.get(real, 0) + 1
        stock["coin_shop"][real] -= 1
        save_coins(coins); save_inventory(inv); save_shop_stock(stock)
        e = success("Purchase Complete!", f"Bought **{real}**")
        e.add_field(name="Cost", value=f"`{price:,}`", inline=True)
        e.add_field(name="Stock Left", value=f"`{stock['coin_shop'][real]}`", inline=True)
        e.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=True)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="buystaritem", description="Buy from the star shop.")
    async def buystaritem(self, ctx, *, item: str):
        real = _item_lookup(item)
        if not real or real not in STAR_SHOP_ITEMS:
            return await ctx.send(embed=error("Star Shop", "Item not found in star shop."))
        stock = ensure_shop_stock(load_shop_stock())
        if stock["star_shop"].get(real, 0) <= 0:
            return await ctx.send(embed=error("Star Shop", "Out of stock."))
        price = STAR_SHOP_ITEMS[real]["price"]
        coins = load_coins()
        user = ensure_user(coins, ctx.author.id)
        if user.get("stars", 0) < price:
            return await ctx.send(embed=error("Star Shop", "Not enough stars."))
        inv = load_inventory()
        user_inv = ensure_inventory(inv, ctx.author.id)
        user["stars"] -= price
        user_inv[real] = user_inv.get(real, 0) + 1
        stock["star_shop"][real] -= 1
        save_coins(coins); save_inventory(inv); save_shop_stock(stock)
        e = success("Purchase Complete!", f"Bought **{real}**")
        e.add_field(name="Cost", value=f"`{price}` ✦", inline=True)
        e.add_field(name="Stock Left", value=f"`{stock['star_shop'][real]}`", inline=True)
        e.add_field(name=f"{E.STAR} Stars", value=f"`{user['stars']}`", inline=True)
        await ctx.send(embed=e)

    # ── INVENTORY ──────────────────────────────────────────────

    @commands.hybrid_command(name="inventory", description="View your inventory.")
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        inv = load_inventory()
        user_inv = ensure_inventory(inv, member.id)
        if not user_inv:
            return await ctx.send(embed=_embed(f"📦  {member.display_name}'s Inventory",
                "Inventory is empty.", EMBED_COLOR))
        lines = [f"**{item}** × `{qty}`" for item, qty in sorted(user_inv.items()) if qty > 0]
        e = _embed(f"📦  {member.display_name}'s Inventory", "\n".join(lines) or "Empty.", EMBED_COLOR,
            footer="Use /claim <item> to use an item")
        await ctx.send(embed=e)

    # ── ITEM INFO ──────────────────────────────────────────────

    @commands.hybrid_command(name="iteminfo", description="Show info for a shop item.")
    async def iteminfo(self, ctx, *, item: str = "all"):
        if item.lower() == "all":
            lines = []
            for name, meta in list(COIN_SHOP_ITEMS.items()) + list(STAR_SHOP_ITEMS.items()):
                currency = "coins" if name in COIN_SHOP_ITEMS else "✦ stars"
                lines.append(f"{meta.get('emoji','📦')} **{name}** — `{meta['price']}` {currency}\n{meta['description']}\n")
            return await ctx.send(embed=_embed("📦  Item Encyclopedia", "\n".join(lines)[:4000], EMBED_COLOR))

        real = _item_lookup(item)
        if not real:
            return await ctx.send(embed=error("Item Info", "Item not found."))
        meta = (COIN_SHOP_ITEMS | STAR_SHOP_ITEMS)[real]
        currency = "coins" if real in COIN_SHOP_ITEMS else "✦ stars"
        e = _embed(f"{meta.get('emoji','📦')}  {real}",
            f"**Cost:** `{meta['price']}` {currency}\n**Max Stock:** `{meta['max_stock']}`\n\n{meta['description']}",
            EMBED_COLOR)
        await ctx.send(embed=e)

    # ── CLAIM ──────────────────────────────────────────────────

    @commands.hybrid_command(name="claim", description="Use an item from your inventory.")
    async def claim(self, ctx, *, item: str):
        real = _item_lookup(item)
        if not real:
            return await ctx.send(embed=error("Claim", "Item not found."))
        inv = load_inventory()
        user_inv = ensure_inventory(inv, ctx.author.id)
        if user_inv.get(real, 0) <= 0:
            return await ctx.send(embed=error("Claim", "You don't own that item."))
        if real == "Crash token":
            return await ctx.send(embed=_embed("Claim", "Use `/claimcrash <stock>` instead.", EMBED_COLOR))
        if real == "Fwiz's USB":
            return await ctx.send(embed=_embed("Claim", "Use `/claimusb <member> <stock>` instead.", EMBED_COLOR))

        async def do_claim(interaction):
            inv_data = load_inventory()
            ui = ensure_inventory(inv_data, ctx.author.id)
            if ui.get(real, 0) <= 0:
                return await interaction.message.edit(embed=error("Claim", "You no longer own that."), view=None)
            ui[real] -= 1
            if ui[real] <= 0: ui.pop(real, None)
            save_inventory(inv_data)
            coins = load_coins()
            user = ensure_user(coins, ctx.author.id)

            if real == "Kachow clock":
                user.setdefault("active_effects", {})["kachow_clock_until"] = _future_ts(hours=1)
                save_coins(coins)
                await interaction.message.edit(embed=success("Kachow Clock Activated!",
                    "Rob cooldown → **1 min** · Bankrob → **3 min** for 1 hour."), view=None)
            elif real == "Pocket PC":
                user.setdefault("active_effects", {})["comfort_until"] = _future_ts(hours=1)
                save_coins(coins)
                await interaction.message.edit(embed=success("Comfort Buff Active!",
                    "Rob defense boosted for 1 hour."), view=None)
            elif real == "Bank note":
                await interaction.message.edit(embed=_embed("Bank Note", "Spinning...", EMBED_COLOR), view=None)
                final_reward = _bank_note_reward()
                for delay in [0.08, 0.10, 0.12, 0.16, 0.20, 0.28]:
                    vals = [random.choice(BANK_NOTE_WHEEL) for _ in range(5)]
                    await interaction.message.edit(embed=_embed("Bank Note", _spinner_text(vals), EMBED_COLOR))
                    await asyncio.sleep(delay)
                final_vals = [random.choice(BANK_NOTE_WHEEL) for _ in range(5)]
                final_vals[2] = final_reward
                coins = load_coins(); user = ensure_user(coins, ctx.author.id)
                user["wallet"] += final_reward; save_coins(coins)
                re = _embed("Bank Note Result", f"{_spinner_text(final_vals)}\nYou won **{final_reward:,}** coins!", EMBED_COLOR)
                re.add_field(name=f"{E.WALLET} Wallet", value=f"`{user['wallet']:,}`", inline=False)
                await interaction.message.edit(embed=re)
            elif real == "Imran's Nose":
                _reset_all_json_except_actions()
                await interaction.message.edit(embed=success("Imran's Nose Used!",
                    "All data reset. Action commands preserved."), view=None)

        await ctx.send(embed=_embed("Confirm Claim", f"Use **{real}**?", EMBED_COLOR),
            view=ConfirmView(author_id=ctx.author.id, on_confirm=do_claim))

    # ── CLAIM CRASH ────────────────────────────────────────────

    @commands.hybrid_command(name="claimcrash", description="Crash a stock's price by 50%.")
    async def claimcrash(self, ctx, stock: str):
        inv = load_inventory()
        user_inv = ensure_inventory(inv, ctx.author.id)
        if user_inv.get("Crash token", 0) <= 0:
            return await ctx.send(embed=error("Crash Token", "You don't own one."))
        stocks = load_stocks()
        stock_names = {s.lower(): s for s in stocks}
        stock_name = stock_names.get(stock.lower().strip())
        if not stock_name:
            return await ctx.send(embed=error("Crash Token", "Unknown stock."))

        async def do_crash(interaction):
            inv_data = load_inventory()
            ui = ensure_inventory(inv_data, ctx.author.id)
            if ui.get("Crash token", 0) <= 0:
                return await interaction.message.edit(embed=error("Crash", "Token gone."), view=None)
            ui["Crash token"] -= 1
            if ui["Crash token"] <= 0: ui.pop("Crash token", None)
            save_inventory(inv_data)
            sd = load_stocks()
            old = int(sd[stock_name].get("price", 0))
            new = max(1, old // 2)
            sd[stock_name]["price"] = new
            sd[stock_name].setdefault("history", []).append(new)
            sd[stock_name]["history"] = sd[stock_name]["history"][-240:]
            save_stocks(sd)
            await interaction.message.edit(embed=success("Stock Crashed!",
                f"**{stock_name}** halved: `{old}` → `{new}`"), view=None)

        await ctx.send(embed=warn("Confirm Crash", f"Halve **{stock_name}**?"),
            view=ConfirmView(author_id=ctx.author.id, on_confirm=do_crash))

    # ── CLAIM USB ──────────────────────────────────────────────

    @commands.hybrid_command(name="claimusb", description="Steal shares from another user.")
    async def claimusb(self, ctx, member: discord.Member, stock: str):
        if member == ctx.author:
            return await ctx.send(embed=error("USB", "Can't target yourself."))
        inv = load_inventory()
        if ensure_inventory(inv, ctx.author.id).get("Fwiz's USB", 0) <= 0:
            return await ctx.send(embed=error("USB", "You don't own one."))
        coins = load_coins()
        victim = ensure_user(coins, member.id)
        stock_names = {s.lower(): s for s in victim.get("portfolio", {})}
        stock_name = stock_names.get(stock.lower().strip())
        if not stock_name or int(victim["portfolio"].get(stock_name, 0)) <= 0:
            return await ctx.send(embed=error("USB", "Target has no shares in that stock."))

        async def do_usb(interaction):
            inv_data = load_inventory()
            ui = ensure_inventory(inv_data, ctx.author.id)
            if ui.get("Fwiz's USB", 0) <= 0:
                return await interaction.message.edit(embed=error("USB", "Token gone."), view=None)
            ui["Fwiz's USB"] -= 1
            if ui["Fwiz's USB"] <= 0: ui.pop("Fwiz's USB", None)
            save_inventory(inv_data)
            cd = load_coins()
            attacker = ensure_user(cd, ctx.author.id)
            vict = ensure_user(cd, member.id)
            owned = int(vict["portfolio"].get(stock_name, 0))
            if owned <= 0:
                save_coins(cd)
                return await interaction.message.edit(embed=error("USB", "No shares left."), view=None)
            if random.random() < 0.40:
                stolen = random.randint(1, max(1, int(owned * 0.40)))
                vict["portfolio"][stock_name] = owned - stolen
                attacker.setdefault("portfolio", {})[stock_name] = int(attacker.get("portfolio", {}).get(stock_name, 0)) + stolen
                save_coins(cd)
                await interaction.message.edit(embed=success("USB Success!",
                    f"Stole **{stolen}** shares of **{stock_name}** from {member.mention}."), view=None)
            else:
                save_coins(cd)
                await interaction.message.edit(embed=error("USB Failed",
                    f"The USB couldn't crack {member.mention}'s security."), view=None)

        await ctx.send(embed=warn("Confirm USB", f"Use on {member.mention} for **{stock_name}**?"),
            view=ConfirmView(author_id=ctx.author.id, on_confirm=do_usb))


async def setup(bot):
    await bot.add_cog(Shop(bot))
