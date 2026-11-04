"""Плагины: навыки + MCP-серверы + свои настройки + примеры фраз + дела по расписанию — одним пакетом, одной кнопкой
(решение владельца 20.10: «скилы отдельно, mcp отдельно — красиво скомпоновать и приправить возможностями»).

Папка плагина:
    <id>/plugin.json        — {id, name, icon, color, category, tagline, description, version, author,
                               skills: [имена папок в skills/], phrases: [...], uses: [инструменты — для подписи],
                               settings: [{key, label, type: text|select|number|toggle|folder, options, default, placeholder}],
                               jobs: [{id, title, when, task}]  — дела по расписанию, включаются по желанию; {key} в task —
                                                                  значение настройки плагина,
                               mcp: {имя: {type: stdio|http, command, args, env, url, headers}} — необязательно,
                               ui: {tools: {инструмент: {title, hint, button, hidden, fields: {арг: подпись | false}}},
                                    labels: {ключ ответа: подпись}, asks: [{title, hint, say: "… {поле} …", fields}],
                                    folder: "Рисунки", page_title: подпись вкладки ui.html} — страница плагина в студии (необязательно),
                               data: ["notes" | "reminders" | "money" | "chat_stats" | "chat"] — что из данных Лиры странице можно
                                     попросить (dewiar.data; каждое — только после «Разрешить» человека, см. plugin_bridge.py),
                               theme: true — страница может перекрасить студию (dewiar.theme),
                               made: {by: "lira", code: bool} — плагин сделан по описанию словами (plugin_maker.py)}
    <id>/ui.html            — своя страница плагина (необязательно): студия показывает её во фрейме-песочнице с мостом
                               window.dewiar (только свои действия, настройки и файлы) — см. core/plugin_pages.py
    <id>/skills/<имя>/SKILL.md — обычные навыки (core/skills.py), видны модели, пока плагин установлен
    <id>/README.md          — для людей

Встроенные — DATA_DIR/plugins (каталог в студии сразу, без скачивания); свои — CONFIG_DIR/plugins (из zip).
Установлен ли и с какими настройками — settings.plugins.on = {id: {"at": unix, "values": {...}, "jobs": {jid: id напоминания}}}.
MCP-серверы плагина кладутся в settings.mcp.servers под именем «<id>-<имя>» с пометкой plugin (их видно и в списке MCP);
удаление плагина убирает и их. Чужой плагин запускает программы только через MCP-сервер, который человек видит и может
выключить, — а скрипты навыков, как и раньше, только через run_command с подтверждением."""

import io
import json
import logging
import re
import shutil
import time
import zipfile
from pathlib import Path

from settings import CONFIG_DIR, DATA_DIR, STATE_DIR

log = logging.getLogger("dewiar.plugins")
BUILTIN_DIR = DATA_DIR / "plugins"
USER_DIR = CONFIG_DIR / "plugins"
MAX_ZIP = 20 * 1024 * 1024
SET_TYPES = ("text", "select", "number", "toggle", "folder")   # folder — путь с кнопкой «Выбрать папку…» (№461)
# данные Лиры, которые странице плагина можно попросить (только с разрешения человека; core/plugin_bridge.py)
DATA_SCOPES = {"notes": "заметки", "reminders": "напоминания и дела", "money": "расходы и доходы",
               "chat_stats": "статистику разговоров — сколько, когда, с кем, о чём (без текста)", "chat": "текст переписки с Лирой"}


def data_dir(pid):
    """Папка данных сервера плагина (DEWIAR_PLUGIN_DATA): рядом с настройками, переживает переустановку."""
    return STATE_DIR / "plugins-data" / _id(pid)


class PluginError(Exception):
    pass


def _id(x):
    return re.sub(r"[^a-z0-9-]+", "-", str(x or "").lower()).strip("-")[:40]


def _txt(v, n):
    return " ".join(str(v or "").split())[:n]


