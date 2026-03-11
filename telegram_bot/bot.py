import html as html_module
import logging
import re
import json
import os
import random
import base64
import asyncio
import time
import requests
from datetime import time as dtime, datetime
from io import BytesIO

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

import pytz
from openai import AsyncOpenAI
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import *
from content_plan import (WEEKLY_PLAN, POST_TYPE_LABELS,
                          EXPERT_TOPICS, DOCTOR_PHOTO_PROMPTS,
                          VIRAL_TOPICS, VIRAL_PHOTO_PROMPTS, VIRAL_PHOTO_PROMPT, VIRAL_MINERAL_PHOTO_PROMPT, VIRAL_MINERAL_KEYWORDS,
                          build_viral_image_prompt, build_viral_photo1_prompt, build_viral_photo2_prompt, _VIRAL_PERSON_VARIANTS,
                          LIFESTYLE_TOPICS, LIFESTYLE_PHOTO_PROMPT, LIFESTYLE_PHOTO_PROMPTS,
                          _LIFESTYLE_PRODUCTION_TOPICS,
                          PARTNER_TOPICS, PARTNER_PHOTO_PROMPT, PARTNER_PHOTO_PROMPTS,
                          HEALTH_PROGRAMS, HEALTH_PROGRAM_URLS)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

oai = AsyncOpenAI(api_key=OPENAI_API_KEY)  # только для gpt-image-1
groq = AsyncOpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

# Хранилище ожидающих постов: owner_chat_id -> {text, photo, post_id, mode, weekday}
pending = {}

# Редактирование промптов: owner_id → ключ редактируемого промпта
editing_state = {}
PROMPT_OVERRIDES_FILE = os.path.join(os.path.dirname(__file__), 'prompt_overrides.json')


