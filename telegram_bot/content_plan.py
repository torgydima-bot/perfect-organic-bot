# Контент-план канала @perfektorganic
# 7 типов постов — каждый день разный, без повторений

# Типы постов по дням недели (0=Пн, 6=Вс)
WEEKLY_PLAN = {
    0: "expert",    # Понедельник  — экспертный (врач про минералы/витамины + фото доктора)
    1: "review",    # Вторник      — отзыв клиента с фото/видео (из канала)
    2: "partner",   # Среда        — партнёрский (как зарабатывать с Perfect Organic)
    3: "sales",     # Четверг      — продающий (один продукт + польза + ссылка)
    4: "lifestyle", # Пятница      — о компании и здоровом образе жизни
    5: "viral",     # Суббота      — вирусный (факты, мифы — на выходных хорошо разлетается)
    6: "faq",       # Воскресенье  — рекомендации при болезнях
}

POST_TYPE_LABELS = {
    "expert":    "📚 Экспертный",
    "review":    "⭐ Отзыв клиента",
    "viral":     "🔥 Вирусный",
    "sales":     "💰 Продающий",
    "lifestyle": "💚 О здоровой жизни",
    "partner":   "🤝 Партнёрский",
    "faq":       "💊 Рекомендации при болезнях",
}

# ─── ЭКСПЕРТНЫЕ посты ────────────────────────────────────────────────────────
# Пишем от лица врача-нутрициолога, генерируем фото доктора через gpt-image-1

EXPERT_TOPICS = [
    "Почему минералы важнее витаминов — объясняю как нутрициолог",
    "Топ-5 признаков нехватки магния: узнайте себя",
    "Морские водоросли как источник минералов: научный взгляд",
    "Почему синтетические витамины хуже натуральных",
    "Связь между хронической усталостью и дефицитом минералов",
    "Как стресс вымывает минералы из организма — и что делать",
    "Кальций без магния — почему это деньги на ветер",
    "Йод: почему 80% людей испытывают скрытый дефицит",
    "Железо и усталость у женщин: что нужно знать",
    "Как правильно принимать добавки для максимального результата",
    "Цинк и иммунитет: научно доказанная связь",
    "Почему дети в России всё чаще испытывают дефицит витамина D",
]

# Один и тот же образ женщины-нутрициолога — одна внешность, один кабинет, меняется только ПОЗА
# ВАЖНО: NO English text anywhere. NO supplement bottles. Only books, pen, paper, plant on desk.
_DOCTOR_CHARACTER = (
    "Photorealistic professional photo, natural camera look, NOT illustrated, NOT painted. "
    "ALWAYS the exact same woman — never change her appearance. "
    "Russian female doctor-nutritionist, 45-48 years old. "
    "HAIR: light warm brown (Russian 'русый') hair — sandy blonde-brown, NOT dark, NOT chestnut, "
    "shoulder-length, soft natural wave at the ends, parted slightly to the side, "
    "warm golden-brown tone, natural highlights, looks like natural Russian light brown hair. "
    "FACE: soft oval face, grey-blue eyes (серо-голубые), wide genuine smile showing white teeth, "
    "subtle natural wrinkles around eyes and cheeks, very light natural makeup. "
    "CLOTHING: plain clean white medical coat — NO text, NO logos, NO badges, NO English words. "
    "Stethoscope hanging around her neck. "
    "SETTING: bright airy medical office, very bright white background, "
    "large window with soft daylight on the left, white desk in front of her, "
    "2-3 medical books stacked on the desk, one green plant blurred in background. "
    "Overall mood: bright, clean, light — NO dark shadows, NO dark background. "
    "NO supplement bottles, NO pills, NO product packaging anywhere. "
    "Do NOT change hair, face, or clothing — only her pose and hand position change. "
)

