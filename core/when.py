"""«Напомни мне завтра в 9 позвонить маме» → когда, что, как часто — без языковой модели, мгновенно.

parse(text, now) → {"text", "at": datetime, "repeat": dict|None, "kind": "reminder"|"alarm"|"timer"} или None,
если это не просьба напомнить или время не понятно (тогда фразу разбирает модель).

Понимает: «через 10 минут / через полчаса / через полтора часа / через час 20», «в 15:30 / в 9 утра / в 7 вечера /
в 3 часа дня / в половине восьмого / в полдень», «сегодня / завтра / послезавтра / в пятницу / 5 октября / 05.10»,
«утром / днём / вечером», повторы: «каждый день в 8», «ежедневно», «каждое утро», «по будням», «по выходным»,
«каждый понедельник», «по вторникам и четвергам», «каждые 2 часа», «каждые полчаса», «каждый месяц 5 числа».
Числа — цифрами и словами («через пять минут», «в девять»), как пишет любое распознавание речи.

repeat: {"kind": "daily", "time": "08:00"}  {"kind": "weekly", "days": [0, 2], "time": "19:00"} (0 — понедельник)
        {"kind": "interval", "minutes": 120}  {"kind": "monthly", "day": 5, "time": "10:00"}
        {"kind": "interval", "minutes": 60, "from": "09:00", "to": "18:00", "days": [0, 1, 2, 3, 4]} — «по будням с 9 до 18
        каждый час» (окно — только днём и только в эти дни; отчёт №137, 20.10)
Этот формат хранят напоминания (Reminders в tools.py) и фоновые задания (jobs.py), он же уходит в синхронизацию
(sync.py) — менять только вместе с ними.
Следующее срабатывание повтора — next_time(), время словами — human(), повтор словами — describe_repeat().
"""

import calendar
import re
from datetime import datetime, timedelta

UNITS = {"ноль": 0, "один": 1, "одну": 1, "одна": 1, "одно": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5,
         "шесть": 6, "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12,
         "тринадцать": 13, "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17,
         "восемнадцать": 18, "девятнадцать": 19}
TENS = {"двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60, "семьдесят": 70,
        "восемьдесят": 80, "девяносто": 90}
HUNDREDS = {"сто": 100}
ORD_GEN = {"первого": 1, "второго": 2, "третьего": 3, "четвёртого": 4, "четвертого": 4, "пятого": 5, "шестого": 6,
           "седьмого": 7, "восьмого": 8, "девятого": 9, "десятого": 10, "одиннадцатого": 11, "двенадцатого": 12}
MONTHS = {"январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6, "июл": 7, "август": 8, "сентябр": 9,
          "октябр": 10, "ноябр": 11, "декабр": 12}
WEEKDAYS = [("понедельник", 0), ("вторник", 1), ("сред", 2), ("четверг", 3), ("пятниц", 4), ("суббот", 5),
            ("воскресень", 6)]
# дни недели: полное слово (любой падеж) или сокращение «пн, вт, ср, чт, пт, сб, вс» (30.10: «по будням, кроме пятницы»,
# «с понедельника по четверг», «пн-чт»)
DAY_RX = r"(?:понедельник\w*|вторник\w*|сред[аеуы]\w*|четверг\w*|пятниц\w*|суббот\w*|воскресень\w*|пн|вт|ср|чт|пт|сб|вс)"
DAY_SHORT = {"пн": 0, "вт": 1, "ср": 2, "чт": 3, "пт": 4, "сб": 5, "вс": 6}


def _day_of(w):
    w = w.strip().lower()
    return DAY_SHORT.get(w, next((i for p, i in WEEKDAYS if w.startswith(p)), None))


def _except_days(t):
    """«кроме пятницы», «кроме пт и сб», «за исключением субботы», «но не в пятницу» -> (дни, (начало, конец)) или None."""
    m = re.search(r"(?:,\s*)?\b(?:кроме|за\s+исключением|но\s+не\s+(?:в|по))\s+(" + DAY_RX + r"(?:\s*(?:,|и)\s*" + DAY_RX + r")*)\b", t)
    if not m:
        return None
    days = {d for d in (_day_of(w) for w in re.findall(DAY_RX, m.group(1))) if d is not None}
    return (days, (m.start(), m.end())) if days else None


