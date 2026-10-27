"""Память 2.0: факты «Обо мне» — по людям и темам, и в разговор то, что нужно для вопроса.

Отзыв владельца 27.10: «в подсказку идут только последние 2500 знаков "Обо мне" — старое о человеке просто теряется;
нужны страницы по людям и темам с датами и поиск по смыслу». Файл остаётся прежним («Память/Обо мне.md», строка на факт
«- факт _(дд.мм.гггг)_» — её же понимают телефон и синхронизация), а этот модуль его читает:

  • parse — факты с датой записи и историей «(раньше: … → …; менялось N раз)» (её ведёт workspace.remember);
  • страницы (pages): люди («Мама», «Маша, дочь», «Питомцы»…) и темы («Работа», «Здоровье»…) — по словам факта;
    имя, однажды названное с родством («дочь Маша»), дальше узнаётся и одно («Маша пошла в школу»);
  • core_text — то, что идёт в системную подсказку: всё, если влезает в бюджет (как раньше); иначе главное о самом
    человеке, кто есть кто и самое новое. Подсказка не меняется от вопроса к вопросу (кэш модели, отзыв 19.10);
  • relevant — к вопросу: факты, что не попали в главное, по смыслу вопроса. «По смыслу» без модели и без
    интернета: основы слов (recall.stem), группы близких слов («подарок» ↔ «день рождения», «любит») и страницы
    («что подарить маме» → вся страница «Мама»). Работает и на слабом компьютере, мгновенно;
  • timeline-метки для студии: «сейчас» (значение менялось — это новое), «через N дней» (дата в факте скоро).
"""

import datetime as dt
import re

from recall import stem, STOP