DOCTOR_PHOTO_PROMPTS = [
    _DOCTOR_CHARACTER + (
        "POSE: she sits at the desk, both hands clasped together on the desk, "
        "looking directly and warmly at the camera. Confident and friendly expression."
    ),
    _DOCTOR_CHARACTER + (
        "POSE: she sits at the desk writing notes with a pen in a notebook, "
        "slightly leaning forward, focused and professional."
    ),
    _DOCTOR_CHARACTER + (
        "POSE: she sits at the desk, one hand resting on an open medical book, "
        "looking up at the camera with a warm knowledgeable smile."
    ),
    _DOCTOR_CHARACTER + (
        "POSE: she sits at the desk, arms crossed lightly, leaning back slightly, "
        "confident and relaxed posture, warm direct gaze at camera."
    ),
    _DOCTOR_CHARACTER + (
        "POSE: she sits slightly turned toward the camera, one hand on the desk, "
        "the other raised slightly as if explaining something, engaged expression."
    ),
    _DOCTOR_CHARACTER + (
        "POSE: she sits at the desk, both hands folded on the desk, "
        "leaning forward slightly toward the camera, attentive and caring expression."
    ),
]

# Оставляем для обратной совместимости — берём первый вариант
DOCTOR_PHOTO_PROMPT = DOCTOR_PHOTO_PROMPTS[0]

# ─── ВИРУСНЫЕ посты ──────────────────────────────────────────────────────────
# Шокирующие факты, мифы vs правда, тесты — максимальная вовлечённость

VIRAL_TOPICS = [
    "5 неожиданных признаков что вам не хватает магния прямо сейчас",
    "Миф или правда: витамин С защищает от простуды? Учёные ответили",
    "Сколько минералов теряет организм за один стрессовый день — цифры шокируют",
    "Почему наши бабушки были здоровее нас: ответ в питании",
    "Тест: угадайте каких минералов вам не хватает по 3 симптомам",
    "3 продукта которые блокируют усвоение кальция — вы едите их каждый день",
    "Что происходит с организмом за 30 дней приёма натуральных минералов",
    "Железный факт: 60% женщин живут с анемией и не знают об этом",
]

# ─── Динамические промпты для вирусных split-фото ────────────────────────────

def _viral_topic_elements(topic: str) -> tuple[str, str]:
    """
    По теме поста возвращает (right_elements, left_elements):
      right_elements — красивые тематические элементы для правой (золотой) половины
      left_elements  — тусклые версии тех же элементов для левой (серой) половины
    """
    t = topic.lower()

    if any(k in t for k in ("железо", "анемия", "феррум", "гемоглоб")):
        right = (
            "halved ripe pomegranate with ruby-red seeds spilling out, "
            "fresh dark green spinach leaves, deep red kidney beans in a small bowl, "
            "a slice of beef on a wooden board — all naturally arranged on a table"
        )
        left = "wilted pale spinach, faded kidney beans, unripe pomegranate"

    elif any(k in t for k in ("магний", "magn")):
        right = (
            "dark chocolate bar broken into pieces, roasted pumpkin seeds in a small bowl, "
            "whole almonds and cashews, a halved ripe avocado — "
            "all naturally arranged on a wooden table"
        )
        left = "plain chocolate, dry pale seeds, dull nuts on a grey surface"

    elif any(k in t for k in ("кальций", "кальц", "calcium", "кость")):
        right = (
            "white sesame seeds in a small bowl, fresh green broccoli florets, "
            "a glass of milk, a piece of hard cheese — all naturally arranged on a table"
        )
        left = "grey sesame seeds, pale dull broccoli, an empty glass"

    elif any(k in t for k in ("витамин с", "аскорб", "цитрус", "простуд", "иммун")):
        right = (
            "halved bright orange and lemon, a whole kiwi cut in half, "
            "ripe red strawberries in a bowl, fresh green parsley — "
            "all naturally arranged on a table"
        )
        left = "pale unripe citrus halves, wilted herbs, dull berries"

    elif any(k in t for k in ("цинк", "zinc")):
        right = (
            "pumpkin seeds in a small ceramic bowl, whole cashews, "
            "fresh oysters on a plate, a piece of beef — all naturally arranged on a table"
        )
        left = "grey pumpkin seeds, dull pale nuts, empty plate"

    elif any(k in t for k in ("йод", "iod", "водоросл", "щитовид", "морск")):
        right = (
            "fresh green seaweed salad in a bowl, a piece of baked fish fillet on a plate, "
            "sea salt in a small dish, shrimp — all naturally arranged on a table"
        )
        left = "grey dried seaweed, pale fish, empty grey plate"

    elif any(k in t for k in ("витамин д", "vitamin d", "солнц", "d3")):
        right = (
            "sunny-side-up eggs with bright golden yolks on a plate, "
            "a piece of baked salmon, a small glass of milk — "
            "all naturally arranged, warm sunlight through kitchen window"
        )
        left = "grey scrambled egg, pale unseasoned fish, cloudy dim kitchen"

    elif any(k in t for k in ("омега", "omega", "жирн", "рыб")):
        right = (
            "fresh salmon fillet on a plate, a small bowl of walnuts, "
            "flaxseeds in a spoon, a bottle of fish oil capsules on the table — "
            "all naturally arranged"
        )
        left = "pale grey fish, dull walnuts, grey seeds on a grey surface"

    else:
        # Общий набор: разнообразные овощи и фрукты
        right = (
            "colorful assortment of fresh fruits and vegetables: halved orange, green apple, "
            "broccoli florets, carrot sticks, a handful of nuts — all naturally arranged on a table"
        )
        left = "grey pale fruits and vegetables, wilted greenery, dull seeds"

    return right, left


