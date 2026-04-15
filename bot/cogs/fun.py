"""
fun.py — Fun & entertainment commands
Commands: 8ball, rps, choose, ship, howgay, iq, simp, pp, rate,
          textfx (mock/clap/emojify/fandomify via select),
          fact, quote, wyr, dare, nhie, topic, confess
"""
import hashlib
import random
import time
from datetime import date

import aiohttp
import discord
from discord.ext import commands

from config import TENOR_API_KEY, CONFESSIONS_CHANNEL_ID, CONFESSION_LOG_USER_ID
from ui_utils import C, E, embed, error, warn, success

TENOR_BASE = "https://tenor.googleapis.com/v2/search"

_iq_cd: dict[int, float] = {}
_rate_cd: dict[int, float] = {}
IQ_COOLDOWN = 3600
RATE_COOLDOWN = 300


def _seed(text: str) -> int:
    key = f"{text.lower().strip()}{date.today().isoformat()}"
    return int(hashlib.md5(key.encode()).hexdigest(), 16) % 101


def _cd_remaining(store, uid, seconds):
    return max(0, int(seconds - (time.time() - store.get(uid, 0))))


async def fetch_gif(query: str) -> str | None:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(TENOR_BASE,
                params={"q": query, "key": TENOR_API_KEY, "limit": 20,
                        "media_filter": "gif", "contentfilter": "medium"},
                timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status != 200: return None
                data = await r.json()
                results = data.get("results", [])
                if not results: return None
                chosen = random.choice(results[:10])
                media = chosen.get("media_formats", {})
                gif = media.get("gif") or media.get("mediumgif") or media.get("tinygif") or {}
                return gif.get("url")
    except Exception:
        return None


EIGHT_BALL = [
    ("It is certain.", True), ("Without a doubt.", True), ("Most likely.", True),
    ("Outlook good.", True), ("Signs point to yes.", True), ("Yes, definitely.", True),
    ("Reply hazy, try again.", None), ("Ask again later.", None), ("Cannot predict now.", None),
    ("Don't count on it.", False), ("My reply is no.", False), ("Very doubtful.", False),
    ("Outlook not so good.", False), ("My sources say no.", False),
]

WYR_QUESTIONS = [
    "Would you rather fight 100 duck-sized horses or 1 horse-sized duck?",
    "Would you rather have unlimited money but no friends, or be broke with amazing friends?",
    "Would you rather be able to fly at walking pace, or run 100mph but only backwards?",
    "Would you rather always say everything you think, or never speak again?",
    "Would you rather have a rewind button for life or a pause button?",
    "Would you rather be the funniest person in the room or the smartest?",
    "Would you rather live without music or without colour?",
    "Would you rather know when you die or how you die?",
    "Would you rather be famous but hated or unknown but beloved?",
    "Would you rather give up the internet for a year or streaming services forever?",
]

NHIE = [
    "Never have I ever replied 'on my way' while still in bed.",
    "Never have I ever pretended to be busy to avoid someone.",
    "Never have I ever accidentally liked an old photo while stalking.",
    "Never have I ever Googled myself.",
    "Never have I ever stayed up past 4 AM for no reason.",
    "Never have I ever faked being sick to get out of plans.",
    "Never have I ever read someone's messages without them knowing.",
    "Never have I ever cheated at a board game and got away with it.",
]

TOPICS = [
    "If you found out life was a simulation, what's the first thing you'd test?",
    "What's the most genuinely useful skill most people don't have?",
    "What's a law that doesn't exist but absolutely should?",
    "What's an opinion you hold that the majority disagrees with?",
    "If this server were a country, what would the national dish be?",
    "What mundane superpower would change your life the most?",
    "What skill would be useless if society collapsed?",
]

DARES = [
    "Change your nickname to something embarrassing for an hour.",
    "Send the last thing you copied to your clipboard.",
    "Post your Spotify top artist or most played song.",
    "DM someone 'I think we need to talk' and wait 2 minutes.",
    "Type with your elbows for your next three messages.",
    "Post your screen time stats.",
]

FACTS = [
    "Honey never spoils. 3000-year-old honey from Egyptian tombs was still edible.",
    "A day on Venus is longer than a year on Venus.",
    "Octopuses have three hearts, and two stop when they swim.",
    "The shortest war lasted 38 minutes — Britain vs Zanzibar, 1896.",
    "Bananas are slightly radioactive due to potassium.",
    "Wombat poo is cube-shaped.",
    "Sharks are older than trees — 450 million years.",
    "Humans share 50% of their DNA with bananas.",
    "The unicorn is Scotland's national animal.",
    "Crows can recognise human faces and hold grudges for years.",
]

FAMOUS_QUOTES = [
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Be yourself; everyone else is already taken.", "Oscar Wilde"),
    ("It always seems impossible until it is done.", "Nelson Mandela"),
    ("You miss 100% of the shots you don't take.", "Wayne Gretzky"),
    ("In the middle of every difficulty lies opportunity.", "Albert Einstein"),
]


class WYRView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="Next Question", style=discord.ButtonStyle.primary)
    async def next_q(self, interaction, button):
        e = embed("🤔  Would You Rather…", random.choice(WYR_QUESTIONS), C.GAMES,
            footer=f"Asked by {interaction.user.display_name}")
        await interaction.response.edit_message(embed=e, view=WYRView())


