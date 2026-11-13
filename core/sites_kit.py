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
    # 05.11 (владелец: «ещё шаблоны и более разнообразные») — палитры новых шаблонов
    "pulse": {"title": "Пульс", "bg": "#F2F2EE", "surface": "#E4E5DF", "ink": "#14161B", "muted": "#50545C", "accent": "#FF5A1F",
              "accent_ink": "#14161B", "dark": "#14161B", "dark_ink": "#F2F2EE", "accent2": "#2F5BFF", "line": "#D3D5CD"},
    "aqua": {"title": "Аква", "bg": "#F6FAFB", "surface": "#E4F0F3", "ink": "#0D2B35", "muted": "#476670", "accent": "#12708C",
             "accent_ink": "#FFFFFF", "dark": "#0D2B35", "dark_ink": "#F6FAFB", "accent2": "#F3B49B", "line": "#D2E3E8"},
    "crayon": {"title": "Мелки", "bg": "#FFFAF0", "surface": "#FFEFC7", "ink": "#2A2154", "muted": "#5A5480", "accent": "#5B3FD6",
               "accent_ink": "#FFFFFF", "dark": "#2A2154", "dark_ink": "#FFFAF0", "accent2": "#FF7B47", "line": "#F1DFAF"},
    "garage": {"title": "Гараж", "bg": "#1A1F26", "surface": "#232A33", "ink": "#EDF0F3", "muted": "#A3ABB5", "accent": "#FF7A1A",
               "accent_ink": "#1A1F26", "dark": "#10141A", "dark_ink": "#EDF0F3", "accent2": "#5FA8FF", "line": "#313A45"},
    "garden": {"title": "Сад", "bg": "#F8F6F1", "surface": "#ECE8DE", "ink": "#1F2A26", "muted": "#58625C", "accent": "#2C4A3E",
               "accent_ink": "#F8F6F1", "dark": "#1F2A26", "dark_ink": "#F8F6F1", "accent2": "#C29B5F", "line": "#DDD8CB"},
    "brick": {"title": "Кирпич", "bg": "#F6F4F1", "surface": "#EBE6DF", "ink": "#22262B", "muted": "#5B5F65", "accent": "#9C3F2A",
              "accent_ink": "#FFFFFF", "dark": "#22262B", "dark_ink": "#F6F4F1", "accent2": "#3E6B78", "line": "#DCD5CC"},
    "lagoon": {"title": "Лагуна", "bg": "#FBF6EC", "surface": "#F1E6D1", "ink": "#0F2A3B", "muted": "#4A5D69", "accent": "#0A6C96",
               "accent_ink": "#FFFFFF", "dark": "#0F2A3B", "dark_ink": "#FBF6EC", "accent2": "#EE8648", "line": "#E5D7BC"},
    "apricot": {"title": "Абрикос", "bg": "#FFF9F0", "surface": "#FDEBD3", "ink": "#2B2620", "muted": "#66594A", "accent": "#E8702A",
                "accent_ink": "#2B2620", "dark": "#1F3A3A", "dark_ink": "#FFF9F0", "accent2": "#1F7A7A", "line": "#F1DCC0"},
    "vanilla": {"title": "Ваниль", "bg": "#FDF6EC", "surface": "#F5E4CC", "ink": "#3A2820", "muted": "#6F5A4D", "accent": "#3A2820",
                "accent_ink": "#FDF6EC", "dark": "#3A2820", "dark_ink": "#FDF6EC", "accent2": "#E58BA3", "line": "#EAD5B8"},
    # 0.94 «Авангард» (13.11): баклажановая тушь, кислотный лайм — главное и действие, сиреневый — второй план
    "nightlime": {"title": "Ночь и лайм", "bg": "#15121C", "surface": "#211B2B", "ink": "#EFEAF7", "muted": "#A79FB6", "accent": "#D4FF52",
                  "accent_ink": "#16120A", "dark": "#100D16", "dark_ink": "#EFEAF7", "accent2": "#CBBCFF", "line": "#3A3149"},
    # «Афиша»: тёплый жёлтый лист, томатный красный и глубокий зелёный — как вывеска рынка
    "market": {"title": "Рынок", "bg": "#FFF1D6", "surface": "#FFE3AE", "ink": "#1F1A17", "muted": "#5E5246", "accent": "#CF2D22",
               "accent_ink": "#FFF8EC", "dark": "#174F38", "dark_ink": "#FFF1D6", "accent2": "#174F38", "line": "#1F1A17"},
    # «Ателье»: светлая лаванда, сливовый и пудровый — тихо и дорого
    "lavender": {"title": "Лаванда", "bg": "#F7F4FA", "surface": "#ECE5F2", "ink": "#2A2433", "muted": "#6B6275", "accent": "#6F4E86",
                 "accent_ink": "#FFFFFF", "dark": "#2A2433", "dark_ink": "#F7F4FA", "accent2": "#C9A98A", "line": "#DCD2E5"},
}
COLOR_KEYS = ("bg", "surface", "ink", "muted", "accent", "accent_ink", "dark", "dark_ink", "accent2", "line")

# ---------- шрифты ----------
# Вшитые (OFL, лежат в ui/assets/fonts, на опубликованный сайт уходят только нужные): Lora, Manrope, Unbounded, а с 05.11 —
# Oswald (узкий, «вывеска»), Cormorant (праздничные засечки), Nunito (округлый); у всех есть кириллица. Остальное — системные стеки (ничего не грузится).
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
    "sport": {"title": "Вывеска", "sub": "узкий Oswald + Manrope", "head": '"Oswald", "Arial Narrow", ' + SANS, "body": SANS, "hw": 600,
              "track": "0", "scale": 1.1, "scale3": 1.08, "files": ["oswald", "manrope"]},
    "elegant": {"title": "Праздничный", "sub": "Cormorant + Manrope", "head": '"Cormorant", Georgia, serif', "body": SANS, "hw": 600,
                "track": "-0.005em", "scale": 1.14, "scale3": 1.22, "files": ["cormorant", "manrope"]},
    "wide": {"title": "Широкий", "sub": "Unbounded крупно + Manrope", "head": '"Unbounded", "Arial Black", ' + SANS, "body": SANS, "hw": 800,
             "track": "-0.045em", "scale": 1.12, "files": ["unbounded", "manrope"]},
    "round": {"title": "Дружелюбный", "sub": "округлый Nunito", "head": '"Nunito", ' + SANS, "body": '"Nunito", ' + SANS, "hw": 800,
              "track": "-0.015em", "files": ["nunito"]},
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
    "oswald": [("oswald-cyr.woff2", "oswald-cyrillic-wght-normal.woff2", "Oswald", "normal", _CYR),
               ("oswald-lat.woff2", "oswald-latin-wght-normal.woff2", "Oswald", "normal", _LAT)],
    "cormorant": [("cormorant-cyr.woff2", "cormorant-cyrillic-wght-normal.woff2", "Cormorant", "normal", _CYR),
                  ("cormorant-lat.woff2", "cormorant-latin-wght-normal.woff2", "Cormorant", "normal", _LAT)],
    "nunito": [("nunito-cyr.woff2", "nunito-cyrillic-wght-normal.woff2", "Nunito", "normal", _CYR),
               ("nunito-lat.woff2", "nunito-latin-wght-normal.woff2", "Nunito", "normal", _LAT)],
}
RADII = {"sharp": {"title": "Строгие углы", "r": 2, "btn": 2}, "soft": {"title": "Мягкие", "r": 12, "btn": 10},
         "round": {"title": "Круглые", "r": 26, "btn": 999}}
