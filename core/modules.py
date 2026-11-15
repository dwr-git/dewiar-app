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
    {"id": "mail", "title": "Почта", "tools": MAIL_TOOLS, "ready": _mail,
     "need": ("Сначала подключите почту — «Подключение» → «Почта»", "connect")},
    {"id": "telegram", "title": "Telegram и MAX", "tools": ("send_telegram",),
     "ready": lambda h, s: bool(h.get("telegram") and h["telegram"].paired()),
     "need": ("Сначала подключите Telegram или MAX — «Подключение»", "connect")},
    {"id": "posts", "title": "Посты в канал", "tools": ("channel_post",), "ready": _posts},
    {"id": "home", "title": "Умный дом", "tools": ("smart_home",),
     "ready": lambda h, s: bool(h.get("home") and h["home"].connected()),
     "need": ("Сначала подключите умный дом (Яндекс или Home Assistant) — «Подключение»", "connect")},
    {"id": "clients", "title": "Клиенты", "prefixes": ("client_",), "tools": ("deal_remind",), "feature": ("clients", False),
     "ready": lambda h, s: h.get("clients") is not None,
     "tool_ready": {"client_crm": lambda h, s: bool(h.get("crm") and h["crm"].connected())}},
    {"id": "sites", "title": "Сайты", "prefixes": ("site_",), "feature": ("sites", True),
     "ready": lambda h, s: h.get("sites") is not None},
    {"id": "team", "title": "Поручения", "tools": ("team_assign", "team_status", "team_message"), "feature": ("team", False),
     "ready": lambda h, s: bool(h.get("team") and h["team"].connected())},
    {"id": "servers", "title": "Серверы", "tools": ("server_run",),
     "ready": lambda h, s: bool(h.get("servers") and h["servers"].items),
     "need": ("Сначала добавьте сервер — «Серверы»", "servers")},
    {"id": "knowledge", "title": "Документы в «Знаниях»", "tools": ("search_documents",),
     "ready": lambda h, s: bool(h.get("knowledge") and h["knowledge"].has_files()),
     "need": ("Сначала добавьте документы в «Знания» — «Обо мне» → «Мои документы»", "me")},
    {"id": "account", "title": "Облачные знания", "tools": ("ask_knowledge",),
     "ready": lambda h, s: bool(h.get("account") and h["account"].logged_in()),
     "need": ("Нужен вход аккаунтом dewiar.pro — «Dewiar.pro»", "dw")},
    {"id": "maker", "title": "Плагин словами", "tools": ("plugin_create", "plugin_change"), "ready": _maker,
     "tool_ready": {"plugin_change": _maker_change}},
    # модули без условий подключения — в двери ради предохранителя и единого счёта (пилот 1.0)
    {"id": "podcast", "title": "Подкасты", "tools": ("make_podcast",)},
    {"id": "council", "title": "Совет ИИ", "tools": ("council", "debate")},
    {"id": "radar", "title": "Радар", "tools": ("insight_ask",)},
    {"id": "music", "title": "Музыка и радио", "tools": ("play_music", "play_radio", "play_youtube", "yandex_music")},
]

_BY_TOOL = {}
_PREFIXES = []
for _m in MODULES:
    for _t in _m.get("tools") or ():
        _BY_TOOL[_t] = _m
    for _p in _m.get("prefixes") or ():
        _PREFIXES.append((_p, _m))


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