def build_viral_image_prompt(topic: str, variant: str = "medium_woman") -> str:
    """Строит динамический split-промпт на основе темы и варианта съёмки."""
    right_el, left_el = _viral_topic_elements(topic)

    if variant == "wide_family":
        shot = "Wide establishing shot"
        person_left = (
            "A Russian family (parents aged 40-50, kids 10-15) sitting together on a grey picnic blanket "
            "in an overcast park, looking tired and downcast, hunched posture"
        )
        person_right = (
            "The same Russian family laughing and energetic on a sunny green meadow, "
            "parents and children smiling broadly, sunlight pouring down, outdoors in nature"
        )
        placement_left = f"On the grey picnic blanket beside them: {left_el}"
        placement_right = f"On the sunny picnic blanket in front of them: {right_el}"

    elif variant == "medium_man":
        shot = "Medium chest-up shot"
        person_left = (
            "A Russian man aged 45-55, sitting at a kitchen table, leaning forward with tired eyes, "
            "looking down, dim grey natural light from window"
        )
        person_right = (
            "The same Russian man aged 45-55, sitting upright, smiling warmly, "
            "bright alert eyes, warm sunny light from window, energetic posture"
        )
        placement_left = f"On the kitchen table in front of him: {left_el}"
        placement_right = f"On the kitchen table in front of him, neatly arranged: {right_el}"

    elif variant == "closeup_woman":
        shot = "Close-up portrait shot"
        person_left = (
            "Close-up portrait of a Russian woman aged 45-50, tired pale skin, "
            "downcast eyes, sad expression, cold grey natural light"
        )
        person_right = (
            "Close-up portrait of the same Russian woman aged 45-50, glowing healthy skin, "
            "bright smiling eyes, radiant confident expression, warm golden natural light"
        )
        placement_left = f"She holds in her hands (visible at frame bottom): {left_el}"
        placement_right = f"She holds in her hands (visible at frame bottom): {right_el}"

    else:  # medium_woman (default)
        shot = "Medium chest-up shot"
        person_left = (
            "A Russian woman aged 45-50, sitting at a wooden table by window, looking down pensively, "
            "tired expression, cold grey overcast light"
        )
        person_right = (
            "The same Russian woman aged 45-50, sitting upright at the table, smiling confidently, "
            "radiant skin, bright eyes, warm golden sunlight through window"
        )
        placement_left = f"On the wooden table in front of her: {left_el}"
        placement_right = f"On the wooden table in front of her, neatly placed: {right_el}"

    return (
        f"A split diptych photograph divided exactly in half by a sharp vertical line. "
        f"Wide horizontal landscape format (16:9). {shot}. "
        f"No text, no labels, no objects floating in the air — everything naturally placed. "
        f"Photorealistic natural photography, no CGI, no compositing artifacts. "
        f"LEFT HALF: cold grey-blue desaturated tones. {person_left}. "
        f"{placement_left}. Quiet, subdued, cold atmosphere. "
        f"RIGHT HALF: warm sunny golden tones. {person_right}. "
        f"{placement_right}. Warm, vibrant, natural golden atmosphere. "
        f"Strong visual contrast: cold grey left side vs warm golden right side."
    )


