"""Одна дверь для модулей (1.0 «Надёжность», владелец 15.11: «ядро + плагины, изящно, не осьминог»).

Раньше каждое умение вне ядра проверялось своей веткой в Toolbox.policy (подключена ли почта, включены ли «Сайты»…) и
ещё раз — своей строкой в Toolbox._needs (что сказать человеку). Теперь модуль описан один раз — здесь: какие у него
инструменты, каким переключателем «Возможностей» он включается, что ему нужно для работы и что сказать, если этого нет.
Ядро спрашивает только одно: usable(имя инструмента) — и для чата, и для больших задач, и для студии.

Модуль = {id, title, tools | prefixes, feature, ready, need, tool_ready}:
    feature    — (ключ settings.features, значение по умолчанию): выключили в «Возможностях» — инструментов модели не видно;
    ready(h,s) — подключено ли то, без чего модуль не работает (почта, бот, умный дом…) — по объектам ядра (Toolbox.hooks);
    need       — (что сделать, раздел студии) — подсказка на переключателе «Умения», когда ready() ложно;
    tool_ready — {инструмент: ready} — у отдельного инструмента своё условие (client_crm — ещё и CRM).
Инструмент, которого нет ни в одном модуле, — ядро: разговор, «Мой день», «Мои файлы», голос, задачи.

Предохранитель (Fuse): модуль, который падает (не ToolError — та честно говорит модели «нет такого сайта», — а
настоящий сбой кода: KeyError, TypeError…), 3 раза за 10 минут, на 15 минут выключается: его инструменты пропадают из
подсказки модели, а модель знает, что сказать человеку (off_note). Разговор, голос и «Мой день» не задеты. Через 15 минут
модуль пробует снова; удачный вызов обнуляет счёт. Так же — серверы плагинов (MCP), каждый отдельно: чужой сломанный плагин
не дёргают по кругу. Сработал — счётчик «fuse:<модуль>» в «чем пользуются» (имена плагинов людей не считаем: «fuse:plugin»)."""

import threading
import time

FUSE_FAILS = 3            # сбоев подряд за окно — и модуль на паузе
FUSE_WINDOW = 600         # окно счёта, секунд
FUSE_PAUSE = 900          # пауза, секунд; потом — снова пробуем


def _mail(h, s):
    m = h.get("mail")
    return bool(m and m.configured())


def _posts(h, s):
    P = h.get("pbot_posts")
    return bool(P is not None and P.bot.connected() and any(c["can"] for c in P.chats()))


def _maker(h, s):
    return h.get("maker") is not None


def _maker_change(h, s):
    return h.get("maker") is not None and any(p.get("made") for p in h["maker"].P.items.values())


MAIL_TOOLS = ("send_email", "read_emails", "read_email", "manage_email", "mail_table", "mailing", "mailing_status")

