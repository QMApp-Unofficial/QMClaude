"""
social.py — Social interaction commands
Commands: interact (hug/pat/bonk/stab/lick/kill via select menu), insult, compliment,
          roast, threaten, action, actioncreate, actiondelete, actionlist
Merged: hug/pat/bonk/stab/lick/kill → /interact with dropdown
Merged: insult/threaten/compliment/roast → /social with dropdown
"""
import random
import aiohttp
import discord
from discord.ext import commands

from storage import load_actions, save_actions
from config import TENOR_API_KEY
from ui_utils import C, E, embed, error, warn

TENOR_BASE = "https://tenor.googleapis.com/v2/search"


async def fetch_gif(query: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(TENOR_BASE,
                params={"q": query, "key": TENOR_API_KEY, "limit": 20,
                        "media_filter": "gif", "contentfilter": "medium"},
                timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                results = data.get("results", [])
                if not results:
                    return None
                chosen = random.choice(results[:10])
                media = chosen.get("media_formats", {})
                gif = media.get("gif") or media.get("mediumgif") or media.get("tinygif") or {}
                return gif.get("url")
    except Exception:
        return None


INTERACTIONS = {
    "hug":  {"emoji": "🤗", "verb": "gave", "obj": "a big hug", "gif_query": "anime hug", "color": C.MARRIAGE},
    "pat":  {"emoji": "😊", "verb": "patted", "obj": "on the head", "gif_query": "anime head pat", "color": C.MARRIAGE},
    "bonk": {"emoji": "🔨", "verb": "bonked", "obj": "— straight to jail", "gif_query": "anime bonk", "color": C.LOSE},
    "stab": {"emoji": "🔪", "verb": "stabbed", "obj": "— ouch!", "gif_query": "anime stab", "color": C.LOSE},
    "lick": {"emoji": "👅", "verb": "licked", "obj": "", "gif_query": "anime lick", "color": C.SOCIAL},
    "kill": {"emoji": "💀", "verb": "eliminated", "obj": "dramatically", "gif_query": "anime death", "color": C.LOSE},
}

KILL_METHODS = [
    "dropped a piano on {target}.",
    "challenged {target} to a dance-off — they died of embarrassment.",
    "sent {target} to Italy.",
    "exposed {target}'s search history to the entire server.",
    "forced {target} to watch 12 hours of unskippable YouTube ads.",
]

INSULTS = [
    "You're the human equivalent of a participation trophy.",
    "I'd roast you, but my mum said I'm not allowed to burn trash.",
    "If brains were petrol, you wouldn't have enough to power an ant's go-kart.",
    "You're like a software update. Every time I see you, I think 'not now'.",
    "You're the reason they put instructions on shampoo bottles.",
]

COMPLIMENTS = [
    "You're the MVP of this server.",
    "You make this place genuinely better.",
    "Your memes are elite tier — don't let anyone tell you otherwise.",
    "You are carrying this server on your back. Respect.",
    "You're smarter than the average Discord user, which says a lot.",
]

THREATS = [
    "I will pee your pants", "I will touch you", "I will jiggle your tits",
    "I will send you to Italy", "I will wet your socks (sexually)", "🇫🇷",
]

ROASTS = [
    "You're proof that even evolution makes mistakes.",
    "You have something on your chin... no, the third one down.",
    "I've seen better-looking faces on a clock.",
    "You're not stupid — you just have bad luck thinking.",
    "I would explain it to you, but I left my crayons at home.",
]


class InteractSelect(discord.ui.Select):
    def __init__(self, author: discord.Member, target: discord.Member):
        self.author = author
        self.target = target
        options = [
            discord.SelectOption(label="Hug", emoji="🤗", value="hug"),
            discord.SelectOption(label="Pat", emoji="😊", value="pat"),
            discord.SelectOption(label="Bonk", emoji="🔨", value="bonk"),
            discord.SelectOption(label="Stab", emoji="🔪", value="stab"),
            discord.SelectOption(label="Lick", emoji="👅", value="lick"),
            discord.SelectOption(label="Kill", emoji="💀", value="kill"),
        ]
        super().__init__(placeholder="Choose an action...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("Not your menu.", ephemeral=True)
        action = INTERACTIONS[self.values[0]]
        if self.values[0] == "kill":
            method = random.choice(KILL_METHODS).format(target=self.target.mention)
            desc = f"{self.author.mention} {method}"
        else:
            desc = f"{self.author.mention} **{action['verb']}** {self.target.mention} {action['obj']}"

        e = embed(f"{action['emoji']}  {self.values[0].capitalize()}", desc, action["color"],
            footer=f"{self.author.display_name} → {self.target.display_name}")
        gif = await fetch_gif(action["gif_query"])
        if gif:
            e.set_image(url=gif)
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(embed=e, view=self.view)


class InteractView(discord.ui.View):
    def __init__(self, author: discord.Member, target: discord.Member):
        super().__init__(timeout=30)
        self.add_item(InteractSelect(author, target))


class SocialSelect(discord.ui.Select):
    def __init__(self, author: discord.Member, target: discord.Member):
        self.author = author
        self.target = target
        options = [
            discord.SelectOption(label="Compliment", emoji="❤️", value="compliment"),
            discord.SelectOption(label="Insult", emoji="💀", value="insult"),
            discord.SelectOption(label="Roast", emoji="🔥", value="roast"),
            discord.SelectOption(label="Threaten", emoji="⚔️", value="threaten"),
        ]
        super().__init__(placeholder="Choose your words...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("Not your menu.", ephemeral=True)
        choice = self.values[0]
        pool = {"compliment": COMPLIMENTS, "insult": INSULTS, "roast": ROASTS, "threaten": THREATS}
        emojis = {"compliment": "❤️", "insult": "💀", "roast": "🔥", "threaten": "⚔️"}
        colors = {"compliment": C.MARRIAGE, "insult": C.LOSE, "roast": C.SOCIAL, "threaten": C.WARN}
        line = random.choice(pool[choice])
        e = embed(f"{emojis[choice]}  {choice.capitalize()}",
            f"{self.author.mention} → {self.target.mention}\n\n> {line}",
            colors[choice],
            footer=f"{self.author.display_name} → {self.target.display_name}")
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(embed=e, view=self.view)


class SocialView(discord.ui.View):
    def __init__(self, author: discord.Member, target: discord.Member):
        super().__init__(timeout=30)
        self.add_item(SocialSelect(author, target))


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="interact", description="Interact with another user (hug, pat, bonk, stab, lick, kill).")
    async def interact(self, ctx, member: discord.Member):
        if member.bot:
            return await ctx.send(embed=error("Interact", "Bots don't have feelings... yet."))
        e = embed("✨  Choose an Action",
            f"How would you like to interact with {member.mention}?", C.SOCIAL)
        await ctx.send(embed=e, view=InteractView(ctx.author, member))

    @commands.hybrid_command(name="social", description="Say something to another user (compliment, insult, roast, threaten).")
    async def social(self, ctx, member: discord.Member):
        if member.bot:
            return await ctx.send(embed=error("Social", "Bots don't need compliments."))
        e = embed("💬  Choose Your Words",
            f"What would you like to say to {member.mention}?", C.SOCIAL)
        await ctx.send(embed=e, view=SocialView(ctx.author, member))

    # ── Custom Actions (kept as-is, they're well designed) ─────

    @commands.hybrid_command(name="actioncreate", description="Create a custom action (moderators only).")
    @commands.has_permissions(manage_guild=True)
    async def actioncreate(self, ctx, verb: str, plural: str):
        actions = load_actions()
        verb = verb.lower().strip()
        if not verb.isalpha():
            return await ctx.send(embed=error("Action", "Verb must be letters only."))
        if verb in actions:
            return await ctx.send(embed=error("Action", f"`{verb}` already exists."))
        actions[verb] = plural.strip()
        save_actions(actions)
        await ctx.send(embed=embed(f"{E.SPARKLE}  Action Created",
            f"**Verb:** `{verb}`\n**Output:** _{plural}_\n\nUse: `/action {verb} @user`", C.SOCIAL))

    @commands.hybrid_command(name="action", description="Perform a custom action on someone.")
    async def action(self, ctx, verb: str, member: discord.Member):
        actions = load_actions()
        key = verb.lower().strip()
        if key not in actions:
            return await ctx.send(embed=error("Action", f"`{key}` doesn't exist. See `/actionlist`."))
        e = embed(f"{E.SPARKLE}  Action",
            f"{ctx.author.mention} **{actions[key]}** {member.mention}.", C.SOCIAL,
            footer=f"{ctx.author.display_name} → {member.display_name}")
        gif = await fetch_gif(key)
        if gif:
            e.set_image(url=gif)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="actionlist", description="List all custom actions.")
    async def actionlist(self, ctx):
        actions = load_actions()
        if not actions:
            return await ctx.send(embed=embed(f"{E.SPARKLE}  Actions", "No custom actions yet.", C.SOCIAL))
        lines = [f"`{v}` — _{actions[v]}_" for v in sorted(actions)]
        await ctx.send(embed=embed(f"{E.SPARKLE}  Custom Actions ({len(actions)})", "\n".join(lines), C.SOCIAL))

    @commands.hybrid_command(name="actiondelete", description="Delete a custom action (moderators only).")
    @commands.has_permissions(manage_guild=True)
    async def actiondelete(self, ctx, verb: str):
        actions = load_actions()
        key = verb.lower().strip()
        if key not in actions:
            return await ctx.send(embed=error("Action", f"`{key}` doesn't exist."))
        removed = actions.pop(key)
        save_actions(actions)
        await ctx.send(embed=embed("🗑️  Action Deleted", f"Removed `{key}` — _{removed}_", C.ADMIN))

    async def cog_command_error(self, ctx, err):
        if isinstance(err, commands.MissingPermissions):
            await ctx.send(embed=error("Permission Denied", "You need **Manage Server**."))


async def setup(bot):
    await bot.add_cog(Social(bot))