# Варианты съёмки (для случайного выбора)
_VIRAL_PERSON_VARIANTS = ["medium_woman", "medium_man", "wide_family", "closeup_woman"]

# Для обратной совместимости — статические промпты используют дефолтные элементы
VIRAL_PHOTO_PROMPTS = [
    build_viral_image_prompt("общие витамины минералы", v)
    for v in _VIRAL_PERSON_VARIANTS
]
VIRAL_PHOTO_PROMPT = VIRAL_PHOTO_PROMPTS[0]
VIRAL_MINERAL_PHOTO_PROMPT = build_viral_image_prompt("магний минерал кальций", "woman")


def build_viral_photo1_prompt(topic: str, variant: str = "medium_woman") -> str:
    """Фото 1 вирусного поста: человек уставший — нехватка витаминов/минералов."""
    _scenes = [
        "sitting slumped at an office desk, staring blankly at monitor screen, completely drained",
        "sitting in a bus or metro, leaning head against window, eyes half-closed with fatigue",
        "standing in a kitchen in the morning, hands around coffee cup, looking utterly exhausted",
        "walking slowly on a grey city pavement, hunched posture, heavy tired steps",
    ]
    scene = _scenes[abs(hash(topic)) % len(_scenes)]
    person = "A Russian man aged 42-55" if "man" in variant else "A Russian woman aged 38-52"
    return (
        f"Candid realistic lifestyle photo. {person}, {scene}. "
        f"Pale tired face, dark circles under eyes, dull skin, no energy. "
        f"Cold grey-blue natural daylight or dim indoor lighting, overcast atmosphere. "
        f"No text anywhere on image. No vitamins or pills visible. "
        f"Photorealistic natural photography style, cinematic quality, no CGI elements."
    )


def build_viral_photo2_prompt(topic: str, variant: str = "medium_woman") -> str:
    """Фото 2 вирусного поста: человек счастливый + еда/витамины из темы поста."""
    right_el, _ = _viral_topic_elements(topic)
    _scenes = [
        "working actively at a bright sunny office desk, upright posture, laughing with colleague",
        "outdoors in a sunny park, smiling broadly, enjoying fresh air, full of life",
        "on a sunny outdoor picnic with family (partner and children aged 8-14), all laughing",
        "walking confidently on a sunlit street, bright natural smile, energetic posture",
    ]
    scene = _scenes[abs(hash(topic + "v2")) % len(_scenes)]
    person = "A Russian man aged 42-55" if "man" in variant else "A Russian woman aged 38-52"
    return (
        f"Warm lifestyle photo. {person}, {scene}. "
        f"Glowing healthy skin, bright eyes, radiant energy, wide natural smile. "
        f"Warm golden sunlight. "
        f"On a surface nearby or naturally held in hands: {right_el}. "
        f"Items placed naturally on a flat surface — nothing floating in air. "
        f"No text anywhere on image. Photorealistic natural photography, cinematic quality, no CGI."
    )


# Ключевые слова для определения «минерального» вирусного поста
VIRAL_MINERAL_KEYWORDS = frozenset([
    "минерал", "магний", "кальций", "железо", "цинк", "йод",
    "водоросл", "анемия", "кальц", "микроэлемент",
])

# ─── ПРОДАЮЩИЕ посты ─────────────────────────────────────────────────────────
# Показываем один продукт, боль → решение → выгоды → призыв
# Продукты берём из products.py

# ─── О ЗДОРОВОЙ ЖИЗНИ (бывший Лайфстайл) ────────────────────────────────────
# О компании, ценности, истории клиентов, советы по образу жизни