MODULES = [
    {"id": "mail", "title": "Почта", "words": r"почт|письм|e-?mail|имейл|мейл|рассылк|входящ|ящик", "tools": MAIL_TOOLS, "ready": _mail,
     "need": ("Сначала подключите почту — «Подключение» → «Почта»", "connect")},
    {"id": "telegram", "title": "Telegram и MAX", "words": r"телеграм|telegram|\bтг\b|\bmax\b|\bмакс\b|мессенджер", "tools": ("send_telegram",),
     "ready": lambda h, s: bool(h.get("telegram") and h["telegram"].paired()),
     "need": ("Сначала подключите Telegram или MAX — «Подключение»", "connect")},
    {"id": "posts", "title": "Посты в канал", "words": r"канал|пост[аыуо]?\b|публикац|опубликуй", "tools": ("channel_post",), "ready": _posts},
    {"id": "home", "title": "Умный дом", "words": r"свет|ламп|розетк|умн\w*\s+дом|алис|кондиционер|отоплен|пылесос|штор|термостат|home assistant|обогрев|чайник|увлажнит", "tools": ("smart_home",),
     "ready": lambda h, s: bool(h.get("home") and h["home"].connected()),
     "need": ("Сначала подключите умный дом (Яндекс или Home Assistant) — «Подключение»", "connect")},
    {"id": "clients", "title": "Клиенты", "words": r"клиент|сделк|crm|црм|битрикс|amo|воронк|заказчик|\bлид", "prefixes": ("client_",), "tools": ("deal_remind",), "feature": ("clients", False),
     "ready": lambda h, s: h.get("clients") is not None,
     "tool_ready": {"client_crm": lambda h, s: bool(h.get("crm") and h["crm"].connected())}},
    {"id": "sites", "title": "Сайты", "words": r"сайт|лендинг|домен|\bseo\b|\bсео\b|страниц\w*\s+(?:в интернете|компании|для)", "prefixes": ("site_",), "feature": ("sites", True),
     "ready": lambda h, s: h.get("sites") is not None},
    {"id": "team", "title": "Поручения", "words": r"сотрудник|поручен|поручи|подчинён|подчинен|работник|коллег|команд[аеуы]\b", "tools": ("team_assign", "team_status", "team_message"), "feature": ("team", False),
     "ready": lambda h, s: bool(h.get("team") and h["team"].connected())},
    {"id": "servers", "title": "Серверы", "words": r"сервер|\bssh\b|\bvps\b|хостинг", "tools": ("server_run",),
     "ready": lambda h, s: bool(h.get("servers") and h["servers"].items),
     "need": ("Сначала добавьте сервер — «Серверы»", "servers")},
    {"id": "knowledge", "title": "Документы в «Знаниях»", "words": r"документ|знани|инструкц|регламент|договор|в (?:моих )?файлах|базе", "tools": ("search_documents",),
     "ready": lambda h, s: bool(h.get("knowledge") and h["knowledge"].has_files()),
     "need": ("Сначала добавьте документы в «Знания» — «Обо мне» → «Мои документы»", "me")},
    {"id": "account", "title": "Облачные знания", "words": r"знани|базе|компани", "tools": ("ask_knowledge",),
     "ready": lambda h, s: bool(h.get("account") and h["account"].logged_in()),
     "need": ("Нужен вход аккаунтом dewiar.pro — «Dewiar.pro»", "dw")},
    {"id": "maker", "title": "Плагин словами", "words": r"плагин|расширени", "tools": ("plugin_create", "plugin_change"), "ready": _maker,
     "tool_ready": {"plugin_change": _maker_change}},
    # модули без условий подключения — в двери ради предохранителя и единого счёта (пилот 1.0)
    {"id": "podcast", "title": "Подкасты", "words": r"подкаст|аудиокниг|озвуч|беседу двух", "tools": ("make_podcast",)},
    {"id": "council", "title": "Совет ИИ", "words": r"совет|посовет|мнени|дебат|поспорь|спор[ау]?\b|обсуд|за и против|плюсы и минусы|что выбрать|как лучше|стоит ли", "tools": ("council", "debate")},
    {"id": "radar", "title": "Радар", "words": r"радар|тренд|сигнал|источник|новост|что нового", "tools": ("insight_ask",)},
    {"id": "music", "title": "Музыка и радио", "tools": ("play_music", "play_radio", "play_youtube", "yandex_music")},
]

# Пачки действий (харнесс, шаг 1 — 15.11, «облегчить вопрос»): это ядро — деньги, близкие, файлы, компьютер, — но описания
# их действий модели нужны не в каждом вопросе. Пачка — только о том, КОГДА её действия отдать модели (по словам вопроса,
# недавнему делу или просьбе самой модели — more_tools); предохранитель и «Возможности» к пачкам не относятся (ядро).
PACKS = [
    {"id": "money", "title": "Деньги", "tools": ("money_add", "money_find", "money_fix", "money_report", "month_summary", "payments"),
     "words": r"руб|₽|\$|долл|евро|тенге|\bbyn\b|деньг|потрат|заплат|купил|расход|доход|трат|бюджет|зарплат|плат[её]ж|оплат|"
              r"сч[её]т|кредит|долг|подписк|стоил|стоит|копил|сэконом|кошел|копе|сколько ушло|итог\w* (?:месяц|недел|дня)"},
    {"id": "close", "title": "Близкие: звонки и сообщения", "tools": ("close_call", "close_read", "close_send"),
     "words": r"позвони|звон|набери|близк|сообщени|видеосвяз|напиши|что пиш|мам|пап|жен[аеуы]|муж[уае]?\b|сын|доч|брат|сестр|"
              r"бабушк|дедушк|семь|родн"},
    {"id": "docs", "title": "Документы и файлы", "tools": ("doc_find", "doc_replace", "ocr", "archive_open", "delete_files", "read_file"),
     "words": r"документ|файл|\bpdf\b|docx|ворд|word|excel|эксел|таблиц|архив|\bzip\b|скан|распознай|\bocr\b|удали|папк|договор|"
              r"замени|прочитай|открой|вложени|приложил|прикрепил"},
    {"id": "pc", "title": "Компьютер: экран, камера, система", "tools": ("tv", "power", "look_at_screen", "look_through_camera",
     "save_screenshot", "system_status", "run_command", "open_path", "watch"),   # widget — ядро: «спрячься» с опечаткой — тоже
     "words": r"экран|скриншот|снимок|камер|телевизор|\bтв\b|выключи|перезагру|спящ|виджет|диск|процессор|систем|терминал|консол|"
              r"команд|папк|посмотри|следи|дозор|наблюда|компьютер|ноутбук|места на|памят\w* компьют|спрячь|покажись"},
    {"id": "route", "title": "Маршруты", "tools": ("route",), "words": r"маршрут|доехать|добраться|пройти до|дорог|пробк|навигат|карт[аеуы]\b|ехать"},
    {"id": "persona", "title": "Другие персонажи", "tools": ("call_persona",), "words": r"позови|персонаж|пусть\s+\w+\s+(?:ответ|скаж)|спроси у|патрик|совет|посовет|мнени|обсуд"},
    {"id": "skills", "title": "Навыки и плагины", "tools": ("create_skill", "plugin_enable"), "words": r"навык|плагин|умени|научись"},
    {"id": "lab", "title": "Лаборатория: код и расчёты", "tools": ("lab_write", "lab_run"),
     "words": r"код|python|питон|скрипт|график|программ|посчитай|рассчитай|вычисл|данны|csv|формул"},
]
SLIM_RECENT = 900                 # пачка, которой пользовались последние 15 минут, остаётся у модели («а теперь отправь ему»)

