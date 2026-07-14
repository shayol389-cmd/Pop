"""
Summertime Saga Guide Bot
A Telegram bot (python-telegram-bot v20+) that serves as a walkthrough guide
for the game "Summertime Saga", with mandatory channel-join enforcement,
premium subscriptions, admin group moderation, and photo delivery.

Run with:  python main.py
Requires:  pip install "python-telegram-bot[job-queue]"==20.7
"""

import json
import logging
import os
import random
import re
import string
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ============================================================
# 1. CONFIGURATION BLOCK
# ============================================================
BOT_TOKEN = "8946712747:AAEHHKlngGrmbGJYLE0MjRtmog9WBAaADNc"
CHANNEL_USERNAME = "@Summertime221"
CHANNEL_URL = "https://t.me/Summertime221"

# 👇 آیدی عددی خودت (و هر ادمین دیگه) رو اینجا بذار.
# برای گرفتن آیدی عددی‌ت می‌تونی به ربات @userinfobot توی تلگرام پیام بدی.
ADMIN_IDS = [7837042019]  # <-- این عدد رو با آیدی عددی خودت عوض کن

DATA_FILE = "bot_data.json"      # فایلی که اطلاعات کاربرها، کدها و عکس‌ها توش ذخیره می‌شه
FREE_COOLDOWN_HOURS = 24         # فاصله‌ی زمانی بین دو ماموریت رایگان
CODE_LENGTH = 12                 # طول کد سریال (اشتراک)
PHOTO_AUTO_DELETE_SECONDS = 10   # بعد از چند ثانیه عکس ارسالی پاک بشه

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# 5. WALKTHROUGH DATABASE
# ============================================================
GUIDES = {
    "character_01": {
        "title": "🧑 راهنمای آنون",
        "text": """
آنون شخصیت اصلی داستان ما هستش و همه چیز از او شروع می شود.

اون به همه چیزمربوطه

مرحله ۱
از اتاق بیاین بیرون و به طبقه پایین بروید با جنی رویه پله ها اشنا شوید 
وارد اسپز خونه شوید و با دابی اشنا شوید مرحله ۲
از خونه بزنین بیرون و رویه نقشه بزنین و به خونه سبز یعنی خونه اریک بروید با اریک صحبت کنین 
مرحله ۳
رویه نقشه بزنین و رویه مدرسه کلیک کنین با میا اشنا شوید و باهاش حرف بزنین
مرحله ۴
وارد مدرسه شوید و با بقیه اشنا شوید 
مرحله ۵
با انیا اشنا شوید و به دفتر مدیر بروید 
با کوین اشنا شوید
مرحله ۶
به دفتر مدیر بروید و با مدیر مدرسه حرف بزنین 
مرحله ۷
مجددا به طبقه پایین بروید و رویه راهرویه سمته چپ بروید وارد رختکن شوید و با جودیت اشنا شوید
مرحله ۸
بعد از تعویض لباس به راهرویه اصلی مدرسه بروید و رویه حیاط ورزش کلیک کنین و با معلم ورزش اشنا شوید
مرحله ۹
بعدش مجددا وارد رختکن شوید و لباس خود را عوض کنید
مرحله ۱۰
به بقیه کلاس ها بروید و با معلم ها اشنا شوید

تبریک شما روزه اول خود را گزراندید و مسیر مدرسه را باز کردید 
""",
    },
"character_02": {
    "title": "راهنمای دابی",
    "text": """
دابی کیست ؟ دابی همسایه مهربون شخصیت اصلی یعنی Anon هستش که الان انون رو به فرزند خوندگی گرفته 
دابی با پدر anon قبلا رابطه داشته قبل از کشته شدنش توسط مافیا
مرحله ۱
کارهای برای نزدیک شدن به دابی 
۱ کمک در کار های خانه 
۲ تعمیر وسایل
۳ چرب زبونی 

برای کمک به کار های داخل خانه اینکار هارو بکنین شستن ظرف ها 
کمک در شستن لباس ها 
و تعمیر دستشویی طبقه دوم
مرحله ۲
""",
},
    "character_03": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_04": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_05": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_06": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_07": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_08": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_09": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_10": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_11": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_12": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_13": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_14": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_15": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_16": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_17": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_18": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_19": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
    "character_20": {
        "title": "",  # مثال: "🧑 راهنمای نام‌شخصیت"
        "text": (
            ""  # متن کامل راهنمای شخصیت رو اینجا بنویس
        ),
    },
}