def parse_ui(u):
    """Блок ui из plugin.json -> проверенный словарь (страница плагина в студии, 03.11: «у каждого плагина своя страничка»).
    tools — человеческие названия действий и их полей (иначе на странице сырые art_draw / query), hidden — действие только
    для помощницы (код svg, оценка по критериям); labels — подписи ключей ответа; asks — формы «попросить Лиру» для
    плагинов без своего кода: say с {поле} уходит в чат; folder — папка плагина в папке Dewiar («Рисунки»)."""
    u = u if isinstance(u, dict) else {}
    tools = {}
    for name, t in (u.get("tools") or {}).items() if isinstance(u.get("tools"), dict) else []:
        if not isinstance(t, dict) or not re.fullmatch(r"[\w.-]{1,64}", str(name)):
            continue
        fields = {}
        for k, v in (t.get("fields") or {}).items() if isinstance(t.get("fields"), dict) else []:
            if v is False:
                fields[str(k)[:64]] = False
            elif isinstance(v, dict):
                fields[str(k)[:64]] = {"label": _txt(v.get("label"), 80), "hint": _txt(v.get("hint"), 200),
                                       "placeholder": _txt(v.get("placeholder"), 120),
                                       "kind": v.get("kind") if v.get("kind") in ("long", "folder", "file", "path") else ""}
            elif v:
                fields[str(k)[:64]] = {"label": _txt(v, 80), "hint": "", "placeholder": "", "kind": ""}
        tools[str(name)] = {"title": _txt(t.get("title"), 60), "hint": _txt(t.get("hint"), 240), "button": _txt(t.get("button"), 30),
                            "hidden": bool(t.get("hidden")), "fields": fields}
    labels = {str(k)[:40]: _txt(v, 60) for k, v in (u.get("labels") or {}).items()} if isinstance(u.get("labels"), dict) else {}
    asks = []
    for a in (u.get("asks") or [])[:6] if isinstance(u.get("asks"), list) else []:
        if not isinstance(a, dict) or not a.get("title") or not a.get("say"):
            continue
        fl = {}
        for k, v in (a.get("fields") or {}).items() if isinstance(a.get("fields"), dict) else []:
            v = v if isinstance(v, dict) else {"label": v}
            fl[str(k)[:40]] = {"label": _txt(v.get("label") or k, 80), "placeholder": _txt(v.get("placeholder"), 120),
                               "kind": "long" if v.get("kind") == "long" else ""}
        asks.append({"title": _txt(a["title"], 60), "hint": _txt(a.get("hint"), 240), "say": str(a["say"])[:400],
                     "button": _txt(a.get("button"), 30), "fields": fl})
    folder = str(u.get("folder") or "")
    if ".." in folder or folder.startswith(("/", "\\")) or ":" in folder:
        folder = ""
    return {"tools": tools, "labels": labels, "asks": asks, "folder": folder[:60], "page_title": _txt(u.get("page_title"), 30)}