TRIGGER = re.compile(
    r"^(?:(?:а|и|ну|пожалуйста|слушай)\s+)*"
    r"(?P<trig>напомни(?:те)?|напоминай(?:те)?|(?:поставь|сделай|создай|заведи)(?:те)?\s+(?:мне\s+)?(?:напоминание|будильник|таймер)"
    r"|разбуди(?:те)?|будильник|таймер|засеки(?:те)?|не\s+дай\s+(?:мне\s+)?забыть)\b(?P<rest>.*)$")
DAYPART = {"утром": 9, "утра": 9, "с утра": 9, "днём": 13, "днем": 13, "дня": 13, "вечером": 19, "вечера": 19,
           "ночью": 23, "ночи": 23}


def _num_words(text):
    """Числа словами — цифрами: «двадцать пять» → «25», «сто» → «100». «Полчаса», «полтора» и «пару» не трогаем —
    их разбирают _relative и _repeat."""
    words = text.split()
    out, i = [], 0
    while i < len(words):
        w = words[i]
        if w in TENS:
            n = TENS[w]
            if i + 1 < len(words) and words[i + 1] in UNITS and UNITS[words[i + 1]] < 10:
                n += UNITS[words[i + 1]]
                i += 1
            out.append(str(n))
        elif w in HUNDREDS:
            out.append(str(HUNDREDS[w]))
        elif w in UNITS:
            out.append(str(UNITS[w]))
        else:
            out.append(w)
        i += 1
    return " ".join(out)


