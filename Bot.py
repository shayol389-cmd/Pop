"""
Summertime Saga Guide Bot
A Telegram bot (python-telegram-bot v20+) that serves as a walkthrough guide
for the game "Summertime Saga".

Sections: Characters, Item Locations & Usage, Side Missions, Referral Program.
Includes: channel-join lock, coupon-based access system, admin group moderation,
and admin-managed photo delivery with auto-delete.

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
ADMIN_IDS = [123456789]  # <-- این عدد رو با آیدی عددی خودت عوض کن

DATA_FILE = "bot_data.json"      # فایلی که اطلاعات کاربرها، کدها و عکس‌ها توش ذخیره می‌شه
CODE_LENGTH = 12                 # طول کد سریال
AUTO_DELETE_SECONDS = 20         # بعد از چند ثانیه عکس/فایل/ویدیوی ارسالی خودکار پاک بشه
COUPONS_PER_REFERRAL = 2         # هر زیرمجموعه چند کوپن به معرف می‌ده
COUPON_COST_PER_VIEW = 5         # هزینه‌ی هر راهنما/آیتم/ماموریت بعد از تموم شدن سهمیه‌ی رایگان روزانه (به کوپن)
COUPON_COST_MEDIA = 1            # هزینه‌ی هر عکس/فایل/ویدیو بعد از تموم شدن سهمیه‌ی رایگان روزانه (به کوپن)

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ============================================================
# 5. CONTENT DATABASES
# ============================================================

# ---------- 👤 شخصیت‌ها ----------
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
        "title": "👩‍🦰 راهنمای جنی",
        "text": """
مرحله ۱
صبح‌ها زیر دوش به جنی نگاه کن .
مرحله ۲
روز بعد، تا بعد از ظهر صبر کنید و به ورودی بروید تا حرف‌هایش را بشنوید و درباره مشکل مالی‌اش بیشتر بدانید.
بگذارید ۲ روز بگذرد.
مرحله ۳
صبح‌ها با جنی در اتاق غذاخوری صبحانه بخورید.
بگذارید ۲ روز بگذرد.
مرحله ۴
عصر، به راهروی طبقه بالا برو. جنی در اتاقش درباره... بابابزرگ حرف می‌زند؟ راستش، دارد فیلم تماشا می‌کند و حسابی خوش می‌گذرد. با پول می‌توانی سکوتش را بخری.
مرحله ۵
عکس‌های داغ
بگذارید ۳ روز بگذرد.
صبح، به اتاق غذاخوری بروید تا صبحانه دیگری را با دختر صرف کنید. او مجذوب یک شبکه اجتماعی به نام Sluttygram شده است . او برای جلب رضایت دنبال‌کنندگان جدید چه کاری انجام نمی‌دهد؟ شما در حال شروع یک حرفه جدید به عنوان عکاس شهوانی هستید .
مرحله ۶
دفتر خاطرات عزیز
صبح روز بعد، وقتی دارد لباس می‌شورد، وارد اتاق خوابش شوید. افکار شیطنت‌آمیز داخل دفتر خاطراتش را بخوانید. سپس میز کنار تخت را که سعی در دزدیدن شورت داشتید، باز کنید. جنی شما را در حین عمل مچتان را می‌گیرد! از پرداخت پول برای دیدن عکس‌ها خودداری کنید ▲ یا رضایت دهید ▼ .
پیشنهاد بی‌شرمانه
مرحله ۷
بگذارید ۳ روز بگذرد.
برای صبحانه به همخانه‌ات ملحق شو. او هنوز به صفحه گوشی‌اش چسبیده است. انکار ▲ یا موافقت ▼ کن که جنی جذاب است. برای یک معامله جدید، این بار در مورد سینه‌هایش، او را در اتاقش دنبال کن.
الکترو کلیتوریس
مرحله ۸
بگذارید ۲ روز بگذرد.
جنی صبح زود با عجله وارد اتاق شما می‌شود. وقتی به اتاق خوابش رسید، برای ادامه کارش به یک اسباب‌بازی مخصوص نیاز دارد. به مرکز خرید هیل‌ساید و سپس به فروشگاه لوازم جنسی پینک بروید . خوشبختانه برای شما، کتابدار از خرید راضی نیست و شما الکترو کلیتوریس را دوباره روی پیشخوان فروشگاه می‌گیرید. تا بعد از ظهر صبر کنید و اسباب‌بازی را به جنی بدهید. او به شما اجازه می‌دهد تا فرم‌هایش را در ساده‌ترین لباس تحسین کنید.
اولترا وایب ۲۰۰۰
مرحله ۹
بگذارید ۲ روز بگذرد.
صبح، جنی و دبی در آشپزخانه درباره شغل جدید دختر صحبت می‌کنند. یا با او برخورد کنید ▲ یا بگذارید برود ▼ . بسته به پاسختان، به ترتیب در راهرو یا اتاق غذاخوری ادامه دهید.
مرحله ۱۰
روز بعد، جنی دم در ورودی است و آماده‌ی خرید. بعد از مذاکره، او را تا مرکز خرید همراهی می‌کنید و در آنجا با گریس روبرو می‌شوید . در فروشگاه سکس، دیلدو حلقه‌دار آبی و سفید را برمی‌دارید.
مرحله ۱۱
دفتر خاطرات جنی نکات زیادی را ارائه می‌دهد
جاسوسی کامپیوتری
مرحله ۱۲
روز بعد، کنجکاوی شما را وادار می‌کند که دوباره دفتر خاطرات جنی را زیر نظر بگیرید. صبر کنید تا او دوش بگیرد و یواشکی وارد اتاقش شوید. به نظر می‌رسد جنی به یک وب‌کم‌گرل تبدیل شده است! دفتر خاطرات علاقه‌ی جنی به یک اسباب‌بازی جنسی خاص را نشان می‌دهد. لپ‌تاپ را بررسی کنید، اما وقت کافی ندارید؛ تا عصر صبر کنید و برگردید. برای ورود، BADMONSTER را به عنوان رمز عبور تایپ کنید. ایمیل‌های او نشان می‌دهد که او هم در LiveCrush و هم در Pink Channel حساب کاربری دارد. سپس، برنامه CAMslut را باز کنید و روی دکمه‌ی Videos کلیک کنید. حریم خصوصی قدیمی است، بنابراین هر دو کامپیوتر را به هم متصل کنید (به حدود ۵ اینچ هوش نیاز دارد). آفرین! حالا به سراغ کامپیوترتان بروید؛ می‌توانید از طریق دسترسی از راه دور از ویدیوهای قبلی CAMslut او لذت ببرید.
آیا این یک هدیه است؟ (هیولای بد)
مرحله ۱۳
بگذارید ۳ روز بگذرد.
صبح، ویدیوی جدید را روی کامپیوترتان چک کنید. وقت آن است که آن هیولای بد معروف را تهیه کنید : دیلدو بزرگ و بسیار سبز را از پینک بخرید. بعدازظهر هدیه را به دختر وبکم بدهید.
مرحله ۱۴
روز بعد، یک ویدیوی جدید در CAMslut در انتظار شماست. این دختر با استفاده از تخصص خود، دو اسباب‌بازی را همزمان ناپدید می‌کند!
یک ستاره پورن متولد شد
مرحله ۱۵
بگذارید ۲ روز بگذرد.
طبق معمول صبح، جنی در اتاق غذاخوری مشغول خوردن صبحانه است. او از شما درخواست لطفی می‌کند و مبلغی را به عنوان پاداش به شما می‌دهد. مرد مو قرمز پشت سالن ورزشی ، سدریک است ، با او در مورد جنی صحبت کنید. امتناع او کار را برای شما آسان‌تر نمی‌کند و حالا باید به دوست دختر سابق دیوانه‌اش گزارش دهید.
مرحله ۱۶
بگذارید ۳ روز بگذرد.
منتظر شب بمانید و از اتاق خوابتان بیرون بیایید. جنی را در حال چت کردن کاملاً برهنه غافلگیر می‌کنید، که باعث می‌شود هیولای بد را به شکلی دیگر تجربه کنید!
مرحله ۱۷
صبح روز بعد، از تلسکوپ برای تماشای میا استفاده کنید . جنی شما را دستگیر می‌کند و آناتومی شما را نشان می‌دهد. شما برای نمایش بعدی استخدام شده‌اید! تا بعد از ظهر صبر کنید و وارد اتاق خواب او شوید، جایی که او اصرار دارد صورت خود را بپوشانید. به مرکز خرید بروید، جایی که یک ماسک پینک سایکلون در کازمیک کامیکس موجود است . در اتاق خواب جنی، دختر برای روز بعد به شما وقت ملاقات می‌دهد.
مرحله ۱۸
اولین نمایش دوربین: جابجایی دستی
روز بعد، بعد از ظهر، به اتاق جنی برگرد. دختر مسئول اولین ویدیوی پورن توست.
صبح روز بعد، درآمد خود را از جنی در اتاق غذاخوری دریافت کنید؛ این کار همچنین گزینه نمایش دوربین در اتاق خواب او را فعال می‌کند.
مرحله ۱۹
وارد کانال pink داخل تلبیوزون شود و شروع به دیدن فیلم کنید جنی شمارو می بیند و باهم وقت میگزرانید

