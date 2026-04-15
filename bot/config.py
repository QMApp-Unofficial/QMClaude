# config.py — Central configuration for QMBOT
import os
from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════════════
# Core
# ═══════════════════════════════════════════════════════════════
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_DIR = os.getenv("DATA_DIR", "./data")

# ═══════════════════════════════════════════════════════════════
# Guild / Channels / Roles
# ═══════════════════════════════════════════════════════════════
ANNOUNCEMENT_CHANNEL_ID   = int(os.getenv("ANNOUNCEMENT_CHANNEL_ID", "1433248053665726547"))
WELCOME_CHANNEL_ID        = int(os.getenv("WELCOME_CHANNEL_ID", "1433248053665726546"))
MARKET_ANNOUNCE_CHANNEL_ID = int(os.getenv("MARKET_ANNOUNCE_CHANNEL_ID", "1433412796531347586"))
SUGGESTION_CHANNEL_ID     = int(os.getenv("SUGGESTION_CHANNEL_ID", "1433413006842396682"))
LEVEL_ANNOUNCE_CHANNEL_ID = int(os.getenv("LEVEL_ANNOUNCE_CHANNEL_ID", "1433417692320239666"))
CONFESSIONS_CHANNEL_ID    = int(os.getenv("CONFESSIONS_CHANNEL_ID", "1492170739955138630"))

TOP_ROLE_NAME = "🌟 EXP Top"
OWNER_IDS = {734468552903360594}
PACKAGE_USER_ID = 734468552903360594
CONFESSION_LOG_USER_ID = 734468552903360594

# ═══════════════════════════════════════════════════════════════
# Economy
# ═══════════════════════════════════════════════════════════════
XP_PER_MESSAGE = 10

INTEREST_RATE     = 0.02
INTEREST_INTERVAL = 3600

DIVIDEND_RATE     = 0.01
DIVIDEND_INTERVAL = 86400

DEBT_INTEREST_RATE     = 0.03
DEBT_INTEREST_INTERVAL = 3600

# Tax brackets: (up_to_amount, rate)
TAX_BRACKETS = [
    (1_000,         0.05),
    (5_000,         0.10),
    (15_000,        0.18),
    (40_000,        0.26),
    (100_000,       0.35),
    (float("inf"),  0.45),
]

# ═══════════════════════════════════════════════════════════════
# Career
# ═══════════════════════════════════════════════════════════════
WORK_COOLDOWN = 3600
PROMOTION_THRESHOLDS = [0, 10, 25, 50, 90]

CAREER_FIELDS = {
    "tech": {
        "name": "Tech", "icon": "💻",
        "tiers": [
            {"title": "Junior Dev",        "min": 80,   "max": 200},
            {"title": "Mid Dev",           "min": 200,  "max": 400},
            {"title": "Senior Dev",        "min": 400,  "max": 700},
            {"title": "Staff Engineer",    "min": 700,  "max": 1100},
            {"title": "Principal Engineer","min": 1100, "max": 1800},
        ],
    },
    "finance": {
        "name": "Finance", "icon": "📊",
        "tiers": [
            {"title": "Analyst",           "min": 90,   "max": 220},
            {"title": "Associate",         "min": 220,  "max": 450},
            {"title": "VP",                "min": 450,  "max": 750},
            {"title": "Director",          "min": 750,  "max": 1200},
            {"title": "CFO",               "min": 1200, "max": 2000},
        ],
    },
    "medicine": {
        "name": "Medicine", "icon": "🏥",
        "tiers": [
            {"title": "Intern",            "min": 60,   "max": 160},
            {"title": "Resident",          "min": 160,  "max": 350},
            {"title": "Junior Doctor",     "min": 350,  "max": 600},
            {"title": "Consultant",        "min": 600,  "max": 1000},
            {"title": "Lead Consultant",   "min": 1000, "max": 1600},
        ],
    },
    "law": {
        "name": "Law", "icon": "⚖️",
        "tiers": [
            {"title": "Paralegal",         "min": 70,   "max": 180},
            {"title": "Solicitor",         "min": 180,  "max": 380},
            {"title": "Senior Solicitor",  "min": 380,  "max": 650},
            {"title": "Partner",           "min": 650,  "max": 1100},
            {"title": "Senior Partner",    "min": 1100, "max": 1900},
        ],
    },
    "entertainment": {
        "name": "Entertainment", "icon": "🎬",
        "tiers": [
            {"title": "Intern",            "min": 30,   "max": 120},
            {"title": "Production Assist", "min": 120,  "max": 300},
            {"title": "Content Creator",   "min": 300,  "max": 600},
            {"title": "Producer",          "min": 600,  "max": 1000},
            {"title": "Executive Producer","min": 1000, "max": 1700},
        ],
    },
    "crime": {
        "name": "Crime", "icon": "🦹",
        "tiers": [
            {"title": "Street Rat",        "min": 50,   "max": 200},
            {"title": "Grifter",           "min": 200,  "max": 450},
            {"title": "Enforcer",          "min": 450,  "max": 800},
            {"title": "Crime Boss",        "min": 800,  "max": 1400},
            {"title": "Kingpin",           "min": 1400, "max": 2500},
        ],
    },
}

# ═══════════════════════════════════════════════════════════════
# Gambling
# ═══════════════════════════════════════════════════════════════
GAMBLE_MIN_BET = 10
GAMBLE_MAX_BET = 50_000