def load_prompt_overrides() -> dict:
    if os.path.exists(PROMPT_OVERRIDES_FILE):
        with open(PROMPT_OVERRIDES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_prompt_override(key: str, value: str):
    overrides = load_prompt_overrides()
    overrides[key] = value
    with open(PROMPT_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)


def delete_prompt_override(key: str):
    overrides = load_prompt_overrides()
    overrides.pop(key, None)
    with open(PROMPT_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)

DAY_NAMES = {0: "Понедельник", 1: "Вторник", 2: "Среда",
             3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"}
DAY_SHORT  = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}


def _resize_bytes(img_bytes: bytes, w: int, h: int) -> bytes:
    """Уменьшает изображение до (w, h) с качеством JPEG 85."""
    if not HAS_PIL:
        return img_bytes
    try:
        img = Image.open(BytesIO(img_bytes))
        img = img.resize((w, h), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception as e:
        logging.warning(f"_resize_bytes: {e}")
        return img_bytes


def load_saved_posts():
    if os.path.exists(SAVED_POSTS_FILE):
        with open(SAVED_POSTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_post_for_day(weekday, data):
    posts = load_saved_posts()
    entry = {"text": data["text"], "post_type": data["post_type"]}
    if data.get("photo"):
        entry["photo"] = base64.b64encode(data["photo"]).decode()
    if data.get("photo2"):
        entry["photo2"] = base64.b64encode(data["photo2"]).decode()
    if data.get("video"):
        entry["video"] = base64.b64encode(data["video"]).decode()
    posts[str(weekday)] = entry
    with open(SAVED_POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False)


def delete_saved_post(weekday):
    posts = load_saved_posts()
    posts.pop(str(weekday), None)
    with open(SAVED_POSTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False)


USED_TOPICS_FILE = "used_topics.json"


def get_fresh_topic(post_type, topics_list):
    """Возвращает тему, которая ещё не использовалась. Сбрасывает цикл когда все исчерпаны."""
    used = {}
    if os.path.exists(USED_TOPICS_FILE):
        with open(USED_TOPICS_FILE, 'r', encoding='utf-8') as f:
            used = json.load(f)

    used_keys = set(used.get(post_type, []))
    # Извлекаем строковый ключ: кортеж→первый элемент, dict→"condition", иначе строка
    def _topic_key(t):
        if isinstance(t, tuple):
            return t[0]
        if isinstance(t, dict):
            return t.get("condition", str(id(t)))
        return t
    all_keys = [_topic_key(t) for t in topics_list]
    available = [topics_list[i] for i, k in enumerate(all_keys) if k not in used_keys]

    if not available:
        # Все темы использованы — сбрасываем
        available = topics_list
        used[post_type] = []

    chosen = random.choice(available)
    chosen_key = _topic_key(chosen)
    used.setdefault(post_type, [])
    if chosen_key not in used[post_type]:
        used[post_type].append(chosen_key)

    with open(USED_TOPICS_FILE, 'w', encoding='utf-8') as f:
        json.dump(used, f, ensure_ascii=False)

    return chosen


# ─── Утилиты ────────────────────────────────────────────────────────────────

def load_posted_ids():
    if os.path.exists(POSTED_IDS_FILE):
        with open(POSTED_IDS_FILE, 'r') as f:
            return set(json.load(f))
    return set()


def save_posted_id(post_id):
    ids = load_posted_ids()
    ids.add(post_id)
    with open(POSTED_IDS_FILE, 'w') as f:
        json.dump(list(ids), f)


def get_posts_with_media(channel):
    """Парсит посты с фото/видео из публичного канала."""
    url = f"https://t.me/s/{channel}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = []
        for msg in soup.find_all('div', class_='tgme_widget_message'):
            post_id = msg.get('data-post', '')

            # Текст + ссылки из поста
            text_el = msg.find('div', class_='tgme_widget_message_text')
            text = ''
            links = []
            if text_el:
                text = text_el.get_text(separator='\n', strip=True)
                links = [a['href'] for a in text_el.find_all('a', href=True)]

            # Фото — из background-image
            photo_url = None
            photo_wrap = msg.find('a', class_='tgme_widget_message_photo_wrap')
            if photo_wrap:
                style = photo_wrap.get('style', '')
                m = re.search(r"url\('([^']+)'\)", style)
                if m:
                    photo_url = m.group(1)

            # Видео — src из <video> тега
            video_url = None
            video_el = msg.find('video')
            if video_el:
                video_url = video_el.get('src') or video_el.get('data-src')

            if post_id and (len(text) > 20 or photo_url or video_url):
                posts.append({
                    'id': post_id,
                    'text': text,
                    'links': links,
                    'photo_url': photo_url,
                    'video_url': video_url,
                })
        return posts
    except Exception as e:
        logging.error(f"Ошибка парсинга {channel}: {e}")
        return []


async def adapt_text(original_text, original_links=None):
    """Адаптирует текст отзыва под наш канал через Gemini, заменяет ссылки на наши."""
    if not original_text:
        return None

    links_info = ""
    if original_links:
        links_info = (
            f"\nВ оригинале были ссылки: {', '.join(original_links)}\n"
            f"Замени все ссылки на продукты на нашу: {PARTNER_LINK}\n"
        )

    try:
        prompt = (
            f"Перефразируй этот отзыв о добавках для Telegram канала Perfect Organic. "
            f"Сохрани смысл, эмоции и конкретику. Немного измени формулировки. "
            f"Убери упоминания других каналов или брендов если есть. "
            f"НЕ вставляй никаких ссылок и URL в текст — только чистый текст. "
            f"Без HTML тегов. Только готовый текст без комментариев.\n\n"
            f"Оригинал:\n{original_text}"
        )
        response = await groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.warning(f"Groq ошибка: {e}, используем оригинал")
        result = original_text
        # Заменяем чужие ссылки на наши
        if original_links:
            for link in original_links:
                if link.startswith('http') and 't.me' not in link:
                    result = result.replace(link, PARTNER_LINK)
        result += f"\n\n🛒 Заказать: {SHOP_LINK}"
        return result


def download_media(url):
    """Скачивает фото или видео по URL."""
    r = requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
    return r.content


def scrape_product_page(url):
    """Скрапит страницу продукта: описание, состав и URL главного фото."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Фото — ищем og:image
        image_url = None
        og = soup.find('meta', property='og:image')
        if og:
            image_url = og.get('content') or None

        # Убираем лишние блоки
        for tag in soup(['nav', 'header', 'footer', 'script', 'style']):
            tag.decompose()

        full_text = soup.get_text(separator='\n', strip=True)

        # Состав — ищем секцию с ключевыми словами
        composition = ""
        comp_keywords = ['состав', 'ингредиент', 'компонент', 'ingredient', 'composition']
        lines = full_text.splitlines()
        for i, line in enumerate(lines):
            if any(kw in line.lower() for kw in comp_keywords):
                # Берём эту строку и следующие 10 строк
                chunk = '\n'.join(lines[i:i+12]).strip()
                if len(chunk) > 30:
                    composition = chunk[:600]
                    break

        # Описание — ищем основной контент
        description = ""
        for sel in ['article', 'main', '.detail_text', '.product-description', '.content']:
            el = (soup.find(sel) if not sel.startswith('.')
                  else soup.find(class_=sel[1:]))
            if el:
                txt = el.get_text(separator='\n', strip=True)
                if len(txt) > 100:
                    description = txt[:1200]
                    break
        if not description:
            paras = [p.get_text(strip=True) for p in soup.find_all('p')
                     if len(p.get_text(strip=True)) > 40]
            description = '\n'.join(paras[:10])[:1200]

        return {'description': description, 'composition': composition, 'image_url': image_url}
    except Exception as e:
        logging.warning(f"Не удалось скрапить {url}: {e}")
        return {'description': '', 'composition': '', 'image_url': None}


def scrape_program_page(url):
    """Скрапит страницу программы здоровья: текст, продукты, og:image."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # og:image
        image_url = None
        og = soup.find('meta', property='og:image')
        if og:
            image_url = og.get('content') or None

        # Убираем nav/header/footer/script/style
        for tag in soup(['nav', 'header', 'footer', 'script', 'style']):
            tag.decompose()

        # Собираем весь текст, фильтруем короткие строки
        lines = [l.strip() for l in soup.get_text(separator='\n', strip=True).splitlines()]
        # Отбираем содержательные строки (не кнопки, не меню)
        content_lines = [l for l in lines if len(l) > 30 and not any(
            kw in l.lower() for kw in ['задать вопрос', 'стать партнером', 'получить', 'показать', 'скрыть',
                                        'каталог', 'доставка', 'контакты', 'отзывы', 'телефон:', 'www.',
                                        'javascript', 'function(', 'var ', 'css']
        )]
        description = '\n\n'.join(content_lines[:12])[:2000]

        return {'description': description, 'image_url': image_url}
    except Exception as e:
        logging.warning(f"Не удалось скрапить программу {url}: {e}")
        return {'description': '', 'image_url': None}


_PRODUCT_IMAGES_DIR = os.path.join(os.path.dirname(__file__), 'telegram_botproduct_images')


def get_product_image_bytes(product_url: str):
    """Возвращает bytes локального PNG файла продукта, или None если не найден.
    Имя файла = слаг из URL: https://perfect-org.ru/multiminerals74 → multiminerals74.png"""
    try:
        slug = product_url.rstrip('/').split('/')[-1]
        img_path = os.path.join(_PRODUCT_IMAGES_DIR, f'{slug}.png')
        if os.path.exists(img_path):
            with open(img_path, 'rb') as f:
                logging.info(f"✅ Локальное фото продукта: {slug}.png")
                return f.read()
    except Exception as e:
        logging.warning(f"get_product_image_bytes: {e}")
    return None


def get_random_product_image_bytes():
    """Возвращает bytes случайного PNG продукта из папки (для lifestyle/partner фото)."""
    try:
        files = [f for f in os.listdir(_PRODUCT_IMAGES_DIR)
                 if f.endswith('.png') and not f.startswith('image')]
        if files:
            chosen = random.choice(files)
            with open(os.path.join(_PRODUCT_IMAGES_DIR, chosen), 'rb') as f:
                logging.info(f"✅ Случайное фото продукта: {chosen}")
                return f.read()
    except Exception as e:
        logging.warning(f"get_random_product_image_bytes: {e}")
    return None


async def generate_image_together(prompt: str):
    """Генерирует фото через Together.ai FLUX.1-schnell (~10-30 сек).
    Возвращает (bytes, error_str) — bytes=None если ошибка."""
    if not TOGETHER_API_KEY:
        return None, "ключ не задан"

    def _sync():
        headers = {
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json",
        }
        for model in ("black-forest-labs/FLUX.1-schnell-Free",
                      "black-forest-labs/FLUX.1-schnell"):
            payload = {
                "model": model,
                "prompt": prompt[:500],
                "width": 1024,
                "height": 1024,
                "steps": 4,
                "n": 1,
                "response_format": "url",
            }
            try:
                r = requests.post(
                    "https://api.together.xyz/v1/images/generations",
                    json=payload, headers=headers, timeout=120,
                )
                if r.status_code != 200:
                    err = r.text[:300]
                    logging.warning(f"Together.ai ({model}): HTTP {r.status_code}: {err}")
                    return None, f"HTTP {r.status_code}: {err}"
                data = r.json()
                imgs = data.get("data", [])
                if imgs:
                    url = imgs[0].get("url") or imgs[0].get("b64_json")
                    if url and url.startswith("http"):
                        content = requests.get(url, timeout=30).content
                        return content, None
                    elif url:
                        return base64.b64decode(url), None
                err = str(data)[:300]
                logging.warning(f"Together.ai ({model}): нет изображения: {err}")
                return None, err
            except Exception as e:
                logging.warning(f"Together.ai ({model}): {e}")
                return None, str(e)[:200]
        return None, "все модели не ответили"

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync)


async def generate_image_leonardo(prompt: str):
    """Генерирует фото через Leonardo.ai (~20-40 сек, бесплатно 150 токенов/день).
    Возвращает bytes или None при ошибке."""
    def _sync():
        headers = {
            "Authorization": f"Bearer {LEONARDO_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Leonardo Phoenix 1.0 — флагманская фотореалистичная модель
        payload = {
            "prompt": prompt[:500],
            "width": 1024,
            "height": 1024,
            "num_images": 1,
            "modelId": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf1",
        }
        try:
            r = requests.post(
                "https://cloud.leonardo.ai/api/rest/v1/generations",
                json=payload, headers=headers, timeout=30
            )
            data = r.json()
            gen_id = data.get("sdGenerationJob", {}).get("generationId")
            if not gen_id:
                logging.warning(f"Leonardo: нет generationId: {data}")
                return None
            # Polling каждые 3 сек, максимум 60 сек
            for _ in range(20):
                time.sleep(3)
                r2 = requests.get(
                    f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                    headers=headers, timeout=15
                )
                gd = r2.json().get("generations_by_pk", {})
                status = gd.get("status", "")
                if status == "COMPLETE":
                    imgs = gd.get("generated_images", [])
                    if imgs:
                        return requests.get(imgs[0]["url"], timeout=30).content
                    return None
                if status == "FAILED":
                    logging.warning("Leonardo: генерация не удалась (FAILED)")
                    return None
            logging.warning("Leonardo: timeout ожидания (60 сек)")
            return None
        except Exception as e:
            logging.warning(f"Leonardo: исключение: {e}")
            return None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync)


def md_to_html(text):
    """Конвертирует **жирный** Markdown → <b>жирный</b> HTML и убирает лишние звёздочки."""
    # **жирный** → <b>жирный</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    # Одиночные * убираем
    text = text.replace('*', '')
    # Гарантируем пустую строку между абзацами: одиночный \n между текстом → \n\n
    text = re.sub(r'(?<!\n)\n(?!\n)', '\n\n', text)
    # Убираем тройные+ переносы — не больше двух подряд
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _strip_tags(html: str) -> str:
    """Убирает HTML-теги для подсчёта видимой длины текста."""
    return re.sub(r'<[^>]+>', '', html)


def sanitize_html(text):
    """Исправляет HTML после обрезки: закрывает незакрытые <b> и <a> теги.
    Telegram выдаёт ошибку если <b> или <a> не закрыт."""
    # Убираем незакрытый начатый тег в самом конце (например обрезали на '<b' или '<a href=')
    text = re.sub(r'<[^>]*$', '', text)
    # Закрываем незакрытые <b>
    b_open = len(re.findall(r'<b>', text, re.IGNORECASE))
    b_close = len(re.findall(r'</b>', text, re.IGNORECASE))
    if b_open > b_close:
        text += '</b>' * (b_open - b_close)
    # Закрываем незакрытые <a>
    a_open = len(re.findall(r'<a\b[^>]*>', text, re.IGNORECASE))
    a_close = len(re.findall(r'</a>', text, re.IGNORECASE))
    if a_open > a_close:
        text += '</a>' * (a_open - a_close)
    return text


# Русские гласные окончания, которые могут меняться при склонении
_CYR_VOWELS = frozenset('аяоеёиыуюАЯОЕЁИЫУЮ')


def link_products_in_text(text):
    """Оборачивает названия продуктов в HTML ссылки.
    Для однословных русских имён на гласную обрезает окончание и матчит по основе,
    что позволяет ловить падежные формы: Дарун-а/у/е/ой, Хлорелл-а/ы/е и т.д."""
    from products import PRODUCTS, PRODUCT_ALIASES
    # Длинные имена — в приоритете
    all_items = sorted(
        list(PRODUCTS.items()) + list(PRODUCT_ALIASES.items()),
        key=lambda x: -len(x[0])
    )
    for name, url in all_items:
        # Для однословных кириллических имён на гласную — матчим по основе
        is_single = ' ' not in name
        ends_cyr_vowel = is_single and len(name) >= 4 and name[-1] in _CYR_VOWELS
        if ends_cyr_vowel:
            stem = name[:-1]            # \w{0,3} покрывает падежные окончания: у/е/ы (1), ой/ей/ем (2), ами/ях (3)
            pat_str = r'\b' + re.escape(stem) + r'\w{0,3}\b'
            check = stem.lower()
        else:
            pat_str = r'\b' + re.escape(name) + r'\b'
            check = name.lower()

        if check not in text.lower():
            continue
        pattern = re.compile(pat_str, re.IGNORECASE | re.UNICODE)
        if not pattern.search(text):
            continue

        # Только текст вне существующих <a>...</a> тегов
        parts = re.split(r'(<a\b[^>]*>.*?</a>)', text, flags=re.IGNORECASE | re.DOTALL)
        new_parts = []
        for part in parts:
            if re.match(r'<a\b', part, re.IGNORECASE):
                new_parts.append(part)
            else:
                new_parts.append(pattern.sub(lambda m: f'<a href="{url}">{m.group(0)}</a>', part))
        text = ''.join(new_parts)
    return text


def get_cta_block(post_type, product_url=None):
    """Возвращает ОДИН призыв к действию, релевантный типу поста."""
    blocks = {
        "expert":    f"\n\n📋 <a href='{TEST_LINK}'>Моё здоровье</a> — пройди бесплатный тест",
        "review":    f"\n\n🌐 <a href='{SHOP_LINK}'>Сайт компании</a> — каталог продуктов <a href='{SHOP_LINK}'>Perfect Organic</a>",
        "viral":     f"\n\n📋 <a href='{TEST_LINK}'>Моё здоровье</a> — узнай, каких минералов тебе не хватает",
        "sales":     f"\n\n🛒 <a href='{product_url or SHOP_LINK}'>Заказать сейчас</a>",
        "lifestyle": f"\n\n🤝 <a href='{PARTNER_LINK}'>Стать партнёром</a> — зарегистрируйся в <a href='{PARTNER_LINK}'>Perfect Organic</a>",
        "partner":   f"\n\n🤝 <a href='{PARTNER_LINK}'>Стать партнёром</a> — присоединяйся к команде <a href='{PARTNER_LINK}'>Perfect Organic</a>",
        "faq":       f"\n\n📋 <a href='{TEST_LINK}'>Моё здоровье</a> — пройди тест и узнай свой результат",
    }
    return blocks.get(post_type, f"\n\n🌐 <a href='{SHOP_LINK}'>Сайт компании</a>")


def get_today_post_type():
    """Возвращает тип поста для сегодняшнего дня недели."""
    tz = pytz.timezone('Asia/Krasnoyarsk')
    weekday = datetime.now(tz).weekday()  # 0=Пн, 6=Вс
    return WEEKLY_PLAN[weekday]


async def generate_sales_image_prompt(product_name: str, desc: str) -> str:
    """Генерирует через Groq контекстный промпт для AI-фото: семья в сцене по теме продукта."""
    try:
        resp = await groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": (
                    f"Write a short English image generation prompt (2-3 sentences) for a lifestyle photo "
                    f"for a Telegram health supplement post about '{product_name}'.\n"
                    f"Product info: {desc[:400]}\n\n"
                    f"Rules:\n"
                    f"- Show a happy Russian family (couple or family aged 40-55) in a scene matching the health benefit.\n"
                    f"- Scene examples: digestion/gut → family eating together at a cozy dining table; "
                    f"joints/bones → couple walking happily in a summer park or forest; "
                    f"energy/fatigue → active family outdoors in golden sunlight; "
                    f"sleep → cozy evening at home; immunity/vitamins → family in nature.\n"
                    f"- One person is naturally HOLDING a clean white supplement bottle with a green label in their hands (not on a table). People are the main focus.\n"
                    f"- Beautiful warm lifestyle photography, cinematic quality, photorealistic, no text on image.\n"
                    f"Output ONLY the image prompt text, nothing else."
                )
            }],
            max_tokens=120,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logging.warning(f"generate_sales_image_prompt: {e}")
        return None


