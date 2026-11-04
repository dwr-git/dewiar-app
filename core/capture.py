"""Быстрые записи без модели: «запиши…», «запомни…», «добавь молоко в список покупок».

parse(text) → {"op": "note", "title", "text"} | {"op": "list", "name", "items"} | {"op": "fact", "fact"} | None.
Вызывается из engine_answer.py до обращения к модели; запись делает ToolsMixin._capture (engine_tools.py) через
workspace. None — «не уверен, пусть решает модель»: лучше пропустить фразу, чем записать не то.
_title() используется и в engine_remote.py для заголовков заметок.
"""

import re

VERB = re.compile(r"^(?:(?:а|и|ну|пожалуйста|слушай)\s+)*(?P<verb>запиши(?:те)?\s+(?:в\s+)?заметк\w*|"
                  r"(?:сделай|создай|добавь)\s+(?:новую\s+)?заметку|новая\s+заметка|заметка|сохрани\s+(?:в\s+)?заметк\w*|"
                  r"запиши(?:те)?|запомни(?:те)?)(?:\s*,?\s*(?:себе|мне|в\s+заметки|пожалуйста)(?![а-яё]))*\s*[:,.\-—]?\s*(?P<rest>.+)$", re.I | re.S)
LIST1 = re.compile(r"^(?:добавь|допиши|внеси|запиши)\s+(?P<items>.+?)\s+(?:в|во|к)\s+(?P<name>(?:список|заметку|перечень)\s+.+?|"
                   r"покупки|список)\s*$", re.I)
LIST3 = re.compile(r"^(?:запиши|составь|сделай|создай)\s+(?P<name>список\s+[^\s:,]+(?:\s+[^\s:,]+)?)\s*[:,\-—]\s*"
                   r"(?P<items>.+)$", re.I)
LIST2 = re.compile(r"^(?:добавь|допиши|внеси|запиши)\s+(?:в|во|к)\s+(?P<name>(?:список|заметку)\s+[^\s:,]+(?:\s+[^\s:,]+)?)\s*[:,\-—]\s*"
                   r"(?P<items>.+)$", re.I)
# Списки проверяются раньше VERB: «запиши хлеб в покупки» иначе стало бы заметкой «Хлеб в покупки».
# «запомни, что я …» про себя — факт в память о пользователе, остальное после «запомни» — обычная заметка.
# Про себя — и когда «я / у меня» не в начале: «запомни: в среду в 15:00 у меня встреча» — это планы человека,
# их потом спрашивают («что у меня в среду?»), а заметки в разговор сами не попадают.
FIRST_PERSON = re.compile(r"^(?:что\s+)?(?:я|у\s+меня|мне|мой|моя|моё|мое|мои|меня|мою|моего|моей|моим|мы|у\s+нас|наш\w*)\b", re.I)
ABOUT_ME = re.compile(r"(?<![а-яё])(?:я|у\s+меня|у\s+нас|мне|нам|мы|мой|моя|моё|мое|мои|моего|моей|моим|мою|наш[а-яё]*)(?![а-яё])", re.I)
# «запиши меня к врачу», «запиши это», «запиши заметку про хлеб», «запиши список покупок» — тут нужна модель:
# действие, ссылка на сказанное раньше, тема вместо текста или «составь» вместо «запиши дословно»
SKIP = re.compile(r"^(?:(?:для|на\s+время|в\s+рамках|пока\s+идет|до\s+конца)\s+(?:этого\s+|нашего\s+)?(?:разговор|беседы|чата|диалог)\w*|"
                  r"меня\s+(?:к|на|в)\b|это\b|вот\s+это\b|то\s+что\b|(?:про|о|об|обо)\s+|(?:список|план|конспект|"
                  r"итог|резюме|протокол)(?:\s+\S+){0,2}\s*$)", re.I)

# «запиши потраченную 2.000 руб», «запиши расход 500» — деньги: в «Деньги» (money.parse или модель с money_add), не в заметку
MONEY = re.compile(r"(?<![а-яё])(?:потрач\w*|трат[аыуе]\w*|расход\w*|доход\w*|заплатил\w*|оплатил\w*|купил\w*)(?![а-яё])[^.!?]{0,40}\d"
                   r"|\d[\d\s.,]*\s*(?:руб\w*|р\.|₽|byn|бел\w*\s+руб|долл\w*|\$|евро|€|тенге|грив\w*)(?![а-яё])", re.I)

WD = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
PLAN_DAY = re.compile(r"\(на (\d\d)\.(\d\d)\.(\d{4})")     # метка даты плана в памяти — её читает календарь


def plan_day(text, now=None):
    """День, о котором план («в среду», «завтра», «14 октября», «14.10») -> date или None. Только сегодня и дальше."""
    import datetime as dt
    import when
    now = now or dt.datetime.now()
    r = when._day(when._norm(text), now)
    return r[0] if r and r[0] >= now.date() else None


def _title(text):
    t = text.strip()
    m = re.match(r"^([^:\n]{2,60}):\s*(\S.*)$", t)                    # «Пароль от вайфая: кот123»
    if m and len(m.group(1).split()) <= 6 and len(m.group(2).split()) <= 3:
        return m.group(1).strip()
    first = re.split(r"(?<=[.!?])\s|\n", t, maxsplit=1)[0]
    ws = first.split()
    title = " ".join(ws[:7]) + ("…" if len(ws) > 7 else "")
    return title.strip(" .,;:—-")[:70]


def _list_name(name):
    name = re.sub(r"\s+", " ", name.strip(" .,!")).lower()
    if name in ("покупки", "список"):
        name = "список покупок" if name == "покупки" else "список дел"
    name = re.sub(r"^заметку\s+", "", name)
    if not name.startswith("список"):
        name = name
    return name[:1].upper() + name[1:]


def _items(text):
    parts = re.split(r",|;|\s+и\s+|\n", text)
    return [p.strip(" .-—") for p in parts if p.strip(" .-—")]


def parse(text):
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return None
    for rx in (LIST3, LIST2, LIST1):
        m = rx.match(t)
        if m:
            items = _items(m.group("items"))
            if items:
                return {"op": "list", "name": _list_name(m.group("name")), "items": items}
    m = VERB.match(t)
    if not m:
        return None
    verb, rest = m.group("verb").lower(), m.group("rest").strip()
    rest = re.sub(r"^(?:о\s+том\s*,?\s*)", "", rest)
    if len(rest) < 3 or SKIP.match(rest):
        return None
    if verb.startswith("запиши") and "заметк" not in t[:m.start("rest")].lower() and MONEY.search(rest):
        return None                              # «запиши потраченную 2.000 руб» — трата, а не заметка (экзамен ПК 0.81.1)
    if verb.startswith("запомни"):
        body = re.sub(r"^что\s+", "", rest, flags=re.I)
        if FIRST_PERSON.match(rest) or (ABOUT_ME.search(rest) and len(rest) <= 200):
            body = body.rstrip(".")
            day = plan_day(body)
            if day:                              # «в среду в 15:00 встреча» — с точной датой: через неделю «в среду» уже другая
                return {"op": "fact", "fact": f"Со слов пользователя: {body} (на {day:%d.%m.%Y}, {WD[day.weekday()]}).", "day": day}
            return {"op": "fact", "fact": "Со слов пользователя: " + body + "."}
        rest = body
    rest = rest[:1].upper() + rest[1:]
    return {"op": "note", "title": _title(rest), "text": rest}