FACT_RX = re.compile(r"^- (.+?)(?: _\((\d\d)\.(\d\d)\.(\d{4})\)_)?\s*$")
HIST_RX = re.compile(r"\s*\(раньше: (.+?)(?:; менял\w* \d+ раз\w*)?\)\s*\.?\s*$")
MONTHS = ("январ", "феврал", "март", "апрел", "ма", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр")

# люди: слово родства → (ключ страницы, название, значок). Имя рядом («дочь Маша») — своя страница «Маша, дочь».
KIN = {
    "мама": ("mom", "Мама", "👩"), "мать": ("mom", "Мама", "👩"), "мамы": ("mom", "Мама", "👩"), "маме": ("mom", "Мама", "👩"),
    "маму": ("mom", "Мама", "👩"), "мамой": ("mom", "Мама", "👩"), "матери": ("mom", "Мама", "👩"),
    "папа": ("dad", "Папа", "👨"), "отец": ("dad", "Папа", "👨"), "папы": ("dad", "Папа", "👨"), "папе": ("dad", "Папа", "👨"),
    "папу": ("dad", "Папа", "👨"), "отца": ("dad", "Папа", "👨"), "отцу": ("dad", "Папа", "👨"),
    "жена": ("wife", "Жена", "💍"), "жены": ("wife", "Жена", "💍"), "жене": ("wife", "Жена", "💍"), "жену": ("wife", "Жена", "💍"),
    "муж": ("husband", "Муж", "💍"), "мужа": ("husband", "Муж", "💍"), "мужу": ("husband", "Муж", "💍"),
    "сын": ("son", "Сын", "👦"), "сына": ("son", "Сын", "👦"), "сыну": ("son", "Сын", "👦"), "сыном": ("son", "Сын", "👦"),
    "дочь": ("daughter", "Дочь", "👧"), "дочка": ("daughter", "Дочь", "👧"), "дочери": ("daughter", "Дочь", "👧"),
    "дочку": ("daughter", "Дочь", "👧"), "дочке": ("daughter", "Дочь", "👧"), "дочки": ("daughter", "Дочь", "👧"),
    "дочкой": ("daughter", "Дочь", "👧"), "дочерью": ("daughter", "Дочь", "👧"), "дочерей": ("daughter", "Дочь", "👧"),
    "сыне": ("son", "Сын", "👦"), "сыновья": ("son", "Сын", "👦"), "сыновей": ("son", "Сын", "👦"),
    "женой": ("wife", "Жена", "💍"), "мужем": ("husband", "Муж", "💍"), "муже": ("husband", "Муж", "💍"),
    "братом": ("brother", "Брат", "🧑"), "брате": ("brother", "Брат", "🧑"), "сестрой": ("sister", "Сестра", "👩"),
    "бабушку": ("grandma", "Бабушка", "👵"), "бабушкой": ("grandma", "Бабушка", "👵"), "дедушку": ("grandpa", "Дедушка", "👴"),
    "дедушкой": ("grandpa", "Дедушка", "👴"), "внука": ("grandkids", "Внуки", "🧒"), "внучке": ("grandkids", "Внуки", "🧒"),
    "внучку": ("grandkids", "Внуки", "🧒"), "внуков": ("grandkids", "Внуки", "🧒"), "внукам": ("grandkids", "Внуки", "🧒"),
    "друга": ("friends", "Друзья", "🤝"), "подруги": ("friends", "Друзья", "🤝"), "подругу": ("friends", "Друзья", "🤝"),
    "друзей": ("friends", "Друзья", "🤝"), "коллеге": ("colleagues", "Коллеги", "🧑‍💼"), "коллегу": ("colleagues", "Коллеги", "🧑‍💼"),
    "начальнику": ("colleagues", "Коллеги", "🧑‍💼"), "начальника": ("colleagues", "Коллеги", "🧑‍💼"),
    "собаки": ("pets", "Питомцы", "🐾"), "собаке": ("pets", "Питомцы", "🐾"), "собакой": ("pets", "Питомцы", "🐾"),
    "кота": ("pets", "Питомцы", "🐾"), "коту": ("pets", "Питомцы", "🐾"), "кошки": ("pets", "Питомцы", "🐾"),
    "кошке": ("pets", "Питомцы", "🐾"), "мамочка": ("mom", "Мама", "👩"), "папой": ("dad", "Папа", "👨"),
    "брат": ("brother", "Брат", "🧑"), "брата": ("brother", "Брат", "🧑"), "брату": ("brother", "Брат", "🧑"),
    "сестра": ("sister", "Сестра", "👩"), "сестры": ("sister", "Сестра", "👩"), "сестре": ("sister", "Сестра", "👩"),
    "сестру": ("sister", "Сестра", "👩"),
    "бабушка": ("grandma", "Бабушка", "👵"), "бабушки": ("grandma", "Бабушка", "👵"), "бабушке": ("grandma", "Бабушка", "👵"),
    "дедушка": ("grandpa", "Дедушка", "👴"), "дедушки": ("grandpa", "Дедушка", "👴"), "дедушке": ("grandpa", "Дедушка", "👴"),
    "дед": ("grandpa", "Дедушка", "👴"),
    "внук": ("grandkids", "Внуки", "🧒"), "внучка": ("grandkids", "Внуки", "🧒"), "внуки": ("grandkids", "Внуки", "🧒"),
    "друг": ("friends", "Друзья", "🤝"), "подруга": ("friends", "Друзья", "🤝"), "друзья": ("friends", "Друзья", "🤝"),
    "другу": ("friends", "Друзья", "🤝"), "подруге": ("friends", "Друзья", "🤝"),
    "коллега": ("colleagues", "Коллеги", "🧑‍💼"), "коллеги": ("colleagues", "Коллеги", "🧑‍💼"),
    "начальник": ("colleagues", "Коллеги", "🧑‍💼"), "начальница": ("colleagues", "Коллеги", "🧑‍💼"),
    "шеф": ("colleagues", "Коллеги", "🧑‍💼"), "руководитель": ("colleagues", "Коллеги", "🧑‍💼"),
    "собака": ("pets", "Питомцы", "🐾"), "собаку": ("pets", "Питомцы", "🐾"), "пёс": ("pets", "Питомцы", "🐾"),
    "пес": ("pets", "Питомцы", "🐾"), "щенок": ("pets", "Питомцы", "🐾"), "кот": ("pets", "Питомцы", "🐾"),
    "кошка": ("pets", "Питомцы", "🐾"), "кошку": ("pets", "Питомцы", "🐾"), "котёнок": ("pets", "Питомцы", "🐾"),
    "котенок": ("pets", "Питомцы", "🐾"), "питомец": ("pets", "Питомцы", "🐾"), "попугай": ("pets", "Питомцы", "🐾"),
}
KIN_NAME = {"mom": "мама", "dad": "папа", "wife": "жена", "husband": "муж", "son": "сын", "daughter": "дочь",
            "brother": "брат", "sister": "сестра", "grandma": "бабушка", "grandpa": "дедушка", "grandkids": "внук",
            "friends": "друг", "colleagues": "коллега", "pets": "питомец"}

# темы: ключ → (название, значок, слова). Слова сводятся к основам при загрузке.
TOPICS = {
    "work": ("Работа", "💼", "работа работаю работает должность офис зарплата проект компания фирма бизнес клиент клиенты "
                           "смена отпуск увольнение карьера бухгалтер программист инженер менеджер директор врачом"),
    "health": ("Здоровье", "❤️", "здоровье болит болезнь врач таблетки лекарство давление аллергия диабет сердце больница "
                                "анализы операция зрение зуб зубы диета вес сон бессонница спина"),
    "home": ("Дом", "🏠", "живу живёт живет квартира дом адрес переехал переехала город улица ремонт соседи дача"),
    "car": ("Машина", "🚗", "машина машины авто автомобиль права гараж шины резина бензин заправка техосмотр"),
    "money": ("Деньги", "💰", "деньги бюджет кредит ипотека долг накопления копить сбережения тысяч рублей зарплата счёт карта"),
    "food": ("Еда и вкусы", "☕", "еда ест ем любимое блюдо готовить кофе чай вегетарианец мясо сладкое пицца суши ресторан"),
    "hobby": ("Увлечения", "🎨", "хобби увлекаюсь рисовать рисую спорт бег зал футбол плавание музыка гитара книги читать "
                                 "фильмы сериалы игры рыбалка путешествия вязать фотографировать"),
    "study": ("Учёба", "📚", "учёба учусь школа класс университет институт экзамен курсы английский язык диплом"),
    "trips": ("Поездки", "✈️", "поездка путешествие отпуск лететь полёт билет отель виза море страна страну заграницу"),
    "style": ("Как со мной говорить", "💬", "ответы ответ короткие подробно называй обращайся зови говори тон шутки "
                                          "предпочитаю люблю не люблю нравится неудобно"),
}

# близкие по смыслу слова: вопрос с одним словом группы находит факты с другими («подарить маме» → «любит пионы»)
SYN = [
    "подарок подарить подарки день рождения юбилей праздник любит нравится мечтает хочет",
    "здоровье болеть болит болезнь врач таблетки лекарство давление аллергия самочувствие",
    "работа работать должность профессия начальник коллега офис зарплата",
    "машина авто автомобиль водить права",
    "дом квартира жить живет адрес переехать город",
    "еда есть кушать готовить блюдо любимое вкусно кофе чай",
    "деньги бюджет потратить купить стоить цена копить",
    "учеба учиться школа университет экзамен урок",
    "отпуск поездка путешествие лететь ехать отдых",
    "имя зовут звать",
    "возраст лет год родился рождения",
    "собака пес кот кошка питомец",
]


def _stems(text):
    return [stem(w) for w in re.findall(r"[а-яА-ЯёЁa-zA-Z0-9]+", text or "") if w.lower() not in STOP and len(w) > 1]


_TOPIC_ST = {k: {stem(w) for w in v[2].split()} for k, v in TOPICS.items()}
_SYN_ST = []
for _g in SYN:
    _SYN_ST.append({stem(w) for w in _g.split()})
_KIN_ST = {}
for _w, _v in KIN.items():
    _KIN_ST.setdefault(stem(_w), _v)
    _KIN_ST.setdefault(_w.replace("ё", "е"), _v)


def parse(text):
    """Текст «Обо мне» → [{i, text, date (date|None), prev [было…], line}] — по строке «- …» на факт."""
    out = []
    for ln in (text or "").splitlines():
        m = FACT_RX.match(ln.strip())
        if not m:
            continue
        body = m.group(1).strip()
        d = None
        if m.group(2):
            try:
                d = dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))
            except ValueError:
                d = None
        prev = []
        h = HIST_RX.search(body)
        if h:
            prev = [x.strip() for x in h.group(1).split(" → ") if x.strip()]
            body = body[:h.start()].rstrip(" .")
        out.append({"i": len(out), "text": body, "date": d, "prev": prev, "line": ln.strip()})
    return out