async def generate_text_post(post_type):
    """Генерирует текст поста через Gemini."""
    CTA_NOTE = "ВАЖНО: для жирного текста используй ТОЛЬКО HTML-тег <b>слово</b>. ЗАПРЕЩЕНО использовать **звёздочки** для выделения — только <b>тег</b>. Без ссылок и призывов в конце — они будут добавлены отдельно. Никаких других HTML-тегов кроме <b>. Обязательно используй эмодзи 🌿✅💚🎯❤️⚡ в начале абзацев и рядом с ключевыми фактами."

    generate_text_post._last_image_prompt = None  # сбрасываем для каждого поста
    generate_text_post._last_is_mineral_viral = False
    _post_topic = ""

    if post_type == "expert":
        topic = get_fresh_topic("expert", EXPERT_TOPICS)
        _post_topic = topic
        prompt = (
            f"Напиши экспертный пост для Telegram канала Perfect Organic от лица врача-нутрициолога.\n"
            f"Тема: «{topic}»\n"
            f"Пиши от первого лица: 'Я как нутрициолог...', 'Мои пациенты часто спрашивают...'\n"
            f"Стиль: авторитетный, но дружелюбный, с эмодзи. Без сложных терминов.\n"
            f"Структура: первая строка — придуманный тобой цепляющий заголовок по теме в тегах <b>...</b>, затем 3-4 абзаца пользы, личный вывод врача.\n"
            f"Выдели жирным: заголовок и 2-3 ключевых факта в тексте.\n"
            f"200-250 слов. {CTA_NOTE}"
        )
    elif post_type == "viral":
        topic = get_fresh_topic("viral", VIRAL_TOPICS)
        is_mineral_viral = any(kw in topic.lower() for kw in VIRAL_MINERAL_KEYWORDS)
        generate_text_post._last_is_mineral_viral = is_mineral_viral
        # 2 отдельных фото: уставший человек → счастливый человек с витаминами
        _variant = random.choice(_VIRAL_PERSON_VARIANTS)
        generate_text_post._last_image_prompt = build_viral_photo1_prompt(topic, _variant)
        generate_text_post._last_image_prompt2 = build_viral_photo2_prompt(topic, _variant)
        prompt = (
            f"Напиши вирусный пост для Telegram канала Perfect Organic.\n"
            f"Тема: «{topic}»\n"
            f"Структура (строго по порядку):\n"
            f"1. Крючок в <b>...</b>: симптомы нехватки витаминов/минералов — усталость, "
            f"плохое настроение, проблемы с зубами, частые болезни (1-2 предложения)\n"
            f"2. К чему приводит дефицит — конкретные последствия для здоровья и жизни (2-3 предложения с фактами)\n"
            f"3. Как приём витаминов и минералов возвращает энергию, настроение и здоровье (2-3 предложения)\n"
            f"4. В каких продуктах питания содержится этот витамин/минерал — назови 3-4 конкретных продукта "
            f"с пояснением пользы (список с эмодзи ✅)\n"
            f"5. Мотивирующий вывод в <b>...</b> — призыв заботиться о себе, без вопросов к аудитории\n"
            f"Стиль: живой, эмпатичный, полезный. Давай читателям реальную ценность! С эмодзи.\n"
            f"Не упоминай конкретные бренды или продукты. Говори о витаминах и минералах в еде.\n"
            f"200-230 слов. {CTA_NOTE}"
        )
        _viral_overrides = load_prompt_overrides()
        if _viral_overrides.get("viral_img1"):
            generate_text_post._last_image_prompt = _viral_overrides["viral_img1"].replace("{topic}", topic)
        if _viral_overrides.get("viral_img2"):
            generate_text_post._last_image_prompt2 = _viral_overrides["viral_img2"].replace("{topic}", topic)
        if _viral_overrides.get("viral_text"):
            prompt = _viral_overrides["viral_text"].replace("{topic}", topic)
        _post_topic = topic
    elif post_type == "lifestyle":
        topic = get_fresh_topic("lifestyle", LIFESTYLE_TOPICS)
        _post_topic = topic
        # Если тема о производстве — берём лабораторный промпт, иначе случайный из жизни
        is_production = topic in _LIFESTYLE_PRODUCTION_TOPICS
        if is_production:
            generate_text_post._last_image_prompt = LIFESTYLE_PHOTO_PROMPTS[-1]  # лабораторный (последний)
        else:
            generate_text_post._last_image_prompt = random.choice(LIFESTYLE_PHOTO_PROMPTS[:-1])
        if is_production:
            prompt = (
                f"Напиши познавательный пост для Telegram канала Perfect Organic.\n"
                f"Тема: «{topic}»\n"
                f"Расскажи про: строгий контроль качества, натуральное сырьё, научный подход, современное производство.\n"
                f"Стиль: вызывающий доверие, с гордостью за продукт, познавательный. С эмодзи.\n"
                f"Первая строка — цепляющий заголовок в тегах <b>...</b>.\n"
                f"180-220 слов. {CTA_NOTE}"
            )
        else:
            prompt = (
                f"Напиши тёплый пост о компании Perfect Organic для Telegram канала.\n"
                f"Тема: «{topic}»\n"
                f"Структура (строго по порядку, каждый пункт — новый абзац):\n"
                f"1. Цепляющий заголовок по теме в тегах <b>...</b>\n"
                f"2. Узнаваемая ситуация или вопрос, близкий читателю (2-3 предложения)\n"
                f"3. Как Perfect Organic подходит к этой теме — ценности, принципы, натуральность (2-3 предложения)\n"
                f"4. Конкретная польза или мини-история клиента (2-3 предложения)\n"
                f"5. Тёплый вывод-мотивация (1-2 предложения)\n"
                f"Стиль: душевный, как от друга, с логичным переходом между абзацами — каждая часть плавно вытекает из предыдущей. С эмодзи.\n"
                f"ВАЖНО: НЕ давай список советов — пиши связный текст с единой мыслью от начала до конца.\n"
                f"180-220 слов. {CTA_NOTE}"
            )
    elif post_type == "sales":
        from products import PRODUCTS
        if PRODUCTS:
            product_items = list(PRODUCTS.items())
            product_name, product_url = get_fresh_topic("sales", product_items)
        else:
            product_name, product_url = "МультиМинералс74", SHOP_LINK
        product_info = scrape_product_page(product_url)
        desc = product_info.get('description', '')[:1000]
        composition = product_info.get('composition', '')[:500]
        # Убираем числовой суффикс из отображаемого названия
        # "Урологический сбор 1" → "Урологический сбор"
        display_name = re.sub(r'\s+\d+$', '', product_name)
        _post_topic = display_name
        generate_text_post._last_product_name = display_name
        generate_text_post._last_product_url = product_url
        # Сохраняем og:image — используем как основу для gpt-image-1 edit
        generate_text_post._last_product_image_url = product_info.get('image_url')
        # Генерируем контекстный промпт: семья в сцене по теме продукта
        sales_img_prompt = await generate_sales_image_prompt(display_name, desc)
        generate_text_post._last_image_prompt = sales_img_prompt or (
            f"Warm lifestyle photography: a happy Russian family couple aged 40-55, "
            f"one of them holding a clean white supplement bottle with green label in their hands, "
            f"smiling naturally. Beautiful warm light, photorealistic, no text on image."
        )
        comp_block = f"\nСостав продукта:\n{composition}\n" if composition else ""
        prompt = (
            f"Напиши продающий пост для Telegram канала Perfect Organic о продукте «{display_name}».\n"
            + (f"Информация о продукте с сайта:\n{desc}\n{comp_block}\n" if desc else "")
            + f"ВАЖНО: пиши ТОЛЬКО о конкретном продукте «{display_name}» на основе описания выше — не пиши обобщённо о 'минералах' или 'витаминах' в целом.\n"
            f"Упомяни 2-3 ключевых компонента из состава и кратко объясни их пользу.\n"
            f"Структура: первая строка — цепляющий заголовок с названием «{display_name}» в тегах <b>...</b>, затем боль/проблема → как этот продукт решает → 3-4 конкретные выгоды ✅ → итог.\n"
            f"Стиль: эмоциональный, фокус на конкретном результате от этого продукта. С эмодзи.\n"
            f"Выдели жирным: заголовок и название продукта в тексте.\n"
            f"200-250 слов. {CTA_NOTE}"
        )
    elif post_type == "partner":
        topic = get_fresh_topic("partner", PARTNER_TOPICS)
        _post_topic = topic
        generate_text_post._last_image_prompt = random.choice(PARTNER_PHOTO_PROMPTS)
        prompt = (
            f"Напиши пост о партнёрской программе Perfect Organic для Telegram канала.\n"
            f"Тема: «{topic}»\n"
            f"Расскажи: как стать партнёром, какие возможности для заработка, реальные перспективы.\n"
            f"Стиль: вдохновляющий, честный, без агрессивного MLM-тона. С эмодзи.\n"
            f"Первая строка — придуманный тобой вдохновляющий заголовок по теме в тегах <b>...</b>. Выдели жирным ключевые выгоды.\n"
            f"ВАЖНО: пиши ТОЛЬКО на русском языке — никаких английских слов в тексте!\n"
            f"200-250 слов. {CTA_NOTE}"
        )
    elif post_type == "program":
        prog = get_fresh_topic("health_program_url", HEALTH_PROGRAM_URLS)
        prog_title = prog["title"]
        prog_url = prog["url"]
        _post_topic = prog_title
        scraped = scrape_program_page(prog_url)
        prog_text = scraped['description']
        generate_text_post._last_image_prompt = None
        generate_text_post._last_product_image_url = scraped['image_url']
        prompt = (
            f"Напиши пост для Telegram канала Perfect Organic о программе здоровья «{prog_title}».\n\n"
            f"Информация с сайта о программе:\n{prog_text}\n\n"
            f"Структура поста:\n"
            f"1. Заголовок с эмодзи, название программы, обёрнутый в <b>...</b>\n"
            f"2. Описание проблемы — почему она возникает, кому актуальна (2-3 предложения)\n"
            f"3. Что включает программа — кратко перечисли ключевые компоненты/продукты из текста выше в виде списка:\n"
            f"✅ <b>Название</b> — одно предложение о пользе.\n"
            f"4. Призыв: узнать подробнее на сайте perfect-org.ru\n\n"
            f"Стиль: экспертный, заботливый, с эмодзи. Выдели жирным заголовок и названия продуктов.\n"
            f"200-240 слов. {CTA_NOTE}"
        )
    elif post_type == "faq":
        program = get_fresh_topic("health_program", HEALTH_PROGRAMS)
        condition = program["condition"]
        _post_topic = condition
        symptoms = program["symptoms"]
        details = program["details"]
        products_list = ", ".join(program["products"])
        generate_text_post._last_image_prompt = program["image_prompt"]
        generate_text_post._last_product_image_url = None  # будем генерировать AI-картинку
        prompt = (
            f"Напиши пост-рекомендацию для Telegram канала Perfect Organic на тему «{condition}».\n"
            f"Симптомы: {symptoms}.\n"
            f"Контекст: {details}\n"
            f"Рекомендуемые продукты Perfect Organic: {products_list}.\n\n"
            f"Структура поста:\n"
            f"1. Придуманный тобой заголовок — название проблемы с эмодзи, обёрнутый в <b>...</b>\n"
            f"2. Узнаешь себя? — перечисли симптомы живо и эмпатично (2-3 предложения)\n"
            f"3. Почему так происходит — краткое объяснение причины (2-3 предложения)\n"
            f"4. Что рекомендует Perfect Organic — строго в формате списка, каждый продукт с новой строки:\n"
            f"✅ <b>Название продукта</b> — одно предложение о пользе для этой проблемы.\n"
            f"ВАЖНО: знак ✅ у каждого продукта строго в начале строки, без отступов. Все ✅ выровнены по левому краю.\n"
            f"5. Мотивирующий вывод (1-2 предложения)\n\n"
            f"Стиль: экспертный, заботливый, без медицинских страшилок. С эмодзи. "
            f"Выдели жирным: заголовок и названия продуктов в пункте 4.\n"
            f"220-260 слов. {CTA_NOTE}"
        )
    else:
        return None

    # Применяем текстовые оверрайды для не-вирусных постов (для вирусных — уже выше)
    if post_type != "viral" and _post_topic:
        _text_overrides = load_prompt_overrides()
        _override_key = f"{post_type}_text"
        if _text_overrides.get(_override_key):
            prompt = _text_overrides[_override_key].replace("{topic}", _post_topic)
    # Сохраняем промпт для показа владельцу через кнопку «Промпты»
    generate_text_post._last_text_prompt = prompt

    try:
        response = await groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты копирайтер Telegram-канала Perfect Organic. "
                        "СТРОГО пиши ТОЛЬКО на русском языке — НУЛЕВАЯ толерантность к английским словам в тексте. "
                        "Это включает: supplement→добавка, energy→энергия, natural→натуральный, "
                        "balance→баланс, health→здоровье, boost→усиление, wellness→самочувствие, "
                        "detox→детокс, extract→экстракт, formula→формула, complex→комплекс. "
                        "Используй ТОЛЬКО кириллицу — никаких латинских букв в теле поста. "
                        "Официальные названия продуктов Perfect Organic (GoodBak, Alfa XT и др.) "
                        "используй только в именительном падеже как имя собственное, без пояснений на латинице. "
                        "Никаких HTML-тегов кроме <b>. Отвечай готовым текстом без вводных фраз. "
                        "КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО использовать китайские, японские или корейские иероглифы. "
                        "ВАЖНО: между каждым абзацем обязательно оставляй ПУСТУЮ строку (двойной перенос строки)."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        raw = response.choices[0].message.content.strip()
        # Убираем китайские/японские/корейские иероглифы если AI случайно их вставил
        raw = re.sub(r'[\u3000-\u9fff\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\uf900-\ufaff]+', '', raw)
        # Заменяем частые английские слова на русские (вне HTML-тегов)
        _EN_MAP = [
            (r'\bsupplement[s]?\b', 'добавк'), (r'\bnatural\b', 'натуральный'),
            (r'\benergy\b', 'энергия'), (r'\bhealth\b', 'здоровье'),
            (r'\bwellness\b', 'самочувствие'), (r'\bbalance\b', 'баланс'),
            (r'\bboost\b', 'усиление'), (r'\bdetox\b', 'детокс'),
            (r'\bextract\b', 'экстракт'), (r'\bformula\b', 'формула'),
            (r'\bcomplex\b', 'комплекс'), (r'\beffect[s]?\b', 'эффект'),
            (r'\bresult[s]?\b', 'результат'), (r'\bbenefit[s]?\b', 'польза'),
        ]
        parts = re.split(r'(<[^>]+>)', raw)
        cleaned = []
        for part in parts:
            if part.startswith('<'):
                cleaned.append(part)
            else:
                for pat, repl in _EN_MAP:
                    part = re.sub(pat, repl, part, flags=re.IGNORECASE)
                cleaned.append(part)
        raw = ''.join(cleaned)
        # Убираем буквальное "Жирный заголовок" если AI вывел его как текст-заглушку
        raw = re.sub(r'<b>\s*[Жж]ирный\s+заголовок\s*</b>\s*\n?', '', raw).strip()
        raw = re.sub(r'\*\*\s*[Жж]ирный\s+заголовок\s*\*\*\s*\n?', '', raw).strip()
        # Groq возвращает Markdown **жирный** — конвертируем в HTML <b>жирный</b>
        return md_to_html(raw)
    except Exception as e:
        logging.error(f"Groq ошибка: {e}")
        generate_text_post._last_error = str(e)[:200]
        return None