def _norm(text):
    """Нижний регистр, ё → е, время к виду «15:30», без кавычек и знаков (кроме точек в датах), числа — цифрами."""
    t =(text or "").lower().replace("ё", "е").replace("четвертого", "четвертого")
    t = re.sub(r"\b(\d{1,2})[:\-](\d\d)\b", r"\1:\2", t)       # 15-30 → 15:30
    t = re.sub(r"\b((?:в|на|к)\s+\d{1,2})\.(\d\d)\b(?![./]\d)", r"\1:\2", t)   # «в 15.30» → 15:30, но 05.10 — дата
    t = re.sub(r"[«»\"“”!?;]", " ", t)
    t = re.sub(r"(?<!\d)[,.](?!\d)", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return _num_words(t)


def _unit_minutes(u):
    """Единица времени («секунды», «час», «дней», «неделю») -> сколько в ней минут, иначе None."""
    u = u.lower()
    if u.startswith("сек"):
        return 1 / 60
    if u.startswith("мин"):
        return 1
    if u.startswith("час"):
        return 60
    if u.startswith("д") or u.startswith("сут"):
        return 1440
    if u.startswith("недел"):
        return 10080
    return None


UNIT_RX = r"(секунд[уы]?|сек|минут[уы]?|мин|час(?:а|ов)?|дн(?:я|ей)|день|сут(?:ки|ок)|недел[юиь]|недель)"


def _relative(t):
    """Относительное время -> (минут от сейчас, (начало, конец) во фразе) или None.
    «через 2 часа 15 минут», «через полчаса», «через полтора часа», «через час 20» (20 минут), «через пару минут»,
    «через 10» (без единицы — минуты)."""
    for rx, val in ((r"\bчерез\s+полчаса\b", 30), (r"\bчерез\s+полтора\s+часа\b", 90),
                    (r"\bчерез\s+полторы\s+минуты\b", 1.5)):
        m = re.search(rx, t)
        if m:
            return val, (m.start(), m.end())
    m = re.search(r"\bчерез\s+(?:(пару|\d+(?:[.,]\d+)?)\s*)?" + UNIT_RX +
                  r"(?:\s+(?:и\s+)?(\d+)(?:\s*" + UNIT_RX + r")?)?", t)
    if m:
        n = 2.0 if m.group(1) == "пару" else float((m.group(1) or "1").replace(",", "."))
        base = _unit_minutes(m.group(2))
        total = n * base
        if m.group(3):
            u2 = _unit_minutes(m.group(4)) if m.group(4) else (1 if base == 60 else None)
            if u2 is None:
                return total, (m.start(), m.start(3) - 1)
            total += float(m.group(3)) * u2
        return total, (m.start(), m.end())
    m = re.search(r"\bчерез\s+(\d+)\b(?!\s*:)", t)              # «через 10» — минуты
    if m:
        return float(m.group(1)), (m.start(), m.end())
    return None


def _clock(t):
    """Время суток -> (час, минута, явно ли указана часть суток, (начало, конец)) или None.
    «в 3 часа дня» → 15, «в 2 ночи» → 2, «в 12 утра» → 0, «в половине восьмого» → 7:30. Без части суток час
    остаётся как сказан — утро или вечер решает parse(). Последний образец не берёт «в 5 минут», «в 5 числа», «на 5 мая»."""
    pats = [
        (r"\bв\s+полдень\b", lambda m: (12, 0, True)),
        (r"\bв\s+полночь\b", lambda m: (0, 0, True)),
        (r"\bв\s+половин[еу]\s+(\w+)(?:\s+(утра|дня|вечера|ночи))?", lambda m: (ORD_GEN[m.group(1)] - 1, 30, m.group(2))
         if m.group(1) in ORD_GEN else None),
        (r"\b(?:в|на|к)\s+(\d{1,2}):(\d{2})(?:\s+(утра|дня|вечера|ночи))?", lambda m: (int(m.group(1)), int(m.group(2)), m.group(3))),
        (r"\b(?:в|на|к)\s+(\d{1,2})\s+час(?:а|ов)?(?:\s+(\d{1,2})\s+минут\w*)?(?:\s+(утра|дня|вечера|ночи))?",
         lambda m: (int(m.group(1)), int(m.group(2) or 0), m.group(3))),
        (r"\b(?:в|на|к)\s+(\d{1,2})\s+(\d{2})\b(?:\s+(утра|дня|вечера|ночи))?", lambda m: (int(m.group(1)), int(m.group(2)), m.group(3))),
        (r"\b(?:в|на|к)\s+(\d{1,2})(?:\s+(утра|дня|вечера|ночи))?\b(?!\s*(?:" + UNIT_RX[1:-1] + r"|числ|январ|феврал|март|апрел|ма[яй]|июн|июл|август|сентябр|октябр|ноябр|декабр))",
         lambda m: (int(m.group(1)), 0, m.group(2))),
    ]
    for rx, fn in pats:
        m = re.search(rx, t)
        if not m:
            continue
        r = fn(m)
        if not r:
            continue
        h, mi, part = r
        if part is True:
            return h, mi, True, (m.start(), m.end())
        if part in ("дня", "вечера") and h < 12:
            h += 12
        if part == "ночи" and 6 <= h < 12:
            h += 12
        if part == "утра" and h == 12:
            h = 0
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi, bool(part), (m.start(), m.end())
    return None


def _day(t, now):
    """День -> (дата, (начало, конец)) или None: сегодня/завтра/послезавтра/в пятницу/5 октября/05.10.
    День недели — ближайший, включая сегодня; дата без года, уже прошедшая, — в следующем году."""
    today = now.date()
    for w, d in (("послезавтра", 2), ("завтра", 1), ("сегодня", 0)):
        m = re.search(r"\b(?:на\s+)?" + w + r"\b", t)
        if m:
            return today + timedelta(days=d), (m.start(), m.end())
    m = re.search(r"\b(?:в|во|на)\s+(понедельник|вторник|среду|четверг|пятницу|субботу|воскресенье)\b", t)
    if m:
        wd = next(i for p, i in WEEKDAYS if m.group(1).startswith(p))
        delta = (wd - today.weekday()) % 7
        return today + timedelta(days=delta), (m.start(), m.end())
    m = re.search(r"\b(\d{1,2})(?:-?го)?\s+(январ|феврал|марта?|апрел|мая|июн|июл|август|сентябр|октябр|ноябр|декабр)\w*", t)
    if m:
        key = next(k for k in MONTHS if m.group(2).startswith(k))
        try:
            d = today.replace(month=MONTHS[key], day=int(m.group(1)))
        except ValueError:
            return None
        if d < today:
            d = d.replace(year=d.year + 1)
        return d, (m.start(), m.end())
    m = re.search(r"\b(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\b", t)
    if m:
        y = int(m.group(3)) if m.group(3) else today.year
        y = y + 2000 if y < 100 else y
        try:
            d = today.replace(year=y, month=int(m.group(2)), day=int(m.group(1)))
        except ValueError:
            return None
        if d < today and not m.group(3):
            d = d.replace(year=d.year + 1)
        return d, (m.start(), m.end())
    return None


def _repeat(t):
    """Повтор -> (repeat без времени, (начало, конец)) или None. «Каждый день/каждую неделю» — не интервал, а daily/weekly;
    default_hour — час для «каждое утро/вечер/ночь», если время не названо (parse его убирает)."""
    m = re.search(r"\bкажд(?:ые|ый|ую|ое)\s+(?:(\d+(?:[.,]\d+)?)\s+)?(полчаса|" + UNIT_RX[1:-1] + r")\b", t)
    if m and not re.match(r"(день|дн|сут|недел)", m.group(2)):
        if m.group(2) == "полчаса":
            return {"kind": "interval", "minutes": 30}, (m.start(), m.end())
        n = float((m.group(1) or "1").replace(",", "."))
        mins = n * (_unit_minutes(m.group(2)) or 0)
        if mins >= 1:
            return {"kind": "interval", "minutes": int(mins)}, (m.start(), m.end())
    m = re.search(r"\b(?:каждый\s+день|ежедневно|каждые\s+сутки|каждое\s+утро|каждый\s+вечер|каждую\s+ночь|каждый\s+раз\s+в\s+день)\b", t)
    if m:
        r = {"kind": "daily"}
        if "утро" in m.group(0):
            r["default_hour"] = 9
        elif "вечер" in m.group(0):
            r["default_hour"] = 19
        elif "ночь" in m.group(0):
            r["default_hour"] = 23
        return r, (m.start(), m.end())
    m = re.search(r"\b(?:по\s+будням|в\s+будни|каждый\s+будний\s+день|по\s+рабочим\s+дням|в\s+рабочие\s+дни|(?:каждый\s+)?рабочий\s+день)\b", t)
    if m:
        return {"kind": "weekly", "days": [0, 1, 2, 3, 4]}, (m.start(), m.end())
    m = re.search(r"\b(?:по\s+выходным|в\s+выходные|каждые\s+выходные)\b", t)
    if m:
        return {"kind": "weekly", "days": [5, 6]}, (m.start(), m.end())
    # диапазон: «с понедельника по четверг», «пн-чт», «понедельник–четверг» (30.10)
    m = re.search(r"\b(?:(?:каждую\s+неделю\s+)?со?\s+(" + DAY_RX + r")\s+по\s+(" + DAY_RX + r")|(" + DAY_RX + r")\s*[-–—]\s*(" + DAY_RX + r"))\b", t)
    if m:
        a, b = _day_of(m.group(1) or m.group(3)), _day_of(m.group(2) or m.group(4))
        if a is not None and b is not None and a != b:
            days = list(range(a, b + 1)) if a < b else list(range(a, 7)) + list(range(0, b + 1))
            return {"kind": "weekly", "days": sorted(days)}, (m.start(), m.end())
    m = re.search(r"\b(?:кажд(?:ый|ую|ое)\s+|по\s+)((?:(?:понедельник|вторник|сред|четверг|пятниц|суббот|воскресень)\w*(?:\s*(?:,|и)\s*)?)+)", t)
    if m:
        days = sorted({i for p, i in WEEKDAYS for w in re.findall(r"\w+", m.group(1)) if w.startswith(p)})
        if days:
            return {"kind": "weekly", "days": days}, (m.start(), m.end())
    m = re.search(r"\b(?:каждую\s+неделю|еженедельно)\b", t)
    if m:
        return {"kind": "weekly", "days": None}, (m.start(), m.end())
    m = re.search(r"\b(?:каждый\s+месяц|ежемесячно)(?:\s+(\d{1,2})(?:-?го)?\s+числа)?|\bкаждое\s+(\d{1,2})(?:-?е)?\s+число\b", t)
    if m:
        day = m.group(1) or m.group(2)
        return {"kind": "monthly", "day": int(day) if day else None}, (m.start(), m.end())
    return None


def _hm(x, default):
    try:
        h, m = (int(v) for v in str(x or default).split(":"))
        return h, m
    except ValueError:
        return tuple(int(v) for v in default.split(":"))


def in_window(rep, at: datetime):
    """Попадает ли время в окно повтора (from–to и дни недели); окна нет — всегда да."""
    if rep.get("days") and at.weekday() not in rep["days"] and rep.get("kind") == "interval":
        return False
    if not rep.get("from"):
        return True
    f, t = _hm(rep["from"], "09:00"), _hm(rep.get("to"), "18:00")
    return (f[0], f[1]) <= (at.hour, at.minute) <= (t[0], t[1])


def next_time(rep, after: datetime):
    """Следующее срабатывание повтора строго после after. Нет времени — 09:00; monthly на 31-е в коротком месяце —
    последний день месяца. Интервал с окном (from/to, days) — только внутри окна: вне его — начало следующего окна."""
    k = rep.get("kind")
    if k == "interval":
        c = after + timedelta(minutes=max(1, int(rep.get("minutes") or 60)))
        if not rep.get("from") and not rep.get("days"):
            return c
        if in_window(rep, c):
            return c
        fh, fm = _hm(rep.get("from"), "00:00")
        for d in range(0, 9):
            start = (c + timedelta(days=d)).replace(hour=fh, minute=fm, second=0, microsecond=0)
            if start > after and in_window(rep, start):
                return start
        return c
    hh, mm = (int(x) for x in (rep.get("time") or "09:00").split(":"))
    if k == "daily":
        c = after.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return c if c > after else c + timedelta(days=1)
    if k == "weekly":
        days = rep.get("days") or [after.weekday()]
        for d in range(0, 8):
            c = (after + timedelta(days=d)).replace(hour=hh, minute=mm, second=0, microsecond=0)
            if c > after and c.weekday() in days:
                return c
    if k == "monthly":
        day = int(rep.get("day") or after.day)
        y, mo = after.year, after.month
        for _ in range(3):
            dd = min(day, calendar.monthrange(y, mo)[1])
            c = after.replace(year=y, month=mo, day=dd, hour=hh, minute=mm, second=0, microsecond=0)
            if c > after:
                return c
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return after + timedelta(days=1)


def describe_repeat(rep):
    """Повтор словами для ответа и списка: «каждый день в 8:00», «по пн, чт в 19:00», «каждые 2 ч»."""
    if not rep:
        return ""
    k = rep.get("kind")
    tm = rep.get("time", "")
    tm = tm[1:] if tm.startswith("0") else tm
    if k == "interval":
        m = int(rep.get("minutes") or 0)
        if m % 60 == 0:
            h = m // 60
            s = "каждый час" if h == 1 else f"каждые {h} ч"
        else:
            s = f"каждые {m} мин"
        days = rep.get("days") or []
        if days:
            s += " по будням" if days == [0, 1, 2, 3, 4] else " по выходным" if days == [5, 6] else \
                " по " + ", ".join(["пн", "вт", "ср", "чт", "пт", "сб", "вс"][d] for d in days)
        if rep.get("from"):
            s += f" с {str(rep['from']).lstrip('0') or '0'} до {str(rep.get('to', '')).lstrip('0') or '0'}"
        return s
    if k == "daily":
        return f"каждый день в {tm}"
    if k == "weekly":
        days = rep.get("days") or []
        if days == [0, 1, 2, 3, 4]:
            return f"по будням в {tm}"
        if days == [5, 6]:
            return f"по выходным в {tm}"
        names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
        return ("по " + ", ".join(names[d] for d in days) if days else "каждую неделю") + f" в {tm}"
    if k == "monthly":
        return f"каждый месяц {rep.get('day')}-го в {tm}"
    return ""


def _cut(t, spans):
    """Вырезать из фразы найденные куски (время, день, повтор) — остаётся «что напомнить»."""
    for a, b in sorted(spans, reverse=True):
        t = t[:a] + " " + t[b:]
    return re.sub(r"\s+", " ", t).strip()


def _clean_text(rest):
    """Убрать из текста напоминания служебные слова: «мне», «пожалуйста», «о том, что», висящие предлоги."""
    t = rest
    t = re.sub(r"^(?:(?:мне|меня|нас|нам|пожалуйста|плиз|пж|ещё|еще|раз)\s+)+", "", t)
    t = re.sub(r"^(?:мне|меня|нас|нам)$", "", t)
    t = re.sub(r"\s+(?:мне|пожалуйста)\b", "", t)
    t = re.sub(r"^(?:о\s+том\s*,?\s*что(?:бы)?|о\s+том|что(?:бы)?|чтоб|насчет|насчёт|на\s+счет)\s+", "", t)
    t = re.sub(r"^(?:в|на|о|об|про|и)\s*$", "", t)
    t = re.sub(r"\s+(?:в|на|к|и)$", "", t)
    return t.strip(" ,.-—")


def _restore_case(what, original):
    """Вернуть словам исходный вид из сказанного: «олю» → «Олю», «планерку» → «планёрку» (разбор шёл в нижнем
    регистре и без ё)."""
    orig = {}
    for w in re.findall(r"[\w-]+", original or ""):
        orig.setdefault(w.lower().replace("ё", "е"), w)
    return " ".join(orig.get(w, w) if not w.isdigit() else w for w in what.split())


def parse(text, now=None):
    """Просьба напомнить -> {"text", "at", "repeat", "kind"} или None (формат — в шапке файла).
    Час без части суток: для напоминаний «в 3», когда 3:00 уже прошло, а 15:00 нет, — 15:00; для повторов 1–6 — днём;
    будильник — как сказано. Прошедшее время без дня — завтра; с явным днём («сегодня в 8», уже прошло) — None."""
    now =(now or datetime.now()).replace(microsecond=0)
    t = _norm(text)
    if re.search(r"(?:^|\s)(?:если|ежели|в случае|когда будет|если не)\s", t) or re.search(r"\b(?:иначе|а если|если нет)\b", t):
        return None              # «если завтра дождь — напомни про зонт, иначе…» — условие: решает модель (узнает прогноз)
    m = TRIGGER.match(t)
    if not m:                    # «каждую пятницу в 16:30 напомни сделать бэкап» — время впереди, «напомни» в середине
        mm = re.search(r"\b(напомни(?:те)?|напоминай(?:те)?|разбуди(?:те)?)\b", t)
        pre = t[:mm.start()].strip() if mm else ""
        if mm and pre and len(pre.split()) <= 7 and re.search(
                r"\d|кажд|ежедн|завтра|сегодня|послезавтра|через|утр|вечер|ночь|понедельн|вторн|сред|четверг|пятниц|суббот|"
                r"воскресен|будн|выходн|рабоч|полчаса|минут|час", pre):
            t = f"{mm.group(1)} {pre} {t[mm.end():].strip()}"
            m = TRIGGER.match(t)
    if not m:
        return None
    trig, rest = m.group("trig"), " " + m.group("rest").strip() + " "
    kind = "timer" if trig.startswith(("таймер", "засеки")) or "таймер" in trig else \
        "alarm" if trig.startswith("разбуди") or "будильник" in trig else "reminder"
    rest = rest.strip()
    if kind == "timer":
        rest = re.sub(r"^на\s+", "через ", rest)
        if not rest.startswith("через"):
            rest = "через " + rest
    spans = []
    # окно «с 9 до 18» / «с 9:00 по 18:00» — только днём (дело «проверяй почту по будням с 9 до 18», №137)
    win = re.search(r"\bс\s+(\d{1,2})(?::(\d{2}))?\s+(?:до|по)\s+(\d{1,2})(?::(\d{2}))?(?:\s+час\w*)?(?=\s|$)", rest)
    if win and int(win.group(1)) < int(win.group(3)) <= 24:
        rest = rest[:win.start()] + " " + rest[win.end():]
    else:
        win = None
    rep = _repeat(rest)
    if rep:
        rep, sp = rep
        spans.append(sp)
        ex = _except_days(rest)                  # «по будням, кроме пятницы» (30.10: ставилось и на пятницу)
        if ex and rep["kind"] in ("daily", "weekly"):
            left = [d for d in (rep.get("days") or range(7)) if d not in ex[0]]
            if left:
                rep = dict({k: v for k, v in rep.items() if k != "kind"}, kind="weekly", days=left)
                # «кроме / но не в среду» стираем пробелами: иначе «в среду» дальше примут за день срабатывания
                a0, b0 = ex[1]
                rest = rest[:a0] + " " * (b0 - a0) + rest[b0:]
    rel = _relative(rest) if not rep or rep["kind"] != "interval" else None
    clock = _clock(rest)
    day = _day(rest, now)
    part = None
    if not clock:
        pm = re.search(r"\b(с\s+утра|утром|днем|вечером|ночью)\b", rest)
        if pm:
            part = DAYPART[pm.group(1)]
            spans.append((pm.start(), pm.end()))
    when = None
    if rep and rep["kind"] == "interval":
        when = now + timedelta(minutes=rep["minutes"])
        if clock:                                          # «каждые 2 часа начиная с 9» — первое в это время
            c = now.replace(hour=clock[0], minute=clock[1], second=0)
            when = c if c > now else when
            spans.append(clock[3])
    elif rep:
        hh, mi = (clock[0], clock[1]) if clock else (part or rep.pop("default_hour", 9), 0)
        rep.pop("default_hour", None)
        if clock:
            spans.append(clock[3])
            if not clock[2] and rep["kind"] != "interval" and 1 <= hh <= 6:
                hh += 12                                   # «каждый день в 3» — скорее днём
        rep["time"] = f"{hh:02d}:{mi:02d}"
        if rep["kind"] == "weekly" and not rep.get("days"):
            rep["days"] = [(day[0] if day else now.date()).weekday()]
        if rep["kind"] == "monthly" and not rep.get("day"):
            rep["day"] = (day[0] if day else now.date()).day
        if day:
            spans.append(day[1])
            start = datetime.combine(day[0], datetime.min.time()) - timedelta(seconds=1)
            when = next_time(rep, max(start, now))
        else:
            when = next_time(rep, now)
    elif rel:
        mins, sp = rel
        if mins <= 0:
            return None
        when = now + timedelta(minutes=mins)
        spans.append(sp)
    elif clock or day or part:
        d = day[0] if day else now.date()
        if day:
            spans.append(day[1])
        if clock:
            spans.append(clock[3])
            hh, mi, explicit = clock[0], clock[1], clock[2]
        else:
            hh, mi, explicit = part or 9, 0, True
        when = datetime.combine(d, datetime.min.time()).replace(hour=hh, minute=mi)
        if not explicit and 1 <= hh <= 11 and kind != "alarm":
            if not day and when <= now and when.replace(hour=hh + 12) > now:
                when = when.replace(hour=hh + 12)        # «в 3» в 10 утра — это 15:00
        if when <= now:
            if day and re.search(r"понедельник|вторник|сред|четверг|пятниц|суббот|воскресен", rest[day[1][0]:day[1][1]]):
                when += timedelta(days=7)                # «в пятницу в 15» в пятницу в 16:30 — следующая пятница (16.10:
                                                         # было «не понял» — и напоминание уходило модели)
            elif day:
                return None                              # «сегодня в 8» — уже прошло: пусть уточнит модель
            else:
                when += timedelta(days=1)
    else:
        return None
    if win:
        days = rep.get("days") if rep and rep.get("kind") == "weekly" else (rep or {}).get("days")
        rep = {"kind": "interval", "minutes": rep["minutes"] if rep and rep.get("kind") == "interval" else 60,
               "from": f"{int(win.group(1)):02d}:{int(win.group(2) or 0):02d}", "to": f"{int(win.group(3)):02d}:{int(win.group(4) or 0):02d}"}
        if days:
            rep["days"] = days
        when = next_time(rep, now)                     # внутри окна — через интервал, вне — в начале следующего
    what = _restore_case(_clean_text(_cut(rest, spans)), text)
    if not what:
        what = {"alarm": "Будильник", "timer": "Таймер"}.get(kind, "Напоминание")
    what = what[:1].upper() + what[1:]
    return {"text": what, "at": when, "repeat": rep, "kind": kind}


def human(when: datetime, now=None):
    """«сегодня в 15:30», «завтра в 9:00», «в пятницу, 3 октября, в 10:00»."""
    now = now or datetime.now()
    d = (when.date() - now.date()).days
    tm = f"{when.hour}:{when:%M}"                 # не lstrip("0"): «00:30» превратилось бы в «:30»
    if d == 0:
        secs = int((when - now).total_seconds())
        if 0 <= secs < 60:
            return f"через {secs} с"
        if 0 <= secs < 3600:
            return f"через {round(secs / 60)} мин"
        return f"сегодня в {tm}"
    if d == 1:
        return f"завтра в {tm}"
    if d == 2:
        return f"послезавтра в {tm}"
    wd = ["в понедельник", "во вторник", "в среду", "в четверг", "в пятницу", "в субботу", "в воскресенье"][when.weekday()]
    mon = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября",
           "декабря"][when.month - 1]
    return f"{wd}, {when.day} {mon}, в {tm}" if d < 7 else f"{when.day} {mon} в {tm}"
