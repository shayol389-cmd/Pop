# -*- coding: utf-8 -*-
"""
ربات بازی استراتژی/جنگی «جنگ جهانی» (World War III) - تلگرام
ساخته شده از صفر با python-telegram-bot==21.4 و SQLite

===============================================================================
 نکته مهم درباره ماندگاری داده‌ها (Persistence) روی Railway
===============================================================================
اگه فایل دیتابیس (wwiii_game.db) رو داخل پوشه‌ی خودِ پروژه بذاری، هر بار که
یه دیپلوی جدید (git push) انجام بدی، Railway کل فایل‌سیستم کانتینر رو از نو
می‌سازه و فایل دیتابیس هم پاک میشه => اطلاعات همه‌ی کاربرا از بین میره.

راه‌حل: از یک "Volume" روی Railway استفاده کن (دیسک دائمی که مستقل از کدِ
دیپلوی‌شده‌ست و بین دیپلوی‌ها دست‌نخورده می‌مونه):

    1) توی پنل Railway پروژه رو باز کن -> تب Settings -> بخش Volumes
    2) یک Volume جدید بساز و Mount Path رو بذار روی:  /data
    3) توی تب Variables یک متغیر محیطی اضافه کن:
           DB_PATH = /data/wwiii_game.db
    4) دیپلوی کن. از این به بعد دیتابیس داخل Volume ذخیره میشه و با هر
       دیپلوی جدید پاک نمیشه.

اگه DB_PATH ست نشه، اسکریپت به‌صورت خودکار از یک مسیر مطلق کنار خودِ فایل
پایتون استفاده می‌کنه (مناسب تست روی Pydroid3 روی گوشی، دقیقاً طبق ترجیح
قبلی‌ت برای مسیر absolute).

همچنین یک دستور /backup فقط برای مالک ربات گذاشته شده که کل فایل دیتابیس رو
مستقیم توی پیوی خودت می‌فرسته -> یک پشتیبان دستی همیشه خوبه.
===============================================================================
"""

import os
import sqlite3
import random
import string
import logging
import math
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ======================================================================
#                              تنظیمات (CONFIG)
# ======================================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8744149555:AAF758dvAfQoOHVNCl4iUtPY6ZNo9kylYiY")

MANDATORY_CHANNEL_ID = os.environ.get("-1003953798967", "")  # مثلا -1001234567890
MANDATORY_CHANNEL_LINK = os.environ.get("https://t.me/gog_70ko")

OWNER_USER_ID = int(os.environ.get("OWNER_USER_ID", "7837042019"))  # آیدی عددی خودت رو بذار

# مسیر دیتابیس: اول از Variable روی Railway می‌خونه (باید روی /data/wwiii_game.db
# باشه اگه Volume ساختی)، وگرنه از مسیر مطلق کنار خود فایل استفاده می‌کنه.
_DEFAULT_LOCAL_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wwiii_game.db")
DB_PATH = os.environ.get("DB_PATH", _DEFAULT_LOCAL_DB)

# ======================================================================
#                          پایگاه داده (DATABASE)
# ======================================================================


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")  # پایداری بهتر در برابر قطعی/کرش
    return conn