def make_keyboard():
    """Клавиатура для превью (владельцу)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Опубликовать", callback_data="approve"),
            InlineKeyboardButton("💾 Сохранить", callback_data="save_post"),
        ],
        [
            InlineKeyboardButton("🔄 Другой пост", callback_data="next_post"),
            InlineKeyboardButton("📋 Сохранённые", callback_data="show_saved"),
        ],
        [
            InlineKeyboardButton("📝 Промпты", callback_data="show_prompts"),
        ],
    ])


def make_channel_keyboard():
    """Кнопка под постом в канале — ссылка на личку владельца."""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💬 Задать вопрос", url=OWNER_TG_LINK),
    ]])


def make_week_keyboard(weekday):
    """Клавиатура для режима /week — сохранить или перегенерировать."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"✅ Сохранить ({DAY_SHORT[weekday]})", callback_data="week_save"),
            InlineKeyboardButton("🔄 Другой вариант", callback_data="next_post"),
        ],
        [
            InlineKeyboardButton("💬 Задать вопрос (превью кнопки)", url=OWNER_TG_LINK),
        ],
    ])


async def _safe_edit(query, text, reply_markup=None):
    """Редактирует caption или text сообщения (работает для обоих типов)."""
    try:
        await query.edit_message_caption(caption=text, reply_markup=reply_markup)
    except Exception:
        try:
            await query.edit_message_text(text=text, reply_markup=reply_markup)
        except Exception:
            pass