مرحله ۲۰
بگذارید ۲ روز بگذرد.
عصر، جنی را در حال خودارضایی در اتاق نشیمن تماشا کنید. شما به مهمانی مخصوص عاشقان پا دعوت شده‌اید! اکنون می‌توانید با استفاده از نام کاربری ( L6bv12R ) و رمز عبور ( 12345 ) او، عصرها هر زمان که خواستید، کانال صورتی را از تلویزیون تماشا کنید.
دومین نمایش وب کم: لذت بردن متقابل
روز بعد، جنی شما را با تمام ظرافتی که مختص اوست از خواب بیدار می‌کند. بعدازظهر، طبق قرار قبلی به اتاق خوابش بیایید: وقتی برای تلف کردن نیست، «شاهزاده خانم جنی» برای فیلمبرداری آماده است!
روز بعد، جنی موقع صبحانه سهم تو را می‌دهد.
مرحله ۲۱
روز بعد، تامی ... و اریک را از طریق تلسکوپ نگاه می‌کند. این منظره الهام‌بخش جنی می‌شود و او یک ایده شیطنت‌آمیز به ذهنش می‌رسد.
سومین نمایش وب کم: BDSM، تشویق کننده، رابطه جنسی خام
روز بعد، در اتاق غذاخوری، جنی به شما اطلاع می‌دهد که برنامه بعدی امروز است. چیزی بگویید ▲ یا ساکت بمانید ▼ . اول، لباس تشویقی قدیمی‌اش را از اتاق زیر شیروانی بردارید: کلید کوچک در ورودی، چهارپایه در گاراژ را بردارید، سپس دریچه راهرو را باز کنید و لباس‌ها را برای جنی بیاورید. چه لباس مناسب پوشیده باشید و چه لباس‌هایتان را درنیاورید، آماده یک نمایش وبکم جدید هستید. اگر در انتخاب‌های قبلی با او ( ▲ ) روبرو شده‌اید و اگر حداقل ۷ امتیاز قدرت دارید، می‌توانید دستبندها را برای رابطه جنسی خام بیشتر بشکنید.
برای پیشرفت بیشتر در مسیرش، جنی را باردار نکنین
مرحله ۲۲
فیلم هیجان انگیز
منتظر شنبه یا یکشنبه صبح باشید.
در ورودی، از شما خواسته می‌شود که جنی را برای صبحانه صدا کنید. به حیاط خلوت بروید. اما یک مرد ترسناک شما را زیر نظر دارد و تنها سرنخی که برای دستگیری او دارید، یک بلیط است. این مزاحم که نامش آقای بابلز است ، در پیشخوان سینما در مرکز خرید است. بعد از ظهر، از بلیط‌های رایگانی که برای دردسر گرفته‌اید استفاده کنید تا با جنی در سینما قرار بگذارید و شاهد انتقام او باشید! از آنجایی که فیلم افتضاح است، او راه دیگری برای سرگرم کردن خود تصور می‌کند که شامل دست شما و باسنش می‌شود. دختر آن شب در رختخواب شما به رابطه نامشروع خود ادامه می‌دهد.
روز بعد، جنی و دبی را در اتاق غذاخوری پیدا کنید. می‌توانید از تعاملات جدید با جنی در حمام لذت ببرید!
شما اچیومنت Prolific camshow را دریافت می‌کنید .
صحنه‌های اختیاری
تجربه دوست دختر
مرحله ۲۳
بگذارید ۳ روز بگذرد.
صبح، توی راهرو یه کم با جنی حرف بزن.
صبح روز بعد، برای نگاهی دیگر به دفتر خاطرات جنی آماده شوید. احساسات او نسبت به شما در حال تغییر است. هدیه‌ای عالی برای اغوا کردن او، گردنبندی از فروشگاه کوپید در مرکز خرید است؛ هر کدام از آنها را که دوست دارید بخرید و به جنی هدیه دهید. همانطور که انتظار می‌رفت، نتیجه غافلگیرکننده بود، تشویق‌کننده سابق بیشتر با پول نقد متقاعد شد. امشب، تجربه جدید او را که از روی مبل شروع می‌شود و در رختخواب شما به پایان می‌رسد، بپذیرید!
غذای شاد
مرحله ۲۴
صبح، صبحانه را با جنی در اتاق غذاخوری بخورید. وقتی به او پیشنهاد می‌دهید که کمی خوش بگذراند، او از فرصت استفاده می‌کند تا میل جنسی‌اش را ارضا کند.
در رختخواب با جنی