# Стиль — характер вёрстки поверх палитры и шрифтов (0.94): «Классический» — как было; «Авангард» — крупный широкий
# шрифт, пронумерованные разделы, кнопки-капсулы и движение при прокрутке (только CSS, без скриптов — сайт быстрый и безопасный).
STYLES = {"classic": {"title": "Классический", "sub": "спокойная вёрстка, как раньше"},
          "avangard": {"title": "Авангард", "sub": "крупный широкий шрифт, номера разделов, движение при прокрутке",
                       "palette": "nightlime", "fonts": "wide", "radius": "round", "header": "light"},
          "poster": {"title": "Афиша", "sub": "огромные узкие заголовки, бегущая строка, наклейки и жёсткие тени",
                     "palette": "market", "fonts": "sport", "radius": "sharp", "header": "light"},
          "atelier": {"title": "Ателье", "sub": "тонкие линии, крупные засечки, арки и много воздуха",
                      "palette": "lavender", "fonts": "elegant", "radius": "round", "header": "light"}}

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
    "key": ("Ключ от дома", '<circle cx="7.5" cy="15.5" r="4"/><path d="M10.4 12.6 20 3M15.8 7.2l2.6 2.6M18.4 4.6 21 7.2"/>'),
    "car": ("Машина", '<path d="M5 11l1.6-4.2A2 2 0 0 1 8.5 5.5h7a2 2 0 0 1 1.9 1.3L19 11"/><rect x="3" y="11" width="18" height="6" rx="2"/><path d="M5.5 17v2.5M18.5 17v2.5"/><circle cx="7.5" cy="14" r="1"/><circle cx="16.5" cy="14" r="1"/>'),
    "rings": ("Кольца", '<circle cx="9" cy="14.5" r="5.5"/><circle cx="15" cy="14.5" r="5.5"/><path d="M13 5.6 15 3l2 2.6-2 2.4z"/>'),
    "cake": ("Торт", '<path d="M3.5 20.5h17M5 20.5V14h14v6.5"/><path d="M5 16.6c1.2 1 2.3 1 3.5 0s2.3-1 3.5 0 2.3 1 3.5 0 2.3-1 3.5 0"/><path d="M7.5 14v-3h9v3M12 11V8.4"/><path d="M12 4c.9 1 .9 2 0 3-.9-1-.9-2 0-3z"/>'),
    "compass": ("Компас", '<circle cx="12" cy="12" r="9"/><path d="M15.6 8.4l-2.1 5.1-5.1 2.1 2.1-5.1z"/>'),
    "mountain": ("Горы", '<path d="M2.5 19.5 9.5 7l4.2 7.4L16 11l5.5 8.5z"/><path d="M7.6 10.4 9.5 11.6l1.8-1.2"/>'),
    "blocks": ("Кубики", '<rect x="3.5" y="12" width="8" height="8" rx="1.2"/><rect x="12.5" y="12" width="8" height="8" rx="1.2"/><rect x="8" y="4" width="8" height="8" rx="1.2"/>'),
}
MARK_TITLES = {k: v[0] for k, v in MARKS.items()}
# узоры вместо фото (sites_render.art_svg) — у каждого шаблона свой мотив
ARTS = {"beans": "Зёрна", "arches": "Арки", "frames": "Рамки", "dots": "Точки", "blocks": "Фигуры", "rings": "Круги", "stripes": "Полосы",
        "grid": "Сетка", "pulse": "Пульс", "pebbles": "Галька", "confetti": "Конфетти", "hazard": "Сигнальные полосы", "botanic": "Ветви",
        "plan": "Планировка", "horizon": "Горизонт", "spots": "Пятна", "sprinkles": "Посыпка"}
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
             "variants": {"split": "Текст и картинка", "center": "По центру", "poster": "Афиша", "photo": "Фото на весь экран",
                          "kinetic": "Крупно, слова в движении"},
             "fields": [("title", "Заголовок", "line"), ("text", "Подзаголовок", "text"), ("note", "Строка внизу (адрес, часы, дата)", "line")]
             + _BTN + [("button2", "Вторая кнопка", "line"), ("button2_to", "Куда ведёт вторая", "link"), ("image", "Картинка", "image"),
                         ("words", "Слова в движении — через «·» (вариант «Крупно»)", "line")]},
    "about": {"title": "О нас", "sub": "история, подход, главное о вас",
              "variants": {"text": "Текст", "split": "Текст и картинка", "facts": "Текст и факты"},
              "fields": [("title", "Заголовок", "line"), ("text", "Текст", "text"), ("image", "Картинка", "image")],
              "items": ([("title", "Факт", "line"), ("text", "Пояснение", "line")], "Добавить факт")},
    "services": {"title": "Услуги", "sub": "что вы делаете — карточками или списком",
                 "variants": {"cards": "Карточки", "list": "Список с ценами", "rows": "Крупные строки"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
                 "items": ([("title", "Услуга", "line"), ("text", "Описание", "text"), ("price", "Цена", "line"), ("mark", "Знак", "mark")], "Добавить услугу")},
    "prices": {"title": "Цены", "sub": "меню, прайс или тарифы",
               "variants": {"menu": "Меню с точками", "plans": "Тарифы колонками", "table": "Таблица", "tabs": "Вкладки по разделам"},
               "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")] + _BTN,
               "items": ([("group", "Раздел (необязательно)", "line"), ("title", "Название", "line"), ("text", "Описание", "line"),
                          ("price", "Цена", "line"), ("old", "Старая цена (зачёркнута)", "line"), ("featured", "Выделить", "flag")], "Добавить позицию")},
    "features": {"title": "Преимущества", "sub": "почему выбирают вас",
                 "variants": {"icons": "Со знаками", "big": "Крупно", "split": "Заголовок слева"},
                 "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
                 "items": ([("title", "Преимущество", "line"), ("text", "Пояснение", "text"), ("mark", "Знак", "mark")], "Добавить")},
    "steps": {"title": "Как мы работаем", "sub": "шаги по порядку",
              "variants": {"line": "В ряд", "list": "Столбиком", "snake": "Путь змейкой"},
              "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
              "items": ([("title", "Шаг", "line"), ("text", "Пояснение", "text")], "Добавить шаг")},
    "gallery": {"title": "Галерея", "sub": "фото работ, интерьера, товаров",
                "variants": {"grid": "Сетка", "mosaic": "Мозаика", "strip": "Лента", "pairs": "До и после (фото парами)"},
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
                "variants": {"quotes": "Цитаты", "cards": "Карточки", "masonry": "Сеткой, цветные"},
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
    # 0.94: блоки «Авангарда» — работают в любом стиле
    "stats": {"title": "Цифры", "sub": "главные числа крупно: опыт, клиенты, результаты",
              "variants": {"big": "Крупно в ряд", "formula": "Формулой: 96 + 24 = 3", "stickers": "Карточками у фото"},
              "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text"), ("image", "Фото (для карточек)", "image")],
              "items": ([("value", "Число", "line"), ("label", "Подпись", "line")], "Добавить число")},
    "hub": {"title": "Схема", "sub": "круг в центре и части вокруг — нажмите на часть, чтобы прочитать",
            "variants": {"ring": "Круг с частями"},
            "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text"), ("center", "Что в центре", "line")],
            "items": ([("title", "Часть", "line"), ("sub", "Коротко", "line"), ("text", "Подробнее", "text")], "Добавить часть")},
    "duo": {"title": "Два пути", "sub": "выбор: с вами — и без вас",
            "variants": {"contrast": "Яркая и тёмная карточки"},
            "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
            "items": ([("tag", "Метка (сейчас, через год…)", "line"), ("title", "Заголовок", "line"), ("text", "Текст", "text"),
                       ("foot", "Подпись внизу", "line")], "Добавить путь")},
    "bars": {"title": "Полосы", "sub": "сравнение числами: сроки, цены, результаты",
             "variants": {"rows": "Строками"},
             "fields": [("title", "Заголовок", "line"), ("text", "Пояснение", "text"), ("unit", "Единица (мин, ₽, %)", "line")],
             "items": ([("title", "Что", "line"), ("value", "Число", "line"), ("featured", "Выделить", "flag")], "Добавить строку")},
    "cases": {"title": "Кейсы", "sub": "работы и результаты — листаются карточками",
              "variants": {"carousel": "Карусель", "grid": "Сеткой"},
              "fields": [("title", "Заголовок", "line"), ("text", "Вступление", "text")],
              "items": ([("title", "Проект", "line"), ("who", "Чей (клиент, ученик)", "line"), ("text", "Что сделали", "text"),
                         ("metric", "Результат числом (−18%, ×2)", "line"), ("metric_label", "Что это за число", "line"), ("image", "Картинка", "image")],
                        "Добавить кейс")},
    "ticker": {"title": "Бегущая строка", "sub": "полоса со словами, которые бегут по экрану",
               "variants": {"band": "Полоса"},
               "fields": [("text", "Слова — через «·»", "line")]},
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

# «Подвал и документы» (0.87; люди просят: оферта, политика обработки ПД, ИНН/ОГРН, адрес): site["legal"] =
# {org, inn, ogrn, address, phone, email, docs: {ключ: {mode: link|text, url, text, draft, ts}}, links: [{title, url}]}.
# Документ «свой текст» — отдельная страница сайта /<адрес> в стиле сайта; «ссылка» — на чужой адрес.
LEGAL_FIELDS = {"org": "Название организации или ИП", "inn": "ИНН", "ogrn": "ОГРН или ОГРНИП", "address": "Юридический адрес",
                "phone": "Телефон", "email": "Почта"}
LEGAL_DOCS = {"oferta": {"title": "Публичная оферта", "slug": "oferta", "short": "Оферта"},
              "privacy": {"title": "Политика обработки персональных данных", "slug": "privacy", "short": "Политика конфиденциальности"},
              "consent": {"title": "Согласие на обработку персональных данных", "slug": "soglasie", "short": "Согласие на обработку данных"},
              "terms": {"title": "Пользовательское соглашение", "slug": "terms", "short": "Пользовательское соглашение"}}