# ─── Хэндлеры ───────────────────────────────────────────────────────────────

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Твой chat_id: {chat_id}\n\n"
        f"Добавь в config.py:\nOWNER_CHAT_ID = {chat_id}"
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    owner_id = query.message.chat_id

    # week_next не требует pending — просто запускаем следующий день
    if query.data.startswith("week_next_"):
        next_weekday = int(query.data.split("_")[-1])
        await _safe_edit(query, f"🔄 Генерирую {DAY_NAMES[next_weekday]}...")
        await _generate_preview(
            context.bot, owner_id,
            force_type=WEEKLY_PLAN[next_weekday],
            mode="week", weekday=next_weekday,
        )
        return

    # show_saved не требует pending — показываем список сохранённых постов
    if query.data == "show_saved":
        saved = load_saved_posts()
        if not saved:
            await query.message.reply_text("📭 Нет сохранённых постов.\n\nИспользуй /preview и нажми 💾 Сохранить.")
            return
        lines = []
        for day_str in sorted(saved.keys(), key=int):
            weekday = int(day_str)
            post_type = saved[day_str].get("post_type", "")
            type_label = POST_TYPE_LABELS.get(post_type, post_type)
            lines.append(f"• {DAY_NAMES[weekday]} — {type_label}")
        out = "📋 <b>Сохранённые посты:</b>\n\n" + "\n".join(lines) + "\n\nОтправь /saved чтобы посмотреть полностью."
        await query.message.reply_text(out, parse_mode='HTML')
        return

    # del_saved_X не требует pending — удаляем из saved_posts.json
    if query.data.startswith("del_saved_"):
        weekday = int(query.data.split("_")[-1])
        delete_saved_post(weekday)
        day_name = DAY_NAMES.get(weekday, str(weekday))
        await _safe_edit(query, f"🗑 Пост для <b>{day_name}</b> удалён.", reply_markup=None)
        return

    # pub_saved_X — публикуем сохранённый пост немедленно
    if query.data.startswith("pub_saved_"):
        weekday = int(query.data.split("_")[-1])
        day_name = DAY_NAMES.get(weekday, str(weekday))
        await _safe_edit(query, f"📤 Публикую пост для <b>{day_name}</b>...")
        try:
            published = await _publish_saved_post(context.bot, weekday)
            if published:
                await query.message.reply_text(f"✅ Пост <b>{day_name}</b> опубликован в канал!", parse_mode='HTML')
            else:
                await query.message.reply_text(f"⚠️ Пост для <b>{day_name}</b> не найден.", parse_mode='HTML')
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка публикации: {e}")
        return

    if query.data.startswith("edit_prompt_"):
        prompt_key = query.data[len("edit_prompt_"):]
        editing_state[owner_id] = prompt_key
        _PROMPT_LABELS = {
            "viral_text": "текстовый промпт вирусного поста",
            "viral_img1": "промпт фото 1 (уставший человек)",
            "viral_img2": "промпт фото 2 (счастливый + еда)",
            "expert_text": "текстовый промпт экспертного поста",
            "lifestyle_text": "текстовый промпт лайфстайл поста",
            "partner_text": "текстовый промпт партнёрского поста",
            "faq_text": "текстовый промпт FAQ поста",
            "sales_text": "текстовый промпт продающего поста",
        }
        label = _PROMPT_LABELS.get(prompt_key, prompt_key)
        _has_override = prompt_key in load_prompt_overrides()
        note = ("\n\n<i>Сейчас активен твой кастомный промпт. "
                "Отправь <b>сброс</b> чтобы вернуть умолчание.</i>") if _has_override else ""
        await query.message.reply_text(
            f"✏️ <b>Редактирование: {label}</b>\n\n"
            f"Отправь новый текст промпта следующим сообщением.\n"
            f"Используй <code>{{topic}}</code> для подстановки темы поста.{note}\n\n"
            f"<i>/cancel — отменить</i>",
            parse_mode='HTML'
        )
        return

    data = pending.get(owner_id)

    if not data:
        await _safe_edit(query, "⚠️ Данные поста устарели. Напиши /preview снова.")
        return

    if query.data == "show_prompts":
        post_type = data.get("post_type", "")
        _overrides_now = load_prompt_overrides()
        _sent_any = False
        tp = data.get("text_prompt")
        if tp:
            key = f"{post_type}_text"
            mark = " ✏️ <i>(изменён)</i>" if key in _overrides_now else ""
            kb_e = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_prompt_{key}")]])
            await query.message.reply_text(
                f"📝 <b>Текстовый промпт (Groq):{mark}</b>\n<code>{html_module.escape(tp[:3000])}</code>",
                parse_mode='HTML', reply_markup=kb_e
            )
            _sent_any = True
        ip1 = data.get("img_prompt1")
        if ip1:
            key = f"{post_type}_img1"
            mark = " ✏️ <i>(изменён)</i>" if key in _overrides_now else ""
            kb_e = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_prompt_{key}")]])
            label = "🎨 <b>Фото-промпт 1 (уставший):" if data.get("img_prompt2") else "🎨 <b>Фото-промпт:"
            await query.message.reply_text(
                f"{label}{mark}</b>\n<code>{html_module.escape(ip1[:3000])}</code>",
                parse_mode='HTML', reply_markup=kb_e
            )
            _sent_any = True
        ip2 = data.get("img_prompt2")
        if ip2:
            key = f"{post_type}_img2"
            mark = " ✏️ <i>(изменён)</i>" if key in _overrides_now else ""
            kb_e = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Изменить", callback_data=f"edit_prompt_{key}")]])
            await query.message.reply_text(
                f"🎨 <b>Фото-промпт 2 (счастливый + еда):{mark}</b>\n<code>{html_module.escape(ip2[:3000])}</code>",
                parse_mode='HTML', reply_markup=kb_e
            )
            _sent_any = True
        if not _sent_any:
            await query.message.reply_text("ℹ️ Промпты не сохранились — перегенерируй пост.")
        return

    if query.data == "approve":
        try:
            ch_kb = make_channel_keyboard()
            if data.get("video"):
                await context.bot.send_video(chat_id=TARGET_CHANNEL, video=BytesIO(data["video"]))
                await context.bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
            elif data.get("photo") and data.get("photo2"):
                await context.bot.send_media_group(chat_id=TARGET_CHANNEL, media=[
                    InputMediaPhoto(media=BytesIO(data["photo"])),
                    InputMediaPhoto(media=BytesIO(data["photo2"])),
                ])
                await context.bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
            elif data.get("photo"):
                await context.bot.send_photo(chat_id=TARGET_CHANNEL, photo=BytesIO(data["photo"]))
                await context.bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
            else:
                await context.bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
            save_posted_id(data["post_id"])
            pending.pop(owner_id, None)
            await _safe_edit(query, "✅ Пост опубликован в канал!")
        except Exception as e:
            await _safe_edit(query, f"❌ Ошибка публикации: {e}")

    elif query.data == "week_save":
        weekday = data.get("weekday")
        save_post_for_day(weekday, data)
        # Для отзывов фиксируем post_id чтобы не повторялся
        if data.get("post_type") == "review" and data.get("post_id"):
            save_posted_id(data["post_id"])
        pending.pop(owner_id, None)
        next_weekday = weekday + 1
        if next_weekday > 6:
            await _safe_edit(query, "🎉 Вся неделя заполнена!\nПосты выйдут каждый день в 12:02 по Красноярску.")
        else:
            next_type = WEEKLY_PLAN[next_weekday]
            next_label = POST_TYPE_LABELS.get(next_type, next_type)
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"📅 Генерировать {DAY_NAMES[next_weekday]} — {next_label}",
                    callback_data=f"week_next_{next_weekday}"
                )
            ]])
            await _safe_edit(
                query,
                f"✅ {DAY_NAMES[weekday]} сохранён и уйдёт в канал автоматически.\n\n"
                f"Когда будешь готов — нажми кнопку для следующего дня 👇",
                reply_markup=kb
            )

    elif query.data == "save_post":
        post_type = data.get("post_type")
        # Определяем день недели по типу поста
        weekday = next((d for d, t in WEEKLY_PLAN.items() if t == post_type), None)
        if weekday is None:
            await _safe_edit(query, "❌ Не могу определить день для сохранения.")
            return
        save_post_for_day(weekday, data)
        if data.get("post_type") == "review" and data.get("post_id"):
            save_posted_id(data["post_id"])
        pending.pop(owner_id, None)
        day_name = DAY_NAMES[weekday]
        type_label = POST_TYPE_LABELS.get(post_type, post_type)
        await _safe_edit(
            query,
            f"💾 Пост сохранён!\n\n"
            f"📅 {day_name} — {type_label}\n"
            f"Выйдет автоматически в {POST_HOUR:02d}:{POST_MINUTE:02d} по Красноярску.\n\n"
            f"Посмотреть все сохранённые: /saved"
        )

    elif query.data == "next_post":
        await _safe_edit(query, "🔄 Генерирую другой вариант...")
        await _generate_preview(
            context.bot, owner_id,
            skip_id=data.get("post_id"),
            force_type=data.get("post_type"),
            mode=data.get("mode", "live"),
            weekday=data.get("weekday"),
        )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cancel — отменить редактирование промпта."""
    owner_id = update.effective_chat.id
    if str(owner_id) != str(OWNER_CHAT_ID):
        return
    if owner_id in editing_state:
        editing_state.pop(owner_id)
        await update.message.reply_text("❌ Редактирование отменено.")
    else:
        await update.message.reply_text("ℹ️ Нечего отменять.")


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений — сохраняет кастомный промпт когда активно редактирование."""
    owner_id = update.effective_chat.id
    if str(owner_id) != str(OWNER_CHAT_ID):
        return
    if owner_id not in editing_state:
        return
    key = editing_state.pop(owner_id)
    new_text = update.message.text.strip()
    if new_text.lower() in ("сброс", "default", "reset"):
        delete_prompt_override(key)
        await update.message.reply_text(
            f"🔄 Промпт <code>{key}</code> сброшен к умолчанию.\n\n"
            f"Следующая генерация будет использовать стандартный промпт.",
            parse_mode='HTML'
        )
        return
    save_prompt_override(key, new_text)
    await update.message.reply_text(
        f"✅ <b>Промпт сохранён!</b>\n\n"
        f"Ключ: <code>{key}</code>\n"
        f"Будет применён при следующей генерации поста.\n\n"
        f"Чтобы сбросить к умолчанию — нажми ✏️ Изменить и отправь слово <b>сброс</b>.",
        parse_mode='HTML'
    )


