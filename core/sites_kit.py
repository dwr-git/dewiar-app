"""«Сайты» (03.11, владелец: «Лира должна научиться делать сайты») — набор деталей: палитры, шрифтовые пары, скругления,
знаки для логотипа, узоры вместо фото, блоки с вариантами вёрстки и готовые шаблоны.

Сайт — данные (JSON), а не произвольный HTML: так Лира переделывает его одной фразой (поменять тему, шрифт, меню,
добавить раздел), а вёрстка всегда остаётся аккуратной. Рендер — sites_render.py, работа с сайтами — sites.py.

Шаблоны — со своим характером: кофейня — фисташковая с меню на «точках», юрист — строгий синий с засечками, событие —
афиша на жёлтом, фотограф — тёмная галерея с меню сбоку. Тексты — правдоподобные заготовки по-русски, Лира заменит их
словами человека. Отзывов и людей в шаблонах НЕТ: отзывы — только те, что дал человек; команда — помеченные заглушки
(todo), они не публикуются, пока их не заменят."""

import re

# ---------- палитры ----------
# bg — фон, surface — фон чередующихся разделов, ink/muted — текст, accent/accent_ink — кнопки, dark/dark_ink — тёмные
# разделы и тёмная шапка, accent2 — второй, декоративный цвет (узоры, метки). Контраст текста — не ниже 4,5 (проверка
# sites1103_test); где акцент на фоне светлый (жёлтый на бетоне), ссылки рендер темнит сам (accent_text).
PALETTES = {
    "pistachio": {"title": "Фисташка", "bg": "#F3F5EC", "surface": "#E5EAD9", "ink": "#2A251E", "muted": "#5E5A4E", "accent": "#3D7449",
                  "accent_ink": "#FFFFFF", "dark": "#2A251E", "dark_ink": "#F3F5EC", "accent2": "#C79A62", "line": "#D3DAC4"},
    "espresso": {"title": "Эспрессо", "bg": "#1E1613", "surface": "#2A1F1A", "ink": "#F3E7DA", "muted": "#C2AE9A", "accent": "#E0A75E",
                 "accent_ink": "#1E1613", "dark": "#120D0B", "dark_ink": "#F3E7DA", "accent2": "#8FA37A", "line": "#3B2D26"},
    "plum": {"title": "Слива", "bg": "#FBF6F5", "surface": "#F3E6E8", "ink": "#3A1E2D", "muted": "#735969", "accent": "#9C3866",
             "accent_ink": "#FFFFFF", "dark": "#3A1E2D", "dark_ink": "#FBF6F5", "accent2": "#D9A28F", "line": "#EAD7DC"},
    "navy": {"title": "Морской", "bg": "#FFFFFF", "surface": "#F1F3F7", "ink": "#14213D", "muted": "#545F73", "accent": "#1F3A68",
             "accent_ink": "#FFFFFF", "dark": "#14213D", "dark_ink": "#FFFFFF", "accent2": "#A88A4F", "line": "#DCE1EA"},
    "ultramarine": {"title": "Ультрамарин", "bg": "#F6F7FC", "surface": "#E8EBFB", "ink": "#171A35", "muted": "#555B7B", "accent": "#3F4FF0",
                    "accent_ink": "#FFFFFF", "dark": "#171A35", "dark_ink": "#F6F7FC", "accent2": "#FFC83D", "line": "#D8DDF6"},
    "tomato": {"title": "Томат", "bg": "#FFFFFF", "surface": "#F5F1EA", "ink": "#26221E", "muted": "#68625A", "accent": "#C4421E",
               "accent_ink": "#FFFFFF", "dark": "#26221E", "dark_ink": "#FFFFFF", "accent2": "#2E6B5E", "line": "#E8E1D6"},
    "graphite": {"title": "Графит", "bg": "#16171A", "surface": "#1F2125", "ink": "#ECE8E1", "muted": "#A39F97", "accent": "#E6D9BF",
                 "accent_ink": "#16171A", "dark": "#0E0F11", "dark_ink": "#ECE8E1", "accent2": "#8A9A86", "line": "#2E3035"},
    "mint": {"title": "Мята", "bg": "#F4FAF9", "surface": "#E2F0EE", "ink": "#0F3A41", "muted": "#4A6A6E", "accent": "#0A7275",
             "accent_ink": "#FFFFFF", "dark": "#0F3A41", "dark_ink": "#F4FAF9", "accent2": "#F0A257", "line": "#CDE3E0"},
    "sun": {"title": "Солнце", "bg": "#FFE14A", "surface": "#FFEE95", "ink": "#1C1A3A", "muted": "#45415F", "accent": "#1C1A3A",
            "accent_ink": "#FFE14A", "dark": "#1C1A3A", "dark_ink": "#FFE14A", "accent2": "#E8395E", "line": "#E9CB36"},
    "ice": {"title": "Лёд", "bg": "#FFFFFF", "surface": "#F0F4F8", "ink": "#0F2133", "muted": "#536273", "accent": "#087A5A",
            "accent_ink": "#FFFFFF", "dark": "#0F2133", "dark_ink": "#FFFFFF", "accent2": "#5B6CFF", "line": "#DFE6EE"},
    "sage": {"title": "Шалфей", "bg": "#EDF0E7", "surface": "#E0E6D8", "ink": "#263026", "muted": "#56614F", "accent": "#4A6A4A",
             "accent_ink": "#FFFFFF", "dark": "#263026", "dark_ink": "#EDF0E7", "accent2": "#C08A55", "line": "#CFD7C5"},
    "concrete": {"title": "Бетон", "bg": "#F2F2EF", "surface": "#E5E5E0", "ink": "#1D2125", "muted": "#565B60", "accent": "#F2B705",
                 "accent_ink": "#1D2125", "dark": "#1D2125", "dark_ink": "#F2F2EF", "accent2": "#2F5D8C", "line": "#D6D6D0"},
    "berry": {"title": "Ягода", "bg": "#FFF7F3", "surface": "#FCE8E1", "ink": "#33141E", "muted": "#6E4B55", "accent": "#B8234A",
              "accent_ink": "#FFFFFF", "dark": "#33141E", "dark_ink": "#FFF7F3", "accent2": "#F2B84B", "line": "#F2D6CD"},
    "night": {"title": "Ночь", "bg": "#101626", "surface": "#182036", "ink": "#E8ECF6", "muted": "#A3ACC2", "accent": "#8EA2FF",
              "accent_ink": "#101626", "dark": "#0A0F1C", "dark_ink": "#E8ECF6", "accent2": "#F5C26B", "line": "#252F4A"},
}
COLOR_KEYS = ("bg", "surface", "ink", "muted", "accent", "accent_ink", "dark", "dark_ink", "accent2", "line")

# ---------- шрифты ----------
# Вшитые (OFL, лежат в ui/assets/fonts, на опубликованный сайт уходят только нужные): Lora, Manrope, Unbounded —
# у всех есть кириллица. Остальное — системные стеки (ничего не грузится).
SANS = '"Manrope", system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif'
SYS = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
SERIF_SYS = 'Georgia, "Times New Roman", "PT Serif", Times, serif'
FONTS = {
    "warm": {"title": "Тёплый", "sub": "засечки Lora + Manrope", "head": '"Lora", Georgia, serif', "body": SANS, "hw": 600, "track": "-0.01em",
             "files": ["lora", "manrope"]},
    "editorial": {"title": "Журнальный", "sub": "Lora курсивом", "head": '"Lora", Georgia, serif', "body": '"Lora", Georgia, serif', "hw": 500,
                  "track": "-0.015em", "italic": True, "files": ["lora", "lora-italic"]},
    "strict": {"title": "Строгий", "sub": "Manrope, плотный", "head": SANS, "body": SANS, "hw": 800, "track": "-0.03em", "files": ["manrope"]},
    "bold": {"title": "Смелый", "sub": "Unbounded + Manrope", "head": '"Unbounded", ' + SANS, "body": SANS, "hw": 600, "track": "-0.01em",
             "scale": .84, "files": ["unbounded", "manrope"]},
    "classic": {"title": "Классический", "sub": "Georgia + системный", "head": SERIF_SYS, "body": SYS, "hw": 700, "track": "0", "files": []},
    "light": {"title": "Лёгкий", "sub": "системный, без загрузки", "head": SYS, "body": SYS, "hw": 700, "track": "-0.02em", "files": []},
}
# файлы шрифтов: (имя на сайте, файл в ui/assets/fonts, семейство, стиль, unicode-range)
_CYR = "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116"
_LAT = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, "
        "U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD")
