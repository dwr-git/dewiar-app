"""Личные деньги голосом: «купил кофе за 8 рублей», «получил зарплату 3000», «сколько я потратил за неделю?».

Разбор фраз без модели: parse() -> запись/отмена/вопрос; суммы словами или цифрами («восемь пятьдесят», «полторы
тысячи», «3к», «1 200,50»), категория — по ключевым словам (EXPENSE_CATS, INCOME_CATS).
Money хранит записи в money.json рядом с настройками — это единственный источник правды; «Финансы/ГГГГ-ММ.md» в папке
ассистента (для человека и Obsidian) только перезаписывается из него. Записи синхронизируются с телефоном (upsert по id,
on_change будит синхронизацию — см. engine.py), поэтому id и поля записи менять согласованно с обеими сторонами."""
import datetime as dt
import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path

CURRENCIES = {"BYN": ("руб.", r"бел(?:орусск\w*)?\s*руб\w*|byn|br"), "RUB": ("₽", r"российск\w*\s*руб\w*|rub|₽"),
              "USD": ("$", r"доллар\w*|бакс\w*|usd|\$"), "EUR": ("€", r"евро|eur|€"), "PLN": ("zł", r"злот\w*|pln"),
              "CNY": ("¥", r"юан\w*|cny")}
RUB_WORD = r"руб\w*|р\b"              # просто «рубли» не задают валюту: берётся валюта по умолчанию (настройки или пояс)

EXPENSE_CATS = [
    ("Продукты", r"продукт|магазин|еда|еду|хлеб|молок|овощ|фрукт|мяс|рыб|сыр|яйц|гипермаркет|евроопт|соседи|гиппо|корзин"),
    ("Кафе и рестораны", r"кофе|кафе|ресторан|обед|ужин|завтрак|пицц|суши|бургер|шаурм|доставк\w* еды|бар\b|пиво"),
    ("Транспорт", r"такси|бензин|топлив|заправк|проезд|автобус|метро|маршрутк|парковк|поезд|билет на поезд|самолет|авиа|машин|шиномонтаж|ремонт машин"),
    ("Дом и связь", r"коммуналк|квартир|аренд|интернет|связ|телефон|мобильн|электричеств|газ\b|вод[аеу]\b|свет\b|жкх|ремонт"),
    ("Здоровье", r"аптек|лекарств|врач|клиник|анализ|стоматолог|зуб|таблетк|витамин"),
    ("Одежда", r"одежд|обув|куртк|джинс|кроссовк|футболк|плать|рубашк"),
    ("Развлечения", r"кино|концерт|театр|подписк|игр[ауы]|netflix|spotify|музе|боулинг|отдых|отпуск|путешеств|отел"),
    ("Подарки", r"подар|цвет[ыо]|букет"),
    ("Техника", r"телефон новый|ноутбук|компьютер|наушник|техник|гаджет|видеокарт|монитор|телевизор|холодильник|пылесос|стиральн|микроволнов"),
    ("Учёба", r"курс[ыа]?\b|книг|учеб|обучен|репетитор|школ"),
    ("Красота и спорт", r"спортзал|фитнес|абонемент|парикмахер|стрижк|салон|маникюр|бассейн"),
    ("Дети", r"детск|ребенк|ребёнк|садик|игрушк|памперс"),
    ("Животные", r"корм|ветеринар|кошк|кот[ау]?\b|собак"),
]
INCOME_CATS = [("Зарплата", r"зарплат|зп\b|оклад|получк"), ("Аванс", r"аванс"), ("Премия", r"преми|бонус"),
               ("Подработка", r"фриланс|подработк|проект|заказ|халтур"), ("Подарок", r"подарил|подарок|подарили"),
               ("Возврат", r"вернул|возврат|кэшбэк|кешбек|cashback"), ("Проценты", r"процент|дивиденд|вклад"),
               ("Клиенты", r"клиент\w*:|оплатил\w* сч[её]т|по сделке")]                # оплата сделки («Клиенты» → «Сделки»)