async def _generate_preview(bot, owner_id, skip_id=None, force_type=None, mode="live", weekday=None):
    """Генерирует превью поста нужного типа и отправляет владельцу."""
    try:
        await _generate_preview_inner(bot, owner_id, skip_id, force_type, mode, weekday)
    except Exception as e:
        logging.error(f"_generate_preview упал: {e}", exc_info=True)
        try:
            await bot.send_message(chat_id=owner_id, text=f"❌ Ошибка генерации:\n{e}")
        except Exception:
            pass


async def _generate_preview_inner(bot, owner_id, skip_id=None, force_type=None, mode="live", weekday=None):
    """Внутренняя логика генерации (обёрнута в try/except выше)."""
    post_type = force_type or get_today_post_type()
    type_label = POST_TYPE_LABELS.get(post_type, post_type)
    logging.info(f"Тип поста: {post_type} ({type_label})")

    photo_bytes = None
    photo2_bytes = None
    video_bytes = None
    post_id = None
    text = ""

    if post_type == "review":
        # Берём реальный отзыв из канала с фото/видео
        posted_ids = load_posted_ids()
        if skip_id:
            posted_ids.add(skip_id)

        posts = get_posts_with_media(REVIEW_CHANNEL)
        available = [p for p in posts if p['id'] not in posted_ids]

        if not available:
            await bot.send_message(chat_id=owner_id, text="ℹ️ Нет новых отзывов. Переключаюсь на экспертный пост...")
            post_type = "expert"
        else:
            post = random.choice(available)
            post_id = post['id']
            logging.info(f"Выбран отзыв: {post_id}")

            await bot.send_message(chat_id=owner_id, text=f"✍️ {type_label} — адаптирую текст...")
            text = await adapt_text(post['text'], post.get('links', [])) or ""

            if post.get('video_url'):
                try:
                    await bot.send_message(chat_id=owner_id, text="🎬 Скачиваю видео...")
                    video_bytes = download_media(post['video_url'])
                except Exception as e:
                    logging.warning(f"Видео не скачалось: {e}")

            if not video_bytes and post.get('photo_url'):
                try:
                    photo_bytes = download_media(post['photo_url'])
                except Exception as e:
                    logging.warning(f"Фото не скачалось: {e}")

            # Нет ни фото, ни видео — генерируем AI-иллюстрацию "Отзывы наших клиентов"
            if not video_bytes and not photo_bytes:
                review_img_prompt = (
                    "Warm lifestyle photography: happy smiling Russian women aged 30-50, "
                    "holding a smartphone with a positive review on screen, cozy bright home interior, "
                    "soft natural light, photorealistic, warm pastel colors. "
                    "Text overlay in elegant Cyrillic: 'Отзывы наших клиентов'. No other text."
                )
                await bot.send_message(chat_id=owner_id, text="🎨 В отзыве нет медиа — генерирую иллюстрацию...")
                try:
                    resp = await oai.images.generate(
                        model="gpt-image-1",
                        prompt=review_img_prompt,
                        size="1024x1024",
                        quality="high",
                        n=1
                    )
                    img_data = resp.data[0]
                    if hasattr(img_data, "url") and img_data.url:
                        photo_bytes = requests.get(img_data.url, timeout=30).content
                    else:
                        photo_bytes = base64.b64decode(img_data.b64_json)
                    logging.info("✅ Фото для отзыва: OpenAI")
                except Exception as e:
                    logging.warning(f"OpenAI (review fallback): {e}")

    if post_type != "review":
        # Генерируем текст через Gemini (с retry при превышении квоты)
        await bot.send_message(chat_id=owner_id, text=f"✍️ {type_label} — генерирую текст...")
        text = await generate_text_post(post_type) or ""
        for attempt in range(1, 4):
            if text:
                break
            await bot.send_message(
                chat_id=owner_id,
                text=f"⏳ Groq не ответил (попытка {attempt}/3), жду 10 сек..."
            )
            await asyncio.sleep(10)
            text = await generate_text_post(post_type) or ""
        post_id = f"ai_{post_type}_{random.randint(10000, 99999)}"

        # Определяем промпт для AI-генерации фото
        ai_img_prompt = None
        if post_type == "expert":
            ai_img_prompt = random.choice(DOCTOR_PHOTO_PROMPTS)
        elif post_type in ("faq", "sales", "viral", "lifestyle", "partner"):
            ai_img_prompt = getattr(generate_text_post, '_last_image_prompt', None)
            if not ai_img_prompt:
                product_name = getattr(generate_text_post, '_last_product_name', 'supplement')
                ai_img_prompt = (
                    f"Warm lifestyle photography: a happy healthy Russian woman in her 35-45, "
                    f"smiling naturally, holding a supplement bottle in a bright cozy kitchen. "
                    f"Photorealistic, warm colors, no text on image."
                )

        _img_size = "1024x1024"

        # Генерируем AI-фото
        if ai_img_prompt and not photo_bytes:
            # Для sales: пробуем gpt-image-1 EDIT с реальным фото продукта
            if post_type == "sales":
                product_img_bytes = None
                # 1. Сначала локальный PNG без фона (приоритет)
                prod_url = getattr(generate_text_post, '_last_product_url', None)
                if prod_url:
                    product_img_bytes = get_product_image_bytes(prod_url)
                # 2. Если нет — og:image с сайта
                if not product_img_bytes:
                    product_img_url = getattr(generate_text_post, '_last_product_image_url', None)
                    if product_img_url:
                        try:
                            product_img_bytes = download_media(product_img_url)
                        except Exception as e:
                            logging.warning(f"Фото продукта не скачалось: {e}")
                if product_img_bytes:
                    await bot.send_message(chat_id=owner_id, text="🎨 Генерирую фото с продуктом (OpenAI edit)...")
                    try:
                        pname = getattr(generate_text_post, '_last_product_name', 'продукт')
                        edit_prompt = (
                            f"Show a happy Russian couple aged 40-55 years old holding or looking at "
                            f"this Perfect Organic product '{pname}' with warm smiles. "
                            f"Keep the product clearly visible in their hands or nearby. "
                            f"Beautiful warm lifestyle setting, natural light, photorealistic. No text on image."
                        )
                        img_file = BytesIO(product_img_bytes)
                        img_file.name = "product.png"
                        resp = await oai.images.edit(
                            model="gpt-image-1",
                            image=img_file,
                            prompt=edit_prompt,
                            size="1024x1024",
                            n=1
                        )
                        img_data = resp.data[0]
                        if hasattr(img_data, "url") and img_data.url:
                            photo_bytes = requests.get(img_data.url, timeout=30).content
                        else:
                            photo_bytes = base64.b64decode(img_data.b64_json)
                        logging.info("✅ Фото: OpenAI edit (продукт)")
                    except Exception as e:
                        logging.warning(f"OpenAI edit: {e}")

            # Для lifestyle/partner — edit с случайным продуктом Perfect Organic
            # faq и вирусные посты НЕ используют edit — генерируются с нуля без продуктов
            if not photo_bytes and post_type in ("lifestyle", "partner"):
                rand_img = get_random_product_image_bytes()
                if rand_img:
                    await bot.send_message(chat_id=owner_id, text="🎨 Генерирую фото с продуктом (OpenAI edit)...")
                    try:
                        img_file = BytesIO(rand_img)
                        img_file.name = "product.png"
                        # Усиленная инструкция: использовать ИМЕННО упаковку из предоставленного изображения
                        edit_prompt = (
                            ai_img_prompt +
                            " CRITICAL REQUIREMENT: The supplement product visible in this scene MUST be "
                            "EXACTLY the product from the provided reference image — same packaging, same colors, "
                            "same label design. Do NOT replace it with a generic white bottle. "
                            "Keep the real product from the reference image and place it naturally into the scene."
                        )
                        resp = await oai.images.edit(
                            model="gpt-image-1",
                            image=img_file,
                            prompt=edit_prompt,
                            size="1024x1024",
                            n=1
                        )
                        img_data = resp.data[0]
                        if hasattr(img_data, "url") and img_data.url:
                            photo_bytes = requests.get(img_data.url, timeout=30).content
                        else:
                            photo_bytes = base64.b64decode(img_data.b64_json)
                        logging.info(f"✅ Фото: OpenAI edit ({post_type})")
                    except Exception as e:
                        logging.warning(f"OpenAI edit ({post_type}): {e}")

            # Попытка: OpenAI gpt-image-1 generate (если edit не сработал или не sales)
            if not photo_bytes:
                await bot.send_message(chat_id=owner_id, text="🎨 Генерирую фото (OpenAI)...")
                try:
                    resp = await oai.images.generate(
                        model="gpt-image-1",
                        prompt=ai_img_prompt,
                        size=_img_size,
                        quality="high",
                        n=1
                    )
                    img_data = resp.data[0]
                    if hasattr(img_data, "url") and img_data.url:
                        photo_bytes = requests.get(img_data.url, timeout=30).content
                    else:
                        photo_bytes = base64.b64decode(img_data.b64_json)
                    logging.info(f"✅ Фото: OpenAI")
                except Exception as e:
                    logging.warning(f"OpenAI [{post_type}]: {e}")

        # Для вирусных постов — генерируем второе фото (счастливый человек + витамины)
        photo2_bytes = None
        if post_type == "viral":
            img_prompt2 = getattr(generate_text_post, '_last_image_prompt2', None)
            if img_prompt2:
                await bot.send_message(chat_id=owner_id, text="🎨 Генерирую второе фото (OpenAI)...")
                try:
                    resp2 = await oai.images.generate(
                        model="gpt-image-1",
                        prompt=img_prompt2,
                        size="1024x1024",
                        quality="high",
                        n=1
                    )
                    img_data2 = resp2.data[0]
                    if hasattr(img_data2, "url") and img_data2.url:
                        photo2_bytes = requests.get(img_data2.url, timeout=30).content
                    else:
                        photo2_bytes = base64.b64decode(img_data2.b64_json)
                    logging.info("✅ Фото 2: OpenAI (вирусный)")
                except Exception as e:
                    logging.warning(f"OpenAI фото 2 [viral]: {e}")

    if not text:
        err = getattr(generate_text_post, '_last_error', 'неизвестная ошибка')
        await bot.send_message(chat_id=owner_id, text=f"❌ Не удалось сгенерировать пост.\nОшибка: {err}")
        return

    # Оборачиваем названия продуктов в ссылки + добавляем CTA блок
    # Telegram: caption к фото/видео ≤ 1024 символа, обычное сообщение ≤ 4096
    # ВАЖНО: link_products_in_text добавляет HTML-теги и увеличивает длину текста,
    # поэтому обрезаем ПОСЛЕ подстановки ссылок, по границе слова.
    _product_url = getattr(generate_text_post, '_last_product_url', None) if post_type == "sales" else None
    cta = get_cta_block(post_type, product_url=_product_url)
    # Вирусные посты — без ссылок на продукты (общий контент о витаминах/минералах)
    body = text if post_type == "viral" else link_products_in_text(text)
    # В партнёрских/лайфстайл постах "Perfect Organic" → ссылка на партнёрскую программу
    if post_type in ("partner", "lifestyle"):
        body = body.replace(
            f'<a href="https://perfect-org.ru/">Perfect Organic</a>',
            f'<a href="{PARTNER_LINK}">Perfect Organic</a>'
        )
    # Для вирусных постов о минералах — слово "минерал*" становится ссылкой на тест
    if post_type == "viral" and getattr(generate_text_post, '_last_is_mineral_viral', False):
        _mineral_count = [0]
        def _link_mineral(m):
            if _mineral_count[0] < 2:
                _mineral_count[0] += 1
                return f'<a href="{TEST_LINK}">{m.group(0)}</a>'
            return m.group(0)
        # Применяем только вне существующих <a>...</a> тегов
        _m_parts = re.split(r'(<a\b[^>]*>.*?</a>)', body, flags=re.IGNORECASE | re.DOTALL)
        body = ''.join(
            part if re.match(r'<a\b', part, re.IGNORECASE)
            else re.sub(r'минерал\w*', _link_mineral, part, flags=re.IGNORECASE)
            for part in _m_parts
        )
    # Telegram считает ВИДИМЫЕ символы (без HTML-тегов):
    # caption ≤ 1024, обычное сообщение ≤ 4096
    prefix_visible = len(type_label) + 2  # "Тип\n\n"
    cta_visible = len(_strip_tags(cta))
    # Фото/видео тоже отправляются без caption — текст идёт отдельным сообщением
    max_body_visible = 4090 - prefix_visible - cta_visible - 3

    body_visible = _strip_tags(body)
    if len(body_visible) > max_body_visible:
        # Пропорционально определяем, где резать в сыром HTML
        ratio = len(body) / max(len(body_visible), 1)
        trim_raw = int(max_body_visible * ratio * 0.95)  # 5% запас
        body = body[:trim_raw]
        last_space = body.rfind(' ')
        if last_space > trim_raw * 0.85:
            body = body[:last_space]
        body = body.rstrip('.,;:—- ') + "..."
    # Закрываем незакрытые HTML-теги после обрезки (иначе Telegram выдаёт ошибку)
    body = sanitize_html(body)
    text = body + cta

    pending[owner_id] = {
        "text": text,
        "photo": photo_bytes,
        "photo2": photo2_bytes,
        "video": video_bytes,
        "post_id": post_id,
        "post_type": post_type,
        "mode": mode,
        "weekday": weekday,
        # Промпты — для кнопки «📝 Промпты»
        "text_prompt": getattr(generate_text_post, '_last_text_prompt', None),
        "img_prompt1": getattr(generate_text_post, '_last_image_prompt', None),
        "img_prompt2": getattr(generate_text_post, '_last_image_prompt2', None),
    }

    if mode == "week" and weekday is not None:
        day_name = DAY_NAMES[weekday]
        msg_text = f"📅 {day_name} — {type_label}\n\n{text}"
        kb = make_week_keyboard(weekday)
    else:
        msg_text = f"{type_label}\n\n{text}"
        kb = make_keyboard()

    if video_bytes:
        await bot.send_video(chat_id=owner_id, video=BytesIO(video_bytes))
        await bot.send_message(chat_id=owner_id, text=msg_text, parse_mode='HTML',
                               reply_markup=kb, disable_web_page_preview=True)
    elif photo_bytes and photo2_bytes:
        await bot.send_media_group(chat_id=owner_id, media=[
            InputMediaPhoto(media=BytesIO(photo_bytes)),
            InputMediaPhoto(media=BytesIO(photo2_bytes)),
        ])
        await bot.send_message(chat_id=owner_id, text=msg_text, parse_mode='HTML',
                               reply_markup=kb, disable_web_page_preview=True)
    elif photo_bytes:
        await bot.send_photo(chat_id=owner_id, photo=BytesIO(photo_bytes))
        await bot.send_message(chat_id=owner_id, text=msg_text, parse_mode='HTML',
                               reply_markup=kb, disable_web_page_preview=True)
    else:
        await bot.send_message(chat_id=owner_id, text=msg_text, parse_mode='HTML',
                               reply_markup=kb, disable_web_page_preview=True)


