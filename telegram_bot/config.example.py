# Скопируй в config.py и заполни. Файл config.py в git не попадает.
import os

_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Telegram (обязательно) ───────────────────────────────────────────────
BOT_TOKEN = "получи у @BotFather"
# Твой числовой id (команда /myid в боте после запуска)
OWNER_CHAT_ID = 0
# Куда публиковать посты (@канал или -100...)
TARGET_CHANNEL = "@perfektorganic"
# Публичный username канала с отзывами (без @)
REVIEW_CHANNEL = "P_Organics_product"

# Ссылка на твой Telegram (кнопка «Задать вопрос»)
OWNER_TG_LINK = "https://t.me/username"

# ─── Расписание (Красноярск, см. pytz в bot.py) ─────────────────────────────
POST_HOUR = 10
POST_MINUTE = 0

# ─── Сайт и ссылки в постах ───────────────────────────────────────────────
SHOP_LINK = "https://perfect-org.ru/"
PARTNER_LINK = "https://perfect-org.ru/partner"
TEST_LINK = "https://perfect-org.ru/test"

# ─── API (пустая строка = функция отключена, где это допустимо) ─────────────
OPENAI_API_KEY = ""
GROQ_API_KEY = ""
TOGETHER_API_KEY = ""
LEONARDO_API_KEY = ""

# ─── Файлы данных (лучше не менять пути) ───────────────────────────────────
SAVED_POSTS_FILE = os.path.join(_DIR, "saved_posts.json")
POSTED_IDS_FILE = os.path.join(_DIR, "posted_ids.json")