class NHIEView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.current = random.choice(NHIE)

    def build_embed(self):
        return embed("🙋  Never Have I Ever…", self.current, C.GAMES,
            footer="Press a button or get a new one!")

    @discord.ui.button(label="✋ I Have", style=discord.ButtonStyle.danger)
    async def have(self, interaction, button):
        await interaction.response.send_message(
            embed=embed("📢", f"{interaction.user.mention} **HAS** done this 👀", C.LOSE))

    @discord.ui.button(label="🙅 I Haven't", style=discord.ButtonStyle.success)
    async def havent(self, interaction, button):
        await interaction.response.send_message(
            embed=embed("📢", f"{interaction.user.mention} has **NOT** done this ✅", C.WIN))

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_q(self, interaction, button):
        self.current = random.choice(NHIE)
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


class RPSChallengeView(discord.ui.View):
    BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}
    EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    def __init__(self, challenger, opponent):
        super().__init__(timeout=60)
        self.challenger = challenger
        self.opponent = opponent
        self.choices = {}
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id not in (self.challenger.id, self.opponent.id):
            await interaction.response.send_message("Not in this game.", ephemeral=True)
            return False
        return True

    def _make_cb(self, choice):
        async def callback(interaction):
            if interaction.user.id in self.choices:
                return await interaction.response.send_message("Already picked!", ephemeral=True)
            self.choices[interaction.user.id] = choice
            await interaction.response.send_message(
                embed=embed("🤫", f"You chose **{self.EMOJI[choice]} {choice}**.", C.NEUTRAL), ephemeral=True)
            if len(self.choices) == 2:
                await self._resolve()
        return callback

    async def _resolve(self):
        for c in self.children: c.disabled = True
        c1, c2 = self.choices[self.challenger.id], self.choices[self.opponent.id]
        if c1 == c2:
            result, color = "**Tie!** 🤝", C.NEUTRAL
        elif self.BEATS[c1] == c2:
            result, color = f"**{self.challenger.display_name} wins!** 🎉", C.WIN
        else:
            result, color = f"**{self.opponent.display_name} wins!** 🎉", C.WIN
        e = embed("🪨📄✂️  Result",
            f"{self.challenger.mention}  {self.EMOJI[c1]}\n"
            f"{self.opponent.mention}  {self.EMOJI[c2]}\n\n{result}", color)
        if self.message:
            await self.message.edit(embed=e, view=self)
        self.stop()

    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.secondary)
    async def rock(self, i, b): await self._make_cb("rock")(i)
    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.secondary)
    async def paper(self, i, b): await self._make_cb("paper")(i)
    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.secondary)
    async def scissors(self, i, b): await self._make_cb("scissors")(i)


class TextFXSelect(discord.ui.Select):
    def __init__(self, text: str):
        self.text = text
        options = [
            discord.SelectOption(label="Mock", emoji="🧽", value="mock", description="sPoNgEbOb CaSe"),
            discord.SelectOption(label="Clap", emoji="👏", value="clap", description="ADD 👏 CLAPS"),
            discord.SelectOption(label="Emojify", emoji="🔡", value="emojify", description="Big letter emoji"),
            discord.SelectOption(label="Fandomify", emoji="✨", value="fandomify", description="UwU speak"),
        ]
        super().__init__(placeholder="Pick a text effect...", options=options)

    async def callback(self, interaction):
        t = self.text
        if self.values[0] == "mock":
            result = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(t))
            title = "🧽  mOcKeD"
        elif self.values[0] == "clap":
            result = " 👏 ".join(t.split())
            title = "👏  Clapped"
        elif self.values[0] == "emojify":
            result = ""
            for ch in t.lower():
                if ch.isalpha(): result += f":regional_indicator_{ch}: "
                elif ch == " ": result += "   "
                elif ch.isdigit():
                    names = ["zero","one","two","three","four","five","six","seven","eight","nine"]
                    result += f":{names[int(ch)]}: "
            if len(result) > 500: result = result[:500] + "…"
            title = "🔡  Emojified"
        elif self.values[0] == "fandomify":
            result = t.replace("r","w").replace("l","w").replace("R","W").replace("L","W")
            result = result.replace("na","nya").replace("no","nyo").replace("ne","nye")
            result = result.replace("th","d").replace("Th","D")
            result += random.choice([" uwu"," owo"," >w<"," :3"," nya~"," ✨",""])
            title = "✨  Fandomified"
        else:
            return

        e = embed(title, f"> {result}", C.SOCIAL)
        for child in self.view.children: child.disabled = True
        await interaction.response.edit_message(embed=e, view=self.view)