async def preview_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /preview — вручную запустить генерацию превью (публикует сразу после одобрения)."""
    if str(update.effective_chat.id) != str(OWNER_CHAT_ID):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text("🔍 Генерирую пост...")
    await _generate_preview(context.bot, update.effective_chat.id)


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /saved — показывает все сохранённые посты на неделю."""
    if str(update.effective_chat.id) != str(OWNER_CHAT_ID):
        await update.message.reply_text("Нет доступа.")
        return
    saved = load_saved_posts()
    if not saved:
        await update.message.reply_text("📭 Нет сохранённых постов.\n\nИспользуй /preview или /vt и нажми 💾 Сохранить.")
        return
    for day_str in sorted(saved.keys(), key=int):
        weekday = int(day_str)
        data = saved[day_str]
        post_type = data.get("post_type", "")
        type_label = POST_TYPE_LABELS.get(post_type, post_type)
        day_name = DAY_NAMES.get(weekday, day_str)
        full_text = data.get("text", "")
        header = f"📅 <b>{day_name}</b> — {type_label}"
        # Кнопки: опубликовать или удалить
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"📤 Опубликовать", callback_data=f"pub_saved_{weekday}"),
            InlineKeyboardButton(f"🗑 Удалить {DAY_SHORT[weekday]}", callback_data=f"del_saved_{weekday}"),
        ]])
        if data.get("photo") and data.get("photo2"):
            await update.message.reply_media_group(media=[
                InputMediaPhoto(media=BytesIO(base64.b64decode(data["photo"]))),
                InputMediaPhoto(media=BytesIO(base64.b64decode(data["photo2"]))),
            ])
            await update.message.reply_text(f"{header}\n\n{full_text}", parse_mode='HTML', reply_markup=kb, disable_web_page_preview=True)
        elif data.get("photo"):
            await update.message.reply_photo(
                photo=BytesIO(base64.b64decode(data["photo"])),
                caption=header, parse_mode='HTML'
            )
            await update.message.reply_text(full_text, parse_mode='HTML', reply_markup=kb, disable_web_page_preview=True)
        elif data.get("video"):
            await update.message.reply_video(
                video=BytesIO(base64.b64decode(data["video"])),
                caption=header, parse_mode='HTML'
            )
            await update.message.reply_text(full_text, parse_mode='HTML', reply_markup=kb, disable_web_page_preview=True)
        else:
            await update.message.reply_text(
                f"{header}\n\n{full_text}", parse_mode='HTML', reply_markup=kb, disable_web_page_preview=True
            )