FONT_FILES = {
    "lora": [("lora-cyr.woff2", "lora-cyrillic-wght-normal.woff2", "Lora", "normal", _CYR),
             ("lora-lat.woff2", "lora-latin-wght-normal.woff2", "Lora", "normal", _LAT)],
    "lora-italic": [("lora-cyr-i.woff2", "lora-cyrillic-wght-italic.woff2", "Lora", "italic", _CYR),
                    ("lora-lat-i.woff2", "lora-latin-wght-italic.woff2", "Lora", "italic", _LAT)],
    "manrope": [("manrope-cyr.woff2", "manrope-cyrillic-wght-normal.woff2", "Manrope", "normal", _CYR),
                ("manrope-lat.woff2", "manrope-latin-wght-normal.woff2", "Manrope", "normal", _LAT)],
    "unbounded": [("unbounded-cyr.woff2", "unbounded-cyrillic-wght-normal.woff2", "Unbounded", "normal", _CYR),
                  ("unbounded-lat.woff2", "unbounded-latin-wght-normal.woff2", "Unbounded", "normal", _LAT)],
}
RADII = {"sharp": {"title": "Строгие углы", "r": 2, "btn": 2}, "soft": {"title": "Мягкие", "r": 12, "btn": 10},
         "round": {"title": "Круглые", "r": 26, "btn": 999}}
MENUS = {"top": "Сверху", "center": "По центру", "burger": "Кнопкой «меню»", "side": "Сбоку"}
HEADERS = {"light": "Светлая шапка", "dark": "Тёмная шапка", "accent": "Шапка цвета акцента"}

# ---------- знаки для логотипа ----------
# 24×24, линия currentColor 1.8 — в логотипе, у преимуществ, на узорах вместо фото. Только наши — на сайт не попадает
# чужой SVG (свой рисунок из «Художника» — через очистку, sites.clean_svg).
MARKS = {
    "cup": ("Чашка", '<path d="M4 9h12v4a6 6 0 0 1-12 0z"/><path d="M16 10h1.5a2.5 2.5 0 0 1 0 5H16"/><path d="M8 3.2c-.7.9-.7 1.8 0 2.6M12 3.2c-.7.9-.7 1.8 0 2.6"/><path d="M5 21h10"/>'),
    "cloche": ("Блюдо", '<path d="M3 17.5h18"/><path d="M5 17.5a7 7 0 0 1 14 0"/><path d="M12 10.5V8.8"/><circle cx="12" cy="7.6" r="1.2"/><path d="M6 20.5h12"/>'),
    "croissant": ("Выпечка", '<path d="M3.5 15.5c1.5-6 6-9.5 8.5-9.5s7 3.5 8.5 9.5c-2 1.2-4 .6-5-1l-1.5 2.5c-1 .8-3 .8-4 0L8.5 14.5c-1 1.6-3 2.2-5 1z"/><path d="M9 7.6l1.6 6.4M15 7.6l-1.6 6.4"/>'),
    "scissors": ("Ножницы", '<circle cx="6" cy="18" r="2.6"/><circle cx="18" cy="18" r="2.6"/><path d="M7.8 16 17 4M16.2 16 7 4"/>'),
    "mirror": ("Зеркало", '<ellipse cx="12" cy="9.5" rx="5.5" ry="6.5"/><path d="M12 16v5M8.5 21h7"/><path d="M9.5 7.5a3 3 0 0 1 2-2"/>'),
    "lotus": ("Лотос", '<path d="M12 20c-4.5 0-8.5-3-8.5-8 3.2 0 6.4 2 8.5 5 2.1-3 5.3-5 8.5-5 0 5-4 8-8.5 8z"/><path d="M12 17c-2-3-2-8.5 0-12.5 2 4 2 9.5 0 12.5z"/>'),
    "scales": ("Весы", '<path d="M12 4v16M8 20h8M5 7h14"/><path d="M5 7l-3 6.5a3 3 0 0 0 6 0zM19 7l-3 6.5a3 3 0 0 0 6 0z"/>'),
    "column": ("Колонна", '<path d="M3.5 8 12 3.5 20.5 8z"/><path d="M5 10.5h14M4 20.5h16M7 10.5v8M12 10.5v8M17 10.5v8"/>'),
    "book": ("Книга", '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v14H6.5A1.5 1.5 0 0 0 5 18.5z"/><path d="M5 18.5A1.5 1.5 0 0 0 6.5 20H19"/><path d="M9 7h6"/>'),
    "cap": ("Шапочка выпускника", '<path d="M2 9.5 12 4.5l10 5-10 5z"/><path d="M6 11.5v4.5c0 1.6 3 3 6 3s6-1.4 6-3v-4.5"/><path d="M22 9.5v5"/>'),
    "bag": ("Сумка", '<path d="M5 8h14l-1 12.5H6z"/><path d="M9 10V6.5a3 3 0 0 1 6 0V10"/>'),
    "tag": ("Ценник", '<path d="M3.5 3.5h7.5l9.5 9.5-7.5 7.5-9.5-9.5z"/><circle cx="8" cy="8" r="1.5"/>'),
    "camera": ("Фотоаппарат", '<path d="M3 8h4l2-3h6l2 3h4v11H3z"/><circle cx="12" cy="13" r="3.6"/>'),
    "frame": ("Рамка", '<rect x="3.5" y="3.5" width="17" height="17" rx="1"/><path d="M3.5 16l5-5 4 4 2.5-2.5 5.5 5.5"/><circle cx="15.5" cy="8.5" r="1.5"/>'),
    "heart": ("Сердце с пульсом", '<path d="M12 20s-8-4.6-8-10.2A4.4 4.4 0 0 1 12 7a4.4 4.4 0 0 1 8 2.8C20 15.4 12 20 12 20z"/><path d="M6.5 12.5h3l1.5-2.5 2 5 1.5-2.5h3"/>'),
    "plus": ("Медицинский крест", '<path d="M9.5 3.5h5v6h6v5h-6v6h-5v-6h-6v-5h6z"/>'),
    "tooth": ("Зуб", '<path d="M7.5 3.5c-3 0-4.2 2.8-3.2 5.8.6 1.9 1 3 1.3 5.7.3 3 1 5.5 2.3 5.5 1.6 0 1.7-4.8 4.1-4.8s2.5 4.8 4.1 4.8c1.3 0 2-2.5 2.3-5.5.3-2.7.7-3.8 1.3-5.7 1-3-.2-5.8-3.2-5.8-2 0-2.6 1-4.5 1s-2.5-1-4.5-1z"/>'),
    "paw": ("Лапа", '<circle cx="6.5" cy="10.5" r="1.8"/><circle cx="10" cy="6.5" r="1.8"/><circle cx="14.5" cy="6.5" r="1.8"/><circle cx="18" cy="10.5" r="1.8"/><path d="M12 12c-3 0-5.5 3.5-5.5 5.8 0 1.6 1.4 2.2 2.8 2.2h5.6c1.4 0 2.7-.6 2.7-2.2 0-2.3-2.6-5.8-5.6-5.8z"/>'),
    "ticket": ("Билет", '<path d="M3 5.5h18v4a2.5 2.5 0 0 0 0 5v4H3v-4a2.5 2.5 0 0 0 0-5z"/><path d="M15 6.5v2M15 11v2M15 15.5v2"/>'),
    "spark": ("Искра", '<path d="M12 3c.9 5 4 8.1 9 9-5 .9-8.1 4-9 9-.9-5-4-8.1-9-9 5-.9 8.1-4 9-9z"/>'),
    "mic": ("Микрофон", '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>'),
    "code": ("Код", '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>'),
    "cube": ("Куб", '<path d="M12 2.5 20.5 7.3v9.4L12 21.5 3.5 16.7V7.3z"/><path d="M3.5 7.3 12 12l8.5-4.7M12 12v9.5"/>'),
    "rocket": ("Ракета", '<path d="M12 21c-1.2-1.4-2-3-2-4.5h4c0 1.5-.8 3.1-2 4.5z"/><path d="M8.5 16.5C7 13 7.5 7 12 2.5c4.5 4.5 5 10.5 3.5 14z"/><circle cx="12" cy="9.5" r="1.8"/><path d="M8.3 12.5 5 15.5l.5 3 3-1.5M15.7 12.5l3.3 3-.5 3-3-1.5"/>'),
    "leaf": ("Лист", '<path d="M5 19C5 10 10 5 20 4c-1 10-6 15-15 15z"/><path d="M5 19 13.5 10.5"/>'),
    "pen": ("Перо", '<path d="M4 20l1.2-4.6L16 4.6a2 2 0 0 1 2.8 0l.6.6a2 2 0 0 1 0 2.8L8.6 18.8z"/><path d="M14 7l3 3"/>'),
    "home": ("Дом", '<path d="M3 11 12 4l9 7"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/>'),
    "wrench": ("Ключ", '<path d="M14.6 3.8a4.6 4.6 0 0 0-1.7 5.7L4.2 18.2a1.9 1.9 0 0 0 2.7 2.7l8.7-8.7a4.6 4.6 0 0 0 5.7-1.7l-2.9-.6-.6-2.9 2.6-1.6a4.6 4.6 0 0 0-5.8-1.6z"/>'),
    "brush": ("Кисть", '<path d="M19.5 3.5 10 13"/><path d="M10 13c-2.5-.5-5 1-5 4 0 1.5-.8 2.5-2 3 3.5 1.2 8 .5 8.6-3.3.2-1.4-.3-2.8-1.6-3.7z"/>'),
    "dumbbell": ("Гантель", '<path d="M3 10v4M6 7v10M18 7v10M21 10v4M6 12h12"/>'),
    "note": ("Нота", '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>'),
    "sun": ("Солнце", '<circle cx="12" cy="12" r="4"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/>'),
    "wave": ("Волны", '<path d="M2 9c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2M2 15c2.5 0 2.5-2 5-2s2.5 2 5 2 2.5-2 5-2 2.5 2 5 2"/>'),
    "flower": ("Цветок", '<circle cx="12" cy="9" r="2.2"/><path d="M12 6.8c0-2.5 3.6-2.5 3.2.3 2.6-1 3.7 2.4 1.2 3.2 2.4 1 1.3 4.4-1.2 3.3.4 2.8-3.2 2.8-3.2.3 0 2.5-3.6 2.5-3.2-.3-2.5 1.1-3.6-2.3-1.2-3.3-2.5-.8-1.4-4.2 1.2-3.2-.4-2.8 3.2-2.8 3.2-.3z"/><path d="M12 15.5V21M12 18.5c1.5-1.5 3-1.8 4.5-1.5"/>'),
    "chat": ("Разговор", '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>'),
    "pin": ("Метка", '<path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.4"/>'),
    "star": ("Звезда", '<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.8z"/>'),
    "check": ("Галочка", '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7L16.2 9.5"/>'),
    "clock": ("Часы", '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>'),
    "shield": ("Щит", '<path d="M12 3 4.5 6v6c0 4.5 3.2 7.8 7.5 9 4.3-1.2 7.5-4.5 7.5-9V6z"/><path d="M8.8 12l2.2 2.2 4.2-4.4"/>'),
    "truck": ("Доставка", '<path d="M2.5 6.5h11v9h-11zM13.5 9.5h4l3 3.2v2.8h-7"/><circle cx="6.5" cy="17.5" r="1.8"/><circle cx="17" cy="17.5" r="1.8"/>'),
    "gift": ("Подарок", '<path d="M4 11h16v9.5H4zM3 7.5h18V11H3zM12 7.5v13"/><path d="M12 7.5C10.5 4 7 3.5 7 5.8 7 7.2 9.5 7.5 12 7.5zM12 7.5c1.5-3.5 5-4 5-1.7 0 1.4-2.5 1.7-5 1.7z"/>'),
}
MARK_TITLES = {k: v[0] for k, v in MARKS.items()}
LOGO_STYLES = {"badge": "Знак в круге", "plain": "Знак и надпись", "mono": "Буква", "text": "Только надпись"}