UNITS = {"ноль": 0, "один": 1, "одна": 1, "одну": 1, "два": 2, "две": 2, "три": 3, "четыре": 4, "пять": 5, "шесть": 6,
         "семь": 7, "восемь": 8, "девять": 9, "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13,
         "четырнадцать": 14, "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
         "девятнадцать": 19, "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60,
         "семьдесят": 70, "восемьдесят": 80, "девяносто": 90, "сто": 100, "двести": 200, "триста": 300,
         "четыреста": 400, "пятьсот": 500, "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900}
SCALES = {"тысяча": 1000, "тысячи": 1000, "тысяч": 1000, "тыс": 1000, "тыщ": 1000, "тыщи": 1000, "тысячу": 1000,
          "миллион": 1_000_000, "миллиона": 1_000_000, "миллионов": 1_000_000, "млн": 1_000_000}

EXP_RX = re.compile(r"^(?:(?:а|и|ну|так|запиши|слушай)\s+)*(?:я\s+)?(?:сегодня\s+|вчера\s+)?"
                    r"(?P<verb>купил[аи]?|покупк[аи]|потратил[аи]?|трата|траты|расход|заплатил[аи]?|оплатил[аи]?|"
                    r"отдал[аи]?|скинул[аи]?\s+на|задонатил|спустил[аи]?)\b(?P<rest>.*)$")
INC_RX = re.compile(r"^(?:(?:а|и|ну|так|запиши|слушай)\s+)*(?:мне\s+|я\s+)?(?:сегодня\s+|вчера\s+)?"
                    r"(?P<verb>получил[аи]?|пришл[аои]|пришел|пришёл|заработал[аи]?|доход|начислил[аи]|перевели\s+мне|"
                    r"мне\s+перевели|вернули|поступил[аои]?|поступлени[ея]|выплатил[аи]|дали|подарили)\b(?P<rest>.*)$")
UNDO_RX = re.compile(r"^(?:отмени|удали|убери|сотри)\s+(?:последн\w+\s+)?(?:трату|расход|покупку|запись\s+о\s+(?:трате|"
                     r"расходе|доходе)|доход|операцию|запись\s+в\s+расходах)$")
CONVO_RX = re.compile(r"\bменял|\bменяли|\bпоменял|сколько\s+раз|\bговорил|\bобсуждал|\bостановил|\bзакладыва|\bзаложил|\bпланир")
QUERY_RX = re.compile(r"(?:сколько|какие|покажи|какой|что\s+с|каков|мои|расскажи\s+про)\b.*\b(?:потратил\w*|трат\w*|расход\w*|"
                      r"доход\w*|заработал\w*|получил\w*|деньг\w*|бюджет\w*|баланс\w*|финанс\w*|ушло)")


def words_to_number(text):
    """Первое число в тексте -> (число, (начало, конец)) или (None, None).

    «полторы тысячи двести» → 1700, «восемь пятьдесят» → 8.5 (рубли и копейки), «сто двадцать рублей пятьдесят
    копеек» → 120.5, «3к» → 3000, «1 200,50» → 1200.5. Цифры важнее слов. Для числа словами позиция — только начало
    первого слова (начало и конец совпадают)."""
    t = (text or "").lower().replace("ё", "е")
    m = re.search(r"(\d[\d\s]*(?:[.,]\d{1,2})?)\s*(к|k|тыс\w*|тыщ\w*|млн|миллион\w*)?(?![\d])", t)
    if m:
        n = float(re.sub(r"\s", "", m.group(1)).replace(",", "."))
        if m.group(2):
            n *= 1_000_000 if m.group(2).startswith(("млн", "миллион")) else 1000
        return n, m.span()
    words = re.findall(r"[а-я]+", t)
    total, cur, used = 0, 0, []
    frac = None
    i = 0
    while i < len(words):
        w = words[i]
        if w in ("полторы", "полтора"):
            cur += 1.5
            used.append(w)
        elif w in UNITS:
            if cur and UNITS[w] < 100 and cur % 100 == 0 or cur >= 20 and cur % 10 == 0 and UNITS[w] < 10:
                cur += UNITS[w]
            elif cur and total == 0 and not used[-1:] == ["и"] and UNITS[w] < 100 and len(used) >= 1 and cur < 1000:
                frac = UNITS[w]                       # «восемь пятьдесят» — 8,50: второе число до ста — копейки
                if i + 1 < len(words) and words[i + 1] in UNITS and UNITS[words[i + 1]] < 10 and frac >= 20:
                    frac += UNITS[words[i + 1]]
                    i += 1
                used.append(w)
                break
            else:
                cur += UNITS[w]
            used.append(w)
        elif w in SCALES:
            total += (cur or 1) * SCALES[w]
            cur = 0
            used.append(w)
        elif used and w in ("рублей", "рубля", "рубль", "долларов", "доллара", "евро"):
            j = i + 1
            kop = 0
            while j < len(words) and words[j] in UNITS and UNITS[words[j]] < 100:
                kop += UNITS[words[j]]
                j += 1
            if kop and j < len(words) and words[j].startswith(("копе", "цент")):
                frac = kop
            break
        elif used:
            break
        i += 1
    if not used:
        return None, None
    n = total + cur
    if frac is not None:
        n += frac / 100
    first = re.search(r"\b" + re.escape(used[0]) + r"\b", t)
    return n, ((first.start() if first else 0), (first.start() if first else 0))


NUM_START = r"(?:\d|" + "|".join(list(UNITS) + ["полторы", "полтора", "тысячу"]) + r")"
CUR_ANY = RUB_WORD + "|" + "|".join(rx for _, rx in CURRENCIES.values())


def amount_of(rest):
    """Сумма во фразе: число после последнего «за/на/всего/по», иначе число с валютой, иначе первое число.
    «купил 2 билета за 30» → 30."""
    for m in reversed(list(re.finditer(r"\b(?:за|на|всего|в\s+сумме|по)\s+(?=" + NUM_START + ")", rest))):
        n, _ = words_to_number(rest[m.end():])
        if n:
            return n
    m = re.search(r"(\d[\d\s]*(?:[.,]\d{1,2})?\s*(?:к|тыс\w*)?)\s*(?:" + CUR_ANY + ")", rest)
    if m:
        return words_to_number(m.group(1))[0]
    return words_to_number(rest)[0]


def _currency(text, default):
    """Код валюты, названной в тексте, иначе default (просто «рубли» — тоже default)."""
    t = text.lower()
    for code, (_, rx) in CURRENCIES.items():
        if code in ("BYN", "RUB") and not re.search(rx, t):
            continue
        if re.search(rx, t):
            return code
    return default


def _category(text, kind):
    t = text.lower().replace("ё", "е")
    for name, rx in (EXPENSE_CATS if kind == "expense" else INCOME_CATS):
        if re.search(rx, t):
            return name
    return "Другое"


def _clean_note(rest):
    """Описание операции: фраза без суммы, валюты и служебных слов («кофе за 8 рублей» → «кофе»)."""
    t =re.sub(r"\b(?:за|на|в|по|всего|около|примерно|целых|аж)\b\s*$", "", rest.strip())
    t = re.sub(r"(\d[\d\s]*(?:[.,]\d{1,2})?)\s*(?:к|k|тыс\w*|тыщ\w*)?\s*(?:" + RUB_WORD + r"|копе\w*|"
               + "|".join(rx for _, rx in CURRENCIES.values()) + r")?", " ", t)
    t = re.sub(r"\b(?:" + "|".join(list(UNITS) + list(SCALES) + ["полторы", "полтора"]) + r")\b", " ", t)
    t = re.sub(r"\b(?:рубл\w*|копе\w*|доллар\w*|евро|за|на|в|по|всего|около|примерно|сегодня|вчера|мне|я)\b", " ", t)
    t = re.sub(r"[^\w\s-]", " ", t)
    return " ".join(t.split()).strip(" -")


def parse(text, default_currency="BYN"):
    """Фраза -> {"op": "add", "kind", "amount", "currency", "category", "note", "date"} | {"op": "undo"}
    | {"op": "query", "period", "kind", "category"} | None (не про деньги — пусть отвечает модель).
    Суммы больше 50 млн отбрасываются как ошибка распознавания."""
    t = re.sub(r"[«»\"“”!?]", " ", (text or "").lower().replace("ё", "е"))
    t = " ".join(t.split()).strip(" .")
    if not t:
        return None
    if UNDO_RX.match(t):
        return {"op": "undo"}
    if QUERY_RX.search(t):
        if CONVO_RX.search(t):                   # «сколько раз я менял бюджет», «на чём остановился» — про разговор, не про записи
            return None
        if not EXP_RX.match(t) and not INC_RX.match(t):
            return {"op": "query", "period": period(t), "kind": "income" if re.search(r"доход|заработал|получил", t)
                    else "both" if re.search(r"баланс|бюджет|финанс|деньг", t) else "expense",
                    "category": _query_category(t)}
    for kind, rx in (("expense", EXP_RX), ("income", INC_RX)):
        m = rx.match(t)
        if not m:
            continue
        rest = m.group("rest")
        amount = amount_of(rest)
        if not amount or amount <= 0 or amount > 50_000_000:
            return None
        if kind == "income" and re.match(r"получил|пришл|пришел|пришёл|дали|вернули|подарили|поступ", m.group("verb")) \
                and not re.search(CUR_ANY, rest) and _category(rest, "income") == "Другое":
            return None                                   # «получил 5 сообщений» — это не деньги
        if kind == "expense" and re.match(r"^(?:купил[аи]?)\s+(?:билет|подарок)?\s*$", t):
            return None                                   # «купил билет» без суммы — не запись
        verb = m.group("verb")
        note = _clean_note(rest)
        if kind == "income" and not note:
            note = {"получил": "", "заработал": "заработок"}.get(re.sub(r"[аи]$", "", verb), "")
        day = dt.date.today() - dt.timedelta(days=1) if re.search(r"\bвчера\b", t) else dt.date.today()
        return {"op": "add", "kind": kind, "amount": round(amount, 2), "currency": _currency(rest, default_currency),
                "category": _category(rest + " " + verb, kind), "note": note[:80], "date": day.isoformat()}
    return None


def _query_category(t):
    """Категория в вопросе («сколько ушло на такси») — только после «на/в/за», иначе ""."""
    for name, rx in EXPENSE_CATS + INCOME_CATS:
        if re.search(r"\b(?:на|в|за)\s+\w*(?:" + rx + r")", t):
            return name
    return ""


def period(t, today=None):
    """«за неделю», «в сентябре», «сегодня», «за прошлый месяц», «в этом году» → (с, по) включительно, даты.
    Неделя и год — от начала до сегодня; названный месяц позже текущего — прошлогодний; иначе — текущий месяц."""
    d = today or dt.date.today()
    # «ма[йяе]»: май — единственный месяц, у которого основа меняется в предложном падеже («в мае»)
    months = ["январ", "феврал", "март", "апрел", "ма[йяе]", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
    if re.search(r"сегодня", t):
        return d, d
    if re.search(r"вчера", t):
        return d - dt.timedelta(days=1), d - dt.timedelta(days=1)
    if re.search(r"прошл\w+\s+недел", t):
        s = d - dt.timedelta(days=d.weekday() + 7)
        return s, s + dt.timedelta(days=6)
    if re.search(r"недел", t):
        return d - dt.timedelta(days=d.weekday()), d
    if re.search(r"прошл\w+\s+месяц", t):
        e = d.replace(day=1) - dt.timedelta(days=1)
        return e.replace(day=1), e
    if re.search(r"\bгод|году\b", t):
        return d.replace(month=1, day=1), d
    for i, mrx in enumerate(months):
        if re.search(r"\b(?:в|за)\s+" + mrx, t):
            y = d.year if i + 1 <= d.month else d.year - 1
            s = dt.date(y, i + 1, 1)
            e = (dt.date(y + (i + 1) // 12, (i + 1) % 12 + 1, 1) - dt.timedelta(days=1))
            return s, min(e, d) if y == d.year and i + 1 == d.month else e
    return d.replace(day=1), d                     # по умолчанию — этот месяц


def fmt(n, cur):
    """1234.5, "BYN" → «1 234,50 руб.»; целые — без «,00»."""
    s =f"{n:,.2f}".replace(",", " ").replace(".", ",")
    if s.endswith(",00"):
        s = s[:-3]
    return f"{s} {CURRENCIES.get(cur, (cur,))[0]}"


class Money:
    """Записи о деньгах: path — money.json, workspace — папка ассистента для «Финансы/*.md» (None — без них),
    currency_fn() — валюта по умолчанию. on_change (ставится снаружи) вызывается после каждого сохранения.
    Запись: id, date (ГГГГ-ММ-ДД), kind (expense/income), amount, currency, category, note, said, created."""

    def __init__(self, path, workspace=None, currency_fn=None):
        self.path = Path(path)
        self.ws = workspace
        self.currency_fn = currency_fn or (lambda: "BYN")
        self._lock = threading.RLock()                    # _save → _write_month → list() под тем же замком
        self.items = self._load()
        self.on_add = None                                # новая запись -> (семейный бюджет, engine.py)
        self.on_delete = None                             # запись удалена (в т. ч. «отмени последнюю трату») -> семье

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d.get("items", []) if isinstance(d, dict) else []
        except (OSError, ValueError):
            return []

    def _save(self, months=()):
        """Записать money.json (через .tmp — файл не останется недописанным), позвать on_change и переписать
        «Финансы/*.md» за затронутые месяцы (ГГГГ-ММ). Ошибки on_change и .md не мешают сохранению."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"items": self.items}, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)
        if getattr(self, "on_change", None):
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass
        for ym in set(months):
            try:
                self._write_month(ym)
            except OSError:
                pass

    def currency(self):
        return (self.currency_fn() or "BYN").upper()

    def add(self, kind, amount, currency=None, category="", note="", date=None, said=""):
        if kind not in ("expense", "income"):
            raise ValueError("вид — расход или доход")
        amount = round(float(amount), 2)
        if amount <= 0:
            raise ValueError("сумма должна быть больше нуля")
        day = str(date or dt.date.today().isoformat())[:10]
        dt.date.fromisoformat(day)                         # проверка даты: неверная — ValueError
        it = {"id": uuid.uuid4().hex[:10], "date": day, "kind": kind, "amount": amount,
              "currency": (currency or self.currency()).upper(), "category": category or _category(note, kind),
              "note": (note or "").strip()[:200], "said": (said or "")[:300], "created": int(time.time())}
        with self._lock:
            self.items.append(it)
            self._save([day[:7]])
        if self.on_add:                                    # семейный бюджет (family.py): расход — семье
            try:
                self.on_add(it)
            except Exception:  # noqa: BLE001
                logging.getLogger("dewiar.money").exception("семья: трата не ушла")
        return it

    def update(self, iid, patch):
        with self._lock:
            it = next((x for x in self.items if x["id"] == iid), None)
            if not it:
                raise ValueError("записи нет")
            old = it["date"][:7]
            for k in ("date", "kind", "amount", "currency", "category", "note"):
                if k in patch and patch[k] not in (None, ""):
                    it[k] = round(float(patch[k]), 2) if k == "amount" else str(patch[k])
            self._save([old, it["date"][:7]])
            return it

    def upsert(self, item):
        """Синхронизация: запись с другого устройства — создать или заменить запись с тем же id -> копия записи.
        said и created своей записи сохраняются; .md переписывается за старый и новый месяц."""
        day = str(item.get("date") or dt.date.today().isoformat())[:10]
        dt.date.fromisoformat(day)
        with self._lock:
            it = next((x for x in self.items if x["id"] == item["id"]), None)
            old = it["date"][:7] if it else day[:7]
            if it is None:
                it = {"id": item["id"], "created": int(time.time()), "said": ""}
                self.items.append(it)
            it.update(date=day, kind=item.get("kind") if item.get("kind") in ("expense", "income") else "expense",
                      amount=round(float(item.get("amount") or 0), 2), currency=str(item.get("currency") or self.currency()).upper(),
                      category=str(item.get("category") or ""), note=str(item.get("note") or "")[:200])
            self._save([old, day[:7]])
            return dict(it)

    def delete(self, iid):
        with self._lock:
            it = next((x for x in self.items if x["id"] == iid), None)
            if not it:
                return None
            self.items.remove(it)
            self._save([it["date"][:7]])
        if self.on_delete:
            try:
                self.on_delete(iid)
            except Exception:  # noqa: BLE001
                logging.getLogger("dewiar.money").exception("семья: удаление не ушло")
        return it

    def last(self):
        """Последняя добавленная запись (для «отмени последнюю трату»)."""
        with self._lock:
            return max(self.items, key=lambda x: x.get("created", 0)) if self.items else None

    def list(self, start=None, end=None):
        """Копии записей с start по end включительно (строки ГГГГ-ММ-ДД), новые сначала."""
        s, e = str(start or "0000"), str(end or "9999")
        with self._lock:
            out = [dict(x) for x in self.items if s <= x["date"] <= e]
        return sorted(out, key=lambda x: (x["date"], x.get("created", 0)), reverse=True)

    def summary(self, start=None, end=None):
        """Итоги за период: по каждой валюте — доходы, расходы, остаток и категории; days — по дням, только для
        первой валюты по алфавиту (валюты не складываем)."""
        items = self.list(start, end)
        tot, cats = {}, {}
        for x in items:
            k = (x["kind"], x["currency"])
            tot[k] = tot.get(k, 0) + x["amount"]
            ck = (x["kind"], x["currency"], x["category"])
            cats[ck] = cats.get(ck, 0) + x["amount"]
        curs = sorted({c for _, c in tot}) or [self.currency()]
        by_cur = []
        for c in curs:
            inc, exp = round(tot.get(("income", c), 0), 2), round(tot.get(("expense", c), 0), 2)
            by_cur.append({"currency": c, "income": inc, "expense": exp, "balance": round(inc - exp, 2),
                           "expense_cats": sorted([{"name": n, "sum": round(v, 2)} for (k, cc, n), v in cats.items()
                                                   if k == "expense" and cc == c], key=lambda x: -x["sum"]),
                           "income_cats": sorted([{"name": n, "sum": round(v, 2)} for (k, cc, n), v in cats.items()
                                                  if k == "income" and cc == c], key=lambda x: -x["sum"])})
        days = {}
        for x in items:
            if x["currency"] == curs[0]:
                d = days.setdefault(x["date"], {"income": 0, "expense": 0})
                d[x["kind"]] = round(d[x["kind"]] + x["amount"], 2)
        return {"from": str(start or ""), "to": str(end or ""), "count": len(items), "by_currency": by_cur, "days": days}

    def answer(self, q):
        """Ответ голосом на вопрос из parse() («сколько я потратил за неделю?») — одна-две фразы."""
        s, e = q["period"]
        sm = self.summary(s.isoformat(), e.isoformat())
        when = _period_words(s, e)
        if not sm["count"]:
            return f"{when.capitalize()} записей о деньгах нет."
        parts = []
        for c in sm["by_currency"]:
            if q.get("category"):
                cat = next((x for x in c["expense_cats"] + c["income_cats"] if x["name"] == q["category"]), None)
                parts.append(f"на «{q['category']}» — {fmt(cat['sum'], c['currency'])}" if cat else
                             f"на «{q['category']}» ничего")
                continue
            if q["kind"] in ("expense", "both") and c["expense"]:
                top = ", ".join(f"{x['name'].lower()} {fmt(x['sum'], c['currency'])}" for x in c["expense_cats"][:3])
                parts.append(f"расходы {fmt(c['expense'], c['currency'])}" + (f" (больше всего: {top})" if top else ""))
            if q["kind"] in ("income", "both") and c["income"]:
                parts.append(f"доходы {fmt(c['income'], c['currency'])}")
            if q["kind"] == "both":
                parts.append(f"остаток {fmt(c['balance'], c['currency'])}")
        if not parts:
            return f"{when.capitalize()} {'доходов' if q['kind'] == 'income' else 'расходов'} не записано."
        return f"{when.capitalize()}: " + "; ".join(parts) + "."

    def _write_month(self, ym):
        """Переписать «Финансы/ГГГГ-ММ.md» целиком; месяц без записей — файл удаляется. Правки в .md не читаются."""
        if self.ws is None:
            return
        y, m = map(int, ym.split("-"))
        start = dt.date(y, m, 1)
        end = dt.date(y + m // 12, m % 12 + 1, 1) - dt.timedelta(days=1)
        items = self.list(start.isoformat(), end.isoformat())
        base = Path(self.ws.ensure()) / "Финансы"
        base.mkdir(parents=True, exist_ok=True)
        p = base / f"{ym}.md"
        if not items:
            p.unlink(missing_ok=True)
            return
        sm = self.summary(start.isoformat(), end.isoformat())
        lines = [f"# Деньги — {MONTHS_NOM[m - 1]} {y}", "", "_Файл обновляется сам. Добавить: «купил …», «получил …»; "
                 "поправить — в студии, «Календарь» → «Деньги»._", ""]
        for c in sm["by_currency"]:
            lines += [f"**Доходы:** {fmt(c['income'], c['currency'])} · **Расходы:** {fmt(c['expense'], c['currency'])} · "
                      f"**Остаток:** {fmt(c['balance'], c['currency'])}", ""]
            if c["expense_cats"]:
                lines += ["| Категория | Сумма |", "|---|---:|"] + [f"| {x['name']} | {fmt(x['sum'], c['currency'])} |"
                                                                    for x in c["expense_cats"]] + [""]
        lines += ["## Операции", ""]
        for x in items:
            sign = "+" if x["kind"] == "income" else "−"
            lines.append(f"- {x['date'][8:10]}.{x['date'][5:7]} {sign}{fmt(x['amount'], x['currency'])} · {x['category']}"
                         + (f" — {x['note']}" if x["note"] else ""))
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")


MONTHS_NOM = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь",
              "декабрь"]
MONTHS_PREP = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре", "ноябре",
               "декабре"]


def _period_words(s, e):
    """Период словами для ответа: «сегодня», «на этой неделе», «в сентябре», «с 01.09 по 15.09»."""
    d =dt.date.today()
    if s == e == d:
        return "сегодня"
    if s == e == d - dt.timedelta(days=1):
        return "вчера"
    if s == d - dt.timedelta(days=d.weekday()) and e == d:
        return "на этой неделе"
    if s.day == 1 and s.month == d.month and s.year == d.year and e == d:
        return "в этом месяце"
    if s.day == 1 and (e + dt.timedelta(days=1)).day == 1 and s.month == e.month:
        return f"в {MONTHS_PREP[s.month - 1]}"
    if s == d.replace(month=1, day=1):
        return "в этом году"
    return f"с {s:%d.%m} по {e:%d.%m}"