_NAME_AFTER = re.compile(r"\b((?i:" + "|".join(sorted(KIN, key=len, reverse=True)) + r"))\s+([А-ЯЁ][а-яё]{2,})")
_NAME_BEFORE = re.compile(r"\b([А-ЯЁ][а-яё]{2,})\s*(?:[—–-]|,)\s*(?i:моя |мой |наш |наша )?((?i:" + "|".join(
    sorted(KIN, key=len, reverse=True)) + r"))\b")
NOMS = set("мама мать папа отец жена муж сын дочь дочка брат сестра бабушка дедушка дед внук внучка друг подруга коллега "
           "начальник начальница шеф руководитель собака пёс пес кот кошка щенок котёнок котенок попугай".split())
ONE = {"mom", "dad", "wife", "husband", "grandma", "grandpa"}
ME_RX = re.compile(r"^(?:меня зовут|мне \d+|я\b|мой день рождения|моё имя|мое имя|родил(?:ся|ась)|пользовател[ья] зовут)", re.I)
_NOT_NAMES = {"Это", "Мой", "Моя", "Мои", "Наш", "Наша", "Его", "Её", "Она", "Они", "Он", "Мама", "Папа", "Сегодня", "Завтра",
              "Пользователь", "Со", "Живёт", "Живет", "Любит", "Работает"}