def make_day_handler(weekday: int):
    """Создаёт команду для конкретного дня недели."""
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != str(OWNER_CHAT_ID):
            await update.message.reply_text("Нет доступа.")
            return
        day_name = DAY_NAMES[weekday]
        post_type = WEEKLY_PLAN[weekday]
        type_label = POST_TYPE_LABELS.get(post_type, post_type)
        await update.message.reply_text(f"🔍 Генерирую пост — {day_name} ({type_label})...")
        await _generate_preview(context.bot, update.effective_chat.id, force_type=post_type)
    return handler


async def week_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /week — прогнать все 7 типов постов и сохранить заготовки на неделю."""
    if str(update.effective_chat.id) != str(OWNER_CHAT_ID):
        await update.message.reply_text("Нет доступа.")
        return
    await update.message.reply_text(
        "📅 Генерирую посты на всю неделю.\n"
        "Одобряй каждый — они сохранятся и выйдут автоматически в 12:02 в нужный день.\n\n"
        "Начинаем с Понедельника..."
    )
    await _generate_preview(
        context.bot, update.effective_chat.id,
        force_type=WEEKLY_PLAN[0], mode="week", weekday=0,
    )


# ─── Scheduled job ──────────────────────────────────────────────────────────

async def _publish_saved_post(bot, weekday: int) -> bool:
    """Публикует сохранённый пост для дня weekday. Возвращает True если опубликовано."""
    saved = load_saved_posts()
    if str(weekday) not in saved:
        return False
    data = saved[str(weekday)]
    ch_kb = make_channel_keyboard()
    if data.get("video"):
        await bot.send_video(chat_id=TARGET_CHANNEL, video=BytesIO(base64.b64decode(data["video"])))
        await bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
    elif data.get("photo") and data.get("photo2"):
        await bot.send_media_group(chat_id=TARGET_CHANNEL, media=[
            InputMediaPhoto(media=BytesIO(base64.b64decode(data["photo"]))),
            InputMediaPhoto(media=BytesIO(base64.b64decode(data["photo2"]))),
        ])
        await bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
    elif data.get("photo"):
        await bot.send_photo(chat_id=TARGET_CHANNEL, photo=BytesIO(base64.b64decode(data["photo"])))
        await bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
    else:
        await bot.send_message(chat_id=TARGET_CHANNEL, text=data["text"],
                               parse_mode='HTML', reply_markup=ch_kb, disable_web_page_preview=True)
    delete_saved_post(weekday)
    return True


async def scheduled_job(context: ContextTypes.DEFAULT_TYPE):
    if not OWNER_CHAT_ID:
        logging.error("OWNER_CHAT_ID не задан в config.py!")
        return

    tz = pytz.timezone('Asia/Krasnoyarsk')
    weekday = datetime.now(tz).weekday()
    saved = load_saved_posts()

    if str(weekday) in saved:
        logging.info(f"Публикую заготовку для дня {weekday} ({DAY_NAMES[weekday]})")
        try:
            await _publish_saved_post(context.bot, weekday)
            await context.bot.send_message(
                chat_id=OWNER_CHAT_ID,
                text=f"✅ Заготовка опубликована — {DAY_NAMES[weekday]}!",
            )
        except Exception as e:
            logging.error(f"Ошибка публикации заготовки: {e}")
            await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=f"❌ Ошибка публикации: {e}")
    else:
        # Заготовки нет — генерируем свежий пост и отправляем на превью
        logging.info("Заготовки нет, генерирую свежий пост...")
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text="⏰ Время публикации! Готовлю пост...")
        await _generate_preview(context.bot, OWNER_CHAT_ID)


async def startup_check(app):
    """При запуске бота: если пропустили время публикации — публикуем сохранённый пост."""
    if not OWNER_CHAT_ID:
        return
    tz = pytz.timezone('Asia/Krasnoyarsk')
    now = datetime.now(tz)
    weekday = now.weekday()

    sched_minutes = POST_HOUR * 60 + POST_MINUTE
    now_minutes = now.hour * 60 + now.minute

    # Публикуем только если бот запустился в течение 2 часов после расписания
    if sched_minutes <= now_minutes <= sched_minutes + 120:
        saved = load_saved_posts()
        if str(weekday) in saved:
            logging.info("Startup: обнаружена пропущенная публикация, публикую...")
            try:
                await app.bot.send_message(
                    chat_id=OWNER_CHAT_ID,
                    text="🔄 Бот перезапускался во время публикации — публикую сохранённый пост..."
                )
                published = await _publish_saved_post(app.bot, weekday)
                if published:
                    await app.bot.send_message(
                        chat_id=OWNER_CHAT_ID,
                        text=f"✅ Пост опубликован — {DAY_NAMES[weekday]}!"
                    )
            except Exception as e:
                logging.error(f"Startup: ошибка публикации: {e}")
                try:
                    await app.bot.send_message(chat_id=OWNER_CHAT_ID, text=f"❌ Ошибка публикации при старте: {e}")
                except Exception:
                    pass


# ─── Глобальный обработчик ошибок ───────────────────────────────────────────

async def global_error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    """Перехватывает все необработанные ошибки. TimedOut — нормально, просто логируем."""
    from telegram.error import TimedOut, NetworkError
    err = context.error
    if isinstance(err, (TimedOut, NetworkError)):
        logging.warning(f"Сетевая ошибка (бот продолжает работу): {err}")
        return
    logging.error(f"Необработанная ошибка: {err}", exc_info=err)
    # Сообщаем владельцу об ошибке
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Ошибка бота: {err}"
            )
    except Exception:
        pass


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    from telegram.request import HTTPXRequest
    # Увеличиваем timeout для загрузки больших фото
    req = HTTPXRequest(read_timeout=60, write_timeout=120, connect_timeout=30)
    app = Application.builder().token(BOT_TOKEN).request(req).post_init(startup_check).build()

    app.add_error_handler(global_error_handler)
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("preview", preview_command))
    app.add_handler(CommandHandler("week", week_command))
    app.add_handler(CommandHandler("saved", saved_command))
    # Команды по дням недели: /pn /vt /sr /cht /pt /sb /vs
    app.add_handler(CommandHandler("pn",  make_day_handler(0)))  # Понедельник — Экспертный
    app.add_handler(CommandHandler("vt",  make_day_handler(1)))  # Вторник    — Отзыв
    app.add_handler(CommandHandler("sr",  make_day_handler(2)))  # Среда      — Партнёрский
    app.add_handler(CommandHandler("cht", make_day_handler(3)))  # Четверг    — Продающий
    app.add_handler(CommandHandler("pt",  make_day_handler(4)))  # Пятница    — О компании
    app.add_handler(CommandHandler("sb",  make_day_handler(5)))  # Суббота    — Вирусный
    app.add_handler(CommandHandler("vs",  make_day_handler(6)))  # Воскресенье— Рекомендации
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    tz = pytz.timezone('Asia/Krasnoyarsk')
    app.job_queue.run_daily(
        scheduled_job,
        time=dtime(hour=POST_HOUR, minute=POST_MINUTE, tzinfo=tz)
    )

    print("=" * 50)
    print("Perfect Organic Bot запущен!")
    print(f"Канал источник: @{REVIEW_CHANNEL}")
    print(f"Публикация в: {TARGET_CHANNEL}")
    print(f"Превью каждый день в {POST_HOUR:02d}:{POST_MINUTE:02d}")
    print("=" * 50)

    app.run_polling()


if __name__ == '__main__':
    main()