LIFESTYLE_TOPICS = [
    "История Perfect Organic: как всё начиналось и почему это важно",
    "Почему мы выбираем только натуральные ингредиенты",
    "Как правильно начать заботиться о здоровье: простой план",
    "Утренний ритуал для энергии — делимся лайфхаками наших клиентов",
    "Скидки для новых покупателей Perfect Organic: как получить",
    "Реальная история: как наш клиент вернул себе энергию после 40",
    "5 привычек здоровых людей, которые легко внедрить уже сегодня",
    "Почему важно выбирать натуральные добавки для всей семьи",
    # Темы о производстве и качестве
    "Как создаются добавки Perfect Organic: от идеи до готового продукта",
    "Почему нам можно доверять: стандарты производства Perfect Organic",
    "Лабораторный контроль качества: что происходит до того, как продукт попадёт к вам",
    "От растения до капсулы: полный путь создания натуральной добавки",
    "GMP-производство: почему это важно для вашего здоровья",
    "Чистое производство: как мы гарантируем безопасность каждого продукта",
]

# Темы о производстве (для подбора правильного промпта фото)
_LIFESTYLE_PRODUCTION_TOPICS = {t for t in LIFESTYLE_TOPICS if any(
    kw in t for kw in ["производств", "лаборатор", "создаются", "растения до", "GMP", "контроль качества"]
)}

# Промпты для AI-фото поста "О здоровой жизни" — выбирается случайно для разнообразия
# Каждый промпт имеет РАЗНЫЙ ракурс/масштаб: сверху, полный рост, крупный план, широкий план, и т.д.
LIFESTYLE_PHOTO_PROMPTS = [
    # 1. Завтрак — вид сверху (overhead / flat-lay)
    (
        "Real candid lifestyle photo, NOT a staged advertisement. "
        "CAMERA ANGLE: overhead bird's-eye view, looking straight down at the table. "
        "A happy Russian family at a bright kitchen table having breakfast — "
        "hands reaching for food, bowls with porridge, fresh fruit, mugs with tea. "
        "A supplement bottle sits casually at the edge among everyday items. "
        "Bright airy kitchen, soft morning daylight. "
        "Photorealistic, genuine family feel, no text on image."
    ),
    # 2. Пикник — широкий план, полный рост (wide shot, full body)
    (
        "Candid outdoor snapshot, not an ad. "
        "SHOT TYPE: wide angle, full-body shot showing the whole scene. "
        "A cheerful Russian family (parents 45-55, young adult kids) — full bodies visible — "
        "sitting on a colourful blanket on vivid green grass in a sunny meadow, "
        "laughing and eating. A supplement bottle sits naturally among food and water bottles. "
        "Bright daylight, blue sky with clouds, lush landscape all around. "
        "Photorealistic, genuine real-life feel, no text on image."
    ),
    # 3. Прогулка в парке — крупный план рук (close-up detail shot)
    (
        "Candid close-up lifestyle detail, not an ad. "
        "SHOT TYPE: close-up of hands — a woman's hands gently holding a supplement bottle "
        "while walking in a bright sunny park; a man's hand reaches over affectionately. "
        "Their torsos and smiling faces partially visible and softly blurred in background. "
        "Bokeh of vivid green trees and sunlight behind them. Bright warm daylight. "
        "Photorealistic, intimate real-life feel, no text on image."
    ),
    # 4. Обед на веранде дачи — полный рост, вся сцена (full body, wide)
    (
        "Genuine lifestyle photo, NOT a commercial shoot. "
        "SHOT TYPE: full-body wide shot of the whole scene. "
        "A happy Russian family (3-4 people, ages 40-60) at a big wooden table on a sunny dacha veranda — "
        "full bodies visible, standing and sitting, laughing, serving food, passing dishes. "
        "A supplement bottle sits on the corner of the table among everyday items. "
        "Lush green garden visible behind them, bright summer sunlight. "
        "Photorealistic, candid real-life feel, no text on image."
    ),
    # 5. Отдых у реки — средний план снизу (medium-low angle, waist to ground)
    (
        "Candid lifestyle snapshot, NOT a product photo. "
        "SHOT TYPE: medium-low angle shot, camera near ground level looking up slightly. "
        "A fit Russian couple aged 40-55 sitting on sunny riverbank grass — "
        "their legs and torsos fill the frame, laughing together. "
        "A supplement bottle lies casually on the grass beside them, close to camera. "
        "Sparkling river or lake in background, vivid green grass, clear bright sky. "
        "Photorealistic, feels like a spontaneous snapshot, no text on image."
    ),
    # 6. Утро на даче — задний план, предметы на переднем плане (wide establishing shot)
    (
        "Bright genuine lifestyle moment. "
        "SHOT TYPE: wide establishing shot — garden in background, objects sharp in foreground. "
        "Sharp foreground: a rustic wooden garden table with a supplement bottle, "
        "two mugs of tea, and wildflowers in a glass jar. "
        "Soft background (blurred): a cheerful Russian couple aged 45-55 in the garden — "
        "one tending flower beds, the other laughing in the distance. "
        "Fresh morning light, vivid greens, colorful flowers, blue sky. "
        "Photorealistic, no text on image."
    ),
    # 7. Производство / лаборатория (для тем о создании добавок)
    (
        "Professional pharmaceutical production facility, bright clinical lighting. "
        "A female scientist in a clean white lab coat and hairnet is focused on her work — "
        "examining samples or reading data at a modern lab bench, NOT holding any product. "
        "Background: various stainless steel laboratory equipment — centrifuges, glass flasks with colored liquids, "
        "digital scales, analytical instruments, lab monitors. NO generic unlabelled bottles anywhere. "
        "Foreground on the lab table: ONE supplement product package placed neatly — "
        "it MUST be EXACTLY the product from the provided reference image, with its exact packaging, colors and label design. "
        "Bright sterile white and silver environment, clean and scientific. "
        "Photorealistic, no text on image."
    ),
]
# Для обратной совместимости
LIFESTYLE_PHOTO_PROMPT = LIFESTYLE_PHOTO_PROMPTS[0]