def _names(facts):
    """Имена, однажды названные с родством: {«маша»: (страница, «Маша, дочь», значок, родство)}. У мамы, папы, жены и
    мужа страница одна («мама Людмила» — та же «Мама»), у детей, друзей, питомцев — своя на каждое имя."""
    names = {}

    def put(nm, kin):
        if nm in _NOT_NAMES or nm.lower() in KIN:
            return
        key, title, icon = KIN[kin]
        low = nm.lower().replace("ё", "е")
        if key in ONE:
            names.setdefault(low, (key, title, icon, key))
        else:
            names.setdefault(low, ("p:" + low, f"{nm}, {kin if kin in NOMS else KIN_NAME.get(key, title.lower())}", icon, key))
    for f in facts:
        for m in _NAME_AFTER.finditer(f["text"]):
            put(m.group(2), m.group(1).lower())
        for m in _NAME_BEFORE.finditer(f["text"]):
            put(m.group(1), m.group(2).lower())
    return names


def classify(fact, names=None):
    """Факт → (ключ, название, значок, группа «people»|«topics»|«me»). Люди важнее тем: «у мамы давление» — про маму."""
    t = fact["text"] if isinstance(fact, dict) else str(fact)
    if ME_RX.search(t.strip()):
        return "me", "Обо мне", "🙂", "me"
    low = t.lower().replace("ё", "е")
    toks = re.findall(r"[а-яa-z0-9]+", low)
    for w in toks:                                  # имя, которое уже знаем
        if names and w in names:
            k, title, icon, _ = names[w]
            return k, title, icon, "people"
    for w in toks:
        if w in _KIN_ST:
            k, title, icon = _KIN_ST[w]
            return k, title, icon, "people"
    st = set(_stems(t))
    best, n = None, 0
    for k, s in _TOPIC_ST.items():
        c = len(st & s)
        if c > n:
            best, n = k, c
    if best:
        title, icon, _ = TOPICS[best]
        return best, title, icon, "topics"
    return "me", "Обо мне", "🙂", "me"


def pages(facts):
    """Факты по страницам: [{key, title, icon, group, facts:[…]}]; «Обо мне» первая, затем люди, затем темы."""
    names = _names(facts)
    by = {}
    for f in facts:
        k, title, icon, group = classify(f, names)
        p = by.setdefault(k, {"key": k, "title": title, "icon": icon, "group": group, "facts": []})
        p["facts"].append(f)
    order = {"me": 0, "people": 1, "topics": 2}
    return sorted(by.values(), key=lambda p: (order[p["group"]], -len(p["facts"]), p["title"]))