_BY_TOOL = {}
_PREFIXES = []
for _m in MODULES:
    for _t in _m.get("tools") or ():
        _BY_TOOL[_t] = _m
    for _p in _m.get("prefixes") or ():
        _PREFIXES.append((_p, _m))


_PACK_OF = {t: pk for pk in PACKS for t in pk["tools"]}


def pack_of(name):
    """Модуль или пачка инструмента (для подбора действий модели); ядро — None."""
    return of(name) or _PACK_OF.get(name)


def groups():
    """Модули и пачки со словами — всё, что можно подобрать к вопросу."""
    return [g for g in MODULES + PACKS if g.get("words")]


def wanted(text):
    """id модулей и пачек, к которым относится текст (по их словам)."""
    import re
    t = text or ""
    return {g["id"] for g in groups() if re.search(g["words"], t, re.I)}


def slim(specs, text="", keep=()):
    """Облегчённый набор действий для вопроса: ядро — всегда; модуль или пачка — когда про них вопрос (слова), ими недавно
    пользовались или модель попросила (keep — id). Модули без слов (музыка) — ядро. -> (ядро, {id группы: [действия]},
    [(id, title)] групп, что есть у человека, но в этот вопрос не вошли)."""
    want = wanted(text) | set(keep or ())
    core, extra, left = [], {}, {}
    for x in specs:
        g = pack_of(x.get("name", ""))
        if g is None or not g.get("words"):
            core.append(x)
        elif g["id"] in want:
            extra.setdefault(g["id"], []).append(x)
        else:
            left[g["id"]] = g["title"]
    return core, extra, sorted(left.items())


def of(name):
    """Модуль инструмента или None (ядро)."""
    m = _BY_TOOL.get(name)
    if m is None:
        for p, pm in _PREFIXES:
            if name.startswith(p):
                return pm
    return m


def by_id(mid):
    return next((m for m in MODULES if m["id"] == mid), None)


def feature_on(m, s):
    """Переключатель «Возможностей»: модуль без него — всегда включён."""
    f = m.get("feature")
    if not f:
        return True
    feats = (s.get("features") if s is not None else None) or {}
    v = feats.get(f[0])
    return f[1] if v is None else bool(v)


def ready(m, name, h, s):
    """Подключено ли нужное модулю (и этому инструменту)."""
    r = m.get("ready")
    if r is not None and not r(h, s):
        return False
    tr = (m.get("tool_ready") or {}).get(name)
    return tr is None or bool(tr(h, s))


class Fuse:
    """Предохранитель: считает настоящие сбои по ключу (id модуля или «mcp:<сервер>»), выключает на паузу, сам возвращает."""

    def __init__(self, now=time.monotonic):
        self.now, self.lock = now, threading.Lock()
        self.fails, self.until = {}, {}
        self.on_trip = None            # кладёт ядро: счётчик «чем пользуются»

    def tripped(self, key):
        with self.lock:
            u = self.until.get(key)
            if u is None:
                return False
            if self.now() >= u:        # пауза кончилась — пробуем снова, счёт с нуля
                self.until.pop(key, None)
                self.fails.pop(key, None)
                return False
            return True

    def ok(self, key):
        with self.lock:
            self.fails.pop(key, None)

    def fail(self, key):
        """Сбой; -> True, если предохранитель сработал сейчас."""
        t = self.now()
        with self.lock:
            f = [x for x in self.fails.get(key, []) if t - x < FUSE_WINDOW] + [t]
            self.fails[key] = f
            if len(f) < FUSE_FAILS:
                return False
            self.until[key], self.fails[key] = t + FUSE_PAUSE, []
        cb = self.on_trip
        if cb:
            try:
                cb(key)
            except Exception:  # noqa: BLE001 — счётчик не должен ронять вызов
                pass
        return True

    def paused(self):
        """Ключи на паузе сейчас (для подсказки модели)."""
        with self.lock:
            keys = list(self.until)
        return [k for k in keys if self.tripped(k)]


def title_of(key):
    """Подпись ключа предохранителя для человека."""
    if key.startswith("mcp:"):
        return f"«{key[4:]}»"
    m = by_id(key)
    return f"«{m['title']}»" if m else key
