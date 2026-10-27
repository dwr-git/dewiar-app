"""Текст для русского синтеза речи: числа — словами, латиница — русскими буквами, служебные символы — прочь.

Голоса Vosk TTS знают только русские буквы: на «1», «USB», «16:30» синтез падает или фраза пропадает целиком.
Вызывается из VoskTTS.synth (tts.py) перед синтезом; итог должен состоять только из кириллицы и простой пунктуации
(последний фильтр в speech_norm). Новые английские слова с особым чтением — в _KNOWN.
    speech_norm("Ядро 6.17, порт USB 3, в 16:30 — 45%")
    → "Ядро шесть точка семнадцать, порт ю-эс-би три, в шестнадцать тридцать — сорок пять процентов"
"""

import re

_ONES = ["ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять", "десять", "одиннадцать",
         "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать",
         "девятнадцать"]
_ONES_F = {1: "одна", 2: "две"}
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUND = ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]
_SCALES = [(10 ** 12, ("триллион", "триллиона", "триллионов"), False), (10 ** 9, ("миллиард", "миллиарда", "миллиардов"), False),
           (10 ** 6, ("миллион", "миллиона", "миллионов"), False), (1000, ("тысяча", "тысячи", "тысяч"), True)]


def _plural(n, forms):
    n = abs(n) % 100
    if 11 <= n <= 14:
        return forms[2]
    return forms[0] if n % 10 == 1 else forms[1] if 2 <= n % 10 <= 4 else forms[2]