def mark_svg(name, size=24, stroke=1.8, cls="mk"):
    """Знак набора inline-SVG (цвет — currentColor). Неизвестный — искра."""
    body = (MARKS.get(name) or MARKS["spark"])[1]
    return (f'<svg class="{cls}" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


# ---------- блоки ----------
# поле: (ключ, подпись, вид) — вид: line (строка), text (абзацы), image (картинка), link (куда ведёт кнопка), mark (знак),
# flag (галочка). items — список карточек: (поля, «Добавить …»). Схема уходит и в студию (формы), и модели (правка фразой).
_BTN = [("button", "Кнопка", "line"), ("button_to", "Куда ведёт кнопка", "link")]
BLOCKS = {
    "hero": {"title": "Обложка", "sub": "первый экран: кто вы и что предлагаете",
             "variants": {"split": "Текст и картинка", "center": "По центру", "poster": "Афиша", "photo": "Фото на весь экран"},
             "fields": [("title", "Заголовок", "line"), ("text", "Подзаголовок", "text"), ("note", "Строка внизу (адрес, часы, дата)", "line")]
             + _BTN + [("button2", "Вторая кнопка", "line"), ("button2_to", "Куда ведёт вторая", "link"), ("image", "Картинка", "image")]},
    "about": {"title": "О нас", "sub": "история, подход, главное о вас",
              "variants": {"text": "Текст", "split": "Текст и картинка", "facts": "Текст и факты"},
              "fields": [("title", "Заголовок", "line"), ("text", "Текст", "text"), ("image", "Картинка", "image")],
              "items": ([("title", "Факт", "line"), ("text", "Пояснение", "line")], "Добавить факт")},
    "services": {"title": "Услуги", "sub": "что вы делаете — карточками или списком",
                 "variants": {"cards": "Карточки", "list": "Список с ценами", "rows": "Крупные строки"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
                 "items": ([("title", "Услуга", "line"), ("text", "Описание", "text"), ("price", "Цена", "line"), ("mark", "Знак", "mark")], "Добавить услугу")},
    "prices": {"title": "Цены", "sub": "меню, прайс или тарифы",
               "variants": {"menu": "Меню с точками", "plans": "Тарифы колонками", "table": "Таблица"},
               "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")] + _BTN,
               "items": ([("group", "Раздел (необязательно)", "line"), ("title", "Название", "line"), ("text", "Описание", "line"),
                          ("price", "Цена", "line"), ("featured", "Выделить", "flag")], "Добавить позицию")},
    "features": {"title": "Преимущества", "sub": "почему выбирают вас",
                 "variants": {"icons": "Со знаками", "big": "Крупно", "split": "Заголовок слева"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
                 "items": ([("title", "Преимущество", "line"), ("text", "Пояснение", "text"), ("mark", "Знак", "mark")], "Добавить")},
    "steps": {"title": "Как мы работаем", "sub": "шаги по порядку",
              "variants": {"line": "В ряд", "list": "Столбиком"},
              "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
              "items": ([("title", "Шаг", "line"), ("text", "Пояснение", "text")], "Добавить шаг")},
    "gallery": {"title": "Галерея", "sub": "фото работ, интерьера, товаров",
                "variants": {"grid": "Сетка", "mosaic": "Мозаика", "strip": "Лента"},
                "fields": [("title", "Заголовок", "line"), ("text", "Подпись", "text")],
                "items": ([("image", "Фото", "image"), ("caption", "Подпись", "line")], "Добавить фото")},
    "products": {"title": "Товары", "sub": "витрина с ценами",
                 "variants": {"grid": "Сетка", "list": "Списком"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")] + _BTN,
                 "items": ([("title", "Товар", "line"), ("text", "Описание", "text"), ("price", "Цена", "line"), ("image", "Фото", "image")], "Добавить товар")},
    "schedule": {"title": "Программа", "sub": "расписание события или курса",
                 "variants": {"agenda": "По времени", "days": "По дням"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
                 "items": ([("time", "Время или день", "line"), ("title", "Что", "line"), ("text", "Подробнее", "text")], "Добавить пункт")},
    "reviews": {"title": "Отзывы", "sub": "только настоящие — от ваших клиентов",
                "variants": {"quotes": "Цитаты", "cards": "Карточки"},
                "fields": [("title", "Заголовок", "line")],
                "items": ([("text", "Отзыв", "text"), ("name", "Имя", "line"), ("role", "Кто (необязательно)", "line")], "Добавить отзыв")},
    "team": {"title": "Команда", "sub": "люди, которые работают",
             "variants": {"cards": "Карточки", "row": "В ряд"},
             "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
             "items": ([("name", "Имя", "line"), ("role", "Должность", "line"), ("text", "О человеке", "text"), ("image", "Фото", "image")], "Добавить человека")},
    "faq": {"title": "Вопросы и ответы", "sub": "частые вопросы",
            "variants": {"list": "Списком", "two": "В две колонки"},
            "fields": [("title", "Заголовок", "line")],
            "items": ([("q", "Вопрос", "line"), ("a", "Ответ", "text")], "Добавить вопрос")},
    "links": {"title": "Ссылки", "sub": "соцсети, мессенджеры, площадки",
              "variants": {"buttons": "Кнопками", "list": "Списком"},
              "fields": [("title", "Заголовок", "line")],
              "items": ([("title", "Название", "line"), ("href", "Адрес (https://…)", "line")], "Добавить ссылку")},
    "cta": {"title": "Призыв", "sub": "полоса с главной кнопкой",
            "variants": {"band": "Полоса", "card": "Карточка"},
            "fields": [("title", "Заголовок", "line"), ("text", "Текст", "text")] + _BTN},
    "text": {"title": "Текст", "sub": "свободный раздел",
             "variants": {"plain": "Колонка", "wide": "Крупно"},
             "fields": [("title", "Заголовок", "line"), ("text", "Текст", "text")]},
    "contacts": {"title": "Контакты", "sub": "адрес, телефон, часы, карта",
                 "variants": {"split": "С картой", "band": "Полосой"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Как добраться", "text")]},
    "lead": {"title": "Заявка", "sub": "форма: имя и телефон — заявка придёт вам",
             "variants": {"split": "Текст и форма", "card": "Карточка"},
             "fields": [("title", "Заголовок", "line"), ("text", "Текст", "text"), ("button", "Кнопка", "line"),
                        ("ask_message", "Поле «Комментарий»", "flag"), ("thanks", "Ответ после отправки", "line")]},
}
TONES = {"base": "Основной фон", "alt": "Второй фон", "dark": "Тёмный", "accent": "Цвет акцента"}
CONTACT_KEYS = {"phone": "Телефон", "email": "Почта", "address": "Адрес", "hours": "Часы работы", "telegram": "Telegram",
                "whatsapp": "WhatsApp", "vk": "ВКонтакте", "max": "MAX", "instagram": "Instagram", "site": "Другой сайт"}


def blk(t, variant, tone="base", nav="", **f):
    d = {"type": t, "variant": variant, "tone": tone}
    if nav:
        d["nav"] = nav
    d.update(f)
    return d


def it(**f):
    return f


# ---------- шаблоны ----------
# Каждый: название, для чего, palette, fonts, radius, menu, header, logo (знак, вид), art (узор вместо фото), contacts
# (заглушки), pages — страницы с блоками. Цены и описания — правдоподобные заготовки; людей и отзывов нет.
TEMPLATES = {
    "coffee": {
        "title": "Кофейня, ресторан", "sub": "меню на точках, фисташковый и тёплые засечки", "palette": "pistachio", "fonts": "warm",
        "radius": "soft", "menu": "center", "header": "light", "art": "beans", "logo": {"mark": "cup", "style": "badge"},
        "name": "Зерно", "tagline": "кофейня у дома",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Садовая, 5", "hours": "Пн–Пт 8:00–21:00, Сб–Вс 9:00–22:00"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "poster", "base", title="Зерно", text="Кофе, который хочется пить медленно. Обжариваем сами, печём каждое утро.",
                note="ул. Садовая, 5 · каждый день с 8 утра", button="Посмотреть меню", button_to="#menu", button2="Забронировать стол", button2_to="lead"),
            blk("about", "split", "alt", nav="О нас", title="Маленькая кофейня с большим вниманием к чашке",
                text="Мы открылись, чтобы у района было место, где утром тепло и пахнет выпечкой. Зерно берём у знакомых обжарщиков, "
                     "молоко — фермерское, круассаны печём сами.\n\nЗаходите поработать с ноутбуком, встретиться с друзьями или просто "
                     "взять кофе с собой по дороге."),
            blk("prices", "menu", "base", nav="Меню", id="menu", title="Меню", text="Альтернативное молоко и сиропы — без доплаты.",
                items=[it(group="Кофе", title="Эспрессо", text="30 мл", price="150 ₽"), it(group="Кофе", title="Капучино", text="250 мл", price="240 ₽"),
                       it(group="Кофе", title="Флэт уайт", text="двойной эспрессо и молоко", price="260 ₽"),
                       it(group="Кофе", title="Раф на халве", text="фирменный", price="290 ₽", featured=True),
                       it(group="Выпечка", title="Круассан", text="сливочный, утром ещё тёплый", price="180 ₽"),
                       it(group="Выпечка", title="Синнабон", text="с корицей и сливочным сыром", price="220 ₽"),
                       it(group="Завтраки", title="Сырники", text="со сметаной и ягодами", price="320 ₽"),
                       it(group="Завтраки", title="Тост с авокадо", text="яйцо пашот, микрозелень", price="390 ₽")]),
            blk("features", "icons", "alt", title="Почему к нам возвращаются", items=[
                it(title="Свежая обжарка", text="Зерно не старше двух недель", mark="cup"),
                it(title="Своя выпечка", text="Печём каждое утро с 7:00", mark="croissant"),
                it(title="Тихо и уютно", text="Розетки у каждого стола и быстрый вайфай", mark="home"),
                it(title="С собой", text="Закажите заранее — заберёте без очереди", mark="bag")]),
            blk("gallery", "mosaic", "base", nav="Фото", title="Как у нас", items=[it(caption="Зал у окна"), it(caption="Утренняя выпечка"),
                                                                                  it(caption="Латте-арт"), it(caption="Летняя веранда")]),
            blk("lead", "split", "dark", nav="Бронь", title="Забронировать стол", text="Оставьте имя и телефон — перезвоним и подтвердим бронь.",
                button="Забронировать", ask_message=True, thanks="Спасибо! Перезвоним в течение 15 минут."),
            blk("contacts", "split", "base", nav="Контакты", title="Как нас найти", text="Вход со двора, напротив булочной. Есть парковка для велосипедов."),
        ]}]},
    "salon": {
        "title": "Салон, мастер услуг", "sub": "арки, слива и мягкие формы", "palette": "plum", "fonts": "editorial", "radius": "round",
        "menu": "top", "header": "light", "art": "arches", "logo": {"mark": "lotus", "style": "plain"},
        "name": "Лепесток", "tagline": "студия красоты",
        "contacts": {"phone": "+7 900 000-00-00", "address": "пр. Мира, 12, 2 этаж", "hours": "Ежедневно 10:00–21:00", "telegram": "@lepestok_studio"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Ухоженность без спешки", text="Маникюр, брови и уход за лицом в светлой студии в центре. "
                "Стерильные инструменты, бережные мастера и чай, пока сохнет покрытие.",
                note="пр. Мира, 12 · ежедневно 10–21", button="Записаться", button_to="lead", button2="Цены", button2_to="#prices"),
            blk("services", "list", "alt", nav="Услуги", title="Услуги и цены", id="prices", items=[
                it(title="Маникюр с покрытием", text="снятие, обработка, гель-лак", price="от 2 200 ₽"),
                it(title="Педикюр", text="аппаратный, с покрытием", price="от 2 800 ₽"),
                it(title="Коррекция и окрашивание бровей", text="форма, хна или краска", price="1 500 ₽"),
                it(title="Ламинирование ресниц", text="с окрашиванием и уходом", price="2 500 ₽"),
                it(title="Уход за лицом", text="очищение, маска, массаж", price="от 3 000 ₽")]),
            blk("features", "big", "base", title="Почему нам доверяют", items=[
                it(title="Стерильно", text="Инструменты — через сухожар, крафт-пакеты вскрываем при вас", mark="shield"),
                it(title="Без спешки", text="На каждую процедуру — с запасом времени", mark="clock"),
                it(title="Носится долго", text="Покрытие держится три недели и больше", mark="spark")]),
            blk("gallery", "grid", "alt", nav="Работы", title="Работы мастеров", items=[it(caption="Нюдовый маникюр"), it(caption="Брови"),
                                                                                       it(caption="Френч"), it(caption="Студия"), it(caption="Педикюр"), it(caption="Уход")]),
            blk("steps", "line", "base", title="Как записаться", items=[it(title="Оставьте заявку", text="Или напишите в Telegram"),
                                                                       it(title="Выберем время", text="Подберём мастера и удобный час"),
                                                                       it(title="Приходите", text="Напомним о записи за день")]),
            blk("lead", "card", "accent", nav="Запись", title="Запишитесь онлайн", text="Перезвоним, подберём мастера и время.", button="Записаться",
                thanks="Спасибо! Скоро перезвоним."),
            blk("contacts", "band", "base", nav="Контакты", title="Ждём в студии", text="Вход с торца здания, второй этаж, домофон 12."),
        ]}]},
    "lawyer": {
        "title": "Юрист, консультант", "sub": "строгий синий, засечки и чёткие колонки", "palette": "navy", "fonts": "classic", "radius": "sharp",
        "menu": "top", "header": "dark", "art": "frames", "logo": {"mark": "scales", "style": "plain"},
        "name": "Право и дело", "tagline": "юридическая помощь бизнесу и людям",
        "contacts": {"phone": "+7 900 000-00-00", "email": "office@example.ru", "address": "ул. Ленина, 40, офис 305", "hours": "Пн–Пт 9:00–19:00"},
        "pages": [
            {"title": "Главная", "blocks": [
                blk("hero", "center", "base", title="Решаем юридические вопросы спокойно и по существу",
                    text="Договоры, споры, сопровождение бизнеса. Первая консультация — 30 минут, чтобы понять задачу и назвать стоимость.",
                    button="Получить консультацию", button_to="lead", button2="Позвонить", button2_to="phone"),
                blk("services", "rows", "alt", nav="Практики", title="Чем помогаем", items=[
                    it(title="Договоры", text="Составим и проверим договор, найдём риски до подписания", price="от 5 000 ₽"),
                    it(title="Судебные споры", text="Претензии, иски, представительство в суде", price="от 30 000 ₽"),
                    it(title="Сопровождение бизнеса", text="Абонентское обслуживание: вопросы — по звонку, документы — в срок", price="от 20 000 ₽ в месяц"),
                    it(title="Недвижимость", text="Проверка объекта и сделки, сопровождение покупки", price="от 15 000 ₽")]),
                blk("steps", "list", "base", nav="Как работаем", title="Как мы работаем", items=[
                    it(title="Консультация", text="Слушаем, задаём вопросы, изучаем документы"),
                    it(title="План и стоимость", text="Говорим, что можно сделать и сколько это стоит — до начала работы"),
                    it(title="Работа", text="Сообщаем о каждом шаге, документы — в общей папке"),
                    it(title="Результат", text="Отчёт о сделанном и рекомендации на будущее")]),
                blk("about", "facts", "alt", nav="О нас", title="О практике", text="Работаем с 2012 года. Ведём дела предпринимателей и частных клиентов, "
                    "отвечаем на звонки в рабочее время и называем стоимость заранее.",
                    items=[it(title="с 2012", text="года практики"), it(title="Фиксированная цена", text="за понятный объём работ"),
                           it(title="Конфиденциально", text="соглашение о неразглашении по запросу")]),
                blk("faq", "two", "base", nav="Вопросы", title="Частые вопросы", items=[
                    it(q="Сколько стоит консультация?", a="Первая — 30 минут — бесплатно. Дальше — по договорённости, стоимость называем заранее."),
                    it(q="Можно ли работать удалённо?", a="Да. Документы — по почте или в мессенджере, встречи — по видеосвязи."),
                    it(q="Работаете ли вы с другими городами?", a="Да, по всей России; в суды других регионов выезжаем по договорённости."),
                    it(q="Что взять на консультацию?", a="Все документы по делу: договоры, переписку, решения. Если не уверены — возьмите всё.")]),
                blk("lead", "split", "dark", nav="Консультация", title="Расскажите о задаче", text="Ответим в течение рабочего дня. Всё, что вы напишете, остаётся между нами.",
                    button="Отправить", ask_message=True, thanks="Спасибо! Ответим в течение рабочего дня."),
                blk("contacts", "split", "base", nav="Контакты", title="Офис", text="Бизнес-центр «Меридиан», третий этаж. Пропуск закажем заранее."),
            ]}]},
    "school": {
        "title": "Онлайн-школа, курсы", "sub": "ультрамарин, смелые заголовки и программа по неделям", "palette": "ultramarine", "fonts": "bold",
        "radius": "round", "menu": "top", "header": "light", "art": "dots", "logo": {"mark": "cap", "style": "badge"},
        "name": "Шаг вперёд", "tagline": "онлайн-курсы",
        "contacts": {"email": "hello@example.ru", "telegram": "@shag_school"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Научитесь вести соцсети бизнеса за 6 недель",
                text="Живые занятия, домашние задания с разбором и куратор, который отвечает в тот же день.",
                note="Старт потока — 1 декабря · онлайн", button="Записаться на курс", button_to="lead", button2="Программа", button2_to="#program"),
            blk("features", "icons", "alt", title="Что вы получите", items=[
                it(title="Практику", text="Каждую неделю — задание на своём проекте", mark="pen"),
                it(title="Разбор", text="Куратор смотрит каждую работу и пишет, что улучшить", mark="chat"),
                it(title="Записи", text="Все занятия остаются у вас навсегда", mark="book"),
                it(title="Сертификат", text="После защиты итогового проекта", mark="star")]),
            blk("schedule", "days", "base", nav="Программа", id="program", title="Программа", items=[
                it(time="Неделя 1", title="Стратегия", text="Цели, аудитория, позиционирование"),
                it(time="Неделя 2", title="Контент-план", text="Рубрики, частота, форматы"),
                it(time="Неделя 3", title="Тексты", text="Заголовки, структура поста, тон голоса"),
                it(time="Неделя 4", title="Визуал", text="Фото на телефон, обложки, шаблоны"),
                it(time="Неделя 5", title="Продвижение", text="Реклама, коллаборации, рост без накруток"),
                it(time="Неделя 6", title="Аналитика и защита", text="Цифры, выводы, итоговый проект")]),
            blk("prices", "plans", "alt", nav="Цены", title="Тарифы", items=[
                it(title="Самостоятельно", text="Записи занятий и задания", price="9 900 ₽"),
                it(title="С куратором", text="Разбор заданий и чат потока", price="19 900 ₽", featured=True),
                it(title="Лично", text="Три созвона с автором курса", price="34 900 ₽")], button="Выбрать тариф", button_to="lead"),
            blk("faq", "list", "base", nav="Вопросы", title="Вопросы", items=[
                it(q="Подойдёт ли курс новичку?", a="Да, начинаем с основ. Нужен только телефон и пара часов в неделю."),
                it(q="Можно ли оплатить частями?", a="Да, есть рассрочка без переплаты на 3 месяца."),
                it(q="Что, если не успею?", a="Записи и задания останутся у вас — можно догнать поток позже.")]),
            blk("lead", "card", "accent", nav="Запись", title="Оставьте заявку на курс", text="Пришлём программу и ответим на вопросы.",
                button="Записаться", thanks="Спасибо! Напишем вам сегодня."),
        ]}]},
    "shop": {
        "title": "Магазин-витрина", "sub": "товары с ценами, томатный акцент", "palette": "tomato", "fonts": "strict", "radius": "soft",
        "menu": "top", "header": "light", "art": "blocks", "logo": {"mark": "bag", "style": "badge"},
        "name": "Полка", "tagline": "вещи для дома",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ТЦ «Галерея», 1 этаж", "hours": "Ежедневно 10:00–22:00", "telegram": "@polka_shop"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Вещи, которые делают дом уютнее", text="Керамика, текстиль и свечи небольших мастерских. Доставка по городу — на следующий день.",
                button="Смотреть товары", button_to="#catalog", button2="Заказать", button2_to="lead"),
            blk("products", "grid", "alt", nav="Каталог", id="catalog", title="Сейчас в наличии", text="Нажмите «Заказать» — уточним наличие и доставку.",
                button="Заказать", button_to="lead", items=[
                    it(title="Кружка ручной работы", text="Керамика, 350 мл", price="1 200 ₽"),
                    it(title="Льняная скатерть", text="140×180 см, четыре цвета", price="3 900 ₽"),
                    it(title="Соевая свеча", text="Хвоя и дым, 40 часов", price="990 ₽"),
                    it(title="Плед из хлопка", text="130×170 см", price="4 500 ₽"),
                    it(title="Набор салфеток", text="Лён, 4 штуки", price="1 600 ₽"),
                    it(title="Ваза-бутылка", text="Матовая глазурь", price="2 300 ₽")]),
            blk("features", "split", "base", title="Покупать у нас просто", items=[
                it(title="Доставка завтра", text="По городу — бесплатно от 3 000 ₽", mark="truck"),
                it(title="Красиво упакуем", text="Подарочная упаковка — по просьбе, бесплатно", mark="gift"),
                it(title="Обмен 14 дней", text="Не подошло — заменим или вернём деньги", mark="check")]),
            blk("cta", "band", "dark", title="Ищете подарок?", text="Напишите, для кого и на какую сумму — соберём набор и пришлём фото.",
                button="Подобрать подарок", button_to="lead"),
            blk("lead", "split", "base", nav="Заказ", title="Оформить заказ", text="Напишите, что хотите заказать, — подтвердим наличие и время доставки.",
                button="Отправить заказ", ask_message=True, thanks="Спасибо! Скоро свяжемся, чтобы подтвердить заказ."),
            blk("contacts", "band", "alt", nav="Контакты", title="Магазин", text="Можно забрать заказ самим — в любой день с 10 до 22."),
        ]}]},
    "photo": {
        "title": "Портфолио, фотограф", "sub": "тёмная галерея, меню сбоку, журнальный курсив", "palette": "graphite", "fonts": "editorial",
        "radius": "sharp", "menu": "side", "header": "dark", "art": "frames", "logo": {"mark": "camera", "style": "text"},
        "name": "Анна Светлова", "tagline": "фотограф",
        "contacts": {"phone": "+7 900 000-00-00", "email": "photo@example.ru", "telegram": "@svetlova_photo"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "photo", "dark", title="Снимаю людей такими, какими их любят",
                text="Семейные и портретные съёмки, свадьбы. Москва и область, выезд в другие города.",
                button="Обсудить съёмку", button_to="lead", button2="Портфолио", button2_to="#works"),
            blk("gallery", "mosaic", "base", nav="Портфолио", id="works", title="Работы", items=[
                it(caption="Семья у моря"), it(caption="Портрет в мастерской"), it(caption="Свадьба в саду"),
                it(caption="Утро в городе"), it(caption="Лавстори"), it(caption="Детская съёмка")]),
            blk("prices", "plans", "alt", nav="Цены", title="Съёмки", items=[
                it(title="Портрет", text="1 час, 30 фото в обработке", price="8 000 ₽"),
                it(title="Семейная", text="2 часа, 60 фото, выезд", price="15 000 ₽", featured=True),
                it(title="Свадьба", text="весь день, 400+ фото, слайд-шоу", price="от 45 000 ₽")]),
            blk("about", "split", "base", nav="Обо мне", title="Обо мне",
                text="Снимаю двенадцать лет. Люблю естественный свет, живые эмоции и долгие прогулки на съёмках.\n\n"
                     "Помогу выбрать место и одежду, подскажу, как держаться в кадре, — даже если вы «не умеете фотографироваться»."),
            blk("lead", "card", "alt", nav="Связаться", title="Обсудим съёмку", text="Расскажите о дате и идее — отвечу в течение дня.",
                button="Отправить", ask_message=True, thanks="Спасибо! Отвечу в течение дня."),
            blk("links", "buttons", "base", title="Я в сети", items=[it(title="Telegram", href="https://t.me/"), it(title="ВКонтакте", href="https://vk.com/")]),
        ]}]},
    "clinic": {
        "title": "Клиника, врач", "sub": "спокойная мята, ясные блоки, запись в один шаг", "palette": "mint", "fonts": "strict", "radius": "soft",
        "menu": "top", "header": "light", "art": "rings", "logo": {"mark": "plus", "style": "badge"},
        "name": "Доктор рядом", "tagline": "семейная клиника",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Победы, 8", "hours": "Пн–Сб 8:00–20:00, Вс 9:00–15:00", "email": "info@example.ru"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Врачи, к которым приходят всей семьёй",
                text="Терапевт, педиатр, УЗИ и анализы в одном месте. Запись на сегодня — по телефону или онлайн.",
                note="ул. Победы, 8 · без выходных", button="Записаться к врачу", button_to="lead", button2="Позвонить", button2_to="phone"),
            blk("services", "cards", "alt", nav="Услуги", title="Направления", items=[
                it(title="Терапия", text="Приём, назначения, справки", mark="heart"), it(title="Педиатрия", text="Дети от рождения до 18 лет", mark="sun"),
                it(title="УЗИ", text="Экспертный аппарат, результат сразу", mark="wave"), it(title="Анализы", text="Сдать с 8 утра, результат — на почту", mark="check"),
                it(title="Стоматология", text="Лечение, гигиена, детский приём", mark="tooth"), it(title="Справки", text="Для бассейна, работы, водительские", mark="book")]),
            blk("prices", "table", "base", nav="Цены", title="Цены", text="Полный прайс — по телефону.", items=[
                it(title="Приём терапевта", price="2 000 ₽"), it(title="Приём педиатра", price="2 200 ₽"),
                it(title="УЗИ брюшной полости", price="2 500 ₽"), it(title="Общий анализ крови", price="450 ₽")]),
            blk("team", "cards", "alt", nav="Врачи", title="Врачи", text="Расскажите о врачах — фото, опыт, специализация.", items=[
                it(name="Имя врача", role="Терапевт, стаж … лет", todo=True), it(name="Имя врача", role="Педиатр, стаж … лет", todo=True),
                it(name="Имя врача", role="Врач УЗИ, стаж … лет", todo=True)]),
            blk("faq", "list", "base", nav="Вопросы", title="Вопросы", items=[
                it(q="Нужна ли запись?", a="Лучше записаться: так вас примут вовремя. Без записи — если у врача есть окно."),
                it(q="Можно ли по ОМС?", a="Мы работаем платно; по ДМС — с большинством страховых, уточните по телефону.")]),
            blk("lead", "split", "dark", nav="Запись", title="Запись к врачу", text="Оставьте телефон — администратор перезвонит и подберёт время.",
                button="Записаться", ask_message=True, thanks="Спасибо! Администратор перезвонит в течение 15 минут."),
            blk("contacts", "split", "base", nav="Контакты", title="Как добраться", text="Остановка «Площадь Победы», 2 минуты пешком. Своя парковка."),
        ]}]},
    "event": {
        "title": "Мероприятие", "sub": "афиша на жёлтом, большая дата, программа по часам", "palette": "sun", "fonts": "bold", "radius": "sharp",
        "menu": "burger", "header": "light", "art": "stripes", "logo": {"mark": "ticket", "style": "text"},
        "name": "Осенний маркет", "tagline": "ярмарка мастеров",
        "contacts": {"address": "Лофт «Фабрика», ул. Заводская, 3", "telegram": "@autumn_market", "email": "market@example.ru"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "poster", "base", title="Осенний маркет", text="Сто мастеров, еда, музыка и мастер-классы для детей. Вход свободный.",
                note="23–24 ноября · Лофт «Фабрика»", button="Зарегистрироваться", button_to="lead", button2="Программа", button2_to="#program"),
            blk("schedule", "agenda", "dark", nav="Программа", id="program", title="Программа", items=[
                it(time="11:00", title="Открытие маркета", text="Ряды мастеров и фудкорт"), it(time="13:00", title="Мастер-класс по керамике", text="Для детей от 6 лет"),
                it(time="15:00", title="Лекция «Как начать своё дело»", text="Малый зал"), it(time="17:00", title="Живая музыка", text="Акустический концерт"),
                it(time="20:00", title="Закрытие", text="Розыгрыш призов от участников")]),
            blk("about", "facts", "base", nav="О маркете", title="Что будет", text="Два дня — сто мастеров: керамика, украшения, одежда, сладости. "
                "Можно купить подарки к праздникам и познакомиться с теми, кто их делает.",
                items=[it(title="100", text="мастеров"), it(title="2 дня", text="23 и 24 ноября"), it(title="0 ₽", text="вход свободный")]),
            blk("faq", "two", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="Можно ли с детьми?", a="Конечно: для детей — мастер-классы и игровая зона."),
                it(q="Как стать участником?", a="Оставьте заявку и выберите «Хочу участвовать» в комментарии."),
                it(q="Есть ли парковка?", a="Да, у лофта, бесплатно.")]),
            blk("lead", "card", "accent", nav="Регистрация", title="Зарегистрироваться", text="Пришлём напоминание и карту маркета.",
                button="Я приду", ask_message=True, thanks="Вы зарегистрированы! Пришлём напоминание за день."),
            blk("contacts", "split", "base", nav="Как добраться", title="Место", text="5 минут от метро «Заводская», вход с улицы через арку."),
        ]}]},
    "startup": {
        "title": "IT, стартап, сервис", "sub": "чистый белый, сетка и изумрудный акцент", "palette": "ice", "fonts": "strict", "radius": "soft",
        "menu": "top", "header": "light", "art": "grid", "logo": {"mark": "cube", "style": "badge"},
        "name": "Ладья", "tagline": "учёт заказов для малого бизнеса",
        "contacts": {"email": "team@example.ru", "telegram": "@ladya_app"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Все заказы — в одном окне, а не в пяти чатах",
                text="Ладья собирает заявки из сайта, мессенджеров и звонков, напоминает о сроках и считает выручку.",
                button="Попробовать бесплатно", button_to="lead", button2="Как это работает", button2_to="#how"),
            blk("features", "big", "alt", nav="Возможности", title="Что умеет", items=[
                it(title="Заявки отовсюду", text="Сайт, Telegram, WhatsApp и звонки — в общей ленте", mark="chat"),
                it(title="Напоминания", text="Сроки и оплаты не теряются", mark="clock"),
                it(title="Отчёты", text="Выручка и средний чек за день, неделю, месяц", mark="cube")]),
            blk("steps", "line", "base", nav="Как это работает", id="how", title="Как начать", items=[
                it(title="Регистрация", text="Две минуты, без карты"), it(title="Подключите каналы", text="Сайт и мессенджеры — по подсказкам"),
                it(title="Работайте", text="Заявки приходят сами")]),
            blk("prices", "plans", "alt", nav="Тарифы", title="Тарифы", items=[
                it(title="Старт", text="1 сотрудник, 100 заказов в месяц", price="0 ₽"),
                it(title="Команда", text="до 10 сотрудников, без ограничений", price="1 490 ₽/мес", featured=True),
                it(title="Сеть", text="несколько точек, API, отчёты", price="по запросу")], button="Начать", button_to="lead"),
            blk("faq", "list", "base", nav="Вопросы", title="Вопросы", items=[
                it(q="Где хранятся данные?", a="На серверах в России, с ежедневной резервной копией."),
                it(q="Можно ли перенести заказы из таблицы?", a="Да, загрузите файл Excel — перенесём сами.")]),
            blk("lead", "split", "dark", nav="Демо", title="Покажем на ваших данных", text="Оставьте почту или телефон — проведём демо за 20 минут.",
                button="Записаться на демо", thanks="Спасибо! Напишем, чтобы договориться о времени."),
        ]}]},
    "personal": {
        "title": "Личная страница", "sub": "одна колонка, шалфей и спокойные засечки", "palette": "sage", "fonts": "warm", "radius": "round",
        "menu": "burger", "header": "light", "art": "arches", "logo": {"mark": "leaf", "style": "mono"},
        "name": "Мария Лесная", "tagline": "психолог, консультации онлайн",
        "contacts": {"email": "maria@example.ru", "telegram": "@maria_lesnaya"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "center", "base", title="Мария Лесная", text="Психолог. Помогаю пережить перемены и вернуть опору — бережно и без оценок.",
                note="Консультации онлайн, 50 минут", button="Записаться", button_to="lead", button2="Обо мне", button2_to="#about"),
            blk("about", "text", "alt", nav="Обо мне", id="about", title="Обо мне", text="Восемь лет работаю с тревогой, выгоранием и кризисами. "
                "Сама прошла долгую терапию и знаю, как непросто решиться на первую встречу.\n\nНа первой консультации мы познакомимся, "
                "обсудим запрос и решим, подхожу ли я вам."),
            blk("services", "list", "base", nav="Форматы", title="Форматы", items=[
                it(title="Консультация", text="50 минут, онлайн", price="3 500 ₽"),
                it(title="Пакет из 5 встреч", text="со скидкой", price="15 000 ₽")]),
            blk("links", "buttons", "alt", title="Где меня найти", items=[it(title="Telegram-канал", href="https://t.me/"),
                                                                        it(title="Статьи", href="https://example.ru/")]),
            blk("lead", "card", "base", nav="Запись", title="Записаться на консультацию", text="Напишите пару слов о запросе — отвечу сама.",
                button="Отправить", ask_message=True, thanks="Спасибо! Отвечу в течение дня."),
        ]}]},
    "repair": {
        "title": "Ремонт и стройка", "sub": "бетон и сигнальный жёлтый, шаги и цены", "palette": "concrete", "fonts": "bold", "radius": "sharp",
        "menu": "top", "header": "dark", "art": "blocks", "logo": {"mark": "wrench", "style": "badge"},
        "name": "Ровно", "tagline": "ремонт квартир под ключ",
        "contacts": {"phone": "+7 900 000-00-00", "hours": "Ежедневно 8:00–20:00", "whatsapp": "+7 900 000-00-00"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Ремонт по смете, которая не растёт",
                text="Квартиры и дома под ключ. Фиксируем цену в договоре и сдаём в срок — или платим неустойку.",
                note="Выезд замерщика — бесплатно", button="Рассчитать ремонт", button_to="lead", button2="Позвонить", button2_to="phone"),
            blk("services", "cards", "alt", nav="Услуги", title="Что делаем", items=[
                it(title="Квартира под ключ", text="От демонтажа до уборки", price="от 9 000 ₽/м²", mark="home"),
                it(title="Ванная", text="Плитка, сантехника, тёплый пол", price="от 120 000 ₽", mark="wave"),
                it(title="Электрика", text="Замена проводки, щиток", price="от 1 500 ₽/точка", mark="spark"),
                it(title="Отделка", text="Шпаклёвка, покраска, обои", price="от 600 ₽/м²", mark="brush")]),
            blk("steps", "line", "base", nav="Как работаем", title="Как работаем", items=[
                it(title="Замер", text="Бесплатно, в удобное время"), it(title="Смета", text="Подробная, по каждой позиции"),
                it(title="Договор", text="Цена и сроки фиксируются"), it(title="Ремонт", text="Фотоотчёт каждый день"),
                it(title="Сдача", text="Гарантия 2 года")]),
            blk("gallery", "grid", "alt", nav="Работы", title="Наши объекты", items=[it(caption="Кухня-гостиная"), it(caption="Ванная"),
                                                                                   it(caption="Спальня"), it(caption="Прихожая")]),
            blk("lead", "split", "dark", nav="Расчёт", title="Рассчитаем стоимость", text="Опишите квартиру и что нужно сделать — пришлём предварительную смету.",
                button="Получить смету", ask_message=True, thanks="Спасибо! Перезвоним сегодня."),
            blk("contacts", "band", "base", nav="Контакты", title="Связаться", text="Работаем по городу и области."),
        ]}]},
}
TEMPLATE_ORDER = ["coffee", "salon", "lawyer", "school", "shop", "photo", "clinic", "event", "startup", "personal", "repair"]