LEGAL_TEXT_MAX = 40000
LEGAL_LINKS_MAX = 6


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
    # 0.94 «Авангард» (владелец 13.11: «невероятно круто… повыше в „Сайтах“, чтобы использовали чаще»)
    "course": {
        "title": "Онлайн-курс, эксперт", "sub": "Авангард: крупный шрифт, схема, кейсы, движение", "style": "avangard", "palette": "nightlime",
        "fonts": "wide", "radius": "round", "menu": "top", "header": "light", "art": "rings", "logo": {"mark": "star", "style": "badge"},
        "name": "Срез", "tagline": "онлайн-школа аналитики",
        "contacts": {"email": "hello@srez.example", "telegram": "@srez_school"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "kinetic", "base", title="Аналитик данных", text="За 8 недель — от первого запроса до дашборда, по которому руководитель принимает решения.",
                note="Старт 1 декабря · 24 места в потоке", button="Начать с первой недели", button_to="#plans", words="SQL · Python · Дашборды"),
            blk("hub", "ring", "base", nav="Как устроен", title="Как устроен курс", center="Аналитик",
                text="Шесть частей вокруг одного навыка — отвечать на вопросы бизнеса цифрами. Нажмите на часть, чтобы узнать, что в ней.",
                items=[it(title="Уроки", sub="и разборы вживую", text="Два занятия в неделю: короткая теория и сразу разбор на реальных данных."),
                       it(title="SQL", sub="главный язык данных", text="От первого запроса до оконных функций — на базе с миллионом заказов."),
                       it(title="Python", sub="pandas и графики", text="Чистим, склеиваем и считаем то, что неудобно в SQL."),
                       it(title="Дашборды", sub="панель для руководителя", text="Метрики, фильтры и ни одной лишней цифры."),
                       it(title="Статистика", sub="и A/B-тесты", text="Когда разница — правда, а когда случайность."),
                       it(title="Проекты", sub="в портфолио", text="Три законченных проекта с выводами для бизнеса.")]),
            blk("duo", "contrast", "alt", title="Вопрос не «нужна ли аналитика», а кто будет её делать", items=[
                it(tag="сейчас", title="Научиться за 8 недель", text="И через два месяца самому собирать отчёт, на который раньше уходила неделя.", foot="двигаться вперёд"),
                it(tag="через год", title="Ждать, пока объяснят", text="И снова просить коллегу «выгрузить табличку» к пятнице.", foot="догонять потом")]),
            blk("cases", "carousel", "base", nav="Кейсы", title="Проекты выпускников", items=[
                it(title="Отток в фитнес-клубе", who="Анна К.", text="Нашла, что уходят в третий месяц после заморозки, — клуб поменял правила.", metric="−18%", metric_label="отток за квартал"),
                it(title="Цены в кофейнях", who="Игорь Л.", text="Где можно поднять цену без потери чеков.", metric="+9%", metric_label="к выручке"),
                it(title="Склад маркетплейса", who="Дина Р.", text="Прогноз остатков на две недели вместо ручной таблицы.", metric="−31%", metric_label="пустых полок"),
                it(title="Реклама онлайн-школы", who="Павел С.", text="Сквозная воронка: два канала из пяти оказались убыточными.", metric="×1,6", metric_label="окупаемость")]),
            blk("bars", "rows", "alt", title="Отчёт за минуты, а не за дни", unit="мин",
                text="Сколько занимают типовые задачи у выпускников после курса.", items=[
                it(title="Выручка по дням", value="6", featured=True), it(title="Воронка заказа", value="12", featured=True),
                it(title="Отток клиентов", value="20"), it(title="Итог A/B-теста", value="24"), it(title="Когорты по месяцам", value="38")]),
            blk("steps", "snake", "base", nav="Программа", title="Программа", text="Восемь недель по порядку.", items=[
                it(title="Таблицы и SELECT"), it(title="JOIN и агрегаты"), it(title="Окна и CTE"), it(title="Python и pandas"),
                it(title="Графики и выводы"), it(title="Дашборды"), it(title="Статистика и A/B"), it(title="Итоговый проект")]),
            blk("stats", "formula", "alt", items=[it(value="96", label="часов практики"), it(value="24", label="задачи с разбором"),
                                                   it(value="3", label="проекта в портфолио")]),
            blk("prices", "plans", "base", nav="Тарифы", id="plans", title="Тарифы", items=[
                it(title="Старт", text="Недели 1–4 · 12 задач · доступ на 3 месяца", price="19 900 ₽", old="29 900 ₽"),
                it(title="Аналитик", text="Недели 1–6 · 24 задачи с разбором · 2 проекта · сертификат", price="34 900 ₽", old="49 900 ₽", featured=True),
                it(title="С наставником", text="Все 8 недель · наставник 2 месяца · 3 проекта · доступ навсегда", price="59 900 ₽", old="79 900 ₽")],
                button="Записаться", button_to="lead"),
            blk("stats", "stickers", "alt", nav="Автор", title="Автор курса", text="Руководила аналитикой в банке и маркетплейсе. Сама проверяет итоговые проекты потока.",
                items=[it(value="11+", label="лет в аналитике"), it(value="1 400+", label="выпускников"), it(value="87%", label="сменили работу за полгода"), it(value="4", label="банка и 2 маркетплейса")]),
            blk("faq", "list", "base", title="Вопросы", items=[
                it(q="Я никогда не писал код. Получится?", a="Да. Первые две недели — SQL с нуля: одна таблица продаж и один вопрос бизнеса."),
                it(q="Сколько времени нужно в неделю?", a="8–10 часов: два занятия по полтора часа и задачи в своём темпе."),
                it(q="Можно оплатить частями?", a="Да, на 4 или 12 месяцев без переплаты.")]),
            blk("lead", "split", "dark", nav="Записаться", title="Первая неделя бесплатно", text="Оставьте имя и телефон — пришлём доступ к первой неделе.",
                button="Начать", ask_message=False, thanks="Спасибо! Доступ придёт в течение часа."),
        ]}]},
    "bistro": {
        "title": "Кафе, пекарня, лавка", "sub": "Афиша: огромные заголовки, бегущая строка, наклейки", "style": "poster", "palette": "market",
        "fonts": "sport", "radius": "sharp", "menu": "top", "header": "light", "art": "dots", "logo": {"mark": "croissant", "style": "badge"},
        "name": "Тёплый хлеб", "tagline": "пекарня на углу",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Ленина, 24", "hours": "Каждый день 7:30–21:00"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "kinetic", "base", title="Хлеб из печи к восьми утра", text="Печём на закваске каждое утро — без улучшителей, только мука, вода и время.",
                note="ул. Ленина, 24 · с 7:30", button="Посмотреть витрину", button_to="#menu", button2="Заказать к столу", button2_to="lead",
                words="Закваска · Круассаны · Кофе с собой"),
            blk("ticker", "band", "accent", text="Тёплое с 7:30 · Закваска 48 часов · Кофе с собой · Торты на заказ · Без улучшителей"),
            blk("prices", "menu", "base", nav="Витрина", id="menu", title="Сегодня на витрине", text="Что раскупают первым — к обеду может закончиться.",
                items=[it(group="Хлеб", title="Пшеничный на закваске", text="900 г", price="290 ₽", featured=True),
                       it(group="Хлеб", title="Ржаной с тмином", text="800 г", price="260 ₽"), it(group="Хлеб", title="Багет", text="300 г", price="140 ₽"),
                       it(group="Сладкое", title="Круассан", text="масло 82%", price="160 ₽"), it(group="Сладкое", title="Синнабон", text="с корицей", price="210 ₽"),
                       it(group="Кофе", title="Капучино", text="250 мл", price="220 ₽"), it(group="Кофе", title="Раф лавандовый", text="350 мл", price="290 ₽")]),
            blk("stats", "big", "alt", title="Пекарня в цифрах", items=[it(value="48 ч", label="зреет закваска"), it(value="7:30", label="первый хлеб из печи"),
                                                                       it(value="0", label="улучшителей и консервантов")]),
            blk("duo", "contrast", "base", title="Хлеб, который не черствеет к вечеру", items=[
                it(tag="у нас", title="Закваска и время", text="Тесто зреет двое суток — поэтому корка хрустит, а мякиш живой до третьего дня.", foot="берите на неделю"),
                it(tag="обычно", title="Дрожжи и спешка", text="Поднялся за час, к вечеру уже сухой.", foot="и снова в магазин")]),
            blk("gallery", "mosaic", "alt", nav="Фото", title="Как у нас", items=[it(caption="Печь в 6 утра"), it(caption="Витрина"),
                                                                                it(caption="Круассаны"), it(caption="Столики у окна")]),
            blk("reviews", "masonry", "base", title="Что говорят соседи", items=[]),
            blk("lead", "split", "dark", nav="Заказ", title="Заказать к столу", text="Хлеб, выпечку или торт к празднику — оставьте телефон, перезвоним.",
                button="Заказать", ask_message=True, thanks="Спасибо! Перезвоним в течение получаса."),
            blk("contacts", "split", "base", nav="Контакты", title="Где нас найти", text="Вход с угла, ступенек нет — можно с коляской."),
        ]}]},
    "beauty": {
        "title": "Салон, клиника красоты", "sub": "Ателье: тонкие линии, крупные засечки, арки", "style": "atelier", "palette": "lavender",
        "fonts": "elegant", "radius": "round", "menu": "top", "header": "light", "art": "arches", "logo": {"mark": "lotus", "style": "plain"},
        "name": "Сирень", "tagline": "студия ухода",
        "contacts": {"phone": "+7 900 000-00-00", "address": "Набережная, 7", "hours": "Ежедневно 10:00–21:00", "telegram": "@siren_studio"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Уход, после которого хочется замедлиться", text="Лицо, брови и руки в тихой студии у воды. Один мастер — один гость, без очередей за стенкой.",
                note="Набережная, 7 · ежедневно 10–21", button="Записаться", button_to="lead", button2="Услуги и цены", button2_to="#prices"),
            blk("hub", "ring", "alt", nav="Подход", title="Как мы работаем", center="Вы", text="Каждый визит — четыре шага. Нажмите на шаг, чтобы узнать о нём.",
                items=[it(title="Разговор", sub="10 минут", text="Слушаем, что беспокоит, и смотрим кожу при дневном свете."),
                       it(title="Подбор", sub="под вашу кожу", text="Составляем уход только из того, что нужно именно сейчас."),
                       it(title="Процедура", sub="без спешки", text="Один мастер весь визит, тёплые полотенца, тишина."),
                       it(title="Дома", sub="памятка", text="Пишем, что делать дома, — и напоминаем о следующем визите.")]),
            blk("prices", "table", "base", nav="Цены", id="prices", title="Услуги и цены", items=[
                it(title="Уход за лицом", text="очищение, массаж, маска · 75 мин", price="4 200 ₽"),
                it(title="Архитектура бровей", text="форма и окрашивание · 45 мин", price="2 100 ₽"),
                it(title="Маникюр с покрытием", text="90 мин", price="2 600 ₽"),
                it(title="Ритуал для рук", text="скраб, парафин, массаж · 40 мин", price="1 800 ₽")], button="Записаться", button_to="lead"),
            blk("stats", "big", "alt", items=[it(value="1", label="мастер — один гость"), it(value="9 лет", label="опыта у мастеров"),
                                             it(value="4,9", label="средняя оценка гостей")]),
            blk("gallery", "mosaic", "base", nav="Студия", title="Студия", items=[it(caption="Кабинет ухода"), it(caption="Зона маникюра"),
                                                                                 it(caption="Чай после процедуры"), it(caption="Вид на воду")]),
            blk("faq", "list", "alt", title="Вопросы", items=[
                it(q="Как подготовиться к уходу за лицом?", a="Ничего особенного: приходите без макияжа или снимем его у нас."),
                it(q="Можно ли прийти с подругой?", a="Да, если запишетесь на одно время — подготовим два кабинета."),
                it(q="Есть ли подарочные сертификаты?", a="Да, на любую сумму или услугу — оформим за пять минут.")]),
            blk("lead", "split", "dark", nav="Запись", title="Записаться", text="Оставьте имя и телефон — подберём удобное время.",
                button="Записаться", ask_message=True, thanks="Спасибо! Перезвоним, чтобы подтвердить время."),
            blk("contacts", "split", "base", nav="Контакты", title="Как добраться", text="Вход со стороны набережной, второй этаж."),
        ]}]},
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
    # ---------- 05.11: ещё девять — у каждого свой характер (палитра, шрифт, вёрстка, узор) ----------
    "fitness": {
        "title": "Фитнес, тренер", "sub": "энергичный: смелый шрифт, тёмная обложка, абонементы и «до и после»", "palette": "pulse", "fonts": "bold",
        "radius": "sharp", "menu": "top", "header": "dark", "art": "pulse", "logo": {"mark": "dumbbell", "style": "badge"},
        "name": "Пульс", "tagline": "студия функционального тренинга",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Спортивная, 14", "hours": "Пн–Пт 7:00–22:00, Сб–Вс 9:00–20:00", "telegram": "@puls_studio"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "photo", "dark", title="Тренировки, после которых хочется вернуться",
                text="Малые группы до 8 человек — тренер видит каждого. Первая тренировка бесплатно: подберём нагрузку под вашу форму.",
                note="ул. Спортивная, 14 · с 7 утра", button="Записаться на пробную", button_to="lead", button2="Расписание", button2_to="#schedule"),
            blk("features", "big", "base", title="Почему у нас получается", items=[
                it(title="Группы до 8 человек", text="Тренер поправит технику каждому, а не только тем, кто впереди", mark="dumbbell"),
                it(title="План под вас", text="Замеры и цель — на первой встрече, дальше проверяем прогресс раз в месяц", mark="check"),
                it(title="С 7 утра", text="Успеть до работы — и весь день чувствовать себя бодрее", mark="clock")]),
            blk("schedule", "days", "alt", nav="Расписание", id="schedule", title="Расписание", text="Занятия по 55 минут. Записаться — в Telegram или формой ниже.", items=[
                it(time="Пн, Ср, Пт · 7:30", title="Функциональный тренинг", text="Выносливость, кор и координация"),
                it(time="Вт, Чт · 19:00", title="Силовая в малой группе", text="Штанга и гантели с постановкой техники"),
                it(time="Сб · 10:00", title="Растяжка и мобильность", text="Спина, плечи, тазобедренные суставы"),
                it(time="Каждый день", title="Персональные тренировки", text="Один на один, в удобное время")]),
            blk("prices", "plans", "base", nav="Абонементы", title="Абонементы", items=[
                it(title="Разовое", text="одно групповое занятие", price="800 ₽"),
                it(title="8 занятий", text="на месяц, любые группы", price="5 600 ₽", featured=True),
                it(title="Персонально", text="тренировка один на один", price="2 500 ₽")], button="Выбрать", button_to="lead"),
            blk("gallery", "pairs", "alt", nav="Результаты", title="Результаты", text="Фото «до» и «после» — только с согласия наших учеников.", items=[
                it(caption="Три месяца, минус 9 кг"), it(caption=""), it(caption="Полгода силовых"), it(caption="")]),
            blk("steps", "line", "base", title="Как начать", items=[
                it(title="Заявка", text="Оставьте телефон — перезвоним в течение часа"),
                it(title="Пробная тренировка", text="Бесплатно, с замерами и разговором о цели"),
                it(title="Свой план", text="Подберём группу, время и абонемент")]),
            blk("faq", "list", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="Я никогда не занимался — подойдёт?", a="Да. Нагрузку подбираем под вашу форму, технику ставим с нуля."),
                it(q="Что взять с собой?", a="Удобную одежду, кроссовки и воду. Полотенце дадим."),
                it(q="Можно заморозить абонемент?", a="Да, один раз до 14 дней — на болезнь или отпуск.")]),
            blk("lead", "split", "dark", nav="Запись", title="Запишитесь на пробную тренировку", text="Это бесплатно. Перезвоним и подберём удобное время.",
                button="Записаться", thanks="Спасибо! Перезвоним в течение часа."),
            blk("contacts", "band", "base", nav="Контакты", title="Как нас найти", text="Вход со двора, второй этаж. Есть душевые, шкафчики и парковка."),
        ]}]},
    "dental": {
        "title": "Стоматология", "sub": "спокойная аква, засечки, цены вкладками и «до и после»", "palette": "aqua", "fonts": "warm", "radius": "round",
        "menu": "top", "header": "light", "art": "pebbles", "logo": {"mark": "tooth", "style": "plain"},
        "name": "Белая линия", "tagline": "стоматология",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Гагарина, 21", "hours": "Пн–Сб 9:00–21:00", "email": "clinic@example.ru"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Лечим зубы спокойно и без боли",
                text="Современная анестезия, план лечения с ценой до начала и врачи, которые объясняют каждый шаг.",
                note="ул. Гагарина, 21 · Пн–Сб с 9 до 21", button="Записаться на осмотр", button_to="lead", button2="Цены", button2_to="#prices"),
            blk("services", "cards", "alt", nav="Услуги", title="Что лечим", items=[
                it(title="Лечение кариеса", text="Пломбы, лечение каналов под микроскопом", mark="tooth"),
                it(title="Гигиена", text="Чистка ультразвуком и Air Flow, фторирование", mark="spark"),
                it(title="Имплантация", text="План на 3D-снимке, импланты с гарантией", mark="shield"),
                it(title="Детский приём", text="Врачи, которые умеют договариваться с детьми", mark="sun"),
                it(title="Ортодонтия", text="Брекеты и элайнеры для взрослых и детей", mark="check"),
                it(title="Протезирование", text="Коронки, виниры и съёмные протезы", mark="star")]),
            blk("prices", "tabs", "base", nav="Цены", id="prices", title="Цены", text="Точную стоимость назовём после осмотра — и запишем её в план лечения.", items=[
                it(group="Терапия", title="Консультация и план лечения", price="0 ₽"), it(group="Терапия", title="Лечение кариеса", text="с пломбой", price="от 4 500 ₽"),
                it(group="Терапия", title="Лечение канала", text="под микроскопом", price="от 9 000 ₽"),
                it(group="Гигиена", title="Профессиональная чистка", text="ультразвук и Air Flow", price="4 900 ₽"),
                it(group="Гигиена", title="Отбеливание", price="от 15 000 ₽"),
                it(group="Имплантация", title="Имплант под ключ", text="с коронкой", price="от 45 000 ₽"),
                it(group="Имплантация", title="Синус-лифтинг", price="от 25 000 ₽"),
                it(group="Детям", title="Лечение молочного зуба", price="от 3 000 ₽"), it(group="Детям", title="Герметизация фиссур", price="1 500 ₽")]),
            blk("features", "split", "alt", title="Без страха и сюрпризов", text="Знаем, как непросто прийти к стоматологу. Поэтому всё объясняем заранее.", items=[
                it(title="Без боли", text="Анестезия, которую вы почти не почувствуете", mark="heart"),
                it(title="Цена до начала", text="План лечения со стоимостью — до первого укола", mark="check"),
                it(title="Гарантия", text="До 5 лет на пломбы, коронки и импланты", mark="shield")]),
            blk("gallery", "pairs", "base", nav="Работы", title="До и после", text="Работы наших врачей — с согласия пациентов.", items=[
                it(caption="Виниры на шесть зубов"), it(caption=""), it(caption="Отбеливание"), it(caption="")]),
            blk("team", "cards", "alt", nav="Врачи", title="Врачи", text="Расскажите о врачах — фото, опыт и специализацию.", items=[
                it(name="Имя врача", role="Стоматолог-терапевт, стаж … лет", todo=True), it(name="Имя врача", role="Хирург-имплантолог, стаж … лет", todo=True),
                it(name="Имя врача", role="Детский стоматолог, стаж … лет", todo=True)]),
            blk("faq", "two", "base", nav="Вопросы", title="Вопросы", items=[
                it(q="Больно ли лечить зубы?", a="Нет: делаем анестезию и ждём, пока она подействует. Станет неприятно — остановимся."),
                it(q="Можно ли в рассрочку?", a="Да, без переплаты на срок до 12 месяцев."),
                it(q="Дадите справку для налогового вычета?", a="Да, вернуть можно 13% стоимости лечения."),
                it(q="С какого возраста принимаете детей?", a="С 3 лет. Первый визит — знакомство с врачом, без лечения.")]),
            blk("lead", "card", "accent", nav="Запись", title="Запишитесь на осмотр", text="Перезвоним в течение 15 минут и подберём удобное время.",
                button="Записаться", ask_message=True, thanks="Спасибо! Администратор перезвонит в течение 15 минут."),
            blk("contacts", "split", "base", nav="Контакты", title="Как добраться", text="Пять минут пешком от остановки «Гагарина». Парковка у входа."),
        ]}]},
    "kids": {
        "title": "Детский центр, репетитор", "sub": "мелки и конфетти, округлый шрифт, занятия и расписание", "palette": "crayon", "fonts": "round",
        "radius": "round", "menu": "top", "header": "light", "art": "confetti", "logo": {"mark": "blocks", "style": "badge"},
        "name": "Карандаш", "tagline": "детский развивающий центр",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Школьная, 3", "hours": "Пн–Сб 9:00–20:00", "telegram": "@karandash_center"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Здесь дети учатся с удовольствием",
                text="Подготовка к школе, английский, рисование и логопед — для детей от 3 до 10 лет. Группы до 6 человек.",
                note="ул. Школьная, 3 · пробное занятие бесплатно", button="Записать ребёнка", button_to="lead", button2="Занятия", button2_to="#classes"),
            blk("services", "cards", "alt", nav="Занятия", id="classes", title="Занятия", items=[
                it(title="Подготовка к школе", text="Чтение, счёт и письмо, 5–7 лет", price="от 600 ₽ за занятие", mark="book"),
                it(title="Английский", text="Через игры и песни, с 4 лет", price="от 650 ₽", mark="chat"),
                it(title="Рисование и лепка", text="Акварель, гуашь, пластилин, с 3 лет", price="от 550 ₽", mark="brush"),
                it(title="Логопед", text="Индивидуально, 30 минут", price="1 200 ₽", mark="mic"),
                it(title="Шахматы", text="Логика и усидчивость, с 5 лет", price="от 500 ₽", mark="blocks"),
                it(title="Продлёнка", text="После школы: уроки, обед и прогулка", price="от 9 000 ₽ в месяц", mark="home")]),
            blk("features", "icons", "base", title="Почему родители выбирают нас", items=[
                it(title="Маленькие группы", text="До 6 детей — педагог видит каждого", mark="heart"),
                it(title="Отчёт после занятия", text="Фото и пара слов — вам в мессенджер", mark="chat"),
                it(title="Безопасно", text="Охрана и камеры, ребёнка отдаём только вам", mark="shield"),
                it(title="Рядом со школой", text="Заберём после уроков сами", mark="pin")]),
            blk("schedule", "days", "alt", nav="Расписание", title="Расписание на неделю", items=[
                it(time="Пн и Ср", title="Подготовка к школе", text="17:00 и 18:00"),
                it(time="Вт и Чт", title="Английский", text="16:30 — младшие, 17:30 — старшие"),
                it(time="Пятница", title="Рисование и лепка", text="17:00"),
                it(time="Суббота", title="Шахматы", text="11:00")]),
            blk("prices", "plans", "base", nav="Цены", title="Абонементы", items=[
                it(title="Пробное", text="первое занятие — познакомиться", price="0 ₽"),
                it(title="8 занятий", text="любое направление на месяц", price="4 400 ₽", featured=True),
                it(title="Безлимит", text="все групповые занятия месяца", price="9 900 ₽")], button="Записаться", button_to="lead"),
            blk("faq", "list", "alt", nav="Вопросы", title="Вопросы родителей", items=[
                it(q="С какого возраста можно прийти?", a="С 3 лет — на рисование и лепку, с 4 — на английский, с 5 — на подготовку к школе."),
                it(q="Можно посидеть на занятии?", a="На пробном — да. Потом дети занимаются без родителей: так им легче включиться."),
                it(q="Что, если ребёнок заболел?", a="Пропущенное по болезни занятие перенесём на другой день.")]),
            blk("lead", "split", "dark", nav="Запись", title="Запишите ребёнка на пробное занятие", text="Расскажите возраст и что ребёнку интересно — подберём группу.",
                button="Записаться", ask_message=True, thanks="Спасибо! Перезвоним сегодня и подберём группу."),
            blk("contacts", "split", "base", nav="Контакты", title="Где мы", text="Первый этаж жилого дома, отдельный вход с колясочным пандусом."),
        ]}]},
    "auto": {
        "title": "Автосервис", "sub": "тёмный индустриальный, узкий шрифт-вывеска, цены вкладками", "palette": "garage", "fonts": "sport",
        "radius": "sharp", "menu": "top", "header": "dark", "art": "hazard", "logo": {"mark": "car", "style": "badge"},
        "name": "Гараж 24", "tagline": "автосервис",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Промышленная, 7", "hours": "Ежедневно 8:00–22:00", "whatsapp": "+7 900 000-00-00"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Ремонт без «а ещё вот это надо»",
                text="Диагностика за 30 минут, смета до начала работ и запчасти, которые вы видите в чеке. Иномарки и отечественные.",
                note="ул. Промышленная, 7 · ежедневно с 8 до 22", button="Записаться на ремонт", button_to="lead", button2="Позвонить", button2_to="phone"),
            blk("services", "rows", "alt", nav="Услуги", title="Что делаем", items=[
                it(title="Техобслуживание", text="Масло, фильтры и проверка машины по 40 пунктам", price="от 2 500 ₽"),
                it(title="Ходовая", text="Подвеска, рулевое, развал-схождение", price="от 1 500 ₽"),
                it(title="Тормоза", text="Колодки, диски, замена жидкости", price="от 1 200 ₽"),
                it(title="Диагностика", text="Компьютерная и ходовой части — с отчётом", price="от 900 ₽"),
                it(title="Шиномонтаж", text="Сезонная замена и хранение колёс", price="от 2 000 ₽")]),
            blk("prices", "tabs", "base", nav="Цены", id="prices", title="Цены на работы", text="Запчасти — по чеку; можно привезти свои.", items=[
                it(group="ТО", title="Замена масла двигателя", price="800 ₽"), it(group="ТО", title="Замена воздушного фильтра", price="300 ₽"),
                it(group="ТО", title="ТО-1 под ключ", text="масло, фильтры, проверка", price="от 3 500 ₽"),
                it(group="Ходовая", title="Замена передних колодок", price="1 200 ₽"), it(group="Ходовая", title="Развал-схождение", price="1 800 ₽"),
                it(group="Ходовая", title="Замена амортизатора", price="от 1 500 ₽"),
                it(group="Шины", title="Шиномонтаж R13–R16", text="четыре колеса с балансировкой", price="2 000 ₽"),
                it(group="Шины", title="Хранение колёс", text="сезон", price="3 000 ₽")]),
            blk("features", "split", "alt", title="Почему нам доверяют машину", items=[
                it(title="Смета до работ", text="Без вашего согласия ничего не меняем", mark="check"),
                it(title="Старые запчасти — вам", text="Покажем, что сняли и почему", mark="wrench"),
                it(title="Гарантия полгода", text="На все работы и наши запчасти", mark="shield")]),
            blk("steps", "line", "base", nav="Как работаем", title="Как проходит ремонт", items=[
                it(title="Запись", text="Перезвоним и подберём время"), it(title="Диагностика", text="30 минут, при вас"),
                it(title="Смета", text="Согласуем каждую позицию"), it(title="Ремонт", text="Фото и видео — в мессенджер"),
                it(title="Выдача", text="Проверим машину вместе")]),
            blk("gallery", "grid", "alt", nav="Сервис", title="Наш сервис", items=[it(caption="Шесть подъёмников"), it(caption="Зона ожидания с кофе"),
                                                                                it(caption="Шиномонтаж и хранение колёс")]),
            blk("lead", "split", "accent", nav="Запись", title="Запишитесь на ремонт", text="Марка, модель и что беспокоит — перезвоним с ценой и временем.",
                button="Записаться", ask_message=True, thanks="Спасибо! Мастер перезвонит в течение 20 минут."),
            blk("contacts", "split", "base", nav="Контакты", title="Как проехать", text="С Объездного шоссе — второй поворот направо после заправки."),
        ]}]},
    "wedding": {
        "title": "Свадьбы, праздники", "sub": "праздничные засечки, ветви и золото, меню по центру", "palette": "garden", "fonts": "elegant",
        "radius": "sharp", "menu": "center", "header": "light", "art": "botanic", "logo": {"mark": "rings", "style": "plain"},
        "name": "Белый сад", "tagline": "свадьбы и выездные регистрации",
        "contacts": {"phone": "+7 900 000-00-00", "email": "hello@example.ru", "telegram": "@belyi_sad"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "center", "base", title="Свадьба, на которой отдыхаете вы сами",
                text="Берём на себя площадку, декор, подрядчиков и тайминг дня. Вам остаётся выбирать и радоваться.",
                note="Москва и Подмосковье · открыт сезон 2027", button="Обсудить свадьбу", button_to="lead", button2="Пакеты", button2_to="#packages"),
            blk("about", "split", "alt", nav="О нас", title="Девять лет делаем свадьбы",
                text="На 20–150 гостей: от камерных ужинов до праздников в загородных усадьбах.\n\n"
                     "Начинаем со встречи, где слушаем вашу историю, и только потом предлагаем концепцию, бюджет и площадки."),
            blk("services", "rows", "base", nav="Пакеты", id="packages", title="Пакеты", items=[
                it(title="Координация дня", text="Ведём день по таймингу — вы не думаете о деталях", price="от 40 000 ₽"),
                it(title="Частичная организация", text="Подбор подрядчиков, смета и координация", price="от 120 000 ₽"),
                it(title="Свадьба под ключ", text="Концепция, площадка, декор, подрядчики и сам день", price="от 250 000 ₽"),
                it(title="Выездная регистрация", text="Арка, церемония и ведущий церемонии", price="от 60 000 ₽")]),
            blk("gallery", "mosaic", "alt", nav="Свадьбы", title="Наши свадьбы", items=[
                it(caption="Церемония у озера"), it(caption="Ужин в оранжерее"), it(caption="Букет невесты"), it(caption="Декор зала"), it(caption="Первый танец")]),
            blk("steps", "list", "base", nav="Как готовим", title="Как мы готовим свадьбу", items=[
                it(title="Знакомство", text="Встреча или видеозвонок: идея, дата, бюджет"),
                it(title="Концепция", text="Стиль, палитра и площадки на выбор"),
                it(title="Подготовка", text="Договоры с подрядчиками, общий чат и смета по статьям"),
                it(title="День свадьбы", text="Координаторы на месте с утра и до последнего гостя")]),
            blk("faq", "two", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="За сколько начинать подготовку?", a="Лучше за 6–9 месяцев: популярные площадки бронируют заранее. Камерную свадьбу успеем за два месяца."),
                it(q="Можно со своими подрядчиками?", a="Да. Подключим вашего фотографа или ведущего и впишем их в тайминг."),
                it(q="Как складывается бюджет?", a="Смета по статьям: стоимость каждого подрядчика и наш гонорар — отдельными строками."),
                it(q="Работаете в других городах?", a="Да, проведём свадьбу в любом городе России.")]),
            blk("lead", "card", "dark", nav="Заявка", title="Расскажите о вашей свадьбе", text="Дата, город и примерное число гостей — ответим в течение дня.",
                button="Отправить", ask_message=True, thanks="Спасибо! Ответим в течение дня."),
            blk("contacts", "band", "base", nav="Контакты", title="Связаться", text="Встречаемся в студии или по видеосвязи — как удобнее."),
        ]}]},
    "realty": {
        "title": "Недвижимость, риелтор", "sub": "кирпич и графит, планировки вместо фото, объекты с ценами", "palette": "brick", "fonts": "strict",
        "radius": "sharp", "menu": "top", "header": "light", "art": "plan", "logo": {"mark": "key", "style": "badge"},
        "name": "Ключ", "tagline": "агентство недвижимости",
        "contacts": {"phone": "+7 900 000-00-00", "email": "info@example.ru", "address": "пр. Ленина, 55, офис 12", "hours": "Пн–Сб 9:00–20:00"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Квартира, в которой вы уверены",
                text="Проверяем документы и историю квартиры, ведём переговоры и сопровождаем сделку до ключей. Вторичка и новостройки.",
                note="Комиссию называем до начала работы", button="Подобрать квартиру", button_to="lead", button2="Объекты", button2_to="#objects"),
            blk("products", "grid", "alt", nav="Объекты", id="objects", title="Сейчас в продаже", text="Нажмите «Посмотреть» — договоримся о показе.",
                button="Посмотреть", button_to="lead", items=[
                    it(title="2-комнатная, 54 м²", text="ЖК «Северный», 7 этаж из 12, с ремонтом", price="7 900 000 ₽"),
                    it(title="Студия, 27 м²", text="Центр, дом сдаётся в 2027 году", price="4 300 000 ₽"),
                    it(title="3-комнатная, 78 м²", text="Сталинский дом, потолки 3,2 м, тихий двор", price="11 500 000 ₽"),
                    it(title="Дом, 120 м²", text="Участок 8 соток, газ, 15 км от города", price="9 800 000 ₽")]),
            blk("services", "cards", "base", nav="Услуги", title="Чем поможем", items=[
                it(title="Купить", text="Подбор, проверка документов, торг за цену", price="от 50 000 ₽", mark="home"),
                it(title="Продать", text="Оценка, фото, реклама и показы", price="2% от цены", mark="tag"),
                it(title="Сдать", text="Проверим жильцов и составим договор", price="50% месячной платы", mark="key"),
                it(title="Ипотека", text="Подадим заявки сразу в несколько банков", price="бесплатно для клиентов", mark="check")]),
            blk("steps", "line", "alt", nav="Как работаем", title="Как проходит сделка", items=[
                it(title="Встреча", text="Обсуждаем задачу, бюджет и сроки"), it(title="Подбор", text="Показы в удобное время"),
                it(title="Проверка", text="Юрист проверяет документы и историю"), it(title="Сделка", text="Безопасные расчёты через банк"),
                it(title="Ключи", text="Подписываем акт и передаём ключи")]),
            blk("about", "facts", "base", nav="О нас", title="Агентство «Ключ»", text="Работаем в городе с 2014 года. Каждую сделку проверяет юрист, "
                "а договор с нами фиксирует комиссию и сроки.",
                items=[it(title="с 2014", text="года на рынке"), it(title="Юрист в штате", text="проверяет каждую сделку"),
                       it(title="Без предоплат", text="комиссия — после сделки")]),
            blk("faq", "list", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="Когда платить комиссию?", a="После подписания договора купли-продажи. Предоплат нет."),
                it(q="Работаете с ипотекой и маткапиталом?", a="Да: поможем с одобрением и согласуем сделку с банком и Пенсионным фондом."),
                it(q="Можно продать квартиру с долгом по ипотеке?", a="Да, это обычная сделка — расскажем, как она проходит, на встрече.")]),
            blk("lead", "split", "dark", nav="Заявка", title="Расскажите, что ищете", text="Район, бюджет и сроки — пришлём подходящие варианты.",
                button="Подобрать", ask_message=True, thanks="Спасибо! Пришлём варианты сегодня."),
            blk("contacts", "split", "base", nav="Контакты", title="Офис", text="Бизнес-центр на проспекте Ленина, вход со двора, первый этаж."),
        ]}]},
    "travel": {
        "title": "Туры, экскурсии", "sub": "песок и море, афиша с горизонтом, туры и программа по дням", "palette": "lagoon", "fonts": "editorial",
        "radius": "round", "menu": "top", "header": "accent", "art": "horizon", "logo": {"mark": "compass", "style": "badge"},
        "name": "Тропа", "tagline": "авторские туры по России",
        "contacts": {"phone": "+7 900 000-00-00", "telegram": "@tropa_tours", "email": "go@example.ru"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "poster", "base", title="Тропа", text="Небольшие группы, проверенные маршруты и гиды, которые здесь выросли. Карелия, Алтай, Байкал — от выходных до двух недель.",
                note="Ближайший выезд — 14 июня · Карелия, 5 дней", button="Выбрать тур", button_to="#tours", button2="Задать вопрос", button2_to="lead"),
            blk("products", "grid", "alt", nav="Туры", id="tours", title="Туры сезона", text="Цена — за человека: проживание, питание, трансферы и гид.",
                button="Хочу в тур", button_to="lead", items=[
                    it(title="Карелия: озёра и шхеры", text="5 дней, июнь–август, байдарки", price="38 000 ₽"),
                    it(title="Алтай: Чуйский тракт", text="8 дней, на машинах и пешком", price="64 000 ₽"),
                    it(title="Байкал по льду", text="6 дней, февраль–март", price="72 000 ₽"),
                    it(title="Выходные в Плёсе", text="2 дня, можно с детьми", price="14 500 ₽")]),
            blk("schedule", "agenda", "base", nav="Программа", title="Карелия за пять дней", text="Пример программы — так же подробно расписан каждый тур.", items=[
                it(time="День 1", title="Встреча в Петрозаводске", text="Трансфер на базу, ужин у костра"),
                it(time="День 2", title="Байдарки по шхерам", text="15 км по воде, обед на острове"),
                it(time="День 3", title="Рускеала", text="Мраморный каньон и горный парк"),
                it(time="День 4", title="Свободный день", text="Баня, рыбалка или прогулка по лесу"),
                it(time="День 5", title="Возвращение", text="Трансфер к поезду к 14:00")]),
            blk("features", "icons", "alt", title="Почему с нами спокойно", items=[
                it(title="Группы до 12", text="Успеваем поговорить с каждым", mark="chat"),
                it(title="Местные гиды", text="Знают тропы, погоду и лучшие виды", mark="compass"),
                it(title="Всё включено", text="Жильё, еда и трансферы — уже в цене", mark="check"),
                it(title="Безопасность", text="Страховка и спутниковая связь на маршруте", mark="shield")]),
            blk("gallery", "strip", "base", nav="Фото", title="С наших маршрутов", items=[
                it(caption="Рассвет на Онежском озере"), it(caption="Перевал Кату-Ярык"), it(caption="Лёд Байкала"), it(caption="Плёс с высоты")]),
            blk("faq", "list", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="Нужна ли физическая подготовка?", a="Для большинства туров — нет. У каждого тура указана сложность; подскажем, какой подойдёт."),
                it(q="Что взять с собой?", a="Список вещей пришлём после записи. Палатки и байдарки — наши."),
                it(q="Можно с детьми?", a="Да, в семейные туры — с 7 лет.")]),
            blk("lead", "card", "accent", nav="Запись", title="Забронируйте место", text="Мест в группе немного — напишите, какой тур интересен.",
                button="Забронировать", ask_message=True, thanks="Спасибо! Напишем сегодня и расскажем о туре подробно."),
        ]}]},
    "pets": {
        "title": "Груминг, питомцы", "sub": "абрикосовый и бирюзовый, округлый шрифт, меню цен и «до и после»", "palette": "apricot", "fonts": "round",
        "radius": "round", "menu": "center", "header": "light", "art": "spots", "logo": {"mark": "paw", "style": "badge"},
        "name": "Хвост", "tagline": "груминг для собак и кошек",
        "contacts": {"phone": "+7 900 000-00-00", "address": "ул. Лесная, 9", "hours": "Ежедневно 10:00–21:00", "telegram": "@hvost_groom"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Стрижка без стресса — и для питомца, и для вас",
                text="Груминг собак и кошек любых пород. Работаем без седации, спокойно и с перерывами, если питомец устал.",
                note="ул. Лесная, 9 · ежедневно с 10 до 21", button="Записать питомца", button_to="lead", button2="Цены", button2_to="#prices"),
            blk("prices", "menu", "alt", nav="Цены", id="prices", title="Цены", text="Точная цена зависит от породы и состояния шерсти — скажем при записи.", items=[
                it(group="Собаки", title="Комплекс, мелкие породы", text="мытьё, стрижка, когти, уши", price="от 2 000 ₽", featured=True),
                it(group="Собаки", title="Комплекс, средние породы", price="от 3 000 ₽"),
                it(group="Собаки", title="Тримминг", text="для жесткошёрстных пород", price="от 3 500 ₽"),
                it(group="Кошки", title="Комплекс", text="мытьё, сушка, вычёсывание", price="от 2 500 ₽"),
                it(group="Кошки", title="Стрижка «под льва»", price="от 3 000 ₽"),
                it(group="Отдельно", title="Стрижка когтей", price="500 ₽"), it(group="Отдельно", title="Чистка ушей", price="300 ₽")]),
            blk("features", "big", "base", title="Как мы работаем с питомцем", items=[
                it(title="Без седации", text="Успокаиваем лаской, лакомством и перерывами", mark="heart"),
                it(title="Стерильно", text="Инструменты обрабатываем после каждого гостя", mark="shield"),
                it(title="Вы в курсе", text="Фото и видео процесса — вам в мессенджер", mark="camera")]),
            blk("gallery", "pairs", "alt", nav="Работы", title="До и после", items=[
                it(caption="Шпиц, стрижка «мишка»"), it(caption=""), it(caption="Мейн-кун, вычёсывание"), it(caption="")]),
            blk("steps", "line", "base", title="Первый визит", items=[
                it(title="Запись", text="Порода, возраст и что нужно сделать"),
                it(title="Знакомство", text="Даём питомцу привыкнуть к мастеру"),
                it(title="Груминг", text="С перерывами, без спешки"),
                it(title="Домой", text="Подскажем, как ухаживать за шерстью")]),
            blk("faq", "two", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="Мой пёс боится стрижки — что делать?", a="Начнём с короткого визита-знакомства без стрижки. Обычно со второго раза питомцы спокойнее."),
                it(q="Можно остаться рядом?", a="Да, если питомцу так спокойнее. Некоторым, наоборот, легче без хозяина."),
                it(q="С какого возраста можно стричь щенка?", a="После всех прививок и карантина, обычно с 4 месяцев."),
                it(q="Сколько длится груминг?", a="От часа до трёх — зависит от породы и шерсти.")]),
            blk("lead", "split", "dark", nav="Запись", title="Запишите питомца", text="Расскажите породу и что нужно сделать — подберём мастера и время.",
                button="Записаться", ask_message=True, thanks="Спасибо! Перезвоним и подберём время."),
            blk("contacts", "split", "base", nav="Контакты", title="Как нас найти", text="Отдельный вход с улицы, рядом — площадка для выгула."),
        ]}]},
    "cakes": {
        "title": "Торты на заказ, кондитер", "sub": "ваниль и шоколад, праздничные засечки, витрина и начинки", "palette": "vanilla", "fonts": "elegant",
        "radius": "round", "menu": "burger", "header": "light", "art": "sprinkles", "logo": {"mark": "cake", "style": "plain"},
        "name": "Безе", "tagline": "торты на заказ",
        "contacts": {"phone": "+7 900 000-00-00", "telegram": "@beze_cakes", "address": "Самовывоз: ул. Цветочная, 16", "hours": "Заказы — с 9:00 до 21:00"},
        "pages": [{"title": "Главная", "blocks": [
            blk("hero", "split", "base", title="Торты, которые сначала фотографируют, а потом съедают",
                text="Пеку на сливочном масле и настоящих сливках, без растительных жиров. Бенто, бисквитные и муссовые торты — к любому празднику.",
                note="Заказ — за три дня · доставка по городу", button="Заказать торт", button_to="lead", button2="Начинки", button2_to="#fillings"),
            blk("products", "grid", "alt", nav="Торты", title="Торты и десерты", text="Фото — для примера: каждый торт оформляю под ваш праздник.",
                button="Заказать", button_to="lead", items=[
                    it(title="Бенто-торт", text="Ø 11 см, 450 г, надпись по желанию", price="1 500 ₽"),
                    it(title="Бисквитный торт", text="от 1,5 кг, две начинки на выбор", price="2 600 ₽ за кг"),
                    it(title="Муссовый торт", text="от 1,2 кг, зеркальная глазурь", price="2 900 ₽ за кг"),
                    it(title="Капкейки", text="набор из 6 штук", price="1 500 ₽")]),
            blk("prices", "menu", "base", nav="Начинки", id="fillings", title="Начинки", text="Цена за килограмм; декор — от 500 ₽.", items=[
                it(group="Бисквитные", title="Шоколад и вишня", price="2 600 ₽"), it(group="Бисквитные", title="Ваниль и клубника", price="2 600 ₽"),
                it(group="Бисквитные", title="Морковный", text="крем из сливочного сыра, грецкий орех", price="2 700 ₽", featured=True),
                it(group="Муссовые", title="Три шоколада", price="2 900 ₽"), it(group="Муссовые", title="Манго и маракуйя", price="3 000 ₽")]),
            blk("steps", "line", "alt", nav="Как заказать", title="Как заказать", items=[
                it(title="Напишите", text="Дата, повод и сколько будет гостей"), it(title="Обсудим", text="Начинку, вес и оформление"),
                it(title="Предоплата", text="50% — и дата закреплена за вами"), it(title="Праздник", text="Заберите сами или привезём")]),
            blk("gallery", "mosaic", "base", nav="Фото", title="Мои торты", items=[
                it(caption="Свадебный, три яруса"), it(caption="Бенто на день рождения"), it(caption="Капкейки"), it(caption="Детский торт"), it(caption="Муссовый")]),
            blk("faq", "list", "alt", nav="Вопросы", title="Вопросы", items=[
                it(q="За сколько дней заказывать?", a="Минимум за три дня, на выходные и праздники — лучше за неделю."),
                it(q="Можно без сахара или без глютена?", a="Некоторые начинки — да. Напишите, что нельзя, — предложу варианты."),
                it(q="Как хранить торт?", a="В холодильнике, до трёх суток. Достаньте за 30 минут до подачи.")]),
            blk("lead", "split", "dark", nav="Заказ", title="Заказать торт", text="Расскажите о празднике — отвечу и пришлю варианты оформления.",
                button="Отправить", ask_message=True, thanks="Спасибо! Отвечу в течение пары часов."),
            blk("contacts", "band", "base", nav="Контакты", title="Связаться", text="Доставка по городу — 400 ₽, бесплатно от 5 000 ₽."),
        ]}]},
}
TEMPLATE_ORDER = ["course", "bistro", "beauty", "coffee", "salon", "fitness", "dental", "lawyer", "kids", "school", "auto", "shop", "cakes", "photo", "wedding", "clinic",
                  "realty", "travel", "pets", "event", "startup", "personal", "repair"]