def _soon(text, today=None):
    """Дата в факте («14 ноября», «14.11») и сколько до неё дней в ближайшие 45 — для метки «через N дней»."""
    today = today or dt.date.today()
    low = text.lower()
    m = re.search(r"\b(\d{1,2})\s+(" + "|".join(MONTHS) + r")[а-я]*", low)
    d = None
    try:
        if m:
            mon = next(i for i, p in enumerate(MONTHS, 1) if m.group(2).startswith(p))
            d = dt.date(today.year, mon, int(m.group(1)))
        else:
            m = re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.\d{2,4})?\b", low)
            if m and re.search(r"рожд|юбиле|годовщин|праздн|свадьб", low):
                d = dt.date(today.year, int(m.group(2)), int(m.group(1)))
    except (ValueError, StopIteration):
        return None
    if not d or not re.search(r"рожд|юбиле|годовщин|праздн|свадьб|именин", low):
        return None
    if d < today:
        try:
            d = d.replace(year=today.year + 1)
        except ValueError:
            return None
    n = (d - today).days
    return n if n <= 45 else None


def tags(f, today=None):
    out = []
    if f.get("prev"):
        out.append(["now", "сейчас"])
    n = _soon(f["text"], today)
    if n is not None:
        out.append(["soon", "сегодня" if n == 0 else "завтра" if n == 1 else f"через {n} {_days(n)}"])
    return out


def _days(n):
    return "день" if n % 10 == 1 and n % 100 != 11 else "дня" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "дней"


def _fmt(f):
    return f["line"]


def core_ids(facts, limit=2500):
    """Что идёт в подсказку всегда: всё, если влезает; иначе — о самом человеке и «как со мной говорить», по одному
    первому факту о каждом человеке (кто есть кто), затем самое новое — пока хватает бюджета. -> множество i."""
    total = sum(len(f["line"]) + 1 for f in facts)
    if total <= limit:
        return {f["i"] for f in facts}
    names = _names(facts)
    first_of, mine = {}, []
    for f in facts:
        k, _, _, group = classify(f, names)
        if group == "me" or k == "style":
            mine.append(f)
        elif group == "people" and k not in first_of:
            first_of[k] = f
    picked, used = set(), 0

    def take(f):
        nonlocal used
        n = len(f["line"]) + 1
        if f["i"] in picked or used + n > limit:
            return False
        picked.add(f["i"])
        used += n
        return True
    for f in sorted(mine, key=lambda f: -f["i"])[:30]:          # о себе — сначала новое
        take(f)
    for f in first_of.values():
        take(f)
    for f in sorted(facts, key=lambda f: (f["date"] or dt.date.min, f["i"]), reverse=True):
        if used >= limit - 60:
            break
        take(f)
    return picked


def core_text(text, limit=2500):
    """Для системной подсказки: «Обо мне» целиком, если влезает (как раньше), иначе главное (core_ids) по порядку файла
    и строка о том, что остальное подбирается к вопросу."""
    facts = parse(text)
    if not facts:
        return (text or "").strip()[-limit:]
    ids = core_ids(facts, limit)
    if len(ids) == len(facts):
        return "\n".join(_fmt(f) for f in facts)
    rest = len(facts) - len(ids)
    return ("\n".join(_fmt(f) for f in facts if f["i"] in ids)
            + f"\n(И ещё {rest} {_facts_word(rest)} по людям и темам — нужные к вопросу придут в справке «Из памяти».)")


def _facts_word(n):
    return "факт" if n % 10 == 1 and n % 100 != 11 else "факта" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "фактов"


def _expand(st):
    out = set(st)
    for g in _SYN_ST:
        if st & g:
            out |= g
    return out