# Keywords used for flexible matching (checked with the `in` operator).
CHARACTER_KEYWORDS = {
    "character_01": ["راهنمای آنون", "آنون", "انان"],
    "character_02": [],
    "character_03": [],
    "character_04": [],
    "character_05": [],
    "character_06": [],
    "character_07": [],
    "character_08": [],
    "character_09": [],
    "character_10": [],
    "character_11": [],
    "character_12": [],
    "character_13": [],
    "character_14": [],
    "character_15": [],
    "character_16": [],
    "character_17": [],
    "character_18": [],
    "character_19": [],
    "character_20": [],
}

# ============================================================
# KEYBOARDS
# ============================================================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, guide in GUIDES.items():
        title = guide.get("title") or f"❔ {key}"
        buttons.append([InlineKeyboardButton(title, callback_data=f"char_{key}")])
    return InlineKeyboardMarkup(buttons)


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("↩️ بازگشت به لیست کاراکترها", callback_data="back_to_menu")]]
    )


def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 عضویت در کانال", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ عضو شدم!", callback_data="check_membership")],
        ]
    )


MAIN_MENU_TEXT = (
    "🎮 *به راهنمای بازی Summertime Saga خوش اومدی!*\n\n"
    "یکی از کاراکترهای زیر رو انتخاب کن تا راهنمای کاملش رو ببینی 👇"
)

LOCK_MESSAGE = (
    "🔒 *دسترسی محدود شده است*\n\n"
    "برای استفاده از ربات راهنمای Summertime Saga، ابتدا باید عضو کانال ما بشی.\n\n"
    "1️⃣ روی دکمه‌ی «عضویت در کانال» بزن و عضو شو.\n"
    "2️⃣ بعد از عضویت، روی دکمه‌ی «✅ عضو شدم!» کلیک کن.\n\n"
    "بدون عضویت امکان استفاده از ربات وجود نداره 🙏"
)

INVALID_MESSAGE = (
    "❓ متوجه پیام شما نشدم.\n\n"
    "لطفاً برای دیدن لیست کاراکترها، عبارت «راهنما» رو ارسال کنید."
)

# ============================================================
# 2. MEMBERSHIP CHECK
# ============================================================
async def is_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError as e:
        logger.error("Membership check failed for user %s: %s", user_id, e)
        return False


# ============================================================
# PERSISTENT STORAGE (JSON file: users, premium codes, photos)
# ============================================================
def _default_data() -> dict:
    return {"users": {}, "codes": {}, "photos": {}}


def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return _default_data()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to read data file, starting fresh: %s", e)
        data = {}
    data.setdefault("users", {})
    data.setdefault("codes", {})
    data.setdefault("photos", {})
    return data


def save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("Failed to save data file: %s", e)


def get_user_entry(data: dict, user_id: int) -> dict:
    key = str(user_id)
    if key not in data["users"]:
        data["users"][key] = {"warnings": 0, "premium_until": None, "last_free_guide_at": None}
    return data["users"][key]


def is_premium(data: dict, user_id: int) -> bool:
    entry = data["users"].get(str(user_id))
    if not entry:
        return False
    expiry = entry.get("premium_until")
    if expiry == "lifetime":
        return True
    if not expiry:
        return False
    try:
        expiry_dt = datetime.fromisoformat(expiry)
    except ValueError:
        return False
    return datetime.utcnow() < expiry_dt


def check_free_cooldown(data: dict, user_id: int):
    """Returns (allowed: bool, remaining_seconds: int)."""
    entry = get_user_entry(data, user_id)
    last = entry.get("last_free_guide_at")
    if not last:
        return True, 0
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True, 0
    elapsed = (datetime.utcnow() - last_dt).total_seconds()
    remaining = FREE_COOLDOWN_HOURS * 3600 - elapsed
    if remaining <= 0:
        return True, 0
    return False, int(remaining)