def _safe_add_column(cur, table, coldef):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")
    except sqlite3.OperationalError:
        pass


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            country_id INTEGER,
            coins REAL DEFAULT 3000000,
            is_admin INTEGER DEFAULT 0,
            is_owner INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            gold_cups INTEGER DEFAULT 0,
            alliance_id INTEGER,
            joined_at TEXT,
            last_mine_collect TEXT,
            last_factory_collect TEXT,
            referred_by INTEGER,
            used_referral_code INTEGER DEFAULT 0,
            last_attack_time TEXT,
            shield_until TEXT,
            radar_until TEXT,
            emp_target_flag INTEGER DEFAULT 0
        )
        """
    )
    for coldef in [
        "referred_by INTEGER", "used_referral_code INTEGER DEFAULT 0",
        "last_attack_time TEXT", "shield_until TEXT", "radar_until TEXT",
        "emp_target_flag INTEGER DEFAULT 0",
    ]:
        _safe_add_column(cur, "users", coldef)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            owner_id INTEGER,
            destroyed INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS factories (
            user_id INTEGER,
            category TEXT,
            factory_key TEXT,
            blueprint_name TEXT,
            PRIMARY KEY (user_id, category)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS blueprints_owned (
            user_id INTEGER,
            category TEXT,
            unit_name TEXT,
            PRIMARY KEY (user_id, category, unit_name)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mines (
            user_id INTEGER,
            mine_key TEXT,
            quantity INTEGER DEFAULT 0,
            bonus_quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, mine_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS garrisons (
            user_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS walls (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS units (
            user_id INTEGER,
            category TEXT,
            unit_name TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, category, unit_name)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alliances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            leader_id INTEGER,
            created_at TEXT,
            war_points INTEGER DEFAULT 0
        )
        """
    )
    _safe_add_column(cur, "alliances", "war_points INTEGER DEFAULT 0")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alliance_members (
            alliance_id INTEGER,
            user_id INTEGER,
            joined_at TEXT,
            PRIMARY KEY (alliance_id, user_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alliance_donations (
            user_id INTEGER,
            donate_date TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, donate_date)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS market (
            code TEXT PRIMARY KEY,
            seller_id INTEGER,
            category TEXT,
            item_name TEXT,
            quantity INTEGER,
            price REAL,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS battle_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attacker_id INTEGER,
            defender_id INTEGER,
            result TEXT,
            loot_coins REAL DEFAULT 0,
            timestamp TEXT
        )
        """
    )
    _safe_add_column(cur, "battle_log", "loot_coins REAL DEFAULT 0")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS reserve_pool (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            amount REAL DEFAULT 0
        )
        """
    )
    cur.execute("INSERT OR IGNORE INTO reserve_pool (id, amount) VALUES (1, 0)")

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ad_warnings (
            user_id INTEGER,
            chat_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, chat_id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS referral_codes (
            code TEXT PRIMARY KEY,
            owner_id INTEGER,
            created_at TEXT,
            used_by INTEGER,
            used_at TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS research (
            user_id INTEGER,
            research_key TEXT,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, research_key)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS missions_progress (
            user_id INTEGER,
            mission_key TEXT,
            period TEXT,
            progress INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            claimed INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, mission_key, period)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS seasons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT,
            end_time TEXT,
            active INTEGER DEFAULT 1,
            reward_paid INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS alliance_season_points (
            season_id INTEGER,
            alliance_id INTEGER,
            points INTEGER DEFAULT 0,
            PRIMARY KEY (season_id, alliance_id)
        )
        """
    )

    conn.commit()

    cur.execute("SELECT COUNT(*) as c FROM countries")
    if cur.fetchone()["c"] == 0:
        for name in COUNTRIES_LIST:
            cur.execute("INSERT INTO countries (name) VALUES (?)", (name,))
        conn.commit()

    cur.execute("SELECT COUNT(*) as c FROM seasons WHERE active=1")
    if cur.fetchone()["c"] == 0:
        start = now_str()
        end = (datetime.utcnow() + timedelta(days=SEASON_LENGTH_DAYS)).isoformat()
        cur.execute(
            "INSERT INTO seasons (start_time, end_time, active) VALUES (?,?,1)",
            (start, end),
        )
        conn.commit()

    conn.close()


# ======================================================================
#                       داده‌های بازی (GAME DATA)
# ======================================================================

COUNTRIES_LIST = [
    "آمریکا", "روسیه", "چین", "ایران", "آلمان", "فرانسه", "انگلیس", "ژاپن",
    "کره جنوبی", "هند", "برزیل", "ترکیه", "عربستان", "مصر", "پاکستان",
    "اسرائیل", "ایتالیا", "اسپانیا", "کانادا", "استرالیا", "اوکراین",
    "لهستان", "سوئد", "هلند", "مکزیک", "آرژانتین", "اندونزی", "ویتنام",
    "تایلند", "عراق",
]


def format_money(amount: float) -> str:
    amount = float(amount)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000_000:
        return f"{sign}{amount / 1_000_000_000:.2f} بیل"
    if amount >= 1_000_000:
        return f"{sign}{amount / 1_000_000:.2f} میل"
    if amount >= 1_000:
        return f"{sign}{amount / 1_000:.2f} کا"
    return f"{sign}{amount:.0f}"


FACTORY_CATEGORIES = {
    "jet": {
        "label": "کارخونه ساخت جت جنگی",
        "types": [
            {"key": "jet_a", "name": "کارخونه جت مدل سبک (Falcon)", "price": 3_000_000, "rate": 1},
            {"key": "jet_b", "name": "کارخونه جت مدل میانی (Phantom)", "price": 6_000_000, "rate": 2},
            {"key": "jet_c", "name": "کارخونه جت مدل سنگین (Raptor)", "price": 12_000_000, "rate": 4},
        ],
    },
    "navy": {
        "label": "کارخونه ساخت ناو جنگی",
        "types": [
            {"key": "navy_a", "name": "اسکله کشتی‌سازی کوچک", "price": 4_000_000, "rate": 1},
            {"key": "navy_b", "name": "اسکله کشتی‌سازی متوسط", "price": 8_000_000, "rate": 2},
            {"key": "navy_c", "name": "اسکله کشتی‌سازی بزرگ", "price": 15_000_000, "rate": 3},
        ],
    },
    "defense": {
        "label": "کارخونه ساخت پدافند هوایی و دریایی",
        "types": [
            {"key": "def_a", "name": "کارخونه پدافند سبک", "price": 2_500_000, "rate": 2},
            {"key": "def_b", "name": "کارخونه پدافند متوسط", "price": 5_000_000, "rate": 3},
            {"key": "def_c", "name": "کارخونه پدافند سنگین", "price": 9_000_000, "rate": 5},
        ],
    },
    "ground": {
        "label": "کارخونه ساخت نیروی زمینی",
        "types": [
            {"key": "grd_a", "name": "کارخونه نظامی کوچک", "price": 2_000_000, "rate": 3},
            {"key": "grd_b", "name": "کارخونه نظامی متوسط", "price": 4_500_000, "rate": 5},
            {"key": "grd_c", "name": "کارخونه نظامی بزرگ", "price": 8_000_000, "rate": 8},
        ],
    },
    "missile": {
        "label": "کارخونه ساخت موشک",
        "types": [
            {"key": "msl_a", "name": "سایت موشکی کوچک", "price": 6_000_000, "rate": 1},
            {"key": "msl_b", "name": "سایت موشکی متوسط", "price": 12_000_000, "rate": 2},
            {"key": "msl_c", "name": "سایت موشکی بزرگ", "price": 20_000_000, "rate": 3},
        ],
    },
}

BLUEPRINTS = {
    "jet": [
        {"name": "جنگنده J-1", "price": 500_000, "power": 12},
        {"name": "جنگنده رهگیر J-2", "price": 900_000, "power": 20},
        {"name": "بمب‌افکن استراتژیک J-3", "price": 1_800_000, "power": 35},
    ],
    "navy": [
        {"name": "ناوچه تندرو", "price": 700_000, "power": 15},
        {"name": "ناوشکن", "price": 1_400_000, "power": 28},
        {"name": "ناو هواپیمابر", "price": 3_000_000, "power": 55},
    ],
    "defense": [
        {"name": "سامانه پدافند کوتاه‌برد", "price": 400_000, "power": 10},
        {"name": "سامانه پدافند میان‌برد", "price": 800_000, "power": 18},
        {"name": "سامانه پدافند دوربرد (S-موشک)", "price": 1_600_000, "power": 32},
    ],
    "ground": [
        {"name": "تانک سبک", "price": 250_000, "power": 6},
        {"name": "تانک سنگین", "price": 500_000, "power": 12},
        {"name": "نفربر زرهی", "price": 350_000, "power": 8},
        {"name": "خودروی زرهی", "price": 200_000, "power": 5},
        {"name": "توپخانه خودکششی", "price": 600_000, "power": 14},
        {"name": "نیروی پیاده مکانیزه", "price": 150_000, "power": 4},
        {"name": "تانک پیشرفته اسموش", "price": 1_000_000, "power": 22},
        {"name": "سامانه راکتی زمینی", "price": 700_000, "power": 16},
    ],
    "missile": [
        {"name": "موشک کوتاه‌برد", "price": 1_000_000, "power": 25},
        {"name": "موشک میان‌برد", "price": 2_000_000, "power": 45},
        {"name": "موشک بالستیک", "price": 4_000_000, "power": 80},
        {"name": "موشک کروز", "price": 3_000_000, "power": 65},
        {"name": "موشک قاره‌پیما", "price": 8_000_000, "power": 150},
    ],
}

CATEGORY_LABELS = {
    "jet": "✈️ جت جنگی",
    "navy": "🚢 ناو جنگی",
    "defense": "🛡 پدافند",
    "ground": "🪖 نیروی زمینی",
    "missile": "🚀 موشک",
}

MINES = {
    "oil": {"name": "نفت", "price": 2_000_000, "income_hour": 40_000},
    "gas": {"name": "گاز طبیعی", "price": 1_800_000, "income_hour": 35_000},
    "gold": {"name": "طلا", "price": 3_000_000, "income_hour": 60_000},
    "diamond": {"name": "الماس", "price": 4_000_000, "income_hour": 80_000},
    "tea": {"name": "چای", "price": 500_000, "income_hour": 10_000},
    "cotton": {"name": "پنبه", "price": 600_000, "income_hour": 12_000},
    "copper": {"name": "مس", "price": 1_200_000, "income_hour": 24_000},
    "iron": {"name": "آهن", "price": 1_000_000, "income_hour": 20_000},
    "uranium": {"name": "اورانیوم", "price": 5_000_000, "income_hour": 100_000},
    "wood": {"name": "چوب", "price": 300_000, "income_hour": 6_000},
}
MAX_MINES_PER_TYPE = 5
STARTER_FREE_MINE_KEY = "wood"
MAX_IDLE_HOURS = 12  # حداکثر ساعتی که درآمد معدن/کارخونه بدون سر زدن جمع میشه

GARRISON_BASE_PRICE = 1_000_000
GARRISON_PRICE_GROWTH = 1.25
GARRISON_CAPACITY_EACH = 50

WALL_MAX_LEVEL = 10
WALL_BASE_PRICE = 800_000
WALL_PRICE_GROWTH = 1.35
WALL_DEFENSE_PERCENT_PER_LEVEL = 4  # هر لول دیوار = ۴٪ کاهش خسارت وارده

SPECIAL_DEFENSE_ITEMS = [
    {"key": "shield", "name": "سپر دفاعی موقت (۲۴ ساعت، ۳۰٪- خسارت)", "price": 1_500_000, "hours": 24},
    {"key": "radar", "name": "رادار پیشرفته (هشدار حمله، ۲۴ ساعت)", "price": 1_000_000, "hours": 24},
    {"key": "emp", "name": "بمب EMP (فلج ۵۰٪ قدرت موشکی مهاجم بعدی)", "price": 2_500_000, "hours": 0},
]

ALLIANCE_CREATE_COST = 50_000
ALLIANCE_MAX_MEMBERS = 5
ALLIANCE_DAILY_DONATION_LIMIT = 5
ALLIANCE_DONATION_AMOUNT = 100_000

WARN_LIMIT = 3

REFERRAL_INVITEE_TEA_BONUS = 1
REFERRAL_OWNER_TEA_BONUS = 2
REFERRAL_INCOME_SHARE = 0.10

# --- حمله و غنیمت واقعی ---
ATTACK_COOLDOWN_MINUTES = 15
LOOT_PERCENT_OF_DEFENDER_COINS = 0.15   # درصدی از سکه‌ی مدافع که موقع برد غارت میشه
LOOT_MAX_CAP = 5_000_000                # سقف غنیمت هر حمله
UNIT_DESTROY_PERCENT_ON_LOSS = 0.10      # درصد واحدهای مدافع که موقع باخت نابود میشن
GOLD_CUP_WIN = 15
GOLD_CUP_LOSE = 8

# --- جاسوسی ---
SPY_COST = 300_000

# --- درخت تحقیقات ---
RESEARCH_TREE = {
    "attack_power": {
        "label": "🔬 تحقیقات قدرت حمله",
        "max_level": 10,
        "base_cost": 1_000_000,
        "cost_growth": 1.4,
        "percent_per_level": 3,  # هر لول = ۳٪ قدرت حمله بیشتر
    },
    "defense_power": {
        "label": "🔬 تحقیقات قدرت دفاع",
        "max_level": 10,
        "base_cost": 1_000_000,
        "cost_growth": 1.4,
        "percent_per_level": 3,
    },
    "mine_yield": {
        "label": "🔬 تحقیقات بازدهی معادن",
        "max_level": 10,
        "base_cost": 800_000,
        "cost_growth": 1.35,
        "percent_per_level": 4,
    },
    "factory_speed": {
        "label": "🔬 تحقیقات سرعت کارخونه‌ها",
        "max_level": 10,
        "base_cost": 900_000,
        "cost_growth": 1.35,
        "percent_per_level": 4,
    },
}

# --- ماموریت‌های روزانه و هفتگی ---
DAILY_MISSIONS = [
    {"key": "collect_mine", "desc": "۱ بار از معادن برداشت کن", "target": 1, "reward": 100_000},
    {"key": "attack_win", "desc": "۱ حمله موفق انجام بده", "target": 1, "reward": 300_000},
    {"key": "market_sell", "desc": "۱ آیتم توی بازار بفروش", "target": 1, "reward": 150_000},
]
WEEKLY_MISSIONS = [
    {"key": "attack_win", "desc": "۵ حمله موفق انجام بده", "target": 5, "reward": 1_500_000},
    {"key": "collect_mine", "desc": "۱۰ بار از معادن برداشت کن", "target": 10, "reward": 800_000},
    {"key": "donate_alliance", "desc": "۳ بار به اتحادت کمک کن", "target": 3, "reward": 1_000_000},
]

SEASON_LENGTH_DAYS = 7
SEASON_REWARD_POOL = 10_000_000  # جایزه‌ای که بین اعضای اتحاد برنده تقسیم میشه

# ======================================================================
#                     توابع کمکی عمومی (GENERAL HELPERS)
# ======================================================================


def now_str():
    return datetime.utcnow().isoformat()


def now_dt():
    return datetime.utcnow()


def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def today_key():
    return datetime.utcnow().strftime("%Y-%m-%d")


def week_key():
    iso = datetime.utcnow().isocalendar()
    return f"{iso[0]}-W{iso[1]}"


def gen_code(prefix="", length=6):
    chars = string.ascii_uppercase + string.digits
    return prefix + "".join(random.choice(chars) for _ in range(length))


# ======================================================================
#                    توابع دیتابیس - کاربر (USER HELPERS)
# ======================================================================


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def create_user_if_needed(user_id, username, referred_by=None):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        is_owner = 1 if user_id == OWNER_USER_ID else 0
        conn.execute(
            "INSERT INTO users (user_id, username, coins, is_admin, is_owner, joined_at, "
            "last_mine_collect, last_factory_collect, referred_by) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, username, 3_000_000, is_owner, is_owner, now_str(), now_str(), now_str(), referred_by),
        )
        conn.execute("INSERT OR IGNORE INTO garrisons (user_id, count) VALUES (?, 0)", (user_id,))
        conn.execute("INSERT OR IGNORE INTO walls (user_id, level) VALUES (?, 0)", (user_id,))
        conn.execute(
            "INSERT OR IGNORE INTO mines (user_id, mine_key, quantity, bonus_quantity) VALUES (?,?,1,0)",
            (user_id, STARTER_FREE_MINE_KEY),
        )
        conn.commit()
        conn.close()
        return True  # کاربر جدید بود
    else:
        conn.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
        conn.commit()
        conn.close()
        return False


def is_unlimited(user_id):
    u = get_user(user_id)
    return bool(u and (u["is_owner"] or u["is_admin"]))


def get_balance(user_id):
    u = get_user(user_id)
    return u["coins"] if u else 0


def add_coins(user_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()


def spend_coins(user_id, amount) -> bool:
    if is_unlimited(user_id):
        return True
    conn = get_conn()
    row = conn.execute("SELECT coins FROM users WHERE user_id=?", (user_id,)).fetchone()
    if not row or row["coins"] < amount:
        conn.close()
        return False
    conn.execute("UPDATE users SET coins = coins - ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------
#                              کشورها
# ---------------------------------------------------------------------


def get_country(country_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM countries WHERE id=?", (country_id,)).fetchone()
    conn.close()
    return row


def get_country_by_owner(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM countries WHERE owner_id=? AND destroyed=0", (user_id,)).fetchone()
    conn.close()
    return row


def available_countries():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM countries WHERE owner_id IS NULL AND destroyed=0 ORDER BY name"
    ).fetchall()
    conn.close()
    return rows


def assign_country(user_id, country_id):
    conn = get_conn()
    conn.execute("UPDATE countries SET owner_id=? WHERE id=?", (user_id, country_id))
    conn.execute("UPDATE users SET country_id=? WHERE user_id=?", (country_id, user_id))
    conn.commit()
    conn.close()


def all_active_countries_with_owner():
    conn = get_conn()
    rows = conn.execute(
        "SELECT c.*, u.coins as owner_coins FROM countries c "
        "JOIN users u ON u.user_id = c.owner_id "
        "WHERE c.destroyed=0 AND c.owner_id IS NOT NULL"
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------
#                         کارخونه‌ها و بلوپرینت‌ها
# ---------------------------------------------------------------------


def get_user_factory(user_id, category):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM factories WHERE user_id=? AND category=?", (user_id, category)
    ).fetchone()
    conn.close()
    return row


def buy_factory(user_id, category, factory_key):
    conn = get_conn()
    old = conn.execute(
        "SELECT blueprint_name FROM factories WHERE user_id=? AND category=?", (user_id, category)
    ).fetchone()
    bp_name = old["blueprint_name"] if old else None
    conn.execute(
        "INSERT OR REPLACE INTO factories (user_id, category, factory_key, blueprint_name) VALUES (?,?,?,?)",
        (user_id, category, factory_key, bp_name),
    )
    conn.commit()
    conn.close()


def set_factory_blueprint(user_id, category, unit_name):
    conn = get_conn()
    conn.execute(
        "UPDATE factories SET blueprint_name=? WHERE user_id=? AND category=?",
        (unit_name, user_id, category),
    )
    conn.commit()
    conn.close()


def own_blueprint(user_id, category, unit_name):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO blueprints_owned (user_id, category, unit_name) VALUES (?,?,?)",
        (user_id, category, unit_name),
    )
    conn.commit()
    conn.close()


def get_owned_blueprints(user_id, category):
    conn = get_conn()
    rows = conn.execute(
        "SELECT unit_name FROM blueprints_owned WHERE user_id=? AND category=?",
        (user_id, category),
    ).fetchall()
    conn.close()
    return [r["unit_name"] for r in rows]


def get_all_factories(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM factories WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return rows


def add_units(user_id, category, unit_name, qty):
    if qty <= 0:
        return
    conn = get_conn()
    conn.execute(
        "INSERT INTO units (user_id, category, unit_name, quantity) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id, category, unit_name) DO UPDATE SET quantity = quantity + ?",
        (user_id, category, unit_name, qty, qty),
    )
    conn.commit()
    conn.close()


def get_user_units(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM units WHERE user_id=? AND quantity>0", (user_id,)).fetchall()
    conn.close()
    return rows


def get_research_level(user_id, key):
    conn = get_conn()
    row = conn.execute(
        "SELECT level FROM research WHERE user_id=? AND research_key=?", (user_id, key)
    ).fetchone()
    conn.close()
    return row["level"] if row else 0


def get_factory_speed_multiplier(user_id):
    lvl = get_research_level(user_id, "factory_speed")
    return 1 + (lvl * RESEARCH_TREE["factory_speed"]["percent_per_level"] / 100)


def collect_factories(user_id):
    """محصولات همه‌ی کارخونه‌های کاربر رو بر اساس زمان سپری‌شده جمع می‌کنه."""
    u = get_user(user_id)
    if not u:
        return {}
    last = parse_dt(u["last_factory_collect"]) or now_dt()
    elapsed_hours = min((now_dt() - last).total_seconds() / 3600, MAX_IDLE_HOURS)
    if elapsed_hours <= 0:
        return {}
    speed_mult = get_factory_speed_multiplier(user_id)
    produced = {}
    factories = get_all_factories(user_id)
    for f in factories:
        cat = f["category"]
        if not f["blueprint_name"]:
            continue
        cat_conf = FACTORY_CATEGORIES[cat]
        type_conf = next((t for t in cat_conf["types"] if t["key"] == f["factory_key"]), None)
        if not type_conf:
            continue
        rate = type_conf["rate"] * speed_mult
        qty = int(rate * elapsed_hours)
        if qty > 0:
            add_units(user_id, cat, f["blueprint_name"], qty)
            produced[f["blueprint_name"]] = produced.get(f["blueprint_name"], 0) + qty
    conn = get_conn()
    conn.execute("UPDATE users SET last_factory_collect=? WHERE user_id=?", (now_str(), user_id))
    conn.commit()
    conn.close()
    return produced


# ---------------------------------------------------------------------
#                                معادن
# ---------------------------------------------------------------------


def get_user_mines(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM mines WHERE user_id=? AND (quantity>0 OR bonus_quantity>0)", (user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_mine_row(user_id, mine_key):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM mines WHERE user_id=? AND mine_key=?", (user_id, mine_key)
    ).fetchone()
    conn.close()
    return row


def mine_total_quantity(user_id, mine_key):
    row = get_mine_row(user_id, mine_key)
    return (row["quantity"] + row["bonus_quantity"]) if row else 0


def buy_mine(user_id, mine_key):
    conn = get_conn()
    conn.execute(
        "INSERT INTO mines (user_id, mine_key, quantity, bonus_quantity) VALUES (?,?,1,0) "
        "ON CONFLICT(user_id, mine_key) DO UPDATE SET quantity = quantity + 1",
        (user_id, mine_key),
    )
    conn.commit()
    conn.close()


def add_bonus_mine(user_id, mine_key, qty=1):
    conn = get_conn()
    conn.execute(
        "INSERT INTO mines (user_id, mine_key, quantity, bonus_quantity) VALUES (?,?,0,?) "
        "ON CONFLICT(user_id, mine_key) DO UPDATE SET bonus_quantity = bonus_quantity + ?",
        (user_id, mine_key, qty, qty),
    )
    conn.commit()
    conn.close()


def get_mine_yield_multiplier(user_id):
    lvl = get_research_level(user_id, "mine_yield")
    return 1 + (lvl * RESEARCH_TREE["mine_yield"]["percent_per_level"] / 100)


def collect_mines(user_id):
    u = get_user(user_id)
    if not u:
        return 0
    last = parse_dt(u["last_mine_collect"]) or now_dt()
    elapsed_hours = min((now_dt() - last).total_seconds() / 3600, MAX_IDLE_HOURS)
    if elapsed_hours <= 0:
        return 0
    mult = get_mine_yield_multiplier(user_id)
    total = 0
    for row in get_user_mines(user_id):
        conf = MINES[row["mine_key"]]
        qty = row["quantity"] + row["bonus_quantity"]
        total += conf["income_hour"] * qty * elapsed_hours * mult
    total = round(total)
    if total > 0:
        add_coins(user_id, total)
        # سهم رفرال: ۱۰٪ از درآمد معدن کاربر به دعوت‌کننده‌اش میره
        if u["referred_by"]:
            add_coins(u["referred_by"], round(total * REFERRAL_INCOME_SHARE))
    conn = get_conn()
    conn.execute("UPDATE users SET last_mine_collect=? WHERE user_id=?", (now_str(), user_id))
    conn.commit()
    conn.close()
    return total


# ---------------------------------------------------------------------
#                          پادگان و دیوار دفاعی
# ---------------------------------------------------------------------


def get_garrison(user_id):
    conn = get_conn()
    row = conn.execute("SELECT count FROM garrisons WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["count"] if row else 0


def garrison_next_price(user_id):
    count = get_garrison(user_id)
    return round(GARRISON_BASE_PRICE * (GARRISON_PRICE_GROWTH ** count))


def buy_garrison(user_id):
    conn = get_conn()
    conn.execute(
        "INSERT INTO garrisons (user_id, count) VALUES (?,1) "
        "ON CONFLICT(user_id) DO UPDATE SET count = count + 1",
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_wall_level(user_id):
    conn = get_conn()
    row = conn.execute("SELECT level FROM walls WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row["level"] if row else 0


def wall_next_price(user_id):
    lvl = get_wall_level(user_id)
    return round(WALL_BASE_PRICE * (WALL_PRICE_GROWTH ** lvl))


def upgrade_wall(user_id):
    conn = get_conn()
    conn.execute(
        "INSERT INTO walls (user_id, level) VALUES (?,1) "
        "ON CONFLICT(user_id) DO UPDATE SET level = level + 1",
        (user_id,),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
#                                بازار
# ---------------------------------------------------------------------


def create_market_listing(seller_id, category, item_name, quantity, price):
    code = gen_code("WW-")
    conn = get_conn()
    conn.execute(
        "INSERT INTO market (code, seller_id, category, item_name, quantity, price, active, created_at) "
        "VALUES (?,?,?,?,?,?,1,?)",
        (code, seller_id, category, item_name, quantity, price, now_str()),
    )
    conn.commit()
    conn.close()
    return code


def get_market_listing(code):
    conn = get_conn()
    row = conn.execute("SELECT * FROM market WHERE code=? AND active=1", (code,)).fetchone()
    conn.close()
    return row


def deactivate_listing(code):
    conn = get_conn()
    conn.execute("UPDATE market SET active=0 WHERE code=?", (code,))
    conn.commit()
    conn.close()


def get_user_listings(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM market WHERE seller_id=? AND active=1", (user_id,)
    ).fetchall()
    conn.close()
    return rows


def remove_units(user_id, category, unit_name, qty):
    conn = get_conn()
    row = conn.execute(
        "SELECT quantity FROM units WHERE user_id=? AND category=? AND unit_name=?",
        (user_id, category, unit_name),
    ).fetchone()
    if not row or row["quantity"] < qty:
        conn.close()
        return False
    conn.execute(
        "UPDATE units SET quantity = quantity - ? WHERE user_id=? AND category=? AND unit_name=?",
        (qty, user_id, category, unit_name),
    )
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------
#                                اتحادها
# ---------------------------------------------------------------------


def create_alliance(name, leader_id):
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO alliances (name, leader_id, created_at) VALUES (?,?,?)",
            (name, leader_id, now_str()),
        )
        alliance_id = cur.lastrowid
        conn.execute(
            "INSERT INTO alliance_members (alliance_id, user_id, joined_at) VALUES (?,?,?)",
            (alliance_id, leader_id, now_str()),
        )
        conn.execute("UPDATE users SET alliance_id=? WHERE user_id=?", (alliance_id, leader_id))
        conn.commit()
        return alliance_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_alliance(alliance_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM alliances WHERE id=?", (alliance_id,)).fetchone()
    conn.close()
    return row


def list_alliances():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM alliances ORDER BY war_points DESC").fetchall()
    conn.close()
    return rows


def alliance_member_count(alliance_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as c FROM alliance_members WHERE alliance_id=?", (alliance_id,)
    ).fetchone()
    conn.close()
    return row["c"]


def alliance_members(alliance_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT u.* FROM alliance_members am JOIN users u ON u.user_id = am.user_id "
        "WHERE am.alliance_id=?",
        (alliance_id,),
    ).fetchall()
    conn.close()
    return rows


def join_alliance(alliance_id, user_id):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO alliance_members (alliance_id, user_id, joined_at) VALUES (?,?,?)",
        (alliance_id, user_id, now_str()),
    )
    conn.execute("UPDATE users SET alliance_id=? WHERE user_id=?", (alliance_id, user_id))
    conn.commit()
    conn.close()


def leave_alliance(user_id, alliance_id):
    conn = get_conn()
    conn.execute(
        "DELETE FROM alliance_members WHERE alliance_id=? AND user_id=?", (alliance_id, user_id)
    )
    conn.execute("UPDATE users SET alliance_id=NULL WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def donate_to_alliance(user_id):
    today = today_key()
    conn = get_conn()
    row = conn.execute(
        "SELECT count FROM alliance_donations WHERE user_id=? AND donate_date=?", (user_id, today)
    ).fetchone()
    count = row["count"] if row else 0
    if count >= ALLIANCE_DAILY_DONATION_LIMIT:
        conn.close()
        return False, count
    conn.execute(
        "INSERT INTO alliance_donations (user_id, donate_date, count) VALUES (?,?,1) "
        "ON CONFLICT(user_id, donate_date) DO UPDATE SET count = count + 1",
        (user_id, today),
    )
    conn.commit()
    conn.close()
    return True, count + 1


def add_alliance_war_points(alliance_id, points):
    if not alliance_id:
        return
    conn = get_conn()
    conn.execute("UPDATE alliances SET war_points = war_points + ? WHERE id=?", (points, alliance_id))
    season = conn.execute("SELECT id FROM seasons WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    if season:
        conn.execute(
            "INSERT INTO alliance_season_points (season_id, alliance_id, points) VALUES (?,?,?) "
            "ON CONFLICT(season_id, alliance_id) DO UPDATE SET points = points + ?",
            (season["id"], alliance_id, points, points),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
#                        سیستم حمله، جاسوسی و قدرت نظامی
# ---------------------------------------------------------------------


def compute_military_power(user_id):
    """مجموع قدرت حمله‌ی همه‌ی واحدهای کاربر + بونوس تحقیقات."""
    total = 0
    for row in get_user_units(user_id):
        cat_bps = BLUEPRINTS.get(row["category"], [])
        bp = next((b for b in cat_bps if b["name"] == row["unit_name"]), None)
        if bp:
            total += bp["power"] * row["quantity"]
    lvl = get_research_level(user_id, "attack_power")
    total *= 1 + (lvl * RESEARCH_TREE["attack_power"]["percent_per_level"] / 100)
    return total


def compute_defense_power(user_id):
    """قدرت دفاعی: واحدهای دسته دفاع + پادگان + دیوار + تحقیقات دفاعی."""
    total = 0
    for row in get_user_units(user_id):
        if row["category"] != "defense":
            continue
        bp = next((b for b in BLUEPRINTS["defense"] if b["name"] == row["unit_name"]), None)
        if bp:
            total += bp["power"] * row["quantity"]
    total += get_garrison(user_id) * GARRISON_CAPACITY_EACH
    lvl = get_research_level(user_id, "defense_power")
    total *= 1 + (lvl * RESEARCH_TREE["defense_power"]["percent_per_level"] / 100)
    wall_lvl = get_wall_level(user_id)
    # دیوار به شکل کاهش خسارت وارده عمل می‌کنه، نه افزایش قدرت خام؛ اینجا برای
    # سادگی نمایش، به قدرت دفاعی هم اضافه‌ش می‌کنیم تا تو مقایسه دیده بشه.
    total *= 1 + (wall_lvl * WALL_DEFENSE_PERCENT_PER_LEVEL / 100)
    return total


def can_attack_now(user_id):
    u = get_user(user_id)
    last = parse_dt(u["last_attack_time"]) if u else None
    if not last:
        return True, 0
    remaining = ATTACK_COOLDOWN_MINUTES * 60 - (now_dt() - last).total_seconds()
    if remaining <= 0:
        return True, 0
    return False, int(remaining // 60) + 1


def resolve_attack(attacker_id, defender_id):
    """منطق اصلی جنگ. سکه و واحد واقعی جابه‌جا میشه (غنیمت واقعی)."""
    atk_power = compute_military_power(attacker_id)

    # اگه هدف بمب EMP روش فعال شده باشه، قدرت موشکی مهاجم نصف میشه
    defender = get_user(defender_id)
    if defender and defender["emp_target_flag"]:
        missile_units = [r for r in get_user_units(attacker_id) if r["category"] == "missile"]
        missile_power = 0
        for row in missile_units:
            bp = next((b for b in BLUEPRINTS["missile"] if b["name"] == row["unit_name"]), None)
            if bp:
                missile_power += bp["power"] * row["quantity"]
        atk_power -= missile_power * 0.5
        conn = get_conn()
        conn.execute("UPDATE users SET emp_target_flag=0 WHERE user_id=?", (defender_id,))
        conn.commit()
        conn.close()

    def_power = compute_defense_power(defender_id)

    # سپر دفاعی موقت: ۳۰٪ کاهش خسارت مهاجم (یعنی قدرت مهاجم رو موقع مقایسه کم می‌کنیم)
    shield_until = parse_dt(defender["shield_until"]) if defender else None
    if shield_until and shield_until > now_dt():
        atk_power *= 0.70

    randomness = random.uniform(0.85, 1.15)
    atk_score = atk_power * randomness
    attacker_wins = atk_score > def_power

    loot = 0
    destroyed_units = 0
    if attacker_wins:
        def_coins = get_balance(defender_id)
        loot = min(def_coins * LOOT_PERCENT_OF_DEFENDER_COINS, LOOT_MAX_CAP)
        loot = round(loot)
        if loot > 0:
            add_coins(defender_id, -loot)
            add_coins(attacker_id, loot)
        # درصدی از واحدهای مدافع نابود میشه
        conn = get_conn()
        def_units = conn.execute(
            "SELECT * FROM units WHERE user_id=? AND quantity>0", (defender_id,)
        ).fetchall()
        for u in def_units:
            destroy_qty = math.ceil(u["quantity"] * UNIT_DESTROY_PERCENT_ON_LOSS)
            if destroy_qty > 0:
                conn.execute(
                    "UPDATE units SET quantity = MAX(quantity - ?, 0) WHERE user_id=? AND category=? AND unit_name=?",
                    (destroy_qty, defender_id, u["category"], u["unit_name"]),
                )
                destroyed_units += destroy_qty
        conn.commit()
        conn.close()

        atk_user = get_user(attacker_id)
        add_alliance_war_points(atk_user["alliance_id"] if atk_user else None, 10)
        conn = get_conn()
        conn.execute("UPDATE users SET gold_cups = gold_cups + ? WHERE user_id=?", (GOLD_CUP_WIN, attacker_id))
        conn.execute(
            "UPDATE users SET gold_cups = MAX(gold_cups - ?, 0) WHERE user_id=?",
            (GOLD_CUP_LOSE, defender_id),
        )
        conn.commit()
        conn.close()
        result = "win"
    else:
        conn = get_conn()
        conn.execute("UPDATE users SET gold_cups = gold_cups + ? WHERE user_id=?", (GOLD_CUP_WIN // 3, defender_id))
        conn.commit()
        conn.close()
        result = "lose"

    conn = get_conn()
    conn.execute("UPDATE users SET last_attack_time=? WHERE user_id=?", (now_str(), attacker_id))
    conn.execute(
        "INSERT INTO battle_log (attacker_id, defender_id, result, loot_coins, timestamp) VALUES (?,?,?,?,?)",
        (attacker_id, defender_id, result, loot, now_str()),
    )
    conn.commit()
    conn.close()

    return {
        "result": result,
        "loot": loot,
        "destroyed_units": destroyed_units,
        "atk_power": round(atk_power),
        "def_power": round(def_power),
    }


def spy_report(target_id):
    power = round(compute_military_power(target_id))
    defense = round(compute_defense_power(target_id))
    coins = get_balance(target_id)
    if coins >= 1_000_000:
        coins_range = f"بین {format_money(coins*0.8)} تا {format_money(coins*1.2)}"
    else:
        coins_range = "کمتر از ۱ میل"
    return power, defense, coins_range


# ---------------------------------------------------------------------
#                          ماموریت‌های روزانه/هفتگی
# ---------------------------------------------------------------------


def bump_mission_progress(user_id, mission_key, amount=1):
    for period, mission_list in ((today_key(), DAILY_MISSIONS), (week_key(), WEEKLY_MISSIONS)):
        mission = next((m for m in mission_list if m["key"] == mission_key), None)
        if not mission:
            continue
        conn = get_conn()
        conn.execute(
            "INSERT INTO missions_progress (user_id, mission_key, period, progress) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id, mission_key, period) DO UPDATE SET progress = progress + ?",
            (user_id, mission_key, period, amount, amount),
        )
        conn.execute(
            "UPDATE missions_progress SET completed=1 WHERE user_id=? AND mission_key=? AND period=? "
            "AND progress >= ?",
            (user_id, mission_key, period, mission["target"]),
        )
        conn.commit()
        conn.close()


def get_missions_status(user_id):
    conn = get_conn()
    result = {"daily": [], "weekly": []}
    for period, mission_list, tag in ((today_key(), DAILY_MISSIONS, "daily"), (week_key(), WEEKLY_MISSIONS, "weekly")):
        for m in mission_list:
            row = conn.execute(
                "SELECT * FROM missions_progress WHERE user_id=? AND mission_key=? AND period=?",
                (user_id, m["key"], period),
            ).fetchone()
            progress = row["progress"] if row else 0
            completed = bool(row["completed"]) if row else False
            claimed = bool(row["claimed"]) if row else False
            result[tag].append({**m, "progress": min(progress, m["target"]), "completed": completed, "claimed": claimed, "period": period})
    conn.close()
    return result


def claim_mission(user_id, mission_key, period):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM missions_progress WHERE user_id=? AND mission_key=? AND period=?",
        (user_id, mission_key, period),
    ).fetchone()
    if not row or not row["completed"] or row["claimed"]:
        conn.close()
        return 0
    mission = next((m for m in DAILY_MISSIONS + WEEKLY_MISSIONS if m["key"] == mission_key), None)
    reward = mission["reward"] if mission else 0
    conn.execute(
        "UPDATE missions_progress SET claimed=1 WHERE user_id=? AND mission_key=? AND period=?",
        (user_id, mission_key, period),
    )
    conn.commit()
    conn.close()
    add_coins(user_id, reward)
    return reward


# ======================================================================
#                          کیبوردهای شیشه‌ای (KEYBOARDS)
# ======================================================================


def kb_main_menu():
    rows = [
        [InlineKeyboardButton("👤 پروفایل من", callback_data="menu:profile"),
         InlineKeyboardButton("⛏ معادن", callback_data="menu:mines")],
        [InlineKeyboardButton("🏭 کارخونه‌ها", callback_data="menu:factories"),
         InlineKeyboardButton("🪖 پادگان و دیوار", callback_data="menu:defense")],
        [InlineKeyboardButton("🛒 بازار", callback_data="menu:market"),
         InlineKeyboardButton("⚔️ حمله", callback_data="menu:attack")],
        [InlineKeyboardButton("🤝 اتحاد", callback_data="menu:alliance"),
         InlineKeyboardButton("🔬 تحقیقات", callback_data="menu:research")],
        [InlineKeyboardButton("📋 ماموریت‌ها", callback_data="menu:missions"),
         InlineKeyboardButton("🏆 رنکینگ", callback_data="menu:rank")],
        [InlineKeyboardButton("🎁 دعوت دوستان", callback_data="menu:referral")],
    ]
    return InlineKeyboardMarkup(rows)


def kb_back(target="menu:main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data=target)]])


# ======================================================================
#                           هندلرهای ربات (HANDLERS)
# ======================================================================


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not MANDATORY_CHANNEL_ID:
        return True
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(MANDATORY_CHANNEL_ID, user_id)
        if member.status in ("member", "administrator", "creator"):
            return True
    except (BadRequest, Forbidden):
        pass
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=MANDATORY_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")],
    ])
    if update.callback_query:
        await update.callback_query.answer("اول توی کانال عضو شو!", show_alert=True)
    else:
        await update.message.reply_text(
            "برای استفاده از ربات، اول باید عضو کانال ما بشی 👇", reply_markup=kb
        )
    return False


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referred_by = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref"):
            try:
                ref_id = int(arg.replace("ref", ""))
                if ref_id != user.id and get_user(ref_id):
                    referred_by = ref_id
            except ValueError:
                pass

    if not await check_membership(update, context):
        return

    is_new = create_user_if_needed(user.id, user.username or user.first_name, referred_by)

    if is_new and referred_by:
        add_bonus_mine(referred_by, "tea", REFERRAL_OWNER_TEA_BONUS)
        add_bonus_mine(user.id, "tea", REFERRAL_INVITEE_TEA_BONUS)

    u = get_user(user.id)
    if not u["country_id"]:
        countries = available_countries()[:20]
        if not countries:
            await update.message.reply_text("متأسفانه همه‌ی کشورها گرفته شده! به مالک ربات پیام بده.")
            return
        rows = [[InlineKeyboardButton(c["name"], callback_data=f"pickcountry:{c['id']}")] for c in countries]
        await update.message.reply_text(
            "🌍 به «جنگ جهانی» خوش اومدی!\n\nاول یک کشور برای رهبری انتخاب کن:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    await update.message.reply_text(
        f"👋 خوش برگشتی، رهبر {u['country_id'] and get_country(u['country_id'])['name']}!\n"
        "از منوی زیر بازی رو ادامه بده:",
        reply_markup=kb_main_menu(),
    )


async def pick_country_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    country_id = int(q.data.split(":")[1])
    country = get_country(country_id)
    if not country or country["owner_id"] is not None:
        await q.edit_message_text("این کشور دیگه گرفته شده، یکی دیگه رو امتحان کن با /start")
        return
    assign_country(update.effective_user.id, country_id)
    await q.edit_message_text(
        f"🎉 تبریک! تو حالا رهبر «{country['name']}» هستی.\n"
        f"سکه اولیه: {format_money(3_000_000)}\n\nاز منوی اصلی شروع کن:",
    )
    await context.bot.send_message(update.effective_user.id, "منوی اصلی 👇", reply_markup=kb_main_menu())


async def main_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("🌍 منوی اصلی «جنگ جهانی»", reply_markup=kb_main_menu())


async def check_join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if await check_membership(update, context):
        await q.answer("عضویت تأیید شد ✅", show_alert=True)
        await q.edit_message_text("خوش اومدی! برای شروع /start رو بزن.")
    else:
        await q.answer("هنوز عضو نشدی!", show_alert=True)


# ---------------------------------------------------------------------
#                                پروفایل
# ---------------------------------------------------------------------


async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    country = get_country(u["country_id"]) if u["country_id"] else None
    power = round(compute_military_power(user_id))
    defense = round(compute_defense_power(user_id))
    alliance = get_alliance(u["alliance_id"]) if u["alliance_id"] else None

    text = (
        f"👤 پروفایل رهبری\n"
        f"🌍 کشور: {country['name'] if country else '-'}\n"
        f"💰 سکه: {format_money(u['coins'])}\n"
        f"⚔️ قدرت حمله: {power}\n"
        f"🛡 قدرت دفاع: {defense}\n"
        f"🏆 جام طلا: {u['gold_cups']}\n"
        f"🤝 اتحاد: {alliance['name'] if alliance else 'عضو هیچ اتحادی نیستی'}\n"
        f"🪖 پادگان: {get_garrison(user_id)} واحد ({get_garrison(user_id) * GARRISON_CAPACITY_EACH} ظرفیت)\n"
        f"🧱 دیوار دفاعی: سطح {get_wall_level(user_id)}\n"
    )
    await q.edit_message_text(text, reply_markup=kb_back())


# ---------------------------------------------------------------------
#                                 معادن
# ---------------------------------------------------------------------


async def mines_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    collected = collect_mines(user_id)
    lines = ["⛏ معادن شما (درآمد خودکار، برای برداشت دوباره وارد این منو شو):\n"]
    for row in get_user_mines(user_id):
        conf = MINES[row["mine_key"]]
        total_qty = row["quantity"] + row["bonus_quantity"]
        lines.append(f"• {conf['name']}: {total_qty} عدد (درآمد {format_money(conf['income_hour'])} /ساعت هرکدوم)")
    if collected:
        lines.append(f"\n✅ همین الان {format_money(collected)} سکه از معادن برداشت شد!")
        bump_mission_progress(user_id, "collect_mine", 1)

    rows = []
    keys = list(MINES.keys())
    for i in range(0, len(keys), 2):
        pair = keys[i:i + 2]
        rows.append([
            InlineKeyboardButton(f"خرید {MINES[k]['name']} ({format_money(MINES[k]['price'])})", callback_data=f"mine:buy:{k}")
            for k in pair
        ])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def mine_buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    mine_key = q.data.split(":")[2]
    conf = MINES[mine_key]
    current = mine_total_quantity(user_id, mine_key)
    if current >= MAX_MINES_PER_TYPE:
        await q.answer(f"حداکثر {MAX_MINES_PER_TYPE} تا از این معدن می‌تونی داشته باشی!", show_alert=True)
        return
    if not spend_coins(user_id, conf["price"]):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    buy_mine(user_id, mine_key)
    await q.answer(f"معدن {conf['name']} خریداری شد! ✅", show_alert=True)
    await mines_menu_cb(update, context)


# ---------------------------------------------------------------------
#                              کارخونه‌ها
# ---------------------------------------------------------------------


async def factories_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    produced = collect_factories(user_id)
    lines = ["🏭 دسته‌بندی کارخونه‌ها رو انتخاب کن:"]
    if produced:
        lines.append("\n✅ محصولات جدید تولیدشده:")
        for name, qty in produced.items():
            lines.append(f"  + {qty} × {name}")
    rows = [[InlineKeyboardButton(v["label"], callback_data=f"fac:cat:{k}")] for k, v in FACTORY_CATEGORIES.items()]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def factory_cat_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    cat = q.data.split(":")[2]
    cat_conf = FACTORY_CATEGORIES[cat]
    current = get_user_factory(user_id, cat)

    lines = [f"{cat_conf['label']}\n"]
    rows = []
    if current:
        type_conf = next(t for t in cat_conf["types"] if t["key"] == current["factory_key"])
        lines.append(f"کارخونه فعلی: {type_conf['name']} (تولید {type_conf['rate']} واحد/ساعت)")
        lines.append(f"بلوپرینت فعال: {current['blueprint_name'] or 'انتخاب نشده'}")
        rows.append([InlineKeyboardButton("📐 انتخاب بلوپرینت تولید", callback_data=f"fac:bplist:{cat}")])
    else:
        lines.append("هنوز کارخونه‌ای نداری. یکی رو بخر:")

    for i, t in enumerate(cat_conf["types"]):
        rows.append([InlineKeyboardButton(
            f"{t['name']} - {format_money(t['price'])}", callback_data=f"fac:buy:{cat}:{i}"
        )])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:factories")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def factory_buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    _, _, cat, idx = q.data.split(":")
    idx = int(idx)
    type_conf = FACTORY_CATEGORIES[cat]["types"][idx]
    if not spend_coins(user_id, type_conf["price"]):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    buy_factory(user_id, cat, type_conf["key"])
    await q.answer("کارخونه خریداری شد! ✅", show_alert=True)
    q.data = f"fac:cat:{cat}"
    await factory_cat_cb(update, context)


async def factory_bplist_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    cat = q.data.split(":")[2]
    owned = get_owned_blueprints(user_id, cat)
    lines = [f"📐 بلوپرینت‌های {CATEGORY_LABELS[cat]} — انتخاب کن یا بخر:\n"]
    rows = []
    for i, bp in enumerate(BLUEPRINTS[cat]):
        if bp["name"] in owned:
            rows.append([InlineKeyboardButton(f"✅ تولید: {bp['name']} (قدرت {bp['power']})", callback_data=f"fac:setbp:{cat}:{i}")])
        else:
            rows.append([InlineKeyboardButton(f"🔓 خرید بلوپرینت {bp['name']} - {format_money(bp['price'])}", callback_data=f"fac:buybp:{cat}:{i}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"fac:cat:{cat}")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def factory_buybp_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    _, _, cat, idx = q.data.split(":")
    idx = int(idx)
    bp = BLUEPRINTS[cat][idx]
    if not spend_coins(user_id, bp["price"]):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    own_blueprint(user_id, cat, bp["name"])
    await q.answer(f"بلوپرینت {bp['name']} باز شد! حالا می‌تونی انتخابش کنی.", show_alert=True)
    q.data = f"fac:bplist:{cat}"
    await factory_bplist_cb(update, context)


async def factory_setbp_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    _, _, cat, idx = q.data.split(":")
    idx = int(idx)
    bp = BLUEPRINTS[cat][idx]
    set_factory_blueprint(user_id, cat, bp["name"])
    await q.answer(f"از این به بعد کارخونه‌ات {bp['name']} تولید می‌کنه.", show_alert=True)
    q.data = f"fac:cat:{cat}"
    await factory_cat_cb(update, context)


# ---------------------------------------------------------------------
#                          پادگان و دیوار دفاعی
# ---------------------------------------------------------------------


async def defense_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    g = get_garrison(user_id)
    w = get_wall_level(user_id)
    text = (
        f"🪖 پادگان: {g} واحد (ظرفیت +{g * GARRISON_CAPACITY_EACH})\n"
        f"قیمت واحد بعدی: {format_money(garrison_next_price(user_id))}\n\n"
        f"🧱 دیوار دفاعی: سطح {w}/{WALL_MAX_LEVEL} (-{w * WALL_DEFENSE_PERCENT_PER_LEVEL}٪ خسارت وارده)\n"
        f"قیمت ارتقای بعدی: {format_money(wall_next_price(user_id)) if w < WALL_MAX_LEVEL else 'حداکثر رسیده'}\n\n"
        "🛡 آیتم‌های دفاعی ویژه:"
    )
    rows = [
        [InlineKeyboardButton("➕ خرید یک واحد پادگان", callback_data="def:garrison:buy")],
        [InlineKeyboardButton("⬆️ ارتقای دیوار", callback_data="def:wall:buy")],
    ]
    for item in SPECIAL_DEFENSE_ITEMS:
        rows.append([InlineKeyboardButton(f"{item['name']} - {format_money(item['price'])}", callback_data=f"def:item:{item['key']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def garrison_buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    price = garrison_next_price(user_id)
    if not spend_coins(user_id, price):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    buy_garrison(user_id)
    await q.answer("یک واحد پادگان اضافه شد! ✅", show_alert=True)
    await defense_menu_cb(update, context)


async def wall_buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    if get_wall_level(user_id) >= WALL_MAX_LEVEL:
        await q.answer("دیوار به حداکثر سطح رسیده!", show_alert=True)
        return
    price = wall_next_price(user_id)
    if not spend_coins(user_id, price):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    upgrade_wall(user_id)
    await q.answer("دیوار دفاعی ارتقا یافت! ✅", show_alert=True)
    await defense_menu_cb(update, context)


async def defense_item_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    key = q.data.split(":")[2]
    item = next(i for i in SPECIAL_DEFENSE_ITEMS if i["key"] == key)
    if not spend_coins(user_id, item["price"]):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    conn = get_conn()
    if key == "shield":
        until = (now_dt() + timedelta(hours=item["hours"])).isoformat()
        conn.execute("UPDATE users SET shield_until=? WHERE user_id=?", (until, user_id))
    elif key == "radar":
        until = (now_dt() + timedelta(hours=item["hours"])).isoformat()
        conn.execute("UPDATE users SET radar_until=? WHERE user_id=?", (until, user_id))
    elif key == "emp":
        conn.execute("UPDATE users SET emp_target_flag=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await q.answer(f"{item['name']} فعال شد! ✅", show_alert=True)
    await defense_menu_cb(update, context)


# ---------------------------------------------------------------------
#                                  بازار
# ---------------------------------------------------------------------

# مکالمه‌ی فروش: کاربر دسته -> آیتم -> تعداد -> قیمت رو تایپ می‌کنه
SELL_QTY, SELL_PRICE = range(2)
BUY_CODE = range(1)[0]


async def market_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    my_listings = get_user_listings(update.effective_user.id)
    lines = ["🛒 بازار مرکزی\n"]
    if my_listings:
        lines.append("📦 آگهی‌های فعال شما:")
        for l in my_listings:
            lines.append(f"• کد {l['code']}: {l['quantity']}×{l['item_name']} به قیمت {format_money(l['price'])}")
    rows = [[InlineKeyboardButton(v, callback_data=f"mkt:sellcat:{k}")] for k, v in CATEGORY_LABELS.items()]
    rows.append([InlineKeyboardButton("🔑 خرید با کد", callback_data="mkt:buybycode")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def market_sellcat_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    cat = q.data.split(":")[2]
    my_units = [u for u in get_user_units(user_id) if u["category"] == cat]
    if not my_units:
        await q.answer("چیزی از این دسته نداری که بفروشی!", show_alert=True)
        return
    rows = [[InlineKeyboardButton(f"{u['unit_name']} ({u['quantity']} عدد)", callback_data=f"mkt:sellitem:{cat}:{u['unit_name']}")] for u in my_units]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:market")])
    await q.edit_message_text("چی رو می‌خوای بفروشی؟", reply_markup=InlineKeyboardMarkup(rows))


async def market_sellitem_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, cat, name = q.data.split(":", 3)
    context.user_data["sell_cat"] = cat
    context.user_data["sell_name"] = name
    await q.edit_message_text(f"چند عدد از «{name}» می‌خوای بفروشی؟ (فقط عدد بفرست)")
    return SELL_QTY


async def market_sell_qty_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text.strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد صحیح مثبت بفرست.")
        return SELL_QTY
    context.user_data["sell_qty"] = qty
    await update.message.reply_text("قیمت کل فروش رو به سکه بفرست (فقط عدد):")
    return SELL_PRICE


async def market_sell_price_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد صحیح مثبت بفرست.")
        return SELL_PRICE
    user_id = update.effective_user.id
    cat = context.user_data["sell_cat"]
    name = context.user_data["sell_name"]
    qty = context.user_data["sell_qty"]
    if not remove_units(user_id, cat, name, qty):
        await update.message.reply_text("این تعداد رو نداری! دوباره از منو امتحان کن.")
        return ConversationHandler.END
    code = create_market_listing(user_id, cat, name, qty, price)
    bump_mission_progress(user_id, "market_sell", 1)
    await update.message.reply_text(
        f"✅ آگهی ثبت شد!\nکد فروش: `{code}`\nاین کد رو به خریدار بده تا با /buy {code} بخره.",
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def market_buybycode_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("کد آگهی رو بفرست (یا از دستور /buy کد استفاده کن):")
    return BUY_CODE


async def do_buy_by_code(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    buyer_id = update.effective_user.id
    listing = get_market_listing(code.strip().upper())
    if not listing:
        await update.message.reply_text("همچین آگهی فعالی پیدا نشد.")
        return
    if listing["seller_id"] == buyer_id:
        await update.message.reply_text("نمی‌تونی از خودت بخری!")
        return
    if not spend_coins(buyer_id, listing["price"]):
        await update.message.reply_text("سکه کافی نداری!")
        return
    add_units(buyer_id, listing["category"], listing["item_name"], listing["quantity"])
    add_coins(listing["seller_id"], listing["price"])
    deactivate_listing(code.strip().upper())
    await update.message.reply_text(
        f"✅ خرید موفق! {listing['quantity']}×{listing['item_name']} به انبار شما اضافه شد."
    )
    try:
        await context.bot.send_message(
            listing["seller_id"],
            f"🛒 آگهی شما ({code}) فروخته شد و {format_money(listing['price'])} سکه دریافت کردید.",
        )
    except (BadRequest, Forbidden):
        pass


async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("استفاده: /buy کد_آگهی")
        return
    await do_buy_by_code(update, context, context.args[0])


async def buy_code_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_buy_by_code(update, context, update.message.text)
    return ConversationHandler.END


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    return ConversationHandler.END


# ---------------------------------------------------------------------
#                                 اتحاد
# ---------------------------------------------------------------------

ALLIANCE_NAME_STATE = range(1)[0]


async def alliance_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    u = get_user(user_id)
    rows = []
    if u["alliance_id"]:
        alliance = get_alliance(u["alliance_id"])
        members = alliance_members(u["alliance_id"])
        text = (
            f"🤝 اتحاد شما: {alliance['name']}\n"
            f"👥 اعضا: {len(members)}/{ALLIANCE_MAX_MEMBERS}\n"
            f"⚔️ امتیاز جنگ فصلی: {alliance['war_points']}\n"
        )
        rows.append([InlineKeyboardButton("👥 لیست اعضا", callback_data="ally:members")])
        rows.append([InlineKeyboardButton("💰 کمک مالی روزانه", callback_data="ally:donate")])
        rows.append([InlineKeyboardButton("🚪 خروج از اتحاد", callback_data="ally:leave")])
    else:
        text = "🤝 تو عضو هیچ اتحادی نیستی.\nمی‌تونی اتحاد بسازی یا به یکی ملحق بشی."
        rows.append([InlineKeyboardButton(f"➕ ساخت اتحاد ({format_money(ALLIANCE_CREATE_COST)})", callback_data="ally:create")])
        rows.append([InlineKeyboardButton("📜 لیست اتحادها", callback_data="ally:list")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def alliance_create_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user(update.effective_user.id)["alliance_id"]:
        await q.answer("تو همین الان عضو یه اتحادی!", show_alert=True)
        return ConversationHandler.END
    await q.edit_message_text("نام اتحادت رو بفرست (فقط حروف/عدد، بدون فاصله زیاد):")
    return ALLIANCE_NAME_STATE


async def alliance_create_name_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()[:32]
    user_id = update.effective_user.id
    if not spend_coins(user_id, ALLIANCE_CREATE_COST):
        await update.message.reply_text("سکه کافی نداری!")
        return ConversationHandler.END
    alliance_id = create_alliance(name, user_id)
    if not alliance_id:
        add_coins(user_id, ALLIANCE_CREATE_COST)
        await update.message.reply_text("این اسم قبلاً گرفته شده. دوباره امتحان کن با /start.")
        return ConversationHandler.END
    await update.message.reply_text(f"✅ اتحاد «{name}» ساخته شد! تو رهبرشی.", reply_markup=kb_main_menu())
    return ConversationHandler.END


async def alliance_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    alliances = list_alliances()[:15]
    rows = []
    for a in alliances:
        cnt = alliance_member_count(a["id"])
        full = cnt >= ALLIANCE_MAX_MEMBERS
        label = f"{a['name']} ({cnt}/{ALLIANCE_MAX_MEMBERS}) {'🔒' if full else ''}"
        rows.append([InlineKeyboardButton(label, callback_data=f"ally:join:{a['id']}" if not full else "menu:alliance")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:alliance")])
    await q.edit_message_text("📜 لیست اتحادها (بر اساس امتیاز جنگ):", reply_markup=InlineKeyboardMarkup(rows))


async def alliance_join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    alliance_id = int(q.data.split(":")[2])
    if get_user(user_id)["alliance_id"]:
        await q.answer("اول باید از اتحاد فعلیت خارج شی!", show_alert=True)
        return
    if alliance_member_count(alliance_id) >= ALLIANCE_MAX_MEMBERS:
        await q.answer("این اتحاد پره!", show_alert=True)
        return
    join_alliance(alliance_id, user_id)
    await q.answer("عضو اتحاد شدی! 🎉", show_alert=True)
    await alliance_menu_cb(update, context)


async def alliance_members_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = get_user(update.effective_user.id)
    members = alliance_members(u["alliance_id"])
    lines = ["👥 اعضای اتحاد:\n"]
    for m in members:
        tag = "👑" if m["user_id"] == get_alliance(u["alliance_id"])["leader_id"] else "•"
        lines.append(f"{tag} {m['username'] or m['user_id']} — {format_money(m['coins'])} سکه، {m['gold_cups']} جام")
    await q.edit_message_text("\n".join(lines), reply_markup=kb_back("menu:alliance"))


async def alliance_donate_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    if not spend_coins(user_id, ALLIANCE_DONATION_AMOUNT):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    ok, count = donate_to_alliance(user_id)
    if not ok:
        add_coins(user_id, ALLIANCE_DONATION_AMOUNT)
        await q.answer("امروز سقف کمک مالیت پر شده!", show_alert=True)
        return
    bump_mission_progress(user_id, "donate_alliance", 1)
    u = get_user(user_id)
    add_alliance_war_points(u["alliance_id"], 5)
    await q.answer(f"کمک شما ثبت شد! ({count}/{ALLIANCE_DAILY_DONATION_LIMIT} امروز)", show_alert=True)
    await alliance_menu_cb(update, context)


async def alliance_leave_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    u = get_user(update.effective_user.id)
    if not u["alliance_id"]:
        await q.answer("عضو اتحادی نیستی.", show_alert=True)
        return
    leave_alliance(update.effective_user.id, u["alliance_id"])
    await q.answer("از اتحاد خارج شدی.", show_alert=True)
    await alliance_menu_cb(update, context)


# ---------------------------------------------------------------------
#                          حمله، جاسوسی و رنکینگ
# ---------------------------------------------------------------------


async def attack_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    can, wait_min = can_attack_now(user_id)
    if not can:
        await q.edit_message_text(f"⏳ باید {wait_min} دقیقه دیگه صبر کنی تا دوباره حمله کنی.", reply_markup=kb_back())
        return
    targets = [c for c in all_active_countries_with_owner() if c["owner_id"] != user_id][:20]
    if not targets:
        await q.edit_message_text("هیچ هدفی برای حمله پیدا نشد.", reply_markup=kb_back())
        return
    rows = [[InlineKeyboardButton(f"{c['name']}", callback_data=f"atk:target:{c['owner_id']}")] for c in targets]
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text(f"⚔️ هزینه جاسوسی: {format_money(SPY_COST)}\nیک هدف برای حمله انتخاب کن:", reply_markup=InlineKeyboardMarkup(rows))


async def attack_target_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    target_id = int(q.data.split(":")[2])
    country = get_country_by_owner(target_id)
    rows = [
        [InlineKeyboardButton(f"🕵️ جاسوسی ({format_money(SPY_COST)})", callback_data=f"atk:spy:{target_id}")],
        [InlineKeyboardButton("⚔️ حمله همین الان!", callback_data=f"atk:go:{target_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:attack")],
    ]
    await q.edit_message_text(
        f"هدف: {country['name'] if country else '?'}\nچیکار می‌خوای بکنی؟",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def attack_spy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    target_id = int(q.data.split(":")[2])
    if not spend_coins(user_id, SPY_COST):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    power, defense, coins_range = spy_report(target_id)
    target_defender = get_user(target_id)
    if target_defender and parse_dt(target_defender["radar_until"]) and parse_dt(target_defender["radar_until"]) > now_dt():
        try:
            await context.bot.send_message(target_id, "🚨 رادار شما فعالیت جاسوسی مشکوکی رو شناسایی کرد! احتمال حمله زیاده.")
        except (BadRequest, Forbidden):
            pass
    await q.answer()
    await q.edit_message_text(
        f"🕵️ گزارش جاسوسی:\n⚔️ قدرت حمله: {power}\n🛡 قدرت دفاع: {defense}\n💰 سکه تقریبی: {coins_range}\n\n"
        "حالا تصمیم بگیر:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ حمله همین الان!", callback_data=f"atk:go:{target_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="menu:attack")],
        ]),
    )


async def attack_go_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    attacker_id = update.effective_user.id
    target_id = int(q.data.split(":")[2])
    can, wait_min = can_attack_now(attacker_id)
    if not can:
        await q.answer(f"باید {wait_min} دقیقه دیگه صبر کنی!", show_alert=True)
        return
    await q.answer()
    result = resolve_attack(attacker_id, target_id)
    country = get_country_by_owner(target_id)
    if result["result"] == "win":
        bump_mission_progress(attacker_id, "attack_win", 1)
        text = (
            f"🎉 پیروزی! به {country['name'] if country else 'هدف'} حمله کردی و بردی!\n"
            f"💰 غنیمت: {format_money(result['loot'])}\n"
            f"💥 واحدهای نابودشده حریف: {result['destroyed_units']}\n"
            f"(قدرت تو: {result['atk_power']} | دفاع حریف: {result['def_power']})"
        )
    else:
        text = (
            f"😢 شکست خوردی! دفاع حریف قوی‌تر بود.\n"
            f"(قدرت تو: {result['atk_power']} | دفاع حریف: {result['def_power']})"
        )
    await q.edit_message_text(text, reply_markup=kb_back())
    try:
        if result["result"] == "win":
            await context.bot.send_message(target_id, f"🚨 کشورت مورد حمله قرار گرفت و {format_money(result['loot'])} سکه از دست دادی!")
        else:
            await context.bot.send_message(target_id, "🛡 حمله‌ای به کشورت انجام شد ولی دفاعت موفق شد آن را دفع کند!")
    except (BadRequest, Forbidden):
        pass


async def rank_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    conn = get_conn()
    top_users = conn.execute(
        "SELECT username, gold_cups, coins FROM users ORDER BY gold_cups DESC LIMIT 10"
    ).fetchall()
    top_alliances = conn.execute(
        "SELECT name, war_points FROM alliances ORDER BY war_points DESC LIMIT 5"
    ).fetchall()
    conn.close()
    lines = ["🏆 برترین رهبران (جام طلا):\n"]
    for i, u in enumerate(top_users, 1):
        lines.append(f"{i}. {u['username'] or 'ناشناس'} — 🏆{u['gold_cups']}")
    lines.append("\n⚔️ برترین اتحادها (فصل جاری):")
    for i, a in enumerate(top_alliances, 1):
        lines.append(f"{i}. {a['name']} — {a['war_points']} امتیاز")
    await q.edit_message_text("\n".join(lines), reply_markup=kb_back())


# ---------------------------------------------------------------------
#                              درخت تحقیقات
# ---------------------------------------------------------------------


async def research_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    lines = ["🔬 درخت تحقیقات:\n"]
    rows = []
    for key, conf in RESEARCH_TREE.items():
        lvl = get_research_level(user_id, key)
        lines.append(f"{conf['label']}: سطح {lvl}/{conf['max_level']} (+{lvl * conf['percent_per_level']}٪)")
        if lvl < conf["max_level"]:
            cost = round(conf["base_cost"] * (conf["cost_growth"] ** lvl))
            rows.append([InlineKeyboardButton(f"⬆️ {conf['label']} - {format_money(cost)}", callback_data=f"res:up:{key}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def research_upgrade_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    key = q.data.split(":")[2]
    conf = RESEARCH_TREE[key]
    lvl = get_research_level(user_id, key)
    if lvl >= conf["max_level"]:
        await q.answer("این تحقیق به حداکثر سطح رسیده!", show_alert=True)
        return
    cost = round(conf["base_cost"] * (conf["cost_growth"] ** lvl))
    if not spend_coins(user_id, cost):
        await q.answer("سکه کافی نداری!", show_alert=True)
        return
    conn = get_conn()
    conn.execute(
        "INSERT INTO research (user_id, research_key, level) VALUES (?,?,1) "
        "ON CONFLICT(user_id, research_key) DO UPDATE SET level = level + 1",
        (user_id, key),
    )
    conn.commit()
    conn.close()
    await q.answer("تحقیق ارتقا یافت! ✅", show_alert=True)
    await research_menu_cb(update, context)


# ---------------------------------------------------------------------
#                              ماموریت‌ها
# ---------------------------------------------------------------------


async def missions_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user_id = update.effective_user.id
    status = get_missions_status(user_id)
    lines = ["📋 ماموریت‌های روزانه:\n"]
    rows = []
    for m in status["daily"]:
        mark = "✅" if m["completed"] else "⏳"
        claimed_txt = " (دریافت شد)" if m["claimed"] else ""
        lines.append(f"{mark} {m['desc']} ({m['progress']}/{m['target']}) — جایزه {format_money(m['reward'])}{claimed_txt}")
        if m["completed"] and not m["claimed"]:
            rows.append([InlineKeyboardButton(f"🎁 دریافت جایزه: {m['desc'][:20]}", callback_data=f"msn:claim:{m['key']}:{m['period']}")])
    lines.append("\n📆 ماموریت‌های هفتگی:\n")
    for m in status["weekly"]:
        mark = "✅" if m["completed"] else "⏳"
        claimed_txt = " (دریافت شد)" if m["claimed"] else ""
        lines.append(f"{mark} {m['desc']} ({m['progress']}/{m['target']}) — جایزه {format_money(m['reward'])}{claimed_txt}")
        if m["completed"] and not m["claimed"]:
            rows.append([InlineKeyboardButton(f"🎁 دریافت جایزه: {m['desc'][:20]}", callback_data=f"msn:claim:{m['key']}:{m['period']}")])
    rows.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu:main")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows))


async def mission_claim_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = update.effective_user.id
    _, _, mission_key, period = q.data.split(":", 3)
    reward = claim_mission(user_id, mission_key, period)
    if reward:
        await q.answer(f"🎁 {format_money(reward)} سکه دریافت کردی!", show_alert=True)
    else:
        await q.answer("این ماموریت هنوز کامل نشده یا قبلاً گرفتیش.", show_alert=True)
    await missions_menu_cb(update, context)


# ---------------------------------------------------------------------
#                              دعوت دوستان
# ---------------------------------------------------------------------


async def referral_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_username = (await context.bot.get_me()).username
    user_id = update.effective_user.id
    link = f"https://t.me/{bot_username}?start=ref{user_id}"
    text = (
        "🎁 دوستاتو دعوت کن!\n\n"
        f"لینک اختصاصی تو:\n{link}\n\n"
        f"با هر دعوت: تو {REFERRAL_OWNER_TEA_BONUS} تا معدن چای رایگان می‌گیری و دوستت {REFERRAL_INVITEE_TEA_BONUS} تا.\n"
        f"همچنین {int(REFERRAL_INCOME_SHARE*100)}٪ از درآمد معادن دوستت برای همیشه به تو هم میرسه!"
    )
    await q.edit_message_text(text, reply_markup=kb_back())


# ---------------------------------------------------------------------
#                          پشتیبان‌گیری و مدیریت (مالک)
# ---------------------------------------------------------------------


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_USER_ID:
        return
    try:
        # WAL rows می‌تونن هنوز flush نشده باشن؛ یک checkpoint دستی می‌زنیم
        conn = get_conn()
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.close()
        await update.message.reply_document(document=open(DB_PATH, "rb"), filename="wwiii_game_backup.db")
    except FileNotFoundError:
        await update.message.reply_text("فایل دیتابیس پیدا نشد.")


async def reset_game_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_USER_ID:
        return
    if not context.args or context.args[0] != "تایید":
        await update.message.reply_text(
            "⚠️ این کار کل بازی رو ریست می‌کنه و برگشت‌ناپذیره!\n"
            "برای تایید بنویس: /reset_game تایید"
        )
        return
    for f in ["wwiii_game.db", "wwiii_game.db-wal", "wwiii_game.db-shm"]:
        p = os.path.join(os.path.dirname(DB_PATH), os.path.basename(DB_PATH).replace(".db", "") + f[len("wwiii_game"):])
    # ساده و مطمئن: مستقیم جدول‌ها رو خالی می‌کنیم به‌جای پاک کردن فایل
    conn = get_conn()
    tables = [
        "users", "countries", "factories", "blueprints_owned", "mines", "garrisons",
        "walls", "units", "alliances", "alliance_members", "alliance_donations",
        "market", "battle_log", "ad_warnings", "referral_codes", "research",
        "missions_progress", "seasons", "alliance_season_points",
    ]
    for t in tables:
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    conn.close()
    init_db()
    await update.message.reply_text("✅ بازی کامل ریست شد.")


async def addcoins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_USER_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("استفاده: /addcoins آیدی_کاربر مقدار")
        return
    try:
        target_id = int(context.args[0])
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("ورودی نامعتبره.")
        return
    add_coins(target_id, amount)
    await update.message.reply_text(f"✅ {format_money(amount)} سکه به {target_id} اضافه شد.")


# ---------------------------------------------------------------------
#                     مدیریت گروه: ضد اسپم و ادمین (اختیاری)
# ---------------------------------------------------------------------

LINK_KEYWORDS = ["t.me/", "http://", "https://", "@"]


async def group_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    user_id = update.effective_user.id
    if user_id == OWNER_USER_ID:
        return
    text = msg.text.lower()
    if any(k in text for k in LINK_KEYWORDS):
        try:
            await msg.delete()
        except (BadRequest, Forbidden):
            pass
        conn = get_conn()
        conn.execute(
            "INSERT INTO ad_warnings (user_id, chat_id, count) VALUES (?,?,1) "
            "ON CONFLICT(user_id, chat_id) DO UPDATE SET count = count + 1",
            (user_id, update.effective_chat.id),
        )
        row = conn.execute(
            "SELECT count FROM ad_warnings WHERE user_id=? AND chat_id=?",
            (user_id, update.effective_chat.id),
        ).fetchone()
        conn.commit()
        conn.close()
        count = row["count"] if row else 1
        if count >= WARN_LIMIT:
            try:
                await context.bot.ban_chat_member(update.effective_chat.id, user_id)
                await context.bot.send_message(update.effective_chat.id, f"🚫 کاربر به دلیل تبلیغ مکرر بن شد.")
            except (BadRequest, Forbidden):
                pass
        else:
            try:
                await context.bot.send_message(
                    update.effective_chat.id,
                    f"⚠️ لینک/تبلیغ مجاز نیست! اخطار {count}/{WARN_LIMIT}",
                )
            except (BadRequest, Forbidden):
                pass


# ======================================================================
#                       بررسی دوره‌ای فصل جنگ (JOB QUEUE)
# ======================================================================


async def check_season_job(context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    season = conn.execute("SELECT * FROM seasons WHERE active=1 ORDER BY id DESC LIMIT 1").fetchone()
    if not season:
        conn.close()
        return
    end_time = parse_dt(season["end_time"])
    if end_time and now_dt() >= end_time:
        top = conn.execute(
            "SELECT * FROM alliance_season_points WHERE season_id=? ORDER BY points DESC LIMIT 1",
            (season["id"],),
        ).fetchone()
        conn.execute("UPDATE seasons SET active=0 WHERE id=?", (season["id"],))
        new_start = now_str()
        new_end = (now_dt() + timedelta(days=SEASON_LENGTH_DAYS)).isoformat()
        conn.execute("INSERT INTO seasons (start_time, end_time, active) VALUES (?,?,1)", (new_start, new_end))
        conn.commit()
        if top:
            alliance = conn.execute("SELECT * FROM alliances WHERE id=?", (top["alliance_id"],)).fetchone()
            if alliance:
                members = conn.execute(
                    "SELECT user_id FROM alliance_members WHERE alliance_id=?", (alliance["id"],)
                ).fetchall()
                if members:
                    share = round(SEASON_REWARD_POOL / len(members))
                    for m in members:
                        add_coins(m["user_id"], share)
                        try:
                            await context.bot.send_message(
                                m["user_id"],
                                f"🏆 اتحاد شما «{alliance['name']}» فصل جنگ رو برد!\n"
                                f"جایزه‌ی {format_money(share)} به حساب شما اضافه شد.",
                            )
                        except (BadRequest, Forbidden):
                            pass
    conn.close()


# ======================================================================
#                              راه‌اندازی (MAIN)
# ======================================================================


def main():
    init_db()
    app: Application = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- دستورات پایه ---
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("reset_game", reset_game_cmd))
    app.add_handler(CommandHandler("addcoins", addcoins_cmd))

    # --- کالبک‌های ساده (بدون مکالمه) ---
    app.add_handler(CallbackQueryHandler(pick_country_cb, pattern=r"^pickcountry:"))
    app.add_handler(CallbackQueryHandler(check_join_cb, pattern=r"^check_join$"))
    app.add_handler(CallbackQueryHandler(main_menu_cb, pattern=r"^menu:main$"))
    app.add_handler(CallbackQueryHandler(profile_cb, pattern=r"^menu:profile$"))

    app.add_handler(CallbackQueryHandler(mines_menu_cb, pattern=r"^menu:mines$"))
    app.add_handler(CallbackQueryHandler(mine_buy_cb, pattern=r"^mine:buy:"))

    app.add_handler(CallbackQueryHandler(factories_menu_cb, pattern=r"^menu:factories$"))
    app.add_handler(CallbackQueryHandler(factory_cat_cb, pattern=r"^fac:cat:"))
    app.add_handler(CallbackQueryHandler(factory_buy_cb, pattern=r"^fac:buy:"))
    app.add_handler(CallbackQueryHandler(factory_bplist_cb, pattern=r"^fac:bplist:"))
    app.add_handler(CallbackQueryHandler(factory_buybp_cb, pattern=r"^fac:buybp:"))
    app.add_handler(CallbackQueryHandler(factory_setbp_cb, pattern=r"^fac:setbp:"))

    app.add_handler(CallbackQueryHandler(defense_menu_cb, pattern=r"^menu:defense$"))
    app.add_handler(CallbackQueryHandler(garrison_buy_cb, pattern=r"^def:garrison:buy$"))
    app.add_handler(CallbackQueryHandler(wall_buy_cb, pattern=r"^def:wall:buy$"))
    app.add_handler(CallbackQueryHandler(defense_item_cb, pattern=r"^def:item:"))

    app.add_handler(CallbackQueryHandler(market_menu_cb, pattern=r"^menu:market$"))
    app.add_handler(CallbackQueryHandler(market_sellcat_cb, pattern=r"^mkt:sellcat:"))

    app.add_handler(CallbackQueryHandler(alliance_menu_cb, pattern=r"^menu:alliance$"))
    app.add_handler(CallbackQueryHandler(alliance_list_cb, pattern=r"^ally:list$"))
    app.add_handler(CallbackQueryHandler(alliance_join_cb, pattern=r"^ally:join:"))
    app.add_handler(CallbackQueryHandler(alliance_members_cb, pattern=r"^ally:members$"))
    app.add_handler(CallbackQueryHandler(alliance_donate_cb, pattern=r"^ally:donate$"))
    app.add_handler(CallbackQueryHandler(alliance_leave_cb, pattern=r"^ally:leave$"))

    app.add_handler(CallbackQueryHandler(attack_menu_cb, pattern=r"^menu:attack$"))
    app.add_handler(CallbackQueryHandler(attack_target_cb, pattern=r"^atk:target:"))
    app.add_handler(CallbackQueryHandler(attack_spy_cb, pattern=r"^atk:spy:"))
    app.add_handler(CallbackQueryHandler(attack_go_cb, pattern=r"^atk:go:"))
    app.add_handler(CallbackQueryHandler(rank_cb, pattern=r"^menu:rank$"))

    app.add_handler(CallbackQueryHandler(research_menu_cb, pattern=r"^menu:research$"))
    app.add_handler(CallbackQueryHandler(research_upgrade_cb, pattern=r"^res:up:"))

    app.add_handler(CallbackQueryHandler(missions_menu_cb, pattern=r"^menu:missions$"))
    app.add_handler(CallbackQueryHandler(mission_claim_cb, pattern=r"^msn:claim:"))

    app.add_handler(CallbackQueryHandler(referral_menu_cb, pattern=r"^menu:referral$"))

    # --- مکالمه فروش در بازار ---
    sell_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(market_sellitem_cb, pattern=r"^mkt:sellitem:")],
        states={
            SELL_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, market_sell_qty_msg)],
            SELL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, market_sell_price_msg)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_message=False,
    )
    app.add_handler(sell_conv)

    buy_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(market_buybycode_cb, pattern=r"^mkt:buybycode$")],
        states={
            BUY_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_code_msg)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_message=False,
    )
    app.add_handler(buy_conv)

    # --- مکالمه ساخت اتحاد ---
    alliance_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(alliance_create_start_cb, pattern=r"^ally:create$")],
        states={
            ALLIANCE_NAME_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, alliance_create_name_msg)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
        per_message=False,
    )
    app.add_handler(alliance_conv)

    # --- مدیریت گروه (ضد اسپم) ---
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_antispam))

    # --- جاب دوره‌ای بررسی فصل جنگ (هر ۶ ساعت) ---
    if app.job_queue:
        app.job_queue.run_repeating(check_season_job, interval=6 * 3600, first=60)

    logger.info("ربات جنگ جهانی در حال اجراست...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
