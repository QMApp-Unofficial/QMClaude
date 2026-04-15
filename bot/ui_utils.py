"""
ui_utils.py — Shared design system for QMBOT v2
Colours, emoji constants, embed builders, and reusable UI components.
"""
import discord
from typing import Optional


# ══════════════════════════════════════════════════════════════
# Colour Palette
# ══════════════════════════════════════════════════════════════

class C:
    """Brand colours used across the bot."""
    ECONOMY  = discord.Color.from_rgb(159, 89, 255)
    GAMES    = discord.Color.from_rgb(56, 182, 255)
    MARKET   = discord.Color.from_rgb(0, 214, 143)
    SHOP     = discord.Color.from_rgb(255, 165, 0)
    SOCIAL   = discord.Color.from_rgb(255, 87, 139)
    TRIVIA   = discord.Color.from_rgb(255, 200, 40)
    MARRIAGE = discord.Color.from_rgb(255, 105, 180)
    SWEAR    = discord.Color.from_rgb(200, 80, 80)
    ADMIN    = discord.Color.from_rgb(100, 120, 160)
    LOGS     = discord.Color.from_rgb(90, 200, 200)
    MC       = discord.Color.from_rgb(80, 200, 90)
    WIN      = discord.Color.from_rgb(57, 220, 130)
    LOSE     = discord.Color.from_rgb(240, 80, 80)
    WARN     = discord.Color.from_rgb(255, 193, 7)
    NEUTRAL  = discord.Color.from_rgb(72, 80, 100)
    DEBT     = discord.Color.from_rgb(220, 50, 50)


# ══════════════════════════════════════════════════════════════
# Emoji Constants
# ══════════════════════════════════════════════════════════════

class E:
    COIN      = "🪙";  BANK     = "🏦";  STAR    = "⭐";  WALLET  = "👛"
    CHART     = "📈";  CHART_DN = "📉";  DEBT    = "💸";  TAX     = "🧾"
    WORK      = "💼";  PAY      = "💳";  DAILY   = "📅";  BEG     = "🙏"
    ROB       = "🦹";  SAFE     = "🔐";  TROPHY  = "🏆";  CROWN   = "👑"
    DICE      = "🎲";  CARDS    = "🃏";  JACKPOT = "💎"
    BAG       = "🛍️"; ITEM     = "📦";  PRICE   = "🏷️"
    HEART     = "❤️";  FIRE     = "🔥";  SKULL   = "💀";  SPARKLE = "✨"
    CORRECT   = "✅";  WRONG    = "❌";  STREAK  = "🔥";  QUESTION = "❓"
    LOG       = "📋";  DELETE   = "🗑️";  EDIT    = "✏️"
    CLOCK     = "⏰";  LOCK     = "🔒";  CHECK   = "✅";  CROSS   = "❌"
    ARROW     = "➤";   SHIELD   = "🛡️"; WARN_ACT = "⚠️"
    WIN       = "🎉";  LOSE     = "💥"


# ══════════════════════════════════════════════════════════════
# Embed Builders
# ══════════════════════════════════════════════════════════════

def embed(
    title: str,
    description: str = "",
    color: discord.Color = C.NEUTRAL,
    footer: Optional[str] = None,
    thumbnail: Optional[str] = None,
) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    if footer:
        e.set_footer(text=footer)
    if thumbnail:
        e.set_thumbnail(url=thumbnail)
    return e


def success(title: str, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    return embed(f"{E.WIN}  {title}", description, C.WIN, footer)


def error(title: str, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    return embed(f"{E.CROSS}  {title}", description, C.LOSE, footer)


def warn(title: str, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    return embed(f"{E.WARN_ACT}  {title}", description, C.WARN, footer)


def info(title: str, description: str = "", color: discord.Color = C.NEUTRAL) -> discord.Embed:
    return embed(title, description, color)


# ══════════════════════════════════════════════════════════════
# Formatting Helpers
# ══════════════════════════════════════════════════════════════

def cooldown_str(seconds: int) -> str:
    h, r = divmod(max(0, int(seconds)), 3600)
    m, s = divmod(r, 60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"


def progress_bar(value: float, total: float, length: int = 12) -> str:
    pct = min(1.0, value / total) if total > 0 else 0.0
    filled = int(pct * length)
    return f"`{'█' * filled}{'░' * (length - filled)}` {int(pct * 100)}%"


def balance_bar(wallet: int, bank: int, debt: int = 0) -> str:
    parts = [f"{E.WALLET} **{wallet:,}**", f"{E.BANK} **{bank:,}**"]
    if debt > 0:
        parts.append(f"{E.DEBT} **{debt:,}** owed")
    return "  ·  ".join(parts)


def code_table(rows: list[tuple], headers: Optional[tuple] = None) -> str:
    """Build a clean monospaced table in a code block."""
    if not rows:
        return "```\nNo data.\n```"
    all_rows = [headers] + list(rows) if headers else list(rows)
    widths = [max(len(str(r[i])) for r in all_rows) for i in range(len(all_rows[0]))]
    lines = []
    for j, row in enumerate(all_rows):
        line = "  ".join(str(row[i]).ljust(widths[i]) for i in range(len(row)))
        lines.append(line)
        if headers and j == 0:
            lines.append("─" * len(line))
    return f"```\n{chr(10).join(lines)}\n```"


# ══════════════════════════════════════════════════════════════
# Reusable Views
# ══════════════════════════════════════════════════════════════

class ConfirmView(discord.ui.View):
    """Generic confirm / cancel buttons. Calls on_confirm callback on yes."""

    def __init__(self, *, author_id: int, on_confirm, timeout: int = 30):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.on_confirm = on_confirm

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=error("Access Denied", "This isn't yours."), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def yes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)
        await self.on_confirm(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def no_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(
            embed=embed("❌  Cancelled", "Action cancelled.", C.LOSE), view=self)
        self.stop()

    async def on_timeout(self):
        for c in self.children:
            c.disabled = True


class PaginatorView(discord.ui.View):
    """Generic paginator for lists of embeds."""

    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=120)
        self.pages = pages
        self.author_id = author_id
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current >= len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Not your menu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = max(0, self.current - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current = min(len(self.pages) - 1, self.current + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)