# ─── ПАРТНЁРСКИЕ посты ───────────────────────────────────────────────────────
# Среда — партнёрская программа Perfect Organic

PARTNER_TOPICS = [
    "Как зарабатывать на том, что людям нравится — партнёрская программа Perfect Organic",
    "Сколько реально можно заработать с Perfect Organic: честные цифры",
    "Почему МЛМ в сфере здоровья — это не страшно и как это работает",
    "История нашего партнёра: от покупателя к стабильному доходу",
    "Как начать зарабатывать с Perfect Organic уже в первый месяц",
    "Партнёрская программа Perfect Organic: условия, бонусы, перспективы",
    "Мама двоих детей зарабатывает дома с Perfect Organic — её история",
    "Как Perfect Organic помогает строить бизнес без вложений",
]

# Промпты для AI-фото партнёрского поста — 3 варианта MLM/сетевой бизнес
PARTNER_PHOTO_PROMPTS = [
    # Вариант 1 — Две женщины, беседа / обучение
    (
        "Warm professional lifestyle photography. "
        "Two confident Russian women aged 35-50, sitting together at a bright modern cafe table "
        "or cozy office, having an enthusiastic business conversation. "
        "One woman is showing something on a tablet or brochure, the other listens with a warm smile. "
        "On the table: the Perfect Organic supplement product from the reference image, "
        "displayed clearly and prominently. "
        "Atmosphere: friendly, inspiring, network marketing meeting — warm golden tones, "
        "modern bright interior, natural light. Photorealistic, cinematic quality, no text on image."
    ),
    # Вариант 2 — Мужчина и женщина, презентация
    (
        "Warm professional lifestyle photography. "
        "A confident Russian man and woman aged 35-50, standing together in a bright modern office "
        "or co-working space, both smiling broadly. "
        "The man gestures enthusiastically as if presenting an opportunity; "
        "the woman holds the Perfect Organic supplement product from the reference image "
        "and listens with interest — the product packaging is clearly visible. "
        "Background: other happy people in the office, whiteboard or flip-chart partially visible. "
        "Atmosphere: successful network marketing team, energetic and positive — warm tones, "
        "natural light. Photorealistic, cinematic quality, no text on image."
    ),
    # Вариант 3 — Небольшая группа, командное собрание
    (
        "Warm professional lifestyle photography. "
        "A small group of 3-4 happy Russian people aged 35-50 (mix of men and women), "
        "gathered around a table in a bright modern meeting room or home living room. "
        "They are smiling and engaged — one person is speaking, others nod enthusiastically. "
        "On the table: the Perfect Organic supplement product from the reference image placed "
        "prominently in the centre, alongside notebooks and a laptop. "
        "Atmosphere: team training session, network marketing onboarding — warm golden tones, "
        "cozy and inspiring. Photorealistic, cinematic quality, no text on image."
    ),
]
PARTNER_PHOTO_PROMPT = PARTNER_PHOTO_PROMPTS[0]  # обратная совместимость

