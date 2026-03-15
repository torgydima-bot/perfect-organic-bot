import sys
import os
import re
sys.path.insert(0, "/opt/bot/telegram_bot")

from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import subprocess
import json
import base64
import requests
import functools
from datetime import datetime
from bs4 import BeautifulSoup

app = Flask(__name__)
app.secret_key = "perfectorganic2026"

DASHBOARD_PASSWORD = "admin123"
BOT_DIR = "/opt/bot/telegram_bot"
SERVICE_NAME = "perfectorganic-bot"
UPLOADS_DIR = "/opt/dashboard/uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)
STATS_FILE = os.path.join(BOT_DIR, "post_stats.json")


def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def add_utm(text, campaign_date=None):
    """Добавляет UTM-метки ко всем ссылкам perfect-org.ru в HTML-тексте."""
    if not campaign_date:
        campaign_date = datetime.now().strftime("%Y-%m-%d")
    def replace_link(m):
        url = m.group(1)
        sep = "&" if "?" in url else "?"
        return f'href="{url}{sep}utm_source=telegram&utm_medium=bot&utm_campaign={campaign_date}"'
    return re.sub(r'href="(https://perfect-org\.ru[^"]*)"', replace_link, text)


def get_channel_views():
    """Скрапит t.me/s/perfektorganic и возвращает {message_id: views}."""
    try:
        r = requests.get("https://t.me/s/perfektorganic", timeout=10,
                         headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        result = {}
        for msg in soup.find_all("div", attrs={"data-post": True}):
            data_post = msg.get("data-post", "")
            if "/" in data_post:
                try:
                    msg_id = int(data_post.split("/")[-1])
                    views_el = msg.find("span", class_="tgme_widget_message_views")
                    if views_el:
                        result[msg_id] = views_el.text.strip()
                except (ValueError, AttributeError):
                    pass
        return result
    except Exception:
        return {}

# Load config keys
try:
    from config import (BOT_TOKEN, GROQ_API_KEY, OPENAI_API_KEY, TOGETHER_API_KEY,
                        TARGET_CHANNEL, SHOP_LINK, METRIKA_TOKEN, METRIKA_COUNTER_ID,
                        OWNER_CHAT_ID)
except Exception:
    BOT_TOKEN = GROQ_API_KEY = OPENAI_API_KEY = TOGETHER_API_KEY = ""
    TARGET_CHANNEL = "@perfektorganic"
    SHOP_LINK = "https://perfect-org.ru/"
    METRIKA_TOKEN = ""
    METRIKA_COUNTER_ID = ""
    OWNER_CHAT_ID = 326905536

try:
    from content_plan import HEALTH_PROGRAM_URLS
except Exception:
    HEALTH_PROGRAM_URLS = [
        {"url": "https://perfect-org.ru/pohudenie",       "title": "Снижение веса"},
        {"url": "https://perfect-org.ru/detox",           "title": "Детокс-очищение"},
        {"url": "https://perfect-org.ru/antistress",      "title": "Антистресс"},
        {"url": "https://perfect-org.ru/imunitet",        "title": "Укрепление иммунитета"},
        {"url": "https://perfect-org.ru/sustavy",         "title": "Здоровье суставов"},
        {"url": "https://perfect-org.ru/serdce",          "title": "Здоровье сердца"},
        {"url": "https://perfect-org.ru/zhenskoezdorove", "title": "Женское здоровье"},
        {"url": "https://perfect-org.ru/muzhskoezdorovye","title": "Мужское здоровье"},
    ]


def scrape_program_page(url):
    """Скрапит страницу программы здоровья: текст и og:image."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        image_url = None
        og = soup.find('meta', property='og:image')
        if og:
            image_url = og.get('content') or None
        for tag in soup(['nav', 'header', 'footer', 'script', 'style']):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text(separator='\n', strip=True).splitlines()]
        content_lines = [l for l in lines if len(l) > 30 and not any(
            kw in l.lower() for kw in ['задать вопрос', 'стать партнером', 'получить', 'показать',
                                        'каталог', 'доставка', 'контакты', 'телефон:', 'www.',
                                        'javascript', 'function(', 'var ', 'css']
        )]
        description = '\n\n'.join(content_lines[:12])[:2000]
        return {'description': description, 'image_url': image_url}
    except Exception:
        return {'description': '', 'image_url': None}

WEEKDAYS = {0: "Понедельник", 1: "Вторник", 2: "Среда",
            3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье"}
POST_TYPES = {
    "expert": "Экспертный (врач)",
    "review": "Отзыв",
    "partner": "Партнёрская программа",
    "sales": "Продающий",
    "lifestyle": "О компании",
    "viral": "Вирусный",
    "faq": "Вопрос-ответ",
    "program": "🌿 Программа здоровья"
}
WEEKLY_SCHEDULE = {0: "expert", 1: "review", 2: "partner",
                   3: "sales", 4: "lifestyle", 5: "viral", 6: "program"}


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def run_cmd(cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)


def load_saved_posts():
    path = os.path.join(BOT_DIR, "saved_posts.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_saved_posts(posts):
    path = os.path.join(BOT_DIR, "saved_posts.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


# ─── Auth ───────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "Неверный пароль"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Pages ──────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def index():
    return render_template("index.html", weekdays=WEEKDAYS, post_types=POST_TYPES,
                           weekly_schedule=WEEKLY_SCHEDULE)


# ─── Bot management ─────────────────────────────────────────────────────────

@app.route("/api/status")
@login_required
def api_status():
    output = run_cmd(f"systemctl is-active {SERVICE_NAME}")
    is_running = output.strip() == "active"
    uptime = run_cmd(f"systemctl show {SERVICE_NAME} --property=ActiveEnterTimestamp --value").strip()
    return jsonify({"running": is_running, "uptime": uptime})


@app.route("/api/logs")
@login_required
def api_logs():
    lines = request.args.get("lines", 80)
    logs = run_cmd(f"journalctl -u {SERVICE_NAME} -n {lines} --no-pager -o short-iso")
    return jsonify({"logs": logs})


@app.route("/api/restart", methods=["POST"])
@login_required
def api_restart():
    run_cmd(f"systemctl restart {SERVICE_NAME}")
    return jsonify({"ok": True, "message": "Бот перезапущен"})


@app.route("/api/stop", methods=["POST"])
@login_required
def api_stop():
    run_cmd(f"systemctl stop {SERVICE_NAME}")
    return jsonify({"ok": True, "message": "Бот остановлен"})


@app.route("/api/start", methods=["POST"])
@login_required
def api_start():
    run_cmd(f"systemctl start {SERVICE_NAME}")
    return jsonify({"ok": True, "message": "Бот запущен"})


@app.route("/api/update", methods=["POST"])
@login_required
def api_update():
    import threading
    out1 = run_cmd("cd /opt/bot && git pull origin main")
    out2 = run_cmd("cp -r /opt/bot/dashboard/. /opt/dashboard/")
    out3 = run_cmd(f"systemctl restart {SERVICE_NAME}")
    threading.Timer(2.0, lambda: run_cmd("systemctl restart perfectorganic-dashboard")).start()
    msg = f"pull: {out1.strip().split(chr(10))[-1]} | cp: {out2.strip() or 'ok'} | bot: {out3.strip() or 'ok'}"
    return jsonify({"ok": True, "message": msg})


@app.route("/api/restart_dashboard", methods=["POST"])
@login_required
def api_restart_dashboard():
    import threading
    threading.Timer(1.5, lambda: run_cmd("systemctl restart perfectorganic-dashboard")).start()
    return jsonify({"ok": True, "message": "Дашборд перезапускается..."})


# ─── Queue management ───────────────────────────────────────────────────────

@app.route("/api/queue")
@login_required
def api_queue():
    posts = load_saved_posts()
    result = {}
    for day in range(7):
        key = str(day)
        if key in posts:
            p = posts[key]
            result[key] = {
                "post_type": p.get("post_type", ""),
                "text": p.get("text", ""),
                "has_photo": bool(p.get("photo")),
                "has_photo2": bool(p.get("photo2")),
            }
    return jsonify({"queue": result, "weekdays": WEEKDAYS, "schedule": WEEKLY_SCHEDULE})


@app.route("/api/queue/<int:day>")
@login_required
def api_queue_day(day):
    posts = load_saved_posts()
    p = posts.get(str(day))
    if not p:
        return jsonify({"post": None})
    post = {
        "post_type": p.get("post_type", ""),
        "text": p.get("text", ""),
        "has_photo": bool(p.get("photo")),
        "photo_b64": p.get("photo", "")[:100] if p.get("photo") else None,
    }
    return jsonify({"post": post})


@app.route("/api/queue/<int:day>", methods=["DELETE"])
@login_required
def api_delete_day(day):
    posts = load_saved_posts()
    posts.pop(str(day), None)
    write_saved_posts(posts)
    return jsonify({"ok": True})


@app.route("/api/queue/save", methods=["POST"])
@login_required
def api_save_post():
    data = request.get_json()
    day = int(data.get("day", 0))
    text = data.get("text", "").strip()
    post_type = data.get("post_type", WEEKLY_SCHEDULE.get(day, "expert"))
    photo_b64 = data.get("photo_b64", "")
    photo_url = data.get("photo_url", "").strip()

    if not text:
        return jsonify({"ok": False, "error": "Текст обязателен"})

    entry = {"text": text, "post_type": post_type}

    # Photo from URL
    if photo_url and not photo_b64:
        try:
            r = requests.get(photo_url, timeout=10)
            photo_b64 = base64.b64encode(r.content).decode()
        except Exception as e:
            return jsonify({"ok": False, "error": f"Ошибка загрузки фото: {e}"})

    if photo_b64:
        entry["photo"] = photo_b64

    posts = load_saved_posts()
    posts[str(day)] = entry
    write_saved_posts(posts)
    return jsonify({"ok": True, "message": f"Пост на {WEEKDAYS[day]} сохранён"})


# ─── Publish now ────────────────────────────────────────────────────────────

@app.route("/api/publish_now", methods=["POST"])
@login_required
def api_publish_now():
    data = request.get_json()
    text = data.get("text", "").strip()
    photo_b64 = data.get("photo_b64", "")
    photo_url = data.get("photo_url", "").strip()
    post_type = data.get("post_type", "")

    if not text:
        return jsonify({"ok": False, "error": "Нет текста"})

    # Добавляем UTM-метки ко всем ссылкам perfect-org.ru
    campaign_date = datetime.now().strftime("%Y-%m-%d")
    text = add_utm(text, campaign_date)

    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    if photo_b64:
        photo_bytes = base64.b64decode(photo_b64)
        if len(text) > 1024:
            # Фото без подписи, потом текст отдельным сообщением
            r = requests.post(f"{tg_url}/sendPhoto",
                              data={"chat_id": TARGET_CHANNEL},
                              files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")})
            if r.json().get("ok"):
                r = requests.post(f"{tg_url}/sendMessage",
                                  json={"chat_id": TARGET_CHANNEL, "text": text, "parse_mode": "HTML"})
        else:
            r = requests.post(f"{tg_url}/sendPhoto",
                              data={"chat_id": TARGET_CHANNEL, "caption": text, "parse_mode": "HTML"},
                              files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")})
    elif photo_url:
        if len(text) > 1024:
            r = requests.post(f"{tg_url}/sendPhoto",
                              json={"chat_id": TARGET_CHANNEL, "photo": photo_url})
            if r.json().get("ok"):
                r = requests.post(f"{tg_url}/sendMessage",
                                  json={"chat_id": TARGET_CHANNEL, "text": text, "parse_mode": "HTML"})
        else:
            r = requests.post(f"{tg_url}/sendPhoto",
                              json={"chat_id": TARGET_CHANNEL, "photo": photo_url,
                                    "caption": text, "parse_mode": "HTML"})
    else:
        r = requests.post(f"{tg_url}/sendMessage",
                          json={"chat_id": TARGET_CHANNEL, "text": text, "parse_mode": "HTML"})

    result = r.json()
    if result.get("ok"):
        msg_id = result.get("result", {}).get("message_id")
        if msg_id:
            stats = load_stats()
            entry = {
                "message_id": msg_id,
                "date": campaign_date,
                "time": datetime.now().strftime("%H:%M"),
                "post_type": post_type,
                "text_preview": text[:120],
                "text_full": text,
                "tg_link": f"https://t.me/perfektorganic/{msg_id}",
            }
            if photo_b64:
                entry["photo"] = photo_b64
            elif photo_url:
                entry["photo_url"] = photo_url
            stats.append(entry)
            save_stats(stats)
        return jsonify({"ok": True, "message": "Опубликовано в канал!"})
    else:
        return jsonify({"ok": False, "error": result.get("description", "Ошибка Telegram")})


# ─── Send preview to owner ──────────────────────────────────────────────────

@app.route("/api/send_preview", methods=["POST"])
@login_required
def api_send_preview():
    data = request.get_json()
    text = data.get("text", "").strip()
    photo_b64 = data.get("photo_b64", "")
    photo_url = data.get("photo_url", "").strip()

    if not text:
        return jsonify({"ok": False, "error": "Нет текста"})

    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    chat_id = str(OWNER_CHAT_ID)

    if photo_b64:
        photo_bytes = base64.b64decode(photo_b64)
        caption = text if len(text) <= 1024 else text[:1020] + "..."
        r = requests.post(f"{tg_url}/sendPhoto",
                          data={"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"},
                          files={"photo": ("photo.jpg", photo_bytes, "image/jpeg")})
        if len(text) > 1024:
            requests.post(f"{tg_url}/sendMessage",
                          json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    elif photo_url:
        caption = text if len(text) <= 1024 else text[:1020] + "..."
        r = requests.post(f"{tg_url}/sendPhoto",
                          json={"chat_id": chat_id, "photo": photo_url,
                                "caption": caption, "parse_mode": "HTML"})
    else:
        r = requests.post(f"{tg_url}/sendMessage",
                          json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

    result = r.json()
    if result.get("ok"):
        return jsonify({"ok": True, "message": "Пост отправлен вам в Telegram!"})
    else:
        return jsonify({"ok": False, "error": result.get("description", "Ошибка Telegram")})


# ─── AI Text generation ─────────────────────────────────────────────────────

@app.route("/api/generate_text", methods=["POST"])
@login_required
def api_generate_text():
    data = request.get_json()
    post_type = data.get("post_type", "expert")
    topic = data.get("topic", "")

    prompts = {
        "expert": f"Ты врач-нутрициолог. Напиши экспертный пост для Telegram канала о здоровье и натуральных добавках. Тема: {topic or 'польза витаминов'}. Используй <b>жирный текст</b> для акцентов. 3-4 абзаца. В конце призыв перейти на {SHOP_LINK}",
        "viral": f"Напиши вирусный пост для Telegram о здоровье. Начни с шокирующего факта. Тема: {topic or 'здоровое питание'}. Используй <b>жирный</b>. Призыв к действию в конце.",
        "sales": f"Напиши продающий пост для Telegram о натуральном продукте. Продукт/тема: {topic or 'витамины'}. Преимущества, отзывы, призыв купить на {SHOP_LINK}. Используй <b>жирный</b>.",
        "faq": f"Напиши пост в формате вопрос-ответ для Telegram канала о здоровье. Тема: {topic or 'витамин D'}. Начни с вопроса, дай развёрнутый ответ. Используй <b>жирный</b>.",
        "lifestyle": f"Напиши пост о здоровом образе жизни для Telegram. Тема: {topic or 'утренние ритуалы'}. Вдохновляющий тон. Используй <b>жирный</b>.",
        "partner": f"Напиши пост о партнёрской программе Perfect Organic. Преимущества: пассивный доход, натуральные продукты, поддержка. Ссылка: {SHOP_LINK}. Используй <b>жирный</b>.",
        "review": f"Напиши реалистичный отзыв покупателя натуральных добавок. Тема: {topic or 'витамины'}. От лица покупателя. 2-3 предложения.",
    }

    # Для program — скрапим сайт и строим промпт из реального текста
    if post_type == "program":
        prog_title = topic or "Снижение веса"
        prog_url = next(
            (p["url"] for p in HEALTH_PROGRAM_URLS if p["title"].lower() == prog_title.lower()),
            HEALTH_PROGRAM_URLS[0]["url"]
        )
        scraped = scrape_program_page(prog_url)
        prog_text = scraped['description']
        if prog_text:
            prompt = (
                f"Напиши пост для Telegram канала Perfect Organic о программе здоровья «{prog_title}».\n\n"
                f"Информация с сайта о программе:\n{prog_text}\n\n"
                f"Структура поста:\n"
                f"1. Заголовок с эмодзи, название программы, обёрнутый в <b>...</b>\n"
                f"2. Описание проблемы — почему она возникает, кому актуальна (2-3 предложения)\n"
                f"3. Что включает программа — кратко перечисли ключевые компоненты/продукты из текста выше в виде списка:\n"
                f"✅ <b>Название</b> — одно предложение о пользе.\n"
                f"4. В конце добавь точно эту строку (не меняй): 🌿 <a href=\"{prog_url}\">Подробнее о программе «{prog_title}»</a>\n\n"
                f"Стиль: экспертный, заботливый, с эмодзи. Выдели жирным заголовок и названия продуктов.\n"
                f"200-240 слов. Не добавляй ничего после ссылки."
            )
        else:
            prompt = (
                f"Напиши пост для Telegram о программе здоровья «{prog_title}» от Perfect Organic. "
                f"Опиши: проблему, ключевые продукты, призыв. Используй <b>жирный</b>. 200-240 слов. "
                f"В самом конце добавь точно эту строку: 🌿 <a href=\"{prog_url}\">Подробнее о программе «{prog_title}»</a>"
            )
    else:
        prompt = prompts.get(post_type, prompts["expert"])

    if not GROQ_API_KEY:
        return jsonify({"ok": False, "error": "GROQ_API_KEY не настроен"})

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 900,
                "temperature": 0.8
            },
            timeout=30
        )
        print(f"[Groq] status={r.status_code} body={r.text[:300]}")
        result = r.json()
        if "choices" not in result:
            err_msg = "Неизвестная ошибка Groq"
            if isinstance(result.get("error"), dict):
                err_msg = result["error"].get("message", str(result))
            elif isinstance(result.get("error"), str):
                err_msg = result["error"]
            else:
                err_msg = str(result)[:300]
            return jsonify({"ok": False, "error": f"Groq: {err_msg}"})
        text = result["choices"][0]["message"]["content"]
        if len(text) > 1280:
            text = text[:1260] + "..."
        return jsonify({"ok": True, "text": text})
    except requests.exceptions.Timeout:
        return jsonify({"ok": False, "error": "Groq не ответил за 30 секунд, попробуйте ещё раз"})
    except Exception as e:
        print(f"[Groq] exception: {e}")
        return jsonify({"ok": False, "error": str(e)})


# ─── AI Photo generation ─────────────────────────────────────────────────────

@app.route("/api/generate_photo", methods=["POST"])
@login_required
def api_generate_photo():
    data = request.get_json()
    prompt = data.get("prompt", "")
    post_type = data.get("post_type", "expert")

    if not prompt:
        default_prompts = {
            "expert": "Professional doctor nutritionist in white coat, warm clinic background, natural lighting, photorealistic",
            "viral": "Healthy woman holding fresh vegetables and fruits, bright natural light, lifestyle photo",
            "sales": "Natural health supplements on wooden table with herbs, professional product photo",
            "lifestyle": "Happy healthy family outdoors in nature, sunny day, warm tones",
            "faq": "Close-up hands holding natural capsules with herbs background",
            "program": "Happy healthy Russian person outdoors in nature, warm sunlight, full of energy, photorealistic",
            "partner": "Successful woman working from laptop at home, natural light, modern interior",
            "review": "Smiling satisfied customer, natural background, candid photo",
        }
        prompt = default_prompts.get(post_type, "Healthy lifestyle photo, natural light")

    try:
        r = requests.post(
            "https://api.together.xyz/v1/images/generations",
            headers={"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "black-forest-labs/FLUX.1-schnell-Free",
                "prompt": prompt + ". High quality, photorealistic, no text, no watermarks",
                "width": 1024, "height": 768, "steps": 4, "n": 1
            },
            timeout=60
        )
        result = r.json()
        if "data" in result and result["data"]:
            img_url = result["data"][0].get("url", "")
            if img_url:
                img_r = requests.get(img_url, timeout=30)
                b64 = base64.b64encode(img_r.content).decode()
                return jsonify({"ok": True, "photo_b64": b64, "url": img_url})
        return jsonify({"ok": False, "error": "Нет изображения в ответе"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ─── Photo upload ────────────────────────────────────────────────────────────

@app.route("/api/upload_photo", methods=["POST"])
@login_required
def api_upload_photo():
    if "photo" not in request.files:
        return jsonify({"ok": False, "error": "Нет файла"})
    file = request.files["photo"]
    if not file.filename:
        return jsonify({"ok": False, "error": "Пустое имя файла"})
    b64 = base64.b64encode(file.read()).decode()
    return jsonify({"ok": True, "photo_b64": b64})


# ─── Statistics ──────────────────────────────────────────────────────────────

def get_metrika_clicks():
    """Запрашивает клики по utm_campaign из Яндекс Метрики за последние 90 дней.
    Возвращает {campaign_date: clicks}."""
    if not METRIKA_TOKEN or not METRIKA_COUNTER_ID:
        return {}
    try:
        r = requests.get(
            "https://api-metrika.yandex.net/stat/v1/data",
            headers={"Authorization": f"OAuth {METRIKA_TOKEN}"},
            params={
                "ids": METRIKA_COUNTER_ID,
                "metrics": "ym:s:visits",
                "dimensions": "ym:s:UTMCampaign",
                "date1": "90daysAgo",
                "date2": "today",
                "limit": 100,
                "filters": "ym:s:UTMSource=='telegram'",
            },
            timeout=10
        )
        data = r.json()
        result = {}
        for row in data.get("data", []):
            campaign = row["dimensions"][0].get("name", "")
            clicks = int(row["metrics"][0])
            if campaign:
                result[campaign] = clicks
        return result
    except Exception:
        return {}


@app.route("/api/stats")
@login_required
def api_stats():
    stats = load_stats()
    views_map = get_channel_views()
    clicks_map = get_metrika_clicks()
    for entry in stats:
        mid = entry.get("message_id")
        if mid in views_map:
            entry["views"] = views_map[mid]
        elif "views" not in entry:
            entry["views"] = "—"
        # Клики из Метрики по дате кампании
        campaign = entry.get("date", "")
        entry["clicks"] = clicks_map.get(campaign, 0)
    # Вернуть в обратном порядке (свежие сверху)
    return jsonify({"stats": list(reversed(stats))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