def format_remaining(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return f"{hours} ساعت و {minutes} دقیقه"


# ============================================================
# PREMIUM CODE ("سریال") GENERATION & REDEMPTION
# ============================================================
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_DIGIT_TRANSLATION = str.maketrans(PERSIAN_DIGITS, "0123456789")


def fa_to_en_digits(s: str) -> str:
    return s.translate(_DIGIT_TRANSLATION)


def generate_unique_code(existing_codes) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=CODE_LENGTH))
        if code not in existing_codes:
            return code


PLAN_LABELS = {
    "week": "یک هفته‌ای",
    "month": "ماهانه",
    "lifetime": "نامحدود (دائمی)",
}
PLAN_DAYS = {"week": 7, "month": 30}

# مثال دستورهایی که تشخیص داده می‌شن:
#   "ساخت سریال یک هفته"      -> ۱ کد هفتگی
#   "ساخت سریال ماهانه"        -> ۱ کد ماهانه
#   "ساخت سریال نامحدود"       -> ۱ کد دائمی
#   "ساخت ۵ عدد سریال ماهانه"  -> ۵ کد ماهانه
MAKE_CODE_PATTERN = re.compile(
    r"ساخت\s*(?:([\d۰-۹]+)\s*عدد\s*)?سریال\s*(یک\s*هفته|هفتگی|هفته|ماهانه|ماه|نامحدود|دائمی|دائم)",
)

REDEEM_PATTERN = re.compile(r"وارد\s*کردن\s*سریال\s+([A-Za-z0-9]{%d})" % CODE_LENGTH)


def resolve_plan(word: str) -> str:
    word = word.replace(" ", "").replace("\u200c", "")
    if "هفته" in word:
        return "week"
    if "ماه" in word:
        return "month"
    if "نامحدود" in word or "دائم" in word:
        return "lifetime"
    return ""