class TextFXView(discord.ui.View):
    def __init__(self, text: str):
        super().__init__(timeout=30)
        self.add_item(TextFXSelect(text))


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball.")
    async def eightball(self, ctx, *, question: str):
        answer, sentiment = random.choice(EIGHT_BALL)
        color = C.WIN if sentiment else (C.LOSE if sentiment is False else C.NEUTRAL)
        e = embed("🎱  Magic 8-Ball", f"**Q:** {question}\n**A:** {answer}", color)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="rps", description="Rock Paper Scissors vs someone.")
    async def rps(self, ctx, opponent: discord.Member):
        if opponent == ctx.author or opponent.bot:
            return await ctx.send(embed=error("RPS", "Invalid opponent."))
        view = RPSChallengeView(ctx.author, opponent)
        e = embed("🪨📄✂️  Rock Paper Scissors",
            f"{ctx.author.mention} vs {opponent.mention}\n\nBoth pick your weapon below. Choices are hidden.",
            C.GAMES, footer="60 seconds to choose")
        msg = await ctx.send(embed=e, view=view)
        view.message = msg

    @commands.hybrid_command(name="choose", description="Pick from a comma-separated list.")
    async def choose(self, ctx, *, options: str):
        choices = [o.strip() for o in options.split(",") if o.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=error("Choose", "Give 2+ options separated by commas."))
        await ctx.send(embed=embed("🤔  The bot chooses…",
            f"**{random.choice(choices)}**\n\n*From: {', '.join(choices)}*", C.GAMES))

    @commands.hybrid_command(name="textfx", description="Apply a text effect (mock, clap, emojify, fandomify).")
    async def textfx(self, ctx, *, text: str):
        e = embed("✨  Text Effects", f"Choose an effect for:\n> {text[:200]}", C.SOCIAL)
        await ctx.send(embed=e, view=TextFXView(text))

    @commands.hybrid_command(name="ship", description="Ship two users.")
    async def ship(self, ctx, user1: discord.Member, user2: discord.Member):
        score = _seed(f"{min(user1.id, user2.id)}{max(user1.id, user2.id)}")
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        if score >= 90: verdict = "Absolutely soulmates. 💍"
        elif score >= 70: verdict = "Strong vibes. 💕"
        elif score >= 50: verdict = "Could work. 🤔"
        elif score >= 30: verdict = "Complicated... 😬"
        else: verdict = "Run. Now. 💀"
        ship_name = user1.display_name[:len(user1.display_name)//2] + user2.display_name[len(user2.display_name)//2:]
        e = embed(f"💘  {user1.display_name} × {user2.display_name}",
            f"**Ship name:** _{ship_name}_\n\n`{bar}` **{score}%**\n{verdict}", C.MARRIAGE)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="howgay", description="How gay are you today?")
    async def howgay(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        score = _seed(f"gay{member.id}")
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        e = embed("🏳️‍🌈  Gay-O-Meter", f"`{bar}` **{score}%**", C.SOCIAL,
            footer=f"Results for {member.display_name}")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="iq", description="Check someone's IQ.")
    async def iq(self, ctx, member: discord.Member = None):
        remaining = _cd_remaining(_iq_cd, ctx.author.id, IQ_COOLDOWN)
        if remaining:
            return await ctx.send(embed=warn("Cooldown", f"Try again in **{remaining//60}m {remaining%60}s**."))
        _iq_cd[ctx.author.id] = time.time()
        member = member or ctx.author
        iq_val = max(1, int(_seed(f"iq{member.id}") * 2.5))
        if iq_val >= 200: verdict = "Literally Einstein reborn."
        elif iq_val >= 140: verdict = "Certified genius."
        elif iq_val >= 100: verdict = "Disappointingly average."
        elif iq_val >= 70: verdict = "Concerning."
        else: verdict = "How are you even typing?"
        e = embed("🧠  IQ Test", f"{member.mention}\n\n**IQ: {iq_val}**\n_{verdict}_", C.TRIVIA,
            footer="Cooldown: 1 hour")
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="simp", description="Simp detector.")
    async def simp(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        score = _seed(f"simp{member.id}")
        bar = "█" * (score // 10) + "░" * (10 - score // 10)
        e = embed("💝  Simp Detector", f"{member.mention}\n\n`{bar}` **{score}% simp**", C.MARRIAGE)
        e.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=e)

    @commands.hybrid_command(name="pp", description="The important measurement.")
    async def pp(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        size = _seed(f"pp{member.id}") // 10
        await ctx.send(embed=embed("📏  PP Size",
            f"{member.mention}\n\n`8{'=' * size}D`\n\n**{size} inches**", C.NEUTRAL))

    @commands.hybrid_command(name="rate", description="Rate anything out of 10.")
    async def rate(self, ctx, *, thing: str):
        remaining = _cd_remaining(_rate_cd, ctx.author.id, RATE_COOLDOWN)
        if remaining:
            return await ctx.send(embed=warn("Cooldown", f"Try again in **{remaining}s**."))
        _rate_cd[ctx.author.id] = time.time()
        score = _seed(thing) // 10
        bar = "█" * score + "░" * (10 - score)
        await ctx.send(embed=embed("⭐  Rating",
            f"**{thing}**\n\n`{bar}` **{score}/10**", C.TRIVIA, footer="Cooldown: 5 min"))

    @commands.hybrid_command(name="fact", description="Random interesting fact.")
    async def fact(self, ctx):
        await ctx.send(embed=embed("🧠  Random Fact", random.choice(FACTS), C.TRIVIA, footer="✨"))

    @commands.hybrid_command(name="quote", description="Get a famous quote or quote a replied message.")
    async def quote(self, ctx):
        ref = ctx.message.reference
        if ref and ref.resolved and isinstance(ref.resolved, discord.Message):
            qm = ref.resolved
            e = discord.Embed(description=f"*\"{qm.content or '[no text]'}\"*",
                color=C.TRIVIA, timestamp=qm.created_at)
            e.set_author(name=qm.author.display_name, icon_url=qm.author.display_avatar.url)
            e.set_footer(text=f"Quoted by {ctx.author.display_name}")
            return await ctx.send(embed=e)
        text, attr = random.choice(FAMOUS_QUOTES)
        await ctx.send(embed=embed("💬  Quote", f"*\"{text}\"*\n\n— **{attr}**", C.TRIVIA))

    @commands.hybrid_command(name="wyr", description="Would You Rather.")
    async def wyr(self, ctx):
        await ctx.send(embed=embed("🤔  Would You Rather…", random.choice(WYR_QUESTIONS), C.GAMES,
            footer=f"Asked by {ctx.author.display_name}"), view=WYRView())

    @commands.hybrid_command(name="dare", description="Get a random dare.")
    async def dare(self, ctx):
        await ctx.send(embed=embed("😈  Dare", random.choice(DARES), C.SOCIAL, footer="Do it."))

    @commands.hybrid_command(name="nhie", description="Never Have I Ever.")
    async def nhie(self, ctx):
        view = NHIEView()
        await ctx.send(embed=view.build_embed(), view=view)

    @commands.hybrid_command(name="topic", description="Random conversation starter.")
    async def topic(self, ctx):
        await ctx.send(embed=embed("💬  Conversation Starter", random.choice(TOPICS), C.TRIVIA))

    @commands.hybrid_command(name="confess", description="Send an anonymous confession.")
    async def confess(self, ctx, *, confession: str):
        try: await ctx.message.delete()
        except Exception: pass
        if not ctx.guild:
            return await ctx.send(embed=error("Confession", "Server only."))
        ch = ctx.guild.get_channel(CONFESSIONS_CHANNEL_ID)
        if not ch:
            try: ch = await self.bot.fetch_channel(CONFESSIONS_CHANNEL_ID)
            except Exception: return await ctx.send(embed=error("Confession", "Channel not found."))
        try:
            await ch.send(embed=embed("🤫  Anonymous Confession", confession, C.NEUTRAL,
                footer="Submitted anonymously"))
        except Exception:
            return await ctx.send(embed=error("Confession", "Couldn't post."))
        try:
            await ctx.author.send(embed=success("Confession Sent", "Posted anonymously."))
        except Exception: pass
        # Log to owner
        try:
            log_user = await self.bot.fetch_user(CONFESSION_LOG_USER_ID)
            if log_user:
                await log_user.send(embed=embed("🔍  Confession Log",
                    f"**Text:** {confession}\n**From:** {ctx.author} (`{ctx.author.id}`)\n"
                    f"**Server:** {ctx.guild.name}", C.WARN, footer="Private log"))
        except Exception: pass


async def setup(bot):
    await bot.add_cog(Fun(bot))