# слова в описании -> шаблон (первый подошедший; ничего — «личная страница», если о человеке, иначе «стартап»)
KIND_WORDS = [
    ("coffee", r"коф|кафе|ресторан|\bбар\b|пекарн|пицц|суши|столов|кондитер|бургер|чайн|булочн|кулинар|доставк\w* еды|гастро|бистро|кухн"),
    ("salon", r"салон|маникюр|педикюр|парикмах|барбер|косметолог|массаж|бров|ресниц|красот|\bспа\b|ногт|визаж|эпиляц|тату"),
    ("clinic", r"клиник|врач|стоматолог|медицин|ветеринар|ветклиник|доктор|здоровь|поликлин|медцентр|анализ|лечени"),
    ("lawyer", r"юрист|юридич|адвокат|консалтинг|бухгалт|нотари|финансов|страхов|риелтор|недвижимост|аудит|налог"),
    ("school", r"школ|курс|обучени|репетитор|урок|академи|тренинг|вебинар|занятия|преподава|учител|детск\w* центр|развивашк"),
    ("event", r"мероприят|конференц|фестивал|концерт|свадьб|праздник|вечеринк|митап|выставк|ярмарк|маркет|форум|турнир"),
    ("photo", r"фотограф|портфолио|дизайнер|художни|видеограф|иллюстрат|архитект|фотостуди|видеосъ"),
    ("shop", r"магазин|витрин|товар|интернет-магазин|\bшоп|одежд|цвет(?:ы|ов|очн)|букет|флорист|подарк|сувенир|украшени|мебел\w* на заказ|каталог"),
    ("repair", r"ремонт|стро(?:ит|йк)|сантехник|электрик|отделк|муж на час|мастер на час|клининг|уборк|шиномонтаж|автосервис|окна|потолк|кровл"),
    ("startup", r"стартап|\bit\b|сервис|приложени|программ|saas|разработ|платформ|digital|продукт|айти|бот"),
    ("personal", r"личн|о себе|резюме|блогер|визитк|автор|эксперт|психолог|коуч|тренер|наставник|портфолио"),
]