async def handle_admin_make_codes(update: Update, context: ContextTypes.DEFAULT_TYPE, match) -> None:
    count_str = match.group(1)
    count = int(fa_to_en_digits(count_str)) if count_str else 1
    count = max(1, min(count, 100))  # safety cap
    plan = resolve_plan(match.group(2))
    if not plan:
        await update.message.reply_text("❌ نوع اشتراک تشخیص داده نشد.")
        return

    data = load_data()
    new_codes = []
    for _ in range(count):
        code = generate_unique_code(data["codes"].keys())
        data["codes"][code] = {"type": plan, "used": False, "used_by": None}
        new_codes.append(code)
    save_data(data)

    codes_block = "\n".join(f"`{c}`" for c in new_codes)
    await update.message.reply_text(
        f"✅ {count} عدد سریال «{PLAN_LABELS[plan]}» ساخته شد:\n\n{codes_block}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE, match) -> None:
    user_id = update.effective_user.id
    code = match.group(1).upper()

    data = load_data()
    entry = data["codes"].get(code)
    if not entry or entry.get("used"):
        await update.message.reply_text("❌ این کد سریال معتبر نیست یا قبلاً استفاده شده.")
        return

    entry["used"] = True
    entry["used_by"] = user_id

    user_entry = get_user_entry(data, user_id)
    plan = entry["type"]
    now = datetime.utcnow()

    if plan == "lifetime":
        user_entry["premium_until"] = "lifetime"
        expiry_text = "نامحدود (دائمی) ♾️"
    else:
        current_expiry = user_entry.get("premium_until")
        base = now
        if current_expiry and current_expiry != "lifetime":
            try:
                current_dt = datetime.fromisoformat(current_expiry)
                base = max(now, current_dt)
            except ValueError:
                base = now
        elif current_expiry == "lifetime":
            # already lifetime — nothing to extend, just confirm.
            await update.message.reply_text(
                "🎉 کد با موفقیت ثبت شد، اما اشتراک شما از قبل نامحدود (دائمی) است."
            )
            save_data(data)
            return
        new_expiry = base + timedelta(days=PLAN_DAYS[plan])
        user_entry["premium_until"] = new_expiry.isoformat()
        expiry_text = new_expiry.strftime("%Y-%m-%d %H:%M UTC")

    save_data(data)
    await update.message.reply_text(
        f"🎉 اشتراک پریموم شما فعال شد!\n"
        f"نوع: {PLAN_LABELS[plan]}\n"
        f"اعتبار تا: {expiry_text}\n\n"
        "حالا می‌تونید بدون محدودیت زمانی، ماموریت هر کاراکتری رو ببینید."
    )


# ============================================================
# PHOTO UPLOAD / DELIVERY (with auto-delete)
# ============================================================
# In-memory: admin_id -> the key they're about to attach a photo to.
PENDING_PHOTO_UPLOADS: dict = {}

PHOTO_UPLOAD_CMD = re.compile(r"^آپلود\s*عکس\s+(.+)$")
PHOTO_REQUEST_CMD = re.compile(r"^عکس\s+(.+)$")


async def delete_message_later(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    try:
        await context.bot.delete_message(chat_id=job_data["chat_id"], message_id=job_data["message_id"])
    except TelegramError as e:
        logger.error("Failed to auto-delete photo message: %s", e)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS and user_id in PENDING_PHOTO_UPLOADS:
        key = PENDING_PHOTO_UPLOADS.pop(user_id)
        file_id = update.message.photo[-1].file_id
        data = load_data()
        data["photos"][key] = file_id
        save_data(data)
        await update.message.reply_text(f"✅ عکس برای «{key}» ذخیره شد.\nحالا کاربرها با «عکس {key}» می‌تونن ببیننش.")


# ============================================================
# ANTI-SPAM / LINK & AD FILTER (پاک کردن لینک و تبلیغات)
# ============================================================
LINK_PATTERN = re.compile(
    r"(https?://\S+)"
    r"|(www\.\S+)"
    r"|(t\.me/\S+)"
    r"|(@[A-Za-z0-9_]{4,})"
    r"|([A-Za-z0-9-]+\.(com|ir|net|org|io|xyz|shop|site|online)\b)",
    re.IGNORECASE,
)


async def delete_links_and_ads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    اگه پیام شامل لینک یا آیدی @ باشه، پاکش می‌کنه.
    پیام‌های ادمین‌ها هیچ‌وقت پاک نمی‌شن.
    بعد از ۳ اخطار، کاربر از گروه حذف می‌شه.
    خروجی True یعنی پیام پاک شد (بقیه‌ی هندلر باید متوقف بشه).
    """
    message = update.message
    if not message or not message.text:
        return False

    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        return False  # هیچ‌وقت پیام ادمین پاک نمی‌شه

    if not LINK_PATTERN.search(message.text):
        return False

    data = load_data()
    user_entry = get_user_entry(data, user_id)
    user_entry["warnings"] = user_entry.get("warnings", 0) + 1
    warnings = user_entry["warnings"]

    try:
        await message.delete()
    except TelegramError as e:
        logger.error("Failed to delete spam message: %s", e)

    if warnings >= 3:
        try:
            await context.bot.ban_chat_member(chat_id=message.chat_id, user_id=user_id)
            await context.bot.unban_chat_member(chat_id=message.chat_id, user_id=user_id)
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=f"⛔️ {message.from_user.mention_html()} به دلیل ۳ بار ارسال لینک/تبلیغ از گروه اخراج شد.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            logger.error("Failed to kick user %s: %s", user_id, e)
        user_entry["warnings"] = 0
    else:
        try:
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=(
                    f"🚫 پیام {message.from_user.mention_html()} حذف شد (لینک/آیدی مجاز نیست).\n"
                    f"⚠️ اخطار {warnings} از ۳ — اخطار سوم یعنی حذف از گروه."
                ),
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            logger.error("Failed to send warning message: %s", e)

    save_data(data)
    return True


# ============================================================
# HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not await is_member(context, user_id):
        await update.message.reply_text(
            LOCK_MESSAGE, parse_mode=ParseMode.MARKDOWN, reply_markup=join_keyboard()
        )
        return

    await update.message.reply_text(
        MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    raw_text = update.message.text or ""

    # 0) فیلتر لینک/تبلیغ - همیشه اول چک می‌شه (ادمین‌ها مستثنی هستن)
    if await delete_links_and_ads(update, context):
        return

    # 1) دستور ادمین برای ساخت سریال (اشتراک)
    make_match = MAKE_CODE_PATTERN.search(raw_text)
    if make_match and user_id in ADMIN_IDS:
        await handle_admin_make_codes(update, context, make_match)
        return

    # 2) دستور ادمین برای شروع آپلود عکس
    upload_match = PHOTO_UPLOAD_CMD.match(raw_text.strip())
    if upload_match and user_id in ADMIN_IDS:
        key = upload_match.group(1).strip()
        PENDING_PHOTO_UPLOADS[user_id] = key
        await update.message.reply_text(f"📸 حالا عکس مربوط به «{key}» رو بفرست.")
        return

    # 3) قفل عضویت کانال (برای همه‌ی کاربران دیگر)
    if not await is_member(context, user_id):
        await update.message.reply_text(
            LOCK_MESSAGE, parse_mode=ParseMode.MARKDOWN, reply_markup=join_keyboard()
        )
        return

    # 4) فعال‌سازی اشتراک با کد سریال
    redeem_match = REDEEM_PATTERN.search(raw_text)
    if redeem_match:
        await handle_redeem_code(update, context, redeem_match)
        return

    text = raw_text.strip().lower()

    # 5) منوی اصلی
    if text == "راهنما":
        await update.message.reply_text(
            MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
        )
        return

    # 6) تشخیص کاراکتر (با گیت پریموم/کول‌داون رایگان)
    matched_key = None
    for key, keywords in CHARACTER_KEYWORDS.items():
        for kw in keywords:
            if kw and kw in text:
                matched_key = key
                break
        if matched_key:
            break

    if matched_key:
        data = load_data()
        if not is_premium(data, user_id):
            allowed, remaining = check_free_cooldown(data, user_id)
            if not allowed:
                await update.message.reply_text(
                    f"⏳ شما در حالت رایگان هستید.\n"
                    f"برای دیدن ماموریت کاراکتر بعدی باید {format_remaining(remaining)} دیگه صبر کنید.\n\n"
                    "برای دسترسی نامحدود، اشتراک پریموم تهیه کنید."
                )
                return
            get_user_entry(data, user_id)["last_free_guide_at"] = datetime.utcnow().isoformat()
            save_data(data)

        guide = GUIDES[matched_key]
        await update.message.reply_text(
            guide["text"], parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard()
        )
        return

    # 7) درخواست عکس («عکس <نام>»)
    photo_match = PHOTO_REQUEST_CMD.match(raw_text.strip())
    if photo_match:
        key = photo_match.group(1).strip()
        data = load_data()
        file_id = data["photos"].get(key)
        if file_id:
            sent = await update.message.reply_photo(file_id)
            if context.job_queue:
                context.job_queue.run_once(
                    delete_message_later,
                    PHOTO_AUTO_DELETE_SECONDS,
                    data={"chat_id": sent.chat_id, "message_id": sent.message_id},
                )
        else:
            await update.message.reply_text("❌ عکسی برای این مورد ثبت نشده.")
        return

    await update.message.reply_text(INVALID_MESSAGE)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data_cb = query.data

    # Always answer the callback query to prevent the loading spinner.
    await query.answer()

    if data_cb == "check_membership":
        if await is_member(context, user_id):
            await query.edit_message_text(
                MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
            )
        else:
            await query.answer(
                "❌ هنوز عضو کانال نشدی! لطفاً ابتدا عضو شو.", show_alert=True
            )
        return

    # Re-check membership before serving any content via callback as well.
    if not await is_member(context, user_id):
        await query.edit_message_text(
            LOCK_MESSAGE, parse_mode=ParseMode.MARKDOWN, reply_markup=join_keyboard()
        )
        return

    if data_cb == "back_to_menu":
        await query.edit_message_text(
            MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
        )
        return

    if data_cb.startswith("char_"):
        key = data_cb.replace("char_", "", 1)
        guide = GUIDES.get(key)
        if guide:
            data = load_data()
            if not is_premium(data, user_id):
                allowed, remaining = check_free_cooldown(data, user_id)
                if not allowed:
                    await query.answer(
                        f"⏳ باید {format_remaining(remaining)} دیگه صبر کنید یا اشتراک پریموم تهیه کنید.",
                        show_alert=True,
                    )
                    return
                get_user_entry(data, user_id)["last_free_guide_at"] = datetime.utcnow().isoformat()
                save_data(data)

            await query.edit_message_text(
                guide["text"], parse_mode=ParseMode.MARKDOWN, reply_markup=back_keyboard()
            )
        else:
            await query.edit_message_text(
                MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
            )
        return


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)

    logger.info("Bot started. Polling for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