def score(question, facts, names=None):
    """Насколько каждый факт к вопросу: общие основы слов (с близкими по смыслу — вполовину), страница человека из
    вопроса («маме», «Маша») — весь его раздел. -> [(счёт, факт, почему)] по убыванию, только > 0."""
    names = names if names is not None else _names(facts)
    q = set(_stems(question))
    if not q:
        return []
    qx = _expand(q) - q
    low = (question or "").lower().replace("ё", "е")
    qpages = set()
    for w in re.findall(r"[а-яa-z0-9]+", low):
        if w in names:
            qpages.add(names[w][0])
        elif w in _KIN_ST:
            qpages.add(_KIN_ST[w][0])
            for v in names.values():                    # «дочь» в вопросе — и страница «Маша, дочь»
                if v[3] == _KIN_ST[w][0]:
                    qpages.add(v[0])
    qtop = {k for k, st in _TOPIC_ST.items() if q & st}      # «со здоровьем» — вся страница «Здоровье»
    df = {}
    fst = []
    for f in facts:
        s = set(_stems(f["text"] + " " + " ".join(f.get("prev") or [])))
        fst.append(s)
        for w in s:
            df[w] = df.get(w, 0) + 1
    n = max(1, len(facts))
    out = []
    for f, s in zip(facts, fst):
        sc, why = 0.0, []
        for w in q & s:
            sc += 1.0 + min(2.0, (n / df[w]) ** 0.5 / 2)
            why.append(w)
        for w in qx & s:
            sc += 0.6
            why.append("≈" + w)
        if qpages or qtop:
            k = classify(f, names)[0]
            if k in qpages:
                sc += 2.0
                why.append("страница")
            elif k in qtop:
                sc += 1.5
                why.append("страница")
        if sc > 0:
            out.append((round(sc, 2), f, why))
    out.sort(key=lambda x: (-x[0], -x[1]["i"]))
    return out


def relevant(question, text, limit=1200, skip=None, min_score=1.0):
    """К вопросу: факты не из главного (skip — множество i, по умолчанию core_ids), найденные по смыслу.
    -> (строки, [названия страниц])."""
    facts = parse(text)
    if not facts:
        return "", []
    skip = core_ids(facts) if skip is None else skip
    if len(skip) >= len(facts):
        return "", []
    names = _names(facts)
    lines, used, pg = [], 0, []
    for sc, f, _ in score(question, facts, names):
        if sc < min_score or f["i"] in skip:
            continue
        if used + len(f["line"]) > limit:
            break
        lines.append(f["line"])
        used += len(f["line"]) + 1
        t = classify(f, names)[1]
        if t not in pg:
            pg.append(t)
    return "\n".join(lines), pg


def view(text, today=None):
    """Для студии: страницы с фактами, метками и историей; сколько идёт в подсказку всегда."""
    facts = parse(text)
    ids = core_ids(facts)
    out = []
    for p in pages(facts):
        out.append({"key": p["key"], "title": p["title"], "icon": p["icon"], "group": p["group"],
                    "facts": [{"i": f["i"], "text": f["text"], "date": f["date"].strftime("%d.%m.%Y") if f["date"] else "",
                               "prev": f["prev"], "tags": tags(f, today), "core": f["i"] in ids}
                              for f in sorted(p["facts"], key=lambda f: -f["i"])]})
    return {"pages": out, "total": len(facts), "core": len(ids), "fits": len(ids) == len(facts)}


def find(question, text, limit=12):
    facts = parse(text)
    names = _names(facts)
    res = []
    for sc, f, why in score(question, facts, names)[:limit]:
        k, title, icon, _ = classify(f, names)
        res.append({"i": f["i"], "text": f["text"], "page": title, "icon": icon, "score": sc,
                    "meaning": any(w.startswith("≈") or w == "страница" for w in why)})
    return res


def forget(text, i):
    """Убрать факт номер i (по parse) из текста файла. -> новый текст."""
    facts = parse(text)
    if not 0 <= i < len(facts):
        return text
    target, n, out = facts[i]["line"], 0, []
    for ln in text.split("\n"):
        if FACT_RX.match(ln.strip()):
            if n == i and ln.strip() == target:
                n += 1
                continue
            n += 1
        out.append(ln)
    return "\n".join(out)