آخر شب خودت را مستقیماً به رختخواب او دعوت کن، و جنی به راحتی متقاعد می‌شود که بیشتر ادامه دهد.
ورزش‌های آبی
مرحله ۲۵
منتظر شنبه یا یکشنبه صبح باشید.
همینطور که جنی کنار استخر مشغول استراحت است، به او پیشنهاد دهید که با شما در آب بازی کند؛ چیزی که در ادامه اتفاق می‌افتد ترکیبی از رابطه جنسی و غرق شدن است.
مرحله ۲۶
دوربین مخفی فرصت‌طلبانه

فقط از رختخواب خانگی MC محرک‌ها فعال می‌شوند.
وقتی جنی به هفته سوم بارداری‌اش (شکم بزرگ) برسد، خوابیدن در تخت MC منجر به یک بیداری ناگهانی می‌شود که در آن جنی یک نمایش وب کم بسیار ویژه پیشنهاد می‌دهد .

تبریک شما مراحل جنی را تکمیل کردید


توضیحات اضافی 

بارداری
برای اطلاعات بیشتر در مورد این ویژگی، به بخش بارداری مراجعه کنید .
رابطه جنسی با جنی این امکان را برای او فراهم می‌کند که باردار شود . یک هفته بعد، پیام تلفنی را بخوانید و برای اعلام خبر به اتاق خوابش بروید. تا هفته سوم، در بحث بین دبی و جنی در آشپزخانه شرکت کنید؛ دو هفته دیگر جنی را در حمام پیدا می‌کنید. هفته پنجم پیام جدیدی به پایان می‌رسد و به او اطلاع می‌دهد که در حال زایمان است؛ آن را بخوانید و با زنان بیمارستان ملاقات کنید . دو هفته دیگر طول می‌کشد تا نوزاد به مهدکودک فرستاده شود و شما بتوانید فعالیت‌های عادی خود را با جنی از  اول شروع کنین
""",
    },
    "character_03": {
        "title": "👩‍🦱 راهنمای دبی",
        "text": """

1. صبح به طبقه پایین برو؛ تماس تلفنی Debbie را ببین.


2. روز بعد کمک برای چمن‌زنی را قبول کن.


3. ماشین چمن‌زن را بررسی کن.


4. از فروشگاه یک گالن بنزین بخر.


5. چمن را کوتاه کن.


6. لباس‌های کثیف را به زیرزمین ببر.


7. روز بعد در را برای مرد طلبکار باز کن.


8. روز بعد با Debbie و Mrs. Johnson جلوی خانه صحبت کن.


9. روز بعد Debbie از نشتی دوش می‌گوید.


10. به زیرزمین برو و شیر آب را ببند.


11. از فروشگاه یک آچار بخر.


12. دوش را تعمیر کن.


13. صبح روز بعد وارد حمام شو و صحنه را ببین.


14. روز بعد جلوی خانه برو.


15. روز بعد در تمیز کردن خانه کمک کن.


16. روز بعد برای خرید با Debbie به مرکز خرید برو.


17. وسایل موردنیاز را بخر و به خانه برگرد.


18. شب با Debbie فیلم تماشا کن.


19. روز بعد در آشپزخانه با او صحبت کن.


20. هر بار که امکان داشت در کارهای خانه کمک کن تا رویدادهای بعدی باز شوند.


21. صبح‌ها در آشپزخانه و حمام، شب‌ها در اتاق نشیمن و اتاق Debbie را بررسی کن.