def pick_template(text):
    t = (text or "").lower()
    for tid, rx in KIND_WORDS:
        if re.search(rx, t):
            return tid
    return "personal" if re.search(r"\bя\b|меня|мой|моя", t) else "startup"


def blank_block(t):
    """Новый блок типа t: вариант по умолчанию, понятные заглушки (без выдуманных людей и отзывов)."""
    B = BLOCKS[t]
    v = next(iter(B["variants"]))
    d = {"type": t, "variant": v, "tone": "base", "title": B["title"]}
    starter = {
        "about": {"text": "Расскажите, кто вы, чем занимаетесь и почему вам можно доверять."},
        "services": {"items": [it(title="Услуга", text="Что входит и для кого", price="от 1 000 ₽"), it(title="Ещё услуга", text="Коротко о главном", price="")]},
        "prices": {"items": [it(title="Позиция", text="", price="1 000 ₽"), it(title="Ещё позиция", text="", price="2 000 ₽")]},
        "features": {"items": [it(title="Быстро", text="Почему с вами удобно", mark="clock"), it(title="Надёжно", text="Чем вы отличаетесь", mark="shield"),
                               it(title="С заботой", text="Что важно вашим клиентам", mark="heart")]},
        "steps": {"items": [it(title="Заявка", text="Человек пишет или звонит"), it(title="Встреча", text="Обсуждаете задачу"), it(title="Результат", text="Делаете работу")]},
        "gallery": {"items": [it(caption=""), it(caption=""), it(caption=""), it(caption="")]},
        "products": {"items": [it(title="Товар", text="Короткое описание", price="1 000 ₽"), it(title="Товар", text="Короткое описание", price="1 500 ₽")]},
        "schedule": {"items": [it(time="10:00", title="Начало", text=""), it(time="12:00", title="Главное событие", text="")]},
        "reviews": {"items": []},
        "team": {"items": [it(name="Имя", role="Должность", todo=True)]},
        "faq": {"items": [it(q="Частый вопрос?", a="Короткий понятный ответ.")]},
        "links": {"items": [it(title="Telegram", href="https://t.me/")]},
        "cta": {"text": "Одна фраза — зачем написать вам прямо сейчас.", "button": "Оставить заявку", "button_to": "lead"},
        "text": {"text": "Текст раздела."},
        "contacts": {"title": "Контакты"},
        "lead": {"title": "Оставьте заявку", "text": "Перезвоним и ответим на вопросы.", "button": "Отправить", "thanks": "Спасибо! Скоро свяжемся."},
    }.get(t, {})
    d.update(starter)
    return d