# ─── FAQ посты ───────────────────────────────────────────────────────────────
# Устаревшие темы (не используются — заменены на HEALTH_PROGRAMS)
FAQ_TOPICS = []

# ─── РЕКОМЕНДАЦИИ ПРИ БОЛЕЗНЯХ ───────────────────────────────────────────────
# Воскресенье — рубрика "Рекомендации": конкретная проблема со здоровьем,
# симптомы, рекомендуемые продукты Perfect Organic, AI-картинка.
# Редактируй этот список — добавляй, убирай, меняй продукты и темы.

HEALTH_PROGRAMS = [
    {
        "condition": "Здоровье сердца и сосудов",
        "symptoms": "учащённое сердцебиение, скачки давления, высокий холестерин, отёки ног, онемение конечностей",
        "details": "Сердечно-сосудистые заболевания — главная причина смертности. Дефицит магния, омега-кислот и антиоксидантов напрямую бьёт по сосудам.",
        "products": ["Бальзам для Сосудов", "МультиМинералс74", "Морской Магний", "Эсфолип"],
        "image_prompt": "Wide-angle warm lifestyle photo: a happy Russian couple aged 48-55, walking hand-in-hand along a sunny tree-lined avenue, laughing together. Green trees, golden afternoon light. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Снижение стресса и тревожности",
        "symptoms": "постоянная усталость, раздражительность, бессонница, тревога, панические атаки, нервное истощение",
        "details": "Хронический стресс вымывает магний из организма. Дефицит триптофана ведёт к нехватке серотонина — гормона радости и спокойствия.",
        "products": ["5-HTP Helper", "Морской Магний", "МультиМинералс74"],
        "image_prompt": "Medium-shot peaceful lifestyle photo: a calm Russian woman aged 45-52, sitting on a wooden bench in a quiet garden, eyes closed, face gently raised towards warm sunlight. Soft natural light, blooming flowers around her. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Контроль веса и ускорение метаболизма",
        "symptoms": "лишний вес, медленный обмен веществ, постоянная тяга к сладкому, отёки, чувство тяжести",
        "details": "Лишний вес — часто следствие дефицита минералов и нарушения обмена веществ, а не просто переедание. Правильное питание + натуральная поддержка = результат.",
        "products": ["Mineral Diet Base", "Total Energy Абрикос", "Хлорелла", "Семена Чиа", "Масло Чиа"],
        "image_prompt": "Wide outdoor lifestyle photo: a fit energetic Russian woman aged 45-50, jogging along a riverside path on a fresh sunny morning, smiling broadly. Sportswear, green nature in background, morning mist over water. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Здоровье суставов и позвоночника",
        "symptoms": "боли и хруст в суставах, скованность по утрам, воспаление, ограниченная подвижность, остеохондроз",
        "details": "Суставы страдают от дефицита коллагена, кальция и кремния. Воспаление усугубляется недостатком омега-3 и антиоксидантов.",
        "products": ["Напиток для Суставов", "Мидиактив Форте", "МультиМинералс74", "Морской Магний"],
        "image_prompt": "Wide-angle active nature photo: a healthy energetic Russian man aged 48-55, hiking confidently on a forest trail, wide smile, arms spread wide. Pine trees, blue sky, sunlight through leaves, long trail ahead. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Укрепление иммунитета",
        "symptoms": "частые простуды и ОРВИ, долгое восстановление, слабость, аллергии, герпес, снижение защитных сил",
        "details": "Иммунитет на 70% зависит от состояния кишечника. Дефицит витамина C, цинка и натуральных антиоксидантов — первая причина частых болезней.",
        "products": ["Глуммунофэрон", "Perfect C", "Хлорелла", "МультиМинералс74", "Масло Чёрного Тмина"],
        "image_prompt": "Wide joyful family lifestyle photo: a Russian family — mother, father aged 45-52, and two children aged 10-14 — playing in a sunny park, tossing a frisbee and laughing together. Warm golden afternoon light, lush green grass. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Детоксикация и очищение организма",
        "symptoms": "зашлакованность, проблемная кожа, хроническая усталость, тяжесть в животе, вздутие, неприятный запах",
        "details": "Токсины накапливаются из-за плохой экологии, питания и воды. Мягкое очищение кишечника и печени — основа здоровья и энергии.",
        "products": ["Detox Oil", "Хлорелла", "GoodBak", "МультиМинералс74"],
        "image_prompt": "Medium-shot fresh morning lifestyle photo: a radiant Russian woman aged 45-50 with clear glowing skin, standing on a sunny balcony drinking green juice, smiling brightly. City greenery and rooftops in the background. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Здоровье нервной системы и мозга",
        "symptoms": "рассеянность, провалы памяти, нарушения сна, головные боли, раздражительность, снижение концентрации",
        "details": "Нервная система потребляет огромное количество магния и B-витаминов. Хронический стресс и гаджеты истощают её быстрее, чем мы восстанавливаемся.",
        "products": ["5-HTP Helper", "Морской Магний", "МультиМинералс74"],
        "image_prompt": "Medium outdoor lifestyle photo: a focused calm Russian man aged 45-52, sitting at an outdoor café terrace, reading a book and smiling with satisfaction. Cup of coffee on the table, warm sunlight, relaxed atmosphere. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Мужское здоровье и энергия",
        "symptoms": "снижение тонуса и либидо, быстрая утомляемость, потеря мышечной массы, простатит, гормональный дисбаланс",
        "details": "После 35 лет уровень тестостерона падает на 1-2% в год. Цинк, магний и растительные адаптогены помогают поддержать мужскую силу и энергию.",
        "products": ["Andro Pro", "Alfa XT", "МультиМинералс74", "Морской Магний", "Урологический 1"],
        "image_prompt": "Wide active outdoor lifestyle photo: a strong confident Russian man aged 45-55, cycling along a scenic lakeside road, smiling broadly. Blue sky, open landscape, sunlight on water. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Женское здоровье и гормональный баланс",
        "symptoms": "нерегулярный цикл, ПМС, приливы при климаксе, выпадение волос, ломкость ногтей, перепады настроения",
        "details": "Женский организм особенно чувствителен к дефициту железа, магния и фитоэстрогенов. Натуральная поддержка помогает без гормональных препаратов.",
        "products": ["Климанет", "Дживана", "МультиМинералс74", "Морской Магний", "K-M Beauty Youth"],
        "image_prompt": "Wide beautiful lifestyle photo: an elegant Russian woman aged 47-53, strolling through a blooming garden on a sunny day, healthy flowing hair, radiant skin, natural smile. Colourful flowers all around, warm light. No products, no bottles. Photorealistic, no text.",
    },
    {
        "condition": "Здоровье ЖКТ и пищеварение",
        "symptoms": "вздутие, запоры или диарея, изжога, гастрит, дисбактериоз, тяжесть после еды, непереносимость продуктов",
        "details": "Здоровый кишечник — основа всего. Дисбаланс микрофлоры связан с иммунитетом, настроением, кожей и весом. 80% иммунитета живёт в кишечнике.",
        "products": ["GoodBak", "Максэнзим", "МультиМинералс74", "Хлорелла"],
        "image_prompt": "Wide warm family lifestyle photo: a happy Russian family — mother, father aged 45-53, and a teenager — having a cheerful breakfast together at a sunny dining table. Fresh fruits, yogurt, greens visible. Everyone is smiling and talking. Cosy morning light. No products, no bottles. Photorealistic, no text.",
    },
]