22. با پیشرفت داستان، رویدادهای ماشین، زیرزمین، آشپزخانه و اتاق‌خواب به‌ترتیب باز می‌شوند.


23. ادامه مسیر با انجام رویدادهای جدیدی که هر روز ظاهر می‌شوند کامل می‌شود. 

""",
    },
}
CHARACTER_KEYWORDS = {
    "character_01": ["راهنمای آنون", "آنون", "انان"],
    "character_02": ["راهنمای جنی", "جنی"],
    "character_03": ["راهنمای دبی", "دبی", "دابی"],
}
# برای اضافه کردن کاراکتر جدید، یک بلوک مثل بالا با کلید character_02 و ... اضافه کن.

# ---------- 📦 محل آیتم‌ها و کاربرد آن ----------
ITEMS = {
    # مثال:
    # "i01": {
    #     "title": "🔑 کلید انبار",
    #     "text": "📍 مکان: ...\n🛠 کاربرد: ...",
    # },
}
ITEM_KEYWORDS = {
    # "i01": ["کلید انبار", "کلید"],
}

# ---------- 📜 ماموریت‌های فرعی ----------
SIDE_MISSIONS = {
    # مثال:
    # "m01": {
    #     "title": "🧩 ماموریت کمک به دبی",
    #     "text": "🔹 مرحله ۱ - ...\n🔹 مرحله ۲ - ...",
    # },
}
MISSION_KEYWORDS = {
    # "m01": ["کمک به دبی", "ماموریت دبی"],
}

# ============================================================
# KEYBOARDS
# ============================================================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👤 شخصیت‌ها", callback_data="cat_characters")],
            [InlineKeyboardButton("📦 محل آیتم‌ها و کاربرد آن", callback_data="cat_items")],
            [InlineKeyboardButton("📜 ماموریت‌های فرعی", callback_data="cat_missions")],
            [InlineKeyboardButton("👥 زیرمجموعه‌گیری", callback_data="cat_referral")],
            [InlineKeyboardButton("💰 کیف پول", callback_data="cat_wallet")],
        ]
    )


def build_list_keyboard(
    data_dict: dict, prefix: str, user_id: int = None, cost: int = COUPON_COST_PER_VIEW
) -> InlineKeyboardMarkup:
    show_cost = False
    if user_id is not None:
        data = load_data()
        show_cost = has_used_free_today(data, user_id)

    buttons = []
    for key, entry in data_dict.items():
        title = entry.get("title") or f"❔ {key}"
        if show_cost:
            title = f"{title}  (💰 {cost} کوپن)"
        buttons.append([InlineKeyboardButton(title, callback_data=f"{prefix}_{key}")])
    buttons.append([InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def detail_back_keyboard(cat_callback: str, label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=cat_callback)]])


def join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 عضویت در کانال", url=CHANNEL_URL)],
            [InlineKeyboardButton("✅ عضو شدم!", callback_data="check_membership")],
        ]
    )


MAIN_MENU_TEXT = (
    "🎮 *به راهنمای بازی Summertime Saga خوش اومدی!*\n\n"
    "یکی از بخش‌های زیر رو انتخاب کن 👇"
)

CATEGORY_INTRO = {
    "characters": "👤 *لیست کاراکترها* — یکی رو انتخاب کن:",
    "items": "📦 *لیست آیتم‌ها* — یکی رو انتخاب کن:",
    "missions": "📜 *لیست ماموریت‌های فرعی* — یکی رو انتخاب کن:",
}

CATEGORY_BACK_LABEL = {
    "characters": "↩️ بازگشت به لیست کاراکترها",
    "items": "↩️ بازگشت به لیست آیتم‌ها",
    "missions": "↩️ بازگشت به لیست ماموریت‌های فرعی",
}

LOCK_MESSAGE = (
    "🔒 *دسترسی محدود شده است*\n\n"
    "برای استفاده از ربات راهنمای Summertime Saga، ابتدا باید عضو کانال ما بشی.\n\n"
    "1️⃣ روی دکمه‌ی «عضویت در کانال» بزن و عضو شو.\n"
    "2️⃣ بعد از عضویت، روی دکمه‌ی «✅ عضو شدم!» کلیک کن.\n\n"
    "بدون عضویت امکان استفاده از ربات وجود نداره 🙏"
)

INVALID_MESSAGE = (
    "❓ متوجه پیام شما نشدم.\n\n"
    "لطفاً برای دیدن منوی اصلی، عبارت «راهنما» رو ارسال کنید."
)

# ============================================================
# MESSAGE SPLITTER (تلگرام هر پیام رو حداکثر ۴۰۹۶ کاراکتر قبول می‌کنه)
# ============================================================
TELEGRAM_SAFE_CHUNK = 3500  # کمی کمتر از سقف واقعی، برای حاشیه‌ی امن


def split_text_into_chunks(text: str, max_len: int = TELEGRAM_SAFE_CHUNK):
    """
    اگه متن از max_len بیشتر باشه، تقسیمش می‌کنه به چند تکه.
    تا حد امکان سعی می‌کنه از وسط پاراگراف/خط نشکافه (اول دنبال \\n\\n، بعد \\n، بعد فاصله می‌گرده).
    """
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text
    while len(remaining) > max_len:
        window = remaining[:max_len]
        split_pos = window.rfind("\n\n")
        if split_pos == -1:
            split_pos = window.rfind("\n")
        if split_pos == -1:
            split_pos = window.rfind(" ")
        if split_pos == -1:
            split_pos = max_len
        chunks.append(remaining[:split_pos].rstrip())
        remaining = remaining[split_pos:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks


async def send_guide_text(update: Update, text: str, keyboard: InlineKeyboardMarkup) -> None:
    """برای پاسخ به پیام متنی (handle_text) - متن رو در صورت لزوم به چند پیام تقسیم می‌کنه."""
    chunks = split_text_into_chunks(text)
    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        await update.message.reply_text(
            chunk,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard if is_last else None,
        )


async def send_guide_text_callback(
    query, context: ContextTypes.DEFAULT_TYPE, text: str, keyboard: InlineKeyboardMarkup
) -> None:
    """برای پاسخ به کلیک دکمه (handle_callback) - متن رو در صورت لزوم به چند پیام تقسیم می‌کنه."""
    chunks = split_text_into_chunks(text)

    # تکه‌ی اول جایگزین همون پیامی می‌شه که کاربر روش کلیک کرده
    await query.edit_message_text(
        chunks[0],
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard if len(chunks) == 1 else None,
    )

    # بقیه‌ی تکه‌ها به‌صورت پیام‌های جدید و جداگانه ارسال می‌شن
    for i, chunk in enumerate(chunks[1:], start=1):
        is_last = i == len(chunks) - 1
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=chunk,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard if is_last else None,
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
# PERSISTENT STORAGE (JSON file: users, codes, photos)
# ============================================================
def _default_data() -> dict:
    return {"users": {}, "codes": {}, "photos": {}, "files": {}}


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
    data.setdefault("files", {})
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
        data["users"][key] = {
            "warnings": 0,
            "coupons": 0,
            "last_free_view_date": None,
            "referred_by": None,
            "referral_count": 0,
        }
    entry = data["users"][key]
    entry.setdefault("warnings", 0)
    entry.setdefault("coupons", 0)
    entry.setdefault("last_free_view_date", None)
    entry.setdefault("referred_by", None)
    entry.setdefault("referral_count", 0)
    return entry


def has_used_free_today(data: dict, user_id: int) -> bool:
    """بدون مصرف کردن چیزی، فقط چک می‌کنه که سهمیه‌ی رایگان امروز قبلاً استفاده شده یا نه."""
    entry = get_user_entry(data, user_id)
    today_str = datetime.utcnow().date().isoformat()
    return entry.get("last_free_view_date") == today_str


async def try_unlock_view(user_id: int, cost: int = COUPON_COST_PER_VIEW, item_label: str = "مورد بعدی"):
    """
    تصمیم می‌گیره کاربر می‌تونه محتوا (راهنما/آیتم/ماموریت/عکس/فایل) رو ببینه یا نه.
    هر روز (بر اساس تاریخ UTC) یک مورد رایگانه (فارغ از نوعش - هرکدوم اول درخواست بشه).
    بعد از اون، هر بار به تعداد `cost` کوپن کم می‌شه.
    اگه کوپن کافی نداشته باشه: اجازه نمی‌ده و پیام راهنما برمی‌گردونه.
    خروجی: (allowed: bool, message: str)
    """
    data = load_data()
    entry = get_user_entry(data, user_id)
    today_str = datetime.utcnow().date().isoformat()

    if entry.get("last_free_view_date") != today_str:
        entry["last_free_view_date"] = today_str
        save_data(data)
        return True, ""

    if entry.get("coupons", 0) >= cost:
        entry["coupons"] -= cost
        save_data(data)
        return True, ""

    msg = (
        "🔒 سهمیه‌ی رایگان امروزتون تموم شده.\n"
        f"برای دیدن {item_label} به {cost} کوپن نیاز دارید "
        f"(موجودی فعلی شما: {entry.get('coupons', 0):,} کوپن).\n\n"
        "💡 برای گرفتن کوپن: از بخش «👥 زیرمجموعه‌گیری» دوستاتون رو دعوت کنید یا یک کد سریال فعال کنید.\n"
        "یا فردا دوباره سر بزنید — هر روز ۱ مورد رایگان دارید."
    )
    return False, msg


# ============================================================
# COUPON CODES ("سریال") — GENERATION & REDEMPTION
# ============================================================
PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_DIGIT_TRANSLATION = str.maketrans(PERSIAN_DIGITS, "0123456789")

PERSIAN_NUMBER_WORDS = {
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
}


def fa_to_en_digits(s: str) -> str:
    return s.translate(_DIGIT_TRANSLATION)


def generate_unique_code(existing_codes) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=CODE_LENGTH))
        if code not in existing_codes:
            return code


def parse_coupon_amount(number_token: str, multiplier_word: str) -> int:
    number_token = number_token.strip()
    if number_token in PERSIAN_NUMBER_WORDS:
        base = PERSIAN_NUMBER_WORDS[number_token]
    else:
        try:
            base = int(fa_to_en_digits(number_token))
        except ValueError:
            base = 0
    multiplier = 1
    if multiplier_word:
        if "هزار" in multiplier_word:
            multiplier = 1_000
        elif "میلیون" in multiplier_word:
            multiplier = 1_000_000
    return base * multiplier


# مثال دستورهایی که تشخیص داده می‌شن:
#   "ساخت سریال ۱ هزار کوپن"        -> ۱ کد به ارزش ۱۰۰۰ کوپن
#   "ساخت سریال ۲ هزار کوپن"        -> ۱ کد به ارزش ۲۰۰۰ کوپن
#   "ساخت سریال ۱۰ هزار کوپن"       -> ۱ کد به ارزش ۱۰۰۰۰ کوپن
#   "ساخت سریال یک میلیون کوپن"     -> ۱ کد به ارزش ۱۰۰۰۰۰۰ کوپن
#   "ساخت سریال ۵۰۰۰ کوپن"          -> ۱ کد به ارزش ۵۰۰۰ کوپن (هر عدد دلخواه)
#   "ساخت ۵ عدد سریال ۱۰۰۰ کوپن"    -> ۵ کد، هرکدوم به ارزش ۱۰۰۰ کوپن
MAKE_COUPON_PATTERN = re.compile(
    r"ساخت\s*(?:([\d۰-۹]+)\s*عدد\s*)?سریال\s*"
    r"(یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|[\d۰-۹]+)\s*"
    r"(هزار|میلیون)?\s*کوپن"
)

REDEEM_PATTERN = re.compile(r"وارد\s*کردن\s*سریال\s+([A-Za-z0-9]{%d})" % CODE_LENGTH)


async def handle_admin_make_codes(update: Update, context: ContextTypes.DEFAULT_TYPE, match) -> None:
    count_str = match.group(1)
    count = int(fa_to_en_digits(count_str)) if count_str else 1
    count = max(1, min(count, 100))  # سقف ایمنی برای جلوگیری از اشتباه تایپی

    amount = parse_coupon_amount(match.group(2), match.group(3))
    if amount <= 0:
        await update.message.reply_text("❌ مقدار کوپن تشخیص داده نشد.")
        return

    data = load_data()
    new_codes = []
    for _ in range(count):
        code = generate_unique_code(data["codes"].keys())
        data["codes"][code] = {"coupons": amount, "used": False, "used_by": None}
        new_codes.append(code)
    save_data(data)

    codes_block = "\n".join(f"`{c}`" for c in new_codes)
    await update.message.reply_text(
        f"✅ {count} عدد سریال به ارزش {amount:,} کوپن ساخته شد:\n\n{codes_block}",
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
    user_entry["coupons"] = user_entry.get("coupons", 0) + entry["coupons"]
    save_data(data)

    await update.message.reply_text(
        f"🎉 {entry['coupons']:,} کوپن به موجودی شما اضافه شد!\n"
        f"موجودی فعلی: {user_entry['coupons']:,} کوپن"
    )


# ============================================================
# 💰 WALLET (کیف پول)
# ============================================================
def build_wallet_text(user_id: int) -> str:
    data = load_data()
    entry = get_user_entry(data, user_id)
    used_today = has_used_free_today(data, user_id)

    if used_today:
        free_status = "❌ استفاده شده — فردا دوباره فعال می‌شه"
    else:
        free_status = "✅ در دسترس"

    return (
        "💰 *کیف پول شما*\n\n"
        f"🎟 موجودی کوپن: *{entry.get('coupons', 0):,}*\n"
        f"🎁 سهمیه‌ی رایگان امروز: {free_status}\n\n"
        f"هزینه‌ی هر راهنما/آیتم/ماموریت: {COUPON_COST_PER_VIEW} کوپن\n"
        f"هزینه‌ی هر عکس/فایل/ویدیو: {COUPON_COST_MEDIA} کوپن\n\n"
        "💡 برای افزایش موجودی: از بخش «👥 زیرمجموعه‌گیری» دوستاتون رو دعوت کنید یا یک کد سریال فعال کنید."
    )


# ============================================================
# 👥 REFERRAL PROGRAM (زیرمجموعه‌گیری)
# ============================================================
def build_referral_text(bot_username: str, user_id: int) -> str:
    data = load_data()
    entry = get_user_entry(data, user_id)
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    return (
        "👥 *زیرمجموعه‌گیری*\n\n"
        f"لینک اختصاصی شما:\n`{link}`\n\n"
        f"👤 تعداد زیرمجموعه‌ها: {entry.get('referral_count', 0)}\n"
        f"🎟 موجودی کوپن شما: {entry.get('coupons', 0):,}\n\n"
        f"به‌ازای هر نفری که با لینک شما وارد بات بشه، *{COUPONS_PER_REFERRAL} کوپن* به شما اضافه می‌شه."
    )


async def register_referral_if_needed(context: ContextTypes.DEFAULT_TYPE, user_id: int, args) -> None:
    if not args:
        return
    payload = args[0]
    if not payload.startswith("ref_"):
        return

    try:
        referrer_id = int(payload.replace("ref_", "", 1))
    except ValueError:
        return

    if referrer_id == user_id:
        return  # جلوگیری از دعوت خود شخص

    data = load_data()
    entry = get_user_entry(data, user_id)
    if entry.get("referred_by") is not None:
        return  # قبلاً یک‌بار زیرمجموعه‌ی کسی ثبت شده، دوباره حساب نمی‌شه

    entry["referred_by"] = referrer_id
    referrer_entry = get_user_entry(data, referrer_id)
    referrer_entry["referral_count"] = referrer_entry.get("referral_count", 0) + 1
    referrer_entry["coupons"] = referrer_entry.get("coupons", 0) + COUPONS_PER_REFERRAL
    save_data(data)

    try:
        await context.bot.send_message(
            chat_id=referrer_id,
            text=(
                f"🎉 یک نفر با لینک دعوت شما وارد ربات شد!\n"
                f"🎟 {COUPONS_PER_REFERRAL} کوپن به موجودی شما اضافه شد."
            ),
        )
    except TelegramError as e:
        logger.error("Failed to notify referrer %s: %s", referrer_id, e)


# ============================================================
# PHOTO UPLOAD / DELIVERY (with auto-delete)
# ============================================================
PENDING_PHOTO_UPLOADS: dict = {}  # admin_id -> key در انتظار عکس

PHOTO_UPLOAD_CMD = re.compile(r"^آپلود\s*عکس\s+(.+)$")
PHOTO_REQUEST_CMD = re.compile(r"^عکس\s+(.+)$")


AUTO_DELETE_CAPTION = (
    f"⏳ این فایل/عکس/ویدیو بعد از {AUTO_DELETE_SECONDS} ثانیه خودکار حذف می‌شه.\n"
    "برای ذخیره‌ش، همین الان به «پیام‌های ذخیره‌شده» (Saved Messages) فوروارد کن."
)


async def delete_message_later(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    try:
        await context.bot.delete_message(chat_id=job_data["chat_id"], message_id=job_data["message_id"])
    except TelegramError as e:
        logger.error("Failed to auto-delete message: %s", e)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS and user_id in PENDING_PHOTO_UPLOADS:
        key = PENDING_PHOTO_UPLOADS.pop(user_id)
        file_id = update.message.photo[-1].file_id
        data = load_data()
        data["photos"][key] = file_id
        save_data(data)
        await update.message.reply_text(
            f"✅ عکس برای «{key}» ذخیره شد.\n"
            f"حالا کاربرها با ارسال «عکس {key}» می‌تونن ببیننش "
            f"(هزینه: {COUPON_COST_MEDIA} کوپن بعد از سهمیه‌ی رایگان روزانه، و بعد از {AUTO_DELETE_SECONDS} ثانیه خودکار حذف می‌شه)."
        )


# ============================================================
# FILE / VIDEO DELIVERY (بازی‌ها، فیلم‌های آموزشی، هر فایلی)
# ============================================================
# نکته: اگه فایل/ویدیو از قبل داخل کانالت پست شده، لازم نیست دوباره آپلودش کنی —
# فقط همون پیام رو از کانال به ربات فوروارد کن، دقیقاً مثل فرستادن مستقیم عمل می‌کنه.
PENDING_FILE_UPLOADS: dict = {}  # admin_id -> key در انتظار فایل/ویدیو

FILE_UPLOAD_CMD = re.compile(r"^آپلود\s*فایل\s+(.+)$")
FILE_REQUEST_CMD = re.compile(r"^دریافت\s+(.+)$")


async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not (user_id in ADMIN_IDS and user_id in PENDING_FILE_UPLOADS):
        return

    message = update.message
    if message.document:
        file_id, media_type = message.document.file_id, "document"
    elif message.video:
        file_id, media_type = message.video.file_id, "video"
    elif message.audio:
        file_id, media_type = message.audio.file_id, "audio"
    else:
        return  # نوع پشتیبانی‌نشده - چیزی مصرف نکن، شاید هندلر دیگه‌ای بخواد پردازشش کنه

    key = PENDING_FILE_UPLOADS.pop(user_id)
    data = load_data()
    data["files"][key] = {"file_id": file_id, "type": media_type}
    save_data(data)
    await message.reply_text(
        f"✅ فایل «{key}» ذخیره شد (نوع: {media_type}).\n"
        f"حالا کاربرها با ارسال «دریافت {key}» می‌تونن بگیرنش "
        f"(هزینه: {COUPON_COST_MEDIA} کوپن بعد از سهمیه‌ی رایگان روزانه، و بعد از {AUTO_DELETE_SECONDS} ثانیه خودکار حذف می‌شه)."
    )


async def send_stored_file(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
    data = load_data()
    file_entry = data.get("files", {}).get(key)
    if not file_entry:
        await update.message.reply_text("❌ فایلی با این نام ثبت نشده.")
        return

    file_id = file_entry["file_id"]
    media_type = file_entry["type"]
    try:
        if media_type == "document":
            sent = await update.message.reply_document(file_id, caption=AUTO_DELETE_CAPTION)
        elif media_type == "video":
            sent = await update.message.reply_video(file_id, caption=AUTO_DELETE_CAPTION)
        elif media_type == "audio":
            sent = await update.message.reply_audio(file_id, caption=AUTO_DELETE_CAPTION)
        else:
            return

        if context.job_queue:
            context.job_queue.run_once(
                delete_message_later,
                AUTO_DELETE_SECONDS,
                data={"chat_id": sent.chat_id, "message_id": sent.message_id},
            )
    except TelegramError as e:
        logger.error("Failed to send stored file '%s': %s", key, e)
        await update.message.reply_text("❌ خطا در ارسال فایل. دوباره امتحان کن.")


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
    پیام‌های ادمین‌ها هیچ‌وقت پاک نمی‌شن. بعد از ۳ اخطار، کاربر از گروه حذف می‌شه.
    """
    message = update.message
    if not message or not message.text:
        return False

    user_id = message.from_user.id
    if user_id in ADMIN_IDS:
        return False

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

    await register_referral_if_needed(context, user_id, context.args)

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
    chat_type = update.effective_chat.type  # "private", "group", "supergroup", "channel"

    # 🚦 توی گروه/سوپرگروه فقط فیلتر لینک/تبلیغ فعاله؛ هیچ دستور دیگه‌ای جواب داده نمی‌شه
    if chat_type != "private":
        await delete_links_and_ads(update, context)
        return

    # ---------------------------------------------------------------
    # از این‌جا به بعد فقط توی چت خصوصی (پیوی) با ربات اجرا می‌شه
    # ---------------------------------------------------------------

    # 1) دستور ادمین برای ساخت سریال کوپن
    make_match = MAKE_COUPON_PATTERN.search(raw_text)
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

    # 2.5) دستور ادمین برای شروع آپلود فایل/ویدیو (بازی، فیلم آموزشی، هر فایلی)
    file_upload_match = FILE_UPLOAD_CMD.match(raw_text.strip())
    if file_upload_match and user_id in ADMIN_IDS:
        key = file_upload_match.group(1).strip()
        PENDING_FILE_UPLOADS[user_id] = key
        await update.message.reply_text(
            f"📁 حالا فایل/ویدیوی مربوط به «{key}» رو بفرست.\n"
            "می‌تونی مستقیم بفرستی یا از کانالت به همین چت فوروارد کنی."
        )
        return

    # 3) قفل عضویت کانال
    if not await is_member(context, user_id):
        await update.message.reply_text(
            LOCK_MESSAGE, parse_mode=ParseMode.MARKDOWN, reply_markup=join_keyboard()
        )
        return

    # 4) فعال‌سازی کوپن با کد سریال
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

    # 6) نمایش اطلاعات زیرمجموعه‌گیری با تایپ کلمه
    if "زیرمجموعه" in text or "دعوت" in text:
        referral_text = build_referral_text(context.bot.username, user_id)
        await update.message.reply_text(referral_text, parse_mode=ParseMode.MARKDOWN)
        return

    # 6.5) نمایش کیف پول با تایپ کلمه
    if "کیف پول" in text or "موجودی" in text:
        wallet_text = build_wallet_text(user_id)
        await update.message.reply_text(wallet_text, parse_mode=ParseMode.MARKDOWN)
        return

    # 7) تشخیص کاراکتر / آیتم / ماموریت فرعی (با گیت کول‌داون + کوپن)
    search_groups = (
        (CHARACTER_KEYWORDS, GUIDES, "characters"),
        (ITEM_KEYWORDS, ITEMS, "items"),
        (MISSION_KEYWORDS, SIDE_MISSIONS, "missions"),
    )
    matched_key = None
    matched_data = None
    matched_category = None
    for keywords_dict, data_dict, category in search_groups:
        for key, keywords in keywords_dict.items():
            for kw in keywords:
                if kw and kw in text:
                    matched_key, matched_data, matched_category = key, data_dict, category
                    break
            if matched_key:
                break
        if matched_key:
            break

    if matched_key:
        unlocked, msg = await try_unlock_view(user_id)
        if not unlocked:
            await update.message.reply_text(msg)
            return

        entry = matched_data[matched_key]
        await send_guide_text(
            update,
            entry["text"],
            detail_back_keyboard(f"cat_{matched_category}", CATEGORY_BACK_LABEL[matched_category]),
        )
        return

    # 8) درخواست عکس («عکس <نام>»)
    photo_match = PHOTO_REQUEST_CMD.match(raw_text.strip())
    if photo_match:
        key = photo_match.group(1).strip()
        data = load_data()
        file_id = data["photos"].get(key)
        if not file_id:
            await update.message.reply_text("❌ عکسی برای این مورد ثبت نشده.")
            return

        unlocked, msg = await try_unlock_view(user_id, cost=COUPON_COST_MEDIA, item_label="عکس بعدی")
        if not unlocked:
            await update.message.reply_text(msg)
            return

        sent = await update.message.reply_photo(file_id, caption=AUTO_DELETE_CAPTION)
        if context.job_queue:
            context.job_queue.run_once(
                delete_message_later,
                AUTO_DELETE_SECONDS,
                data={"chat_id": sent.chat_id, "message_id": sent.message_id},
            )
        return

    # 9) درخواست فایل/ویدیو/بازی («دریافت <نام>»)
    file_match = FILE_REQUEST_CMD.match(raw_text.strip())
    if file_match:
        key = file_match.group(1).strip()
        data = load_data()
        if key not in data.get("files", {}):
            await update.message.reply_text("❌ فایلی با این نام ثبت نشده.")
            return

        unlocked, msg = await try_unlock_view(user_id, cost=COUPON_COST_MEDIA, item_label="فایل بعدی")
        if not unlocked:
            await update.message.reply_text(msg)
            return

        await send_stored_file(update, context, key)
        return

    await update.message.reply_text(INVALID_MESSAGE)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    data_cb = query.data

    await query.answer()

    if data_cb == "check_membership":
        if await is_member(context, user_id):
            await query.edit_message_text(
                MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
            )
        else:
            await query.answer("❌ هنوز عضو کانال نشدی! لطفاً ابتدا عضو شو.", show_alert=True)
        return

    if not await is_member(context, user_id):
        await query.edit_message_text(
            LOCK_MESSAGE, parse_mode=ParseMode.MARKDOWN, reply_markup=join_keyboard()
        )
        return

    if data_cb == "back_main":
        await query.edit_message_text(
            MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
        )
        return

    if data_cb == "cat_characters":
        await query.edit_message_text(
            CATEGORY_INTRO["characters"], parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_list_keyboard(GUIDES, "char", user_id),
        )
        return

    if data_cb == "cat_items":
        await query.edit_message_text(
            CATEGORY_INTRO["items"], parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_list_keyboard(ITEMS, "item", user_id),
        )
        return

    if data_cb == "cat_missions":
        await query.edit_message_text(
            CATEGORY_INTRO["missions"], parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_list_keyboard(SIDE_MISSIONS, "mission", user_id),
        )
        return

    if data_cb == "cat_referral":
        referral_text = build_referral_text(context.bot.username, user_id)
        await query.edit_message_text(
            referral_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data="back_main")]]
            ),
        )
        return

    if data_cb == "cat_wallet":
        wallet_text = build_wallet_text(user_id)
        await query.edit_message_text(
            wallet_text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("↩️ بازگشت به منوی اصلی", callback_data="back_main")]]
            ),
        )
        return

    for prefix, data_dict, category in (
        ("char_", GUIDES, "characters"),
        ("item_", ITEMS, "items"),
        ("mission_", SIDE_MISSIONS, "missions"),
    ):
        if data_cb.startswith(prefix):
            key = data_cb[len(prefix):]
            entry = data_dict.get(key)
            if not entry:
                await query.edit_message_text(
                    MAIN_MENU_TEXT, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_keyboard()
                )
                return

            unlocked, msg = await try_unlock_view(user_id)
            if not unlocked:
                await query.answer(msg, show_alert=True)
                return

            await send_guide_text_callback(
                query, context, entry["text"],
                detail_back_keyboard(f"cat_{category}", CATEGORY_BACK_LABEL[category]),
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
    application.add_handler(
        MessageHandler(filters.VIDEO | filters.Document.ALL | filters.AUDIO, handle_file_upload)
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_error_handler(error_handler)

    logger.info("Bot started. Polling for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