# слова в описании -> шаблон (первый подошедший; ничего — «личная страница», если о человеке, иначе «стартап»). Порядок важен:
# «торты» раньше «кофейни», «стоматология» и «груминг» раньше «клиники», «экскурсии» раньше «курсов» (в слове есть «курс»)
KIND_WORDS = [
    ("bistro", r"пекарн|булочн|хлебн|\bхлеб|лавк|фермерск|гастроном|стрит[- ]?фуд|бургерн|пиццери|шаурм|пончик|выпечк\w* (?:к|на) (?:завтрак|утр)"),
    ("beauty", r"косметолог|эстетист|уход\w* за лиц|студи\w* (?:красоты|ухода)|клиник\w* красоты|архитектур\w* бровей|ламинир|\bспа\b|spa"),
    ("cakes", r"торт|кондитер|капкейк|бенто|пряник|макарон|зефир|десерт\w* на заказ|выпечк\w* на заказ"),
    ("coffee", r"коф|кафе|ресторан|\bбар\b|пекарн|пицц|суши|столов|бургер|чайн|булочн|кулинар|доставк\w* еды|гастро|бистро|кухн"),
    ("pets", r"груминг|грумер|зоосалон|зоомагаз|ветеринар|ветклиник|питом|собак|кошек|кошк|щен|котят|кинолог|передержк|животн"),
    ("dental", r"стоматолог|зуб|дантист|ортодонт|имплантаци|брекет|элайнер"),
    ("salon", r"салон|маникюр|педикюр|парикмах|барбер|косметолог|массаж|бров|ресниц|красот|\bспа\b|ногт|визаж|эпиляц|тату"),
    ("fitness", r"фитнес|тренаж|спортзал|спортклуб|\bйог|пилатес|кроссфит|растяжк|бокс|единоборств|танц|стретчинг|персональн\w* тренер|фитнес-тренер|тренер по"),
    ("clinic", r"клиник|врач|медицин|доктор|здоровь|поликлин|медцентр|анализ|лечени"),
    ("realty", r"риелтор|риэлтор|недвижимост|новостро|ипотек|агентств\w* недвиж|продаж\w* квартир|аренд\w* квартир"),
    ("lawyer", r"юрист|юридич|адвокат|консалтинг|бухгалт|нотари|финансов|страхов|аудит|налог"),
    ("kids", r"детск|развива|репетитор|логопед|дошкол|подготовк\w* к школе|кружок|кружк|продлёнк|продленк|няня|для детей"),
    ("travel", r"\bтур(?:ы|ов|ам|агент|оператор|изм|ист)?\b|экскурс|путешеств|\bгид\b|поход|сплав|турбаз|глэмпинг|гостев\w* дом|база отдыха"),
    ("course", r"онлайн[- ]?(?:курс|школ|обучени)|курс\w* по\b|наставни|менторств|вебинар|интенсив|марафон|эксперт\w*,? (?:в|по)\b|инфопродукт"),
    ("school", r"школ|курс|обучени|урок|академи|тренинг|вебинар|занятия|преподава|учител"),
    ("wedding", r"свадьб|свадеб|венчан|выездн\w* регистрац|декор\w* (?:зала|праздник|свадьб)|организаци\w* праздник|ведущ\w* (?:свадьб|праздник)"),
    ("event", r"мероприят|конференц|фестивал|концерт|праздник|вечеринк|митап|выставк|ярмарк|маркет|форум|турнир"),
    ("photo", r"фотограф|портфолио|дизайнер|художни|видеограф|иллюстрат|архитект|фотостуди|видеосъ"),
    ("shop", r"магазин|витрин|товар|интернет-магазин|\bшоп|одежд|цвет(?:ы|ов|очн)|букет|флорист|подарк|сувенир|украшени|мебел\w* на заказ|каталог"),
    ("auto", r"автосервис|шиномонтаж|автомойк|детейлинг|кузовн|автомастерск|\bсто\b|авторемонт|ремонт\w* (?:авто|машин)|автоэлектр|развал"),
    ("repair", r"ремонт|стро(?:ит|йк)|сантехник|электрик|отделк|муж на час|мастер на час|клининг|уборк|окна|потолк|кровл"),
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
        "stats": {"items": [it(value="10+", label="лет опыта"), it(value="500", label="довольных клиентов"), it(value="24/7", label="на связи")]},
        "hub": {"center": "Вы", "items": [it(title="Часть", sub="коротко", text="Подробнее о ней"), it(title="Ещё часть", sub="коротко", text="Подробнее"),
                                          it(title="И ещё", sub="коротко", text="Подробнее")]},
        "duo": {"items": [it(tag="с нами", title="Быстро и спокойно", text="Как будет, если выбрать вас.", foot="вперёд"),
                          it(tag="без нас", title="Долго и самому", text="Как будет без вас.", foot="потом")]},
        "bars": {"unit": "", "items": [it(title="Первое", value="10"), it(title="Второе", value="25"), it(title="Третье", value="40")]},
        "cases": {"items": [it(title="Проект", who="Клиент", text="Что сделали", metric="+20%", metric_label="результат")]},
        "ticker": {"text": "Свежее каждый день · Рядом с домом · Заходите", "title": ""},
        "cta": {"text": "Одна фраза — зачем написать вам прямо сейчас.", "button": "Оставить заявку", "button_to": "lead"},
        "text": {"text": "Текст раздела."},
        "contacts": {"title": "Контакты"},
        "lead": {"title": "Оставьте заявку", "text": "Перезвоним и ответим на вопросы.", "button": "Отправить", "thanks": "Спасибо! Скоро свяжемся."},
    }.get(t, {})
    d.update(starter)
    return d