def _under_1000(n, fem=False):
    out = []
    if n >= 100:
        out.append(_HUND[n // 100])
        n %= 100
    if n >= 20:
        out.append(_TENS[n // 10])
        n %= 10
    if n or not out:
        if n or not out:
            out.append(_ONES_F.get(n, _ONES[n]) if fem and n in _ONES_F else _ONES[n])
    return [w for w in out if w and not (w == "ноль" and len(out) > 1)]


def number_words(n, fem=False):
    """Целое число → слова: 2026 → «две тысячи двадцать шесть»."""
    n = int(n)
    if n < 0:
        return "минус " + number_words(-n, fem)
    if n == 0:
        return "ноль"
    words = []
    for value, forms, female in _SCALES:
        if n >= value:
            k = n // value
            if k > 1:
                words += _under_1000(k, fem=female) if k < 1000 else number_words(k).split()
            words.append(_plural(k, forms))
            n %= value
    if n:
        words += _under_1000(n, fem)
    return " ".join(words)


_LETTER = {"a": "эй", "b": "би", "c": "си", "d": "ди", "e": "и", "f": "эф", "g": "джи", "h": "эйч", "i": "ай", "j": "джей",
           "k": "кей", "l": "эл", "m": "эм", "n": "эн", "o": "оу", "p": "пи", "q": "кью", "r": "ар", "s": "эс", "t": "ти",
           "u": "ю", "v": "ви", "w": "дабл-ю", "x": "экс", "y": "уай", "z": "зед"}
_TR2 = [("sch", "ш"), ("sh", "ш"), ("ch", "ч"), ("th", "т"), ("ph", "ф"), ("ck", "к"), ("oo", "у"), ("ee", "и"), ("ea", "и"),
        ("ou", "ау"), ("qu", "кв"), ("kh", "х"), ("zh", "ж"), ("ya", "я"), ("yu", "ю"), ("yo", "ё"), ("ts", "ц")]
_TR1 = {"a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л",
        "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "кс",
        "y": "и", "z": "з"}
_KNOWN = {"linux": "линукс", "ubuntu": "убунту", "windows": "виндоус", "telegram": "телеграм", "max": "макс", "dewiar": "дэвиаар",
          "youtube": "ютуб", "google": "гугл", "yandex": "яндекс", "wifi": "вай-фай", "wi-fi": "вай-фай", "ok": "окей",
          "email": "имейл", "sudo": "судо", "python": "пайтон", "chrome": "хром", "obsidian": "обсидиан", "android": "андроид",
          "iphone": "айфон", "bluetooth": "блютус", "hdmi": "эйч-ди-эм-ай", "jazz": "джаз", "relax": "релакс", "fm": "эф-эм"}


def latin_word(w):
    low = w.lower()
    if low in _KNOWN:
        return _KNOWN[low]
    if w.isupper() and len(w) <= 6 or len(w) == 1:              # USB, HDMI, AI — по буквам
        return "-".join(_LETTER.get(c, c) for c in low)
    out, i = "", 0
    while i < len(low):
        for a, b in _TR2:
            if low.startswith(a, i):
                out, i = out + b, i + len(a)
                break
        else:
            out += _TR1.get(low[i], low[i])
            i += 1
    return out


def _num(m):
    s = m.group(0)
    if ":" in s:                                                  # время 16:30
        h, mi = s.split(":", 1)
        return number_words(int(h)) + (" ноль " + number_words(int(mi)) if mi.startswith("0") and mi != "00"
                                       else "" if mi == "00" else " " + number_words(int(mi)))
    parts = re.split(r"[.,]", s)
    if len(parts) == 1:                                           # длиннее 15 цифр (номера, коды) — по одной цифре
        return number_words(int(s)) if len(s) <= 15 else " ".join(number_words(int(c)) for c in s)
    return " точка ".join(number_words(int(p)) if p else "" for p in parts)


_FRAC = {1: ("десятая", "десятых", "десятых"), 2: ("сотая", "сотых", "сотых")}
_MONEY = {"rub": (("рубль", "рубля", "рублей"), ("копейка", "копейки", "копеек")),
          "usd": (("доллар", "доллара", "долларов"), ("цент", "цента", "центов")),
          "eur": (("евро", "евро", "евро"), ("цент", "цента", "центов"))}


def _money(m, cur):
    n, k = int(m.group("n")), m.group("k")
    rub, kop = _MONEY[cur]
    out = f"{number_words(n)} {_plural(n, rub)}"
    if k and int(k.ljust(2, "0")):
        kk = int(k.ljust(2, "0"))
        out += f" {number_words(kk, fem=cur == 'rub')} {_plural(kk, kop)}"
    return out


def _decimal(m):
    """«399,5» → «триста девяносто девять и пять десятых» (запятая — дробь; точка — версии и номера, «шесть точка семнадцать»)."""
    a, b = m.group(1), m.group(2)
    return f"{number_words(int(a), fem=True)} и {number_words(int(b), fem=True)} {_plural(int(b), _FRAC[len(b)])}"


# ---------- согласование и порядковые: «1 минута» — «одна», «2 недели» — «две», «15 октября» — «пятнадцатое», «2026 года» ----------
_MONTHS = "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
_ORD = {1: "перв", 2: "втор", 3: "трет", 4: "четвёрт", 5: "пят", 6: "шест", 7: "седьм", 8: "восьм", 9: "девят", 10: "десят",
        11: "одиннадцат", 12: "двенадцат", 13: "тринадцат", 14: "четырнадцат", 15: "пятнадцат", 16: "шестнадцат",
        17: "семнадцат", 18: "восемнадцат", 19: "девятнадцат", 20: "двадцат", 30: "тридцат", 40: "сороков", 50: "пятидесят",
        60: "шестидесят", 70: "семидесят", 80: "восьмидесят", 90: "девяност", 100: "сот"}
# окончания: род/падеж -> (обычное, «ударное» -ой для втор/шест/седьм/восьм/сороков, «трет» — мягкое)
_ORD_END = {"m_nom": ("ый", "ой", "ий"), "n_nom": ("ое", "ое", "ье"), "gen": ("ого", "ого", "ьего"), "dat": ("ому", "ому", "ьему"),
            "prep": ("ом", "ом", "ьем"), "ins": ("ым", "ым", "ьим"), "f_nom": ("ая", "ая", "ья"), "f_gen": ("ой", "ой", "ьей"),
            "pl": ("ые", "ые", "ьи")}


def ordinal_words(n, form="n_nom"):
    """Порядковое: 15 → «пятнадцатое», 2026 (form=gen) → «две тысячи двадцать шестого». Круглые тысячи — None (редко,
    читаем количественным)."""
    n = int(n)
    last = n % 100 if n % 100 < 20 else n % 10 or n % 100
    if n % 100 >= 20 and n % 10:
        last = n % 10
    if not last or last not in _ORD:
        if n % 100 == 0 and n % 1000:
            last = 100
        else:
            return None
    head = number_words(n - last) if n - last else ""
    stem = _ORD[last]
    i = 2 if stem == "трет" else 1 if stem in ("втор", "шест", "седьм", "восьм", "сороков") else 0
    end = _ORD_END[form][i]
    if stem == "трет":
        stem, end = "трет", end
    word = stem + end
    if head.endswith("сто") and last == 100:
        head = head[:-3].strip()
    return (head + " " + word).strip()


_FEM_RX = re.compile(r"[ая]$")                  # «1 минута», «1 неделя»
_FEM2_RX = re.compile(r"[ыи]$")                 # «2 минуты», «2 недели» (у мужского — «2 часа», «2 дня»)
_NEUT_RX = re.compile(r"[ое]$")                 # «1 яблоко», «1 сообщение»
_NOT_FEM = {"часа", "дня", "года", "раза", "рубля", "доллара", "человека", "шага", "градуса", "процента", "километра", "метра",
            "литра", "килограмма", "грамма", "пункта", "этажа", "балла", "урока", "вопроса", "ответа", "файла", "месяца", "мужчина", "папа"}
_NOT_NEUT = {"кофе", "евро", "кино", "метро", "пальто", "радио", "фото"}


def _agree(n, word):
    """Число перед словом — в роде этого слова (только 1 и 2 меняются): «одна минута», «две недели», «одно яблоко»."""
    w = word.lower()
    k, k2 = n % 10, n % 100
    if 11 <= k2 <= 14 or k not in (1, 2):
        return number_words(n)
    if k == 1 and _FEM_RX.search(w) and w not in _NOT_FEM:
        return number_words(n, fem=True)
    if k == 2 and _FEM2_RX.search(w) and w not in _NOT_FEM:
        return number_words(n, fem=True)
    if k == 1 and re.search(r"[ую]$", w):            # «через 1 минуту», «на 1 неделю» — винительный женского
        return re.sub(r"один$", "одну", number_words(n))
    if k == 1 and _NEUT_RX.search(w) and w not in _NOT_NEUT:
        return re.sub(r"один$", "одно", number_words(n))
    return number_words(n)


def _date(m):
    """«15 октября» → «пятнадцатое октября»; после «до/с/от/после/около» — «пятнадцатого», после «к/по» — «пятнадцатому»."""
    pre, n, mon = m.group(1) or "", int(m.group(2)), m.group(3)
    p = pre.strip().lower()
    form = "gen" if p in ("до", "с", "со", "от", "после", "около", "начиная с", "кроме") else "dat" if p in ("к", "ко", "по") else "n_nom"
    w = ordinal_words(n, form) if 1 <= n <= 31 else None
    return f"{pre}{w or number_words(n)} {mon}"


def _year(m):
    """«2026 год» → «две тысячи двадцать шестой год», «2026 года» → «…шестого года», «в 2026 году» → «…шестом году»."""
    n, g = int(m.group(1)), m.group(2)
    form = {"год": "m_nom", "года": "gen", "году": "prep", "годом": "ins", "годе": "prep"}.get(g.lower(), "m_nom")
    w = ordinal_words(n, form)
    return f"{w or number_words(n)} {g}"


_MONTH_LIST = _MONTHS.split("|")


def _ddate(m):
    """«14.10.2026» → «четырнадцатое октября две тысячи двадцать шестого года» (после «до/с/к…» — в нужном падеже)."""
    pre, d, mo, y = m.group(1) or "", int(m.group(2)), int(m.group(3)), int(m.group(4))
    if not (1 <= d <= 31 and 1 <= mo <= 12):
        return m.group(0)
    p = pre.strip().lower()
    form = "gen" if p in ("до", "с", "со", "от", "после", "около", "начиная с", "кроме") else "dat" if p in ("к", "ко", "по") else "n_nom"
    return f"{pre}{ordinal_words(d, form) or number_words(d)} {_MONTH_LIST[mo - 1]} {ordinal_words(y, 'gen') or number_words(y)} года"


# Римские цифры (пакет 27.10: «Лира не умеет читать римские цифры»): «XIX век» → «девятнадцатый век», «Пётр I» → «Пётр
# первый», «Ступень I» → «Ступень первая», «Екатерины II» → «Екатерины второй». Одна буква — только I, V, X (C, D, L, M —
# скорее витамин или размер); после латинского слова («Mac OS X», «I love») — не трогаем.
_ROMAN = r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
_RV = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_R_FEM = {"часть", "ступень", "глава", "книга", "серия", "война", "олимпиада", "категория", "группа", "степень", "четверть",
          "половина", "лига", "конференция", "дума", "республика", "симфония", "соната", "партия", "редакция", "мировая",
          "екатерина", "елизавета", "анна", "мария", "империя", "династия", "эпоха", "фаза", "стадия", "очередь"}
_R_FEM_GEN = {"екатерины", "елизаветы", "анны", "марии", "части", "главы", "книги", "серии", "войны", "степени", "стадии", "фазы"}
_R_NEUT = {"издание", "тысячелетие", "собрание", "поколение", "царство", "отделение"}
_R_SKIP = {"размер", "размера", "размеры", "размеров", "витамин", "витамина", "группы", "класс"}


def roman_value(s):
    """«XIX» → 19; не римское число (или пустое) — 0."""
    if not s or not re.fullmatch(_ROMAN, s):
        return 0
    v = [_RV[c] for c in s]
    return sum(-x if i + 1 < len(v) and x < v[i + 1] else x for i, x in enumerate(v))


def _roman_ok(r):
    return roman_value(r) and (len(r) > 1 or r in "IVX")


def _century(m):
    pre, a, b, w = m.group(1) or "", m.group(2), m.group(3), m.group(4)
    wl = w.lower().rstrip(".")
    if pre and wl == "в":                                       # «в XXI в.» — «в двадцать первом веке»
        wl, w = "веке", "веке"
    elif pre and wl == "вв":
        wl, w = "веках", "веках"
    form = {"век": "m_nom", "века": "gen", "веку": "dat", "веке": "prep", "веком": "ins", "веков": "gen", "веках": "prep",
            "в": "m_nom", "вв": "pl"}.get(wl, "m_nom")
    if b and form == "m_nom":
        form = "pl"
    if not _roman_ok(a) or (b and not _roman_ok(b)):
        return m.group(0)
    word = {"в": "век", "вв": "века"}.get(wl, w)
    if form == "pl" and wl in ("век", "в"):
        word = "века"
    head = ordinal_words(roman_value(a), form)
    if b:
        head += " — " + ordinal_words(roman_value(b), form)
    return f"{pre}{head} {word}"


def _roman_after(m):
    w, r = m.group(1), m.group(2)
    lw = w.lower()
    if not _roman_ok(r) or lw in _R_SKIP:
        return m.group(0)
    if lw in _R_FEM:
        form = "f_nom"
    elif lw in _R_FEM_GEN:
        form = "f_gen"
    elif lw in _R_NEUT:
        form = "n_nom"
    elif w[:1].isupper() and re.search(r"[ая]$", lw):          # «Петра I», «Николая II» — родительный
        form = "gen"
    elif w[:1].isupper() and re.search(r"[ую]$", lw):
        form = "dat"
    elif w[:1].isupper() and re.search(r"(?:ом|ем|ём)$", lw):
        form = "ins"
    elif w[:1].isupper() and re.search(r"е$", lw):              # «при Николае II»
        form = "prep"
    else:
        form = "m_nom"
    return f"{w} {ordinal_words(roman_value(r), form)}"


def roman_norm(t):
    t = re.sub(r"((?:(?<=\s)|^)(?:в|во)\s+)?(?<![A-Za-z])([IVXLCDM]+)(?:\s*[-–—]\s*([IVXLCDM]+))?\s+(век(?:а|у|е|ом|ов|ах)?|вв?\.)(?![а-яё])", _century, t, flags=re.I)
    return re.sub(r"(?<![A-Za-z])([А-ЯЁа-яё]+)\s+([IVXLCDM]+)(?![A-Za-z0-9])(?!\s+[A-Za-z])", _roman_after, t)


def speech_norm(text, latin=True):
    """latin=False — только числа, суммы, проценты, время (Piper, eSpeak, голос Windows: латиницу они читают сами)."""
    t = roman_norm(str(text or ""))
    for _ in range(3):                                             # «1 437 500» — одно число (разряды через пробел)
        t = re.sub(r"(?<![\d.,])(\d{1,3})[ \u00a0\u202f](?=\d{3}(?!\d))", r"\1", t)
    num = r"(?P<n>\d+)(?:[.,](?P<k>\d{1,2}))?"
    t = re.sub(num + r"\s*(?:руб(?:л[а-яё]*)?\.?|₽|р\.|BYN|RUB)(?![а-яёА-ЯЁA-Za-z])", lambda m: _money(m, "rub"), t)
    t = re.sub(r"\$\s*" + num + r"|" + num.replace("?P<n>", "?P<n2>").replace("?P<k>", "?P<k2>") + r"\s*(?:\$|долл\.|USD)",
               lambda m: _money(re.match(num, (m.group("n") or m.group("n2")) + ("," + (m.group("k") or m.group("k2")) if (m.group("k") or m.group("k2")) else "")), "usd"), t)
    t = re.sub(num + r"\s*(?:€|EUR)", lambda m: _money(m, "eur"), t)
    t = re.sub(r"(?<![\d.,:])(\d{1,9}),(\d{1,2})(?!\d|[.,]\d)", _decimal, t)
    # пример со знаками: «12 - 10 = 2», «3 × 4», «8 ÷ 2» — словами (отзыв 16.10: «равно 2» — двойку не было слышно)
    t = re.sub(r"(?<=\d)\s*=\s*(?=[-−]?\d)", " равно ", t)
    t = re.sub(r"(?<=\d)\s+[-−–]\s+(?=\d)", " минус ", t)
    t = re.sub(r"(?<=\d)\s*\+\s*(?=\d)", " плюс ", t)
    t = re.sub(r"(?<=\d)\s*[×*]\s*(?=\d)", " умножить на ", t)
    t = re.sub(r"(?<=\d)\s*÷\s*(?=\d)", " разделить на ", t)
    t = re.sub(r"https?://\S+", "ссылка", t)
    if latin:
        t = re.sub(r"\b(?=\w*\d)(?=\w*[A-Za-z])[A-Za-z0-9_]{4,}\b", " ", t)   # 17e9, x86_64 — служебные метки вслух не нужны
    t = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", t)     # USB3 → USB 3: буквы и цифры читаются по-разному
    t = re.sub(r"(?<![\w-])\+(?=\d)", "плюс ", t)                 # «+12°» — плюс двенадцать градусов
    t = re.sub(r"(?<![\w-])[-−](?=\d)", "минус ", t)
    t = re.sub(r"(\d+)\s*%", lambda m: f"{number_words(int(m.group(1)))} {_plural(int(m.group(1)), ('процент', 'процента', 'процентов'))}", t)
    t = re.sub(r"(\d+)\s*°\s*[CС]?(?![A-Za-zА-Яа-яЁё])", lambda m: f"{number_words(int(m.group(1)))} {_plural(int(m.group(1)), ('градус', 'градуса', 'градусов'))}", t)
    t = re.sub(r"((?:(?<=\s)|^)(?:до|с|со|от|после|около|к|ко|по)\s+)?(?<![\d.,:])(\d{1,2})\.(\d{1,2})\.(\d{4})(?![\d.,]\d)", _ddate, t, flags=re.I)
    t = re.sub(r"(?<![\d.,:])(\d{3,4})\s+(год|года|году|годом|годе)(?![а-яё])", _year, t)
    t = re.sub(r"((?:(?<=\s)|^)(?:до|с|со|от|после|около|к|ко|по|на|в)\s+)?(?<![\d.,:])(\d{1,2})\s+(" + _MONTHS + r")(?![а-яё])", _date, t, flags=re.I)
    # число перед словом — в его роде: «1 минута», «2 недели», «1 сообщение» (время 10:30 и дроби уже словами)
    t = re.sub(r"(?<![\d.,:])(\d{1,15})(?![\d.,:])(\s+)([А-Яа-яЁё]+)", lambda m: _agree(int(m.group(1)), m.group(3)) + m.group(2) + m.group(3), t)
    t = re.sub(r"\b([01]?\d|2[0-3]):[0-5]\d\b|\d+(?:[.,]\d+)*", _num, t)
    if not latin:
        return _end(re.sub(r"[ \t]+", " ", t.replace("№", "номер ")).strip())
    t = re.sub(r"[A-Za-z]+(?:-[A-Za-z]+)?", lambda m: latin_word(m.group(0)), t)
    t = t.replace("&", " и ").replace("+", " плюс ").replace("=", " равно ").replace("№", "номер ")
    t = re.sub(r"[^А-Яа-яЁё ,.!?:;—\-«»\"()']+", " ", t)
    return _end(re.sub(r"\s+", " ", t).strip())


def _end(t):
    """Фраза без точки в конце — с точкой: иначе голос сервера глотал последнее слово («…равно два» — без «два»)."""
    return t + "." if t and re.search(r"[0-9A-Za-zА-Яа-яЁё»)\"']$", t) else t