# ═══════════════════════════════════════════════════════════════
# Rob / Bankrob
# ═══════════════════════════════════════════════════════════════
ALWAYS_BANKROB_USER_ID = 734468552903360594
BANKROB_STEAL_MIN_PCT  = 0.12
BANKROB_STEAL_MAX_PCT  = 0.28
BANKROB_MIN_STEAL      = 100
BANKROB_MAX_STEAL_PCT_CAP = 0.40

# ═══════════════════════════════════════════════════════════════
# Stocks / Market
# ═══════════════════════════════════════════════════════════════
STOCKS = ["Oreobux", "QMkoin", "Seelsterling", "Fwizfinance", "BingBux"]

STOCK_TRADE_COOLDOWN = 60          # 1 min between trades on same stock
STOCK_DAILY_TRADE_LIMIT = 30       # max trades per day
STOCK_TRANSACTION_TAX = 0.02       # 2% tax on buy/sell
STOCK_MAX_SHARES_PER_STOCK = 500   # max holdings per stock

DEFAULT_STOCK_CONFIG = {
    "Oreobux":       {"price": 100, "fair_value": 100.0, "volatility": 0.012, "drift": 0.0001, "liquidity": 1400, "history": [100]},
    "QMkoin":        {"price": 150, "fair_value": 150.0, "volatility": 0.015, "drift": 0.0001, "liquidity": 1200, "history": [150]},
    "Seelsterling":  {"price": 200, "fair_value": 200.0, "volatility": 0.010, "drift": 0.0001, "liquidity": 1800, "history": [200]},
    "Fwizfinance":   {"price": 250, "fair_value": 250.0, "volatility": 0.020, "drift": 0.0001, "liquidity": 900,  "history": [250]},
    "BingBux":       {"price": 120, "fair_value": 120.0, "volatility": 0.013, "drift": 0.0001, "liquidity": 1300, "history": [120]},
}

DIVIDEND_YIELD = {
    "Oreobux": 0.008, "QMkoin": 0.006, "Seelsterling": 0.010,
    "Fwizfinance": 0.004, "BingBux": 0.007,
}

MAX_NORMAL_MOVE = 0.04
MAX_EVENT_MOVE  = 0.09
PRICE_FLOOR     = 1

# ═══════════════════════════════════════════════════════════════
# Shop
# ═══════════════════════════════════════════════════════════════
SHOP_RESTOCK_MINUTES = 30

COIN_SHOP_ITEMS = {
    "Bank note": {
        "price": 1000, "max_stock": 9, "emoji": "🎰",
        "description": "Spin a wheel for cash rewards. Outcomes: 1–2000 coins, or Jackpot (10,000).",
    },
    "Kachow clock": {
        "price": 10000, "max_stock": 3, "emoji": "⚡",
        "description": "Reduces rob cooldown to 1 min and bankrob to 3 min for 1 hour.",
    },
    "Pocket PC": {
        "price": 10000, "max_stock": 3, "emoji": "🛡️",
        "description": "Comfort buff for 1 hour. Rob chance drops to 20%, bankrob to 5%.",
    },
}

STAR_SHOP_ITEMS = {
    "Crash token": {
        "price": 2, "max_stock": 2, "emoji": "💥",
        "description": "Halves the current price of a stock you choose.",
    },
    "Fwiz's USB": {
        "price": 10, "max_stock": 1, "emoji": "💾",
        "description": "40% chance to steal up to 40% of a user's shares in one stock.",
    },
    "Imran's Nose": {
        "price": 100, "max_stock": 1, "emoji": "👃",
        "description": "Nuclear option — resets all server data except action commands.",
    },
}

# ═══════════════════════════════════════════════════════════════
# Swear Jar
# ═══════════════════════════════════════════════════════════════
SWEAR_FINE_ENABLED = True
SWEAR_FINE_AMOUNT  = 10

# ═══════════════════════════════════════════════════════════════
# Minecraft
# ═══════════════════════════════════════════════════════════════
MC_NAME       = "QMUL Survival"
MC_ADDRESS    = "185.206.150.153"
MC_JAVA_PORT  = None
MC_VERSION    = "1.20.10"
MC_LOADER     = "Fabric"
MC_MODPACK_NAME = "QMUL Survival Pack"
MC_WHITELISTED  = False
MC_REGION       = "UK / London"
MC_DISCORD_URL  = "https://discord.gg/6PxXwS7c"
MC_MODRINTH_URL = ""
MC_MAP_URL      = ""
MC_RULES_URL    = ""
MC_SHOW_BEDROCK = False
MC_BEDROCK_PORT = 22165
MC_NOTES = [
    "Be respectful — no griefing.",
    "No x-ray / cheating clients.",
    "Ask an admin if you need help.",
]

# ═══════════════════════════════════════════════════════════════
# Backup
# ═══════════════════════════════════════════════════════════════
PACKAGE_FILES = [
    "data.json", "coins.json", "trivia_stats.json", "trivia_streaks.json",
    "beg_stats.json", "swear_jar.json", "sticker.json", "stocks.json",
    "inventories.json", "shop_stock.json", "marriages.json", "actions.json",
    "suggestions.json",
]

# ═══════════════════════════════════════════════════════════════
# Tenor API
# ═══════════════════════════════════════════════════════════════
TENOR_API_KEY = os.getenv("TENOR_API_KEY", "AIzaSyAyimkuEcdEnPs55ueys84EMt_lFe0BXKQ")