def parse_plugin(d: Path, builtin: bool):
    """plugin.json -> словарь плагина (проверенный и с безопасными значениями) или исключение PluginError."""
    try:
        m = json.loads((d / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PluginError(f"plugin.json не читается: {e}") from e
    if not isinstance(m, dict):
        raise PluginError("plugin.json — не объект")
    pid = _id(m.get("id") or d.name)
    if not pid or not str(m.get("name") or "").strip():
        raise PluginError("у плагина должны быть id и name")
    skills = []
    for s in m.get("skills") or []:
        sd = d / "skills" / str(s)
        if re.fullmatch(r"[\w.-]+", str(s)) and (sd / "SKILL.md").is_file():
            skills.append(sd)
    if not skills:                                   # skills не перечислены — все папки с SKILL.md
        skills = sorted(p.parent for p in (d / "skills").glob("*/SKILL.md")) if (d / "skills").is_dir() else []
    sets = []
    for s in m.get("settings") or []:
        if not isinstance(s, dict) or not _id(s.get("key")).replace("-", "_") or s.get("type", "text") not in SET_TYPES:
            continue
        sets.append({"key": re.sub(r"[^\w]", "_", str(s["key"]))[:40], "label": str(s.get("label") or s["key"])[:80],
                     "type": s.get("type", "text"), "options": [str(o)[:60] for o in (s.get("options") or [])][:12],
                     "default": s.get("default", ""), "placeholder": str(s.get("placeholder") or "")[:120],
                     "hint": str(s.get("hint") or "")[:200], "required": bool(s.get("required"))})
    jobs = [{"id": _id(j.get("id") or f"j{i}"), "title": str(j.get("title") or "")[:120], "when": str(j.get("when") or "")[:80],
             "task": str(j.get("task") or "")[:600]}
            for i, j in enumerate(m.get("jobs") or []) if isinstance(j, dict) and j.get("when") and j.get("task")]
    mcp = {}
    for n, c in (m.get("mcp") or {}).items() if isinstance(m.get("mcp"), dict) else []:
        if not isinstance(c, dict) or c.get("type", "stdio") not in ("stdio", "http"):
            continue
        cfg = {"type": c.get("type", "stdio")}
        if cfg["type"] == "http":
            if not re.match(r"^https?://", str(c.get("url") or "")):
                continue
            cfg["url"] = str(c["url"])
            if isinstance(c.get("headers"), dict):
                cfg["headers"] = {str(k): str(v) for k, v in c["headers"].items()}
        else:
            if not c.get("command"):
                continue
            cfg.update(command=str(c["command"]), args=[str(a) for a in c.get("args") or []],
                       env={str(k): str(v) for k, v in (c.get("env") or {}).items()})
        mcp[re.sub(r"[^\w-]+", "_", str(n))[:30]] = cfg
    return {"id": pid, "name": str(m["name"]).strip()[:60], "icon": str(m.get("icon") or "🧩")[:4],
            "color": m.get("color") if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(m.get("color") or "")) else "#8B8CF7",
            "category": str(m.get("category") or "Разное")[:30], "tagline": str(m.get("tagline") or "")[:160],
            "description": str(m.get("description") or "")[:1200], "version": str(m.get("version") or "1.0")[:20],
            "author": str(m.get("author") or "")[:60], "phrases": [str(x)[:120] for x in (m.get("phrases") or [])][:10],
            # слова, по которым просьба — к этому плагину («нарисуй кота» — «Художник», 03.11: «на локальной модели Лира
            # говорит, что не умеет рисовать и такого плагина у неё нет»)
            "words": [str(x)[:30] for x in (m.get("words") or [])][:24],
            "uses": [str(x)[:40] for x in (m.get("uses") or [])][:12], "settings": sets, "jobs": jobs, "mcp": mcp,
            "skill_dirs": skills, "dir": d, "builtin": builtin,
            # витрина на «Главной» (31.10): фраза «попробуйте сразу» и ролик — id урока Академии («15-plugins») или адрес
            "try": str(m.get("try") or (m.get("phrases") or [""])[0])[:120],
            # ссылки панели плагина на его файлы в папке Dewiar: [{"label": "Открыть галерею", "path": "Рисунки/Галерея.html"}]
            "links": [{"label": str(x.get("label"))[:40], "path": str(x.get("path"))[:120]} for x in (m.get("links") or [])
                      if isinstance(x, dict) and x.get("label") and x.get("path") and ".." not in str(x.get("path"))
                      and not str(x.get("path")).startswith(("/", "\\")) and ":" not in str(x.get("path"))][:3],
            "ui": parse_ui(m.get("ui")), "page": (d / "ui.html").is_file(),
            "data": [x for x in dict.fromkeys(str(s) for s in (m.get("data") or []) if isinstance(m.get("data"), list)) if x in DATA_SCOPES],
            "theme": m.get("theme") is True,
            # сделан Лирой по описанию (Creator, 03.11): только свой (не встроенный), код — только с согласия человека
            "made": bool(isinstance(m.get("made"), dict) and not builtin),
            "made_code": bool(isinstance(m.get("made"), dict) and m["made"].get("code") and not builtin),
            "made_from": str(m["made"].get("template") or "")[:40] if isinstance(m.get("made"), dict) else "",
            "video": str(m.get("video") or "") if re.fullmatch(r"[\w-]{1,40}|https://[^\s\"'<>]{8,300}", str(m.get("video") or "")) else ""}


# №507 (03.11): плагин «Луна» без поля words — на «Когда ближайшее полнолуние?» Лира отвечала по памяти и ошибалась:
# просьба не узнавалась (имя «Луна» — ни «луны», ни «полнолуния» в вопросе). Слова такого плагина выводим сами — из
# названия, подписи, описания и действий его MCP-сервера; сравниваем по началу слова (корню).
_AUTO_STOP = set("""ближайший ближайшие ближайшая сегодня завтра вчера текущий текущая дата даты время расчет рассчитать рассчитывает
показать показывает получить получает возвращает вернуть всегда вызывай вызывать вызов инструмент инструменты плагин плагина
ответ ответь отвечай вопрос вопросы данные данных информация список город города место места день дней дня месяц месяца
неделя недели года число числа точный точно точная параметр параметры формат указать указанный указанная нужно можно
пользователь пользователя человек человека помогает помощь подробно подробный кратко коротко через после перед который
которая которые если также только этот всего ваш свой своей обычно лучше любой любая какой какая когда сколько будет
работает использовать используй используется например описание описанию следующие следующий следующая период периода
начало конец дату дате времени часы часов минут результат результаты значение запрос запросу текст текста строка
интернет интернета алгоритм алгоритму календарь календаря последний последние последняя первый первая каждый каждая
mcp json server tool tools next from date days the and for with this that phase""".split())
# прилагательные и местоимения («первая», «вашего», «точный») — не тема плагина; существительные на -ние — тема
_ADJ = re.compile(r"(?:ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ых|их|ую|юю)$")
_NOUN_NIE = re.compile(r"(?:ние|тие|вие)$")
_ROOT_CUT = "аеиоуыэюяйь"


def _root(w):
    """Корень слова для сравнения по началу: без окончания-гласной, не длиннее 7 букв («Луна» → «лун», «полнолуние» →
    «полнолу», «фазы» → «фаз»)."""
    w = w.lower().replace("ё", "е")
    while len(w) > 3 and w[-1] in _ROOT_CUT:
        w = w[:-1]
    return w[:7]


def _roots(text, topic=False):
    """Корни слов текста; topic — только похожие на тему: без прилагательных и местоимений (кроме слов с корнем имени)."""
    ws = [w for w in re.findall(r"[a-zа-яё]+", str(text or "").lower().replace("ё", "е")) if len(w) >= 4]
    if topic:
        ws = [w for w in ws if not _ADJ.search(w) or _NOUN_NIE.search(w)]
    return {_root(w) for w in ws}


_AUTO_STOP_ROOTS = {_root(w) for w in _AUTO_STOP}


class Plugins:
    def __init__(self, settings):
        self.s = settings
        self.items = {}
        self.tool_texts = None        # () -> {id плагина: [тексты действий]} — подключённые MCP-серверы (engine.py)
        self._auto = {}
        self.user_dir = USER_DIR      # свои плагины (проверки с двумя компьютерами в одном процессе дают каждому свою)
        self.reload()

    def reload(self):
        items = {}
        for root, builtin in ((BUILTIN_DIR, True), (self.user_dir, False)):
            if not root.is_dir():
                continue
            for f in sorted(root.glob("*/plugin.json")):
                try:
                    p = parse_plugin(f.parent, builtin)
                except PluginError as e:
                    log.warning("плагин %s пропущен: %s", f.parent.name, e)
                    continue
                if not builtin and p["id"] in items and items[p["id"]]["builtin"]:
                    continue                         # свой не перекрывает встроенный с тем же id
                items[p["id"]] = p
        self.items = items

    # ---- состояние ----
    def _on(self):
        return dict(self.s.get("plugins", "on") or {})

    def installed(self):
        on = self._on()
        return [p for pid, p in self.items.items() if pid in on]

    def values(self, pid):
        p, on = self.items.get(pid), self._on().get(pid) or {}
        if not p:
            return {}
        v = dict(on.get("values") or {})
        return {s["key"]: v.get(s["key"], s["default"]) for s in p["settings"]}

    # ---- просьба к плагину (№461, №463, №483: «сейчас посмотрю» — и ни одного действия плагина) ----
    _STOP = {"сколько", "сейчас", "будет", "какой", "какая", "какие", "каким", "когда", "этот", "этой", "этом", "тебя", "меня",
             "мне", "есть", "всех", "всего", "нужно", "можно", "пожалуйста", "давай", "сделай", "покажи", "скажи", "через",
             "неделе", "неделю", "завтра", "сегодня", "лучше", "хорошо", "очень"}

    def auto_words(self, p):
        """№507: корни слов плагина без своего words — из названия, подписи, описания, примеров фраз и действий его
        MCP-сервера (название, подпись и первые фразы описания каждого). Общие слова («ближайший», «дата», «плагин») и
        слова, что есть в описаниях двух и больше других плагинов, не берём. -> {корень}."""
        if p.get("words"):
            return set()
        try:
            tt = [str(x) for x in ((self.tool_texts() if self.tool_texts else {}) or {}).get(p["id"]) or []]
        except Exception:  # noqa: BLE001
            tt = []
        key = (p["id"], p["name"], p["tagline"], p["description"][:200], tuple(tt))
        if self._auto.get(p["id"], (None,))[0] == key:
            return self._auto[p["id"]][1]
        name = _roots(p["name"])
        own = _roots(" ".join([p["name"], p["tagline"], p["description"][:600], " ".join(p["phrases"]), *[t[:300] for t in tt]]), topic=True)
        # прилагательные с корнем названия («лунный» у «Луны») — тоже тема
        own |= {r for r in _roots(" ".join([p["tagline"], *tt])) if any(r.startswith(n) for n in name if len(n) >= 3)}
        other = {}
        for q in self.items.values():
            if q["id"] != p["id"]:
                for r in _roots(" ".join([q["name"], q["tagline"], q["description"]])):
                    other[r] = other.get(r, 0) + 1
        out = {r for r in own if len(r) >= 3 and r not in _AUTO_STOP_ROOTS and r not in self._STOP and other.get(r, 0) < 2}
        out |= {r for r in name if r not in _AUTO_STOP_ROOTS}     # название — всегда
        self._auto[p["id"]] = (key, out)
        return out

    @classmethod
    def _stems(cls, text):
        words = re.findall(r"[a-zа-яё0-9]+", str(text or "").lower().replace("ё", "е"))
        return {w[:5] for w in words if len(w) >= 4 and w not in cls._STOP}

    def match(self, text):
        """Установленный плагин, к которому явно эта просьба -> его словарь или None. Признаки: имя плагина в просьбе
        («путешествие», «тендеры») или пример фразы из его карточки — не меньше двух общих слов и половины её слов
        («Разбери резюме в папке», «Кто лучше всех подходит на бухгалтера?» — кнопкой из карточки и «Попробуйте плагин»)."""
        q = self._stems(text)
        if not q:
            return None
        best, top = None, 0
        for p in self.installed():
            sc = 3 if q & self._stems(p["name"]) else 0
            if not sc and any((st := self._stems(w)) and st <= q for w in p.get("words") or []):   # все слова признака
                sc = 2
            for ph in p["phrases"]:
                s = self._stems(ph)
                n = len(q & s)
                if n >= 2 and n * 2 >= len(s):
                    sc = max(sc, n)
            if not sc and not p.get("words"):              # №507: свой плагин без words — по выведенным корням
                auto = self.auto_words(p)
                qw = [w for w in re.findall(r"[a-zа-яё]+", str(text or "").lower().replace("ё", "е")) if len(w) >= 3]
                hit = {r for r in auto if any(w.startswith(r) for w in qw)}
                if hit & _roots(p["name"]):
                    sc = 3
                elif hit:
                    sc = 1
            if sc > top:
                best, top = p, sc
        return best

    def hint_for(self, text, tools=None, status=None):
        """Справка к вопросу: просьба к плагину — какой навык прочитать и какие действия вызвать сразу, а не обещать.
        tools — {id плагина: [(имя действия для модели, название)]} (подключённые MCP-серверы плагина); status — {id
        плагина: текст ошибки сервера}. -> строка или ""."""
        p = self.match(text)
        if not p:
            return ""
        sk = ", ".join(d.name for d in p["skill_dirs"])
        out = f"Это просьба к плагину «{p['name']}»" + (f": сначала use_skill {sk} (как работать)" if sk else "")
        acts = (tools or {}).get(p["id"]) or []
        err = (status or {}).get(p["id"])
        if acts:
            # №507: «Когда ближайшее полнолуние?» — ответила по памяти, неверно. Подсказка — твёрдая: сначала действие
            out += (", затем его действия: " + "; ".join(f"{n} — «{t}»" if t else n for n, t in acts[:8])
                    + ". ОБЯЗАТЕЛЬНО вызови подходящее действие плагина сразу, в этом же ответе, и отвечай только по его "
                    "результату: даты, числа и факты по памяти не называй — они бывают неверны")
        elif p["mcp"] and err:
            out += (f". Действия плагина сейчас не работают ({str(err)[:160]}) — честно скажи это одной фразой и предложи "
                    "проверить плагин в студии («Плагины»)")
        elif p["mcp"]:
            out += ". Действия плагина ещё подключаются — если их нет в списке инструментов, скажи, что плагин запускается, и попроси повторить через минуту"
        else:
            out += " — и делай по нему сразу, в этом же ответе"
        return out + ". Не отвечай «сейчас посмотрю / собираю» без действия: человек ждёт результат."

    def skill_roots(self):
        """[(папка навыка, id плагина)] — для core/skills.py: навыки установленных плагинов."""
        return [(d, p["id"]) for p in self.installed() for d in p["skill_dirs"]]

    def note(self, pid):
        """Настройки плагина словами — к тексту его навыка (use_skill)."""
        p = self.items.get(pid)
        if not p:
            return ""
        vals = self.values(pid)
        parts = [f"{s['label']} — {('да' if vals.get(s['key']) else 'нет') if s['type'] == 'toggle' else vals.get(s['key'])}"
                 for s in p["settings"] if vals.get(s["key"]) not in ("", None) or s["type"] == "toggle"]
        return f"\n\nНастройки плагина «{p['name']}»: " + "; ".join(parts) + "." if parts else ""

    def catalog(self):
        on, out = self._on(), []
        arrived = dict(self.s.get("plugins", "arrived") or {})
        for pid, p in sorted(self.items.items(), key=lambda x: (not x[1]["builtin"], x[1]["category"], x[1]["name"])):
            st = on.get(pid) or {}
            out.append({k: p[k] for k in ("id", "name", "icon", "color", "category", "tagline", "description", "version", "author",
                                          "phrases", "uses", "settings", "builtin", "try", "video", "links", "ui", "page",
                                          "data", "theme", "made", "made_code", "made_from")}
                       | {"installed": pid in on, "values": self.values(pid), "skills": [d.name for d in p["skill_dirs"]],
                          "mcp": [f"{pid}-{n}" for n in p["mcp"]],
                          "jobs": [dict(j, on=bool((st.get("jobs") or {}).get(j["id"]))) for j in p["jobs"]],
                          # пришёл с другого компьютера со своей программой — включает человек (core/plugin_sync.py)
                          "arrived": arrived.get(pid) if pid not in on else None,
                          "readme": self._readme(p)})
        return out

    @staticmethod
    def _readme(p):
        try:
            return (p["dir"] / "README.md").read_text(encoding="utf-8")[:8000]
        except OSError:
            return ""

    @staticmethod
    def guide():
        """«Как сделать свой плагин» — для студии."""
        try:
            return (BUILTIN_DIR / "README.md").read_text(encoding="utf-8")
        except OSError:
            return ""

    # ---- установка ----
    def install(self, pid, values=None):
        p = self.items.get(pid)
        if not p:
            raise PluginError(f"нет плагина {pid}")
        on = self._on()
        cur = dict(on.get(pid) or {"at": int(time.time()), "values": {}, "jobs": {}})
        if values is not None:
            cur["values"] = self._clean(p, values)
        on[pid] = cur
        arrived = dict(self.s.get("plugins", "arrived") or {})
        if arrived.pop(pid, None) is not None:          # «Включить» плагин, пришедший с другого компьютера, — разрешение дано
            self.s.update({"plugins": {"arrived": None}})
            self.s.update({"plugins": {"arrived": arrived}})
        servers = dict(self.s.get("mcp", "servers") or {})
        for n, c in p["mcp"].items():
            servers.setdefault(f"{pid}-{n}", dict(c, plugin=pid, enabled=True))
        self.s.update({"plugins": {"on": on}, "mcp": {"servers": servers}})
        return cur

    def set_values(self, pid, values):
        p, on = self.items.get(pid), self._on()
        if not p or pid not in on:
            raise PluginError("плагин не установлен")
        on[pid] = dict(on[pid], values=self._clean(p, values))
        self.s.update({"plugins": {"on": on}})
        return self.values(pid)

    @staticmethod
    def _clean(p, values):
        out = {}
        for s in p["settings"]:
            v = (values or {}).get(s["key"])
            if v is None:
                continue
            if s["type"] == "toggle":
                out[s["key"]] = bool(v)
            elif s["type"] == "number":
                try:
                    out[s["key"]] = float(v) if "." in str(v) else int(v)
                except ValueError:
                    continue
            elif s["type"] == "select" and s["options"] and str(v) not in s["options"]:
                continue
            else:
                out[s["key"]] = " ".join(str(v).split())[:200]
        return out

    def remove(self, pid):
        """Удалить плагин: его навыки больше не видны модели, его MCP-серверы убираются. -> id дел, которые он завёл
        (снимать ли их — решает вызывающий: они в напоминаниях человека)."""
        on = self._on()
        st = on.pop(pid, None) or {}
        servers = {n: c for n, c in (self.s.get("mcp", "servers") or {}).items() if c.get("plugin") != pid}
        # mcp.servers и plugins.on заменяем целиком (как студия): _merge не умеет удалять ключи
        self.s.update({"plugins": {"on": None}, "mcp": {"servers": None}})
        self.s.update({"plugins": {"on": on}, "mcp": {"servers": servers}})
        return [x for x in (st.get("jobs") or {}).values() if x]

    def job_text(self, pid, jid):
        p = self.items.get(pid)
        j = next((x for x in (p or {}).get("jobs") or [] if x["id"] == jid), None)
        if not j:
            raise PluginError("нет такого дела у плагина")
        vals = self.values(pid)
        task = re.sub(r"\{(\w+)\}", lambda m: str(vals.get(m.group(1)) or "…"), j["task"])
        return task, j["when"]

    def job_mark(self, pid, jid, rid):
        on = self._on()
        if pid not in on:
            raise PluginError("плагин не установлен")
        jobs = dict(on[pid].get("jobs") or {})
        jobs[jid] = rid
        on[pid] = dict(on[pid], jobs=jobs)
        self.s.update({"plugins": {"on": None}})
        self.s.update({"plugins": {"on": on}})

    # ---- свои плагины (zip) ----
    def install_zip(self, data: bytes):
        """Плагин из zip -> id. Папка с самым верхним plugin.json; пути с .. и абсолютные отвергаются; распаковка во
        временную папку и проверка до замены прежней версии. Встроенный плагин своим не перекрыть."""
        if len(data) > MAX_ZIP:
            raise PluginError("архив плагина больше 20 МБ")
        try:
            z = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise PluginError("это не zip-архив") from e
        names = [n for n in z.namelist() if not n.endswith("/")]
        top = sorted((n for n in names if n.split("/")[-1] == "plugin.json"), key=lambda n: n.count("/"))
        if not top:
            raise PluginError("в архиве нет plugin.json")
        prefix = top[0][:-len("plugin.json")]
        self.user_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.user_dir / ".new"
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            for n in names:
                if not n.startswith(prefix):
                    continue
                rel = Path(n[len(prefix):])
                if rel.is_absolute() or ".." in rel.parts or n.startswith("/"):
                    raise PluginError("в архиве опасные пути")
                out = tmp / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(n))
            p = parse_plugin(tmp, False)
            if p["id"] in self.items and self.items[p["id"]]["builtin"]:
                raise PluginError(f"«{p['id']}» — имя встроенного плагина, выберите другое id")
            target = self.user_dir / p["id"]
            shutil.rmtree(target, ignore_errors=True)
            tmp.rename(target)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.reload()
        return p["id"]

    def delete(self, pid):
        p = self.items.get(pid)
        if not p or p["builtin"]:
            raise PluginError("встроенный плагин можно только удалить из установленных")
        self.remove(pid)
        shutil.rmtree(p["dir"], ignore_errors=True)
        self.reload()
