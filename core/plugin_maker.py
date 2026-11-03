"""Лира делает плагин по описанию словами (Creator, 03.11 — владелец увидел «Creator Mode» у DeepSeek: «человек описывает
идею, агент пишет плагин и встраивает в интерфейс»).

«Сделай плагин, который показывает статистику наших разговоров» → текущая модель пишет plugin.json (название, значок,
описание, words, data), ui.html (самодостаточная страница в стиле студии) и при нужде skill.md → проверка → плагин в
пользовательской папке плагинов (plugins.USER_DIR), установлен, сразу в меню «Плагины» и открыт.

  • Ответ модели — разделами «=== plugin.json ===», «=== ui.html ===», «=== skill.md ===» (HTML внутри JSON модели
    ломают кавычками). check() — отбраковка: JSON, непустая страница, никаких внешних скриптов, кроме CDN_OK с точной
    версией, никаких fetch/XMLHttpRequest/WebSocket, внешних картинок, стилей и ссылок, localStorage, alert, форм наружу.
    Не прошло — одна повторная попытка с перечнем ошибок, потом понятная ошибка человеку.
  • Код (MCP-сервер server.py) — только если человек явно разрешил (code=True: в чате — вопрос «Выполнить?» с
    объяснением, в студии — переключатель и вопрос). Без разрешения код и блок mcp выбрасываются, а при правке словами
    код прежней версии остаётся как был.
  • Версии: <папка плагина>/.versions/<n>/ — копия файлов, .versions/index.json — [{v, at, label, to?, code}], KEEP
    последних. Правка словами — новая версия; «верни как было» (undo) — назад по шагам: запись-откат хранит to.
  • Шаблоны (data/plugin_templates/<id>) — готовые плагины одним нажатием: «Статистика разговоров», «Читалка статей»,
    «Тема оформления» — без модели, дальше их можно править словами так же."""

import json
import logging
import re
import shutil
import time
from pathlib import Path

import plugins as PL
from settings import DATA_DIR

log = logging.getLogger("dewiar.maker")
TEMPLATES_DIR = DATA_DIR / "plugin_templates"
KEEP = 10
MAX_HTML = 400_000
CDN_OK = ("https://cdn.jsdelivr.net/npm/", "https://cdnjs.cloudflare.com/ajax/libs/")
FILES = ("plugin.json", "ui.html", "skill.md", "server.py")
UNDO_RX = re.compile(r"верн\w*\s+(?:как\s+было|назад|обратно|прежн|предыдущ)|отмени\w*\s+(?:последн|изменени|правк|это)|"
                     r"откат\w*|(?:прежн|предыдущ)\w+\s+верси", re.I)

SERVER_SKELETON = r'''import json, os, sys
from pathlib import Path
DATA = Path(os.environ.get("DEWIAR_PLUGIN_DATA") or ".")          # своя папка данных

def hello(args):                                                   # действие: args — словарь из inputSchema
    return {"text": "Привет, " + str(args.get("name") or "мир")}

TOOLS = {   # имя: (описание для Лиры, inputSchema, функция, только_читает)
    "myplug_hello": ("Поздороваться", {"type": "object", "properties": {"name": {"type": "string"}}}, hello, True),
}

def main():
    for line in sys.stdin:
        try:
            m = json.loads(line)
        except ValueError:
            continue
        rid, meth = m.get("id"), m.get("method")
        if meth == "initialize":
            res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "myplug", "version": "1"}}
        elif meth == "tools/list":
            res = {"tools": [{"name": n, "description": d, "inputSchema": s, "annotations": {"readOnlyHint": ro}}
                             for n, (d, s, f, ro) in TOOLS.items()]}
        elif meth == "tools/call":
            n = (m.get("params") or {}).get("name"); a = (m.get("params") or {}).get("arguments") or {}
            try:
                out = TOOLS[n][2](a); res = {"content": [{"type": "text", "text": json.dumps(out, ensure_ascii=False)}]}
            except Exception as e:
                res = {"content": [{"type": "text", "text": str(e)}], "isError": True}
        else:
            if rid is None:
                continue
            res = {}
        if rid is not None:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": res}, ensure_ascii=False) + "\n"); sys.stdout.flush()

if __name__ == "__main__":
    main()
'''

EXAMPLE = r'''=== plugin.json ===
{"id": "water-tracker", "name": "Вода за день", "icon": "💧", "color": "#4FC3F7", "category": "Здоровье",
 "tagline": "Стаканы воды за день и за неделю", "description": "Отмечайте стаканы одним нажатием — видно, сколько выпито сегодня и за неделю.",
 "phrases": ["Открой «Воду за день»"], "words": ["вода", "стаканы"], "data": [], "ui": {"page_title": "Сегодня"}}
=== ui.html ===
<!doctype html><html lang="ru"><head><meta charset="utf-8"><style>
.wrap{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.big{font:700 56px/1 inherit;letter-spacing:-.02em}.cups{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.cup{width:34px;height:44px;border-radius:8px 8px 12px 12px;background:var(--field);box-shadow:inset 0 0 0 1px var(--line)}
.cup.on{background:linear-gradient(180deg,color-mix(in srgb,var(--accent) 55%,transparent),var(--accent))}
.week{display:flex;align-items:flex-end;gap:8px;height:120px}.bar{flex:1;border-radius:6px 6px 2px 2px;background:var(--accent);min-height:3px}
.lbl{display:flex;gap:8px}.lbl span{flex:1;text-align:center;font-size:12px;color:var(--muted)}
</style></head><body>
<div class="wrap">
  <section class="card"><h2>Сегодня</h2><div class="big" id="n">0</div><p class="muted">стаканов из <b id="goal">8</b></p>
    <div class="cups" id="cups"></div><button class="btn primary" id="add">+ Стакан</button> <button class="btn ghost" id="undo">Убрать</button></section>
  <section class="card"><h2>Неделя</h2><div class="week" id="week" role="img" aria-label="Стаканы по дням"></div><div class="lbl" id="wl"></div></section>
</div>
<script>
const day = () => new Date().toISOString().slice(0, 10);
let log = {};
async function load() { log = (await dewiar.store.get("log")) || {}; draw(); }
async function save() { await dewiar.store.set("log", log); draw(); }
function draw() {
  const n = log[day()] || 0; document.getElementById("n").textContent = n;
  document.getElementById("cups").innerHTML = Array.from({ length: 8 }, (_, i) => `<i class="cup ${i < n ? "on" : ""}"></i>`).join("");
  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - 6 + i); return d; });
  const max = Math.max(8, ...days.map(d => log[d.toISOString().slice(0, 10)] || 0));
  document.getElementById("week").innerHTML = days.map(d => { const v = log[d.toISOString().slice(0, 10)] || 0;
    return `<div class="bar" style="height:${Math.max(2, v / max * 100)}%" title="${v} ст."></div>`; }).join("");
  document.getElementById("wl").innerHTML = days.map(d => `<span>${d.toLocaleDateString("ru-RU", { weekday: "short" })}</span>`).join("");
}
document.getElementById("add").onclick = () => { log[day()] = (log[day()] || 0) + 1; save(); dewiar.toast("Записала стакан"); };
document.getElementById("undo").onclick = () => { log[day()] = Math.max(0, (log[day()] || 0) - 1); save(); };
load().catch(e => dewiar.toast(e.message));
</script></body></html>'''

SYSTEM = """Ты — опытный дизайнер и фронтенд-разработчик Dewiar. По описанию человека ты делаешь ПЛАГИН — маленькую
страницу, которая живёт внутри студии Dewiar (программа голосового ассистента Лиры) в меню «Плагины».

ФОРМАТ ОТВЕТА — только разделы, без пояснений до и после:
=== plugin.json ===
{JSON}
=== ui.html ===
<!doctype html>… целая страница …
=== skill.md ===   ← необязательно: если Лире в разговоре нужно знать, как помогать с этим плагином (3–8 строк)
{SERVER_PART}
plugin.json: id (латиница, цифры, дефис; по смыслу), name (по-русски, 1–3 слова), icon (ОДИН эмодзи), color (#RRGGBB),
category («Дом», «Работа», «Здоровье», «Учёба», «Развлечения», «Оформление», «Разное»), tagline (одна строка), description
(2–3 предложения для человека), phrases (2–4 фразы, которые можно сказать Лире), words (2–6 слов, по которым просьба — к
плагину), data (список — только если странице нужны данные Лиры: "notes", "reminders", "money", "chat_stats", "chat"),
theme (true — только для плагина, который меняет оформление студии), ui: {"page_title": подпись вкладки, 1–2 слова}.

СТРАНИЦА ui.html — во фрейме-песочнице: НЕТ сети, НЕТ доступа к студии. Всё — внутри файла (CSS в <style>, JS в <script>).
Можно и нужно — мост window.dewiar (всё возвращает Promise, оборачивай в try/catch и показывай ошибку словами):
  dewiar.store.get(ключ) / dewiar.store.set(ключ, значение) — своё хранилище (JSON, до 500 КБ) — вместо localStorage;
  dewiar.data(область) — данные Лиры (только области из plugin.json → data; человек сам разрешит):
    "chat_stats" → {days:[{date,you,lira}] (60 дней), hours:[24 числа], weekdays:[7 чисел, пн=0], personas:[{name,count}],
                   topics:[{word,count}], total:{you,lira,messenger}, active_days, streak, since};
    "chat" → {items:[{at,role:"you"|"lira",who,text}]}; "notes" → {items:[{title,folder,at,text}]};
    "reminders" → {items:[{id,at,text,repeat,kind}]}; "money" → {items:[{date,amount,currency,category,note,kind}]};
    человек может отказать — тогда покажи понятную карточку «Нужен доступ…» с кнопкой, которая снова вызывает dewiar.data;
  dewiar.ask(фраза) — отправить Лире в чат (по нажатию кнопки; Лира ответит в «Чате»);
  dewiar.readUrl(адрес) → {url,title,text} — текст статьи по ссылке (по нажатию);
  dewiar.openUrl(адрес) — открыть сайт в браузере (вместо <a href>);
  dewiar.theme({"--accent": "#…", "--brand": "linear-gradient(…)", "--scene": "…", "--ink": "#…", "--muted": "…",
               "--panel": "…", "--field": "…", "--line": "…", "mode": "dark"|"light"}) — перекрасить студию (только с theme:true);
               dewiar.theme(null) — вернуть как было;
  dewiar.toast(текст) — короткое сообщение (alert/confirm/prompt в песочнице НЕ работают);
  dewiar.plugin → {id,name,icon,color}.
{RUN_PART}
НЕЛЬЗЯ: fetch, XMLHttpRequest, WebSocket, внешние картинки, шрифты и стили, <link>, <a href="http…">, <form action>,
localStorage/sessionStorage/cookie, parent/top. Внешний <script src> — только при крайней нужде и только
https://cdn.jsdelivr.net/npm/<пакет>@<точная версия>/… — лучше рисуй графики сам: inline SVG или canvas.

ДИЗАЙН — уровень дизайн-студии. Фон страницы прозрачный (под ней фон студии). Цвета — только переменные студии, тогда
страница сама подходит к тёмной и светлой теме: var(--ink) текст, var(--muted) и var(--dim) второстепенное, var(--panel)
и var(--panel2) карточки, var(--field) поля, var(--line) линии, var(--accent) акцент, var(--brand) градиент кнопки,
var(--good) / var(--bad) хорошо / плохо; смешивай через color-mix(in srgb, var(--accent) 30%, transparent). Готовые классы:
.card (карточка), .btn, .btn.primary, .btn.ghost, .btn.small, .chip, .chip.on, .pill, .hint, .muted, .spin (крутилка), table.
Сетка — grid с repeat(auto-fit, minmax(260px, 1fr)): страница должна хорошо смотреться от 360 до 1200 px шириной.
Крупные цифры, воздух, скругления 14–20 px, мягкие переходы; пустое состояние и загрузка — красиво и по-человечески.
Тексты — по-русски, просто, без канцелярита. Графики: тонкие столбцы со скруглением сверху, подписи осей приглушённые,
у столбца — подсказка title с числом; рядом — короткий вывод словами («Чаще всего — по вечерам»).

ПРИМЕР (стиль и устройство, не копируй содержание):
""" + EXAMPLE

RUN_NO = ("dewiar.run, settings, saveSettings — НЕ используй: у этого плагина нет своей программы, только страница.")
RUN_YES = ("Человек РАЗРЕШИЛ плагину свою программу на компьютере: можно добавить раздел «=== server.py ===» — MCP-сервер на "
           "Python без сторонних библиотек по заготовке ниже (действия — в TOOLS, имена с приставкой плагина). Страница "
           "вызывает их через dewiar.run(имя, аргументы) → {ok, error, data, text}. Не трогай файлы вне DEWIAR_PLUGIN_DATA, "
           "ничего не удаляй и не отправляй в интернет без явной просьбы человека. Заготовка:\n```python\n"
           + SERVER_SKELETON + "```")


class MakerError(Exception):
    pass


# ---------- разбор ответа модели ----------
def _unfence(t):
    t = str(t or "").strip()
    m = re.match(r"^```[\w.-]*\s*\n(.*?)\n?```\s*$", t, re.S)
    return m.group(1).strip() if m else t


def parse_reply(text):
    """Ответ модели -> {имя файла: текст}. Разделы «=== имя ===» (допускаются ##, **, ``` вокруг)."""
    out, cur, buf = {}, None, []
    for line in str(text or "").replace("\r", "").split("\n"):
        m = re.match(r"^\s*(?:#+\s*|\*\*)?={2,}\s*([\w.-]+\.(?:json|html|md|py))\s*={2,}(?:\*\*)?\s*$", line, re.I)
        if m:
            if cur:
                out[cur] = _unfence("\n".join(buf))
            cur, buf = m.group(1).lower(), []
            continue
        if cur:
            buf.append(line)
    if cur:
        out[cur] = _unfence("\n".join(buf))
    if not out:                                              # одним JSON {"plugin.json": {...}, "ui.html": "..."}
        try:
            d = json.loads(_unfence(text))
            if isinstance(d, dict) and "ui.html" in d:
                out = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v)) for k, v in d.items()}
        except ValueError:
            pass
    return {k: v for k, v in out.items() if k in FILES}


_TR = dict(zip("абвгдеёзийклмнопрстуфхцы", "abvgdeeziyklmnoprstufhcy")) | {"ж": "zh", "ч": "ch", "ш": "sh", "щ": "sch", "ю": "yu", "я": "ya", "э": "e", "ъ": "", "ь": ""}


def slug(name):
    t = "".join(_TR.get(c, c) for c in str(name or "").lower())
    return PL._id(t)[:32].strip("-") or "my-plugin"


def _json_obj(raw):
    raw = _unfence(raw)
    try:
        return json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            return json.loads(m.group(0))
        raise


BAD = [
    (re.compile(r"\bfetch\s*\(", re.I), "fetch — сети на странице нет (статья по ссылке — dewiar.readUrl)"),
    (re.compile(r"XMLHttpRequest|new\s+WebSocket|EventSource|sendBeacon|importScripts|new\s+Worker\s*\(", re.I), "сетевые запросы — сети на странице нет"),
    (re.compile(r"\b(?:localStorage|sessionStorage|indexedDB)\b|document\.cookie"), "localStorage/cookie — в песочнице их нет, нужен dewiar.store"),
    (re.compile(r"<link\b[^>]*\bhref\s*=\s*[\"']?(?:https?:)?//", re.I), "внешние стили или шрифты (<link>) — всё внутри файла"),
    (re.compile(r"@import\b", re.I), "@import — всё внутри файла"),
    (re.compile(r"url\(\s*[\"']?(?:https?:)?//", re.I), "картинка или шрифт по внешнему адресу — url(http…)"),
    (re.compile(r"<(?:img|iframe|audio|video|source|embed|object|track)\b[^>]*\bsrc\s*=\s*[\"']?(?:https?:)?//", re.I), "внешняя картинка или видео — только свои (SVG, data:)"),
    (re.compile(r"\bhref\s*=\s*[\"']?(?:https?:)?//", re.I), "ссылка <a href=\"http…\"> — открывай сайты через dewiar.openUrl"),
    (re.compile(r"<form\b[^>]*\baction\s*=", re.I), "форма с отправкой наружу"),
    (re.compile(r"<base\b|http-equiv\s*=\s*[\"']?refresh", re.I), "<base> и обновление страницы"),
    (re.compile(r"(?<![\w.$])(?:window\.)?(?:alert|confirm|prompt)\s*\(", re.I), "alert/confirm/prompt не работают в песочнице — dewiar.toast"),
    (re.compile(r"\b(?:window\.)?(?:top|parent)\.(?:document|location|postMessage)|window\.opener"), "обращение к студии (parent/top)"),
]


def check(files, code=False, pid=""):
    """Файлы от модели -> (files проверенные и поправленные, manifest, проблемы [строки]). Проблемы — повод для повтора."""
    probs = []
    f = dict(files or {})
    man = None
    try:
        man = _json_obj(f.get("plugin.json") or "")
        if not isinstance(man, dict):
            raise ValueError("не объект")
    except ValueError as e:
        probs.append(f"plugin.json — не JSON-объект ({str(e)[:80]})")
        man = None
    html = str(f.get("ui.html") or "").strip()
    if len(html) < 200 or not re.search(r"<(?:body|div|section|main|script|style)\b", html, re.I):
        probs.append("ui.html пустой или это не страница — нужна целая страница с разметкой, стилями и скриптом")
    elif len(html) > MAX_HTML:
        probs.append("ui.html слишком большой (больше 400 КБ)")
    else:
        for rx, why in BAD:
            if rx.search(html):
                probs.append(why)
        for src in re.findall(r"<script\b[^>]*\bsrc\s*=\s*[\"']?([^\"'\s>]+)", html, re.I):
            if not (src.startswith(CDN_OK) and re.search(r"@\d+(\.\d+)*/", src)):
                probs.append(f"внешний скрипт {src[:80]} — можно только с cdn.jsdelivr.net/npm или cdnjs с точной версией, лучше без него")
        if "var(--" not in html:
            probs.append("цвета не из студии — используй var(--ink), var(--panel), var(--accent)…, иначе страница не подходит к теме")
    if man is not None:
        name = " ".join(str(man.get("name") or "").split())[:40]
        if not name:
            probs.append("в plugin.json нет name")
        man["name"] = name
        man["id"] = pid or slug(man.get("id") or name)
        ic = str(man.get("icon") or "").strip()
        man["icon"] = ic[:4] if ic else "🧩"
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(man.get("color") or "")):
            man["color"] = "#8B8CF7"
        for k, n in (("phrases", 5), ("words", 8)):
            man[k] = [str(x)[:120] for x in (man.get(k) or []) if isinstance(x, (str, int))][:n] if isinstance(man.get(k), list) else []
        used = set(re.findall(r"dewiar\.data\(\s*[\"'](\w+)[\"']", html))
        data = [x for x in (man.get("data") or []) if x in PL.DATA_SCOPES] if isinstance(man.get("data"), list) else []
        for u in used:
            if u in PL.DATA_SCOPES and u not in data:
                data.append(u)                               # страница просит — объявим, человек всё равно разрешит сам
            elif u not in PL.DATA_SCOPES:
                probs.append(f"dewiar.data(\"{u}\") — таких данных нет; есть notes, reminders, money, chat_stats, chat")
        man["data"] = data
        man["theme"] = bool(man.get("theme")) or "dewiar.theme(" in html
        ui = man.get("ui") if isinstance(man.get("ui"), dict) else {}
        man["ui"] = {k: v for k, v in ui.items() if k in ("page_title", "labels", "asks", "tools")}
        for k in ("links", "video", "skills"):
            man.pop(k, None)
        man["version"] = str(man.get("version") or "1.0")[:20]
        man["author"] = "Лира"
        tpl = (man.get("made") or {}).get("template") if isinstance(man.get("made"), dict) else ""
        man["made"] = {"by": "lira", "code": bool(code)} | ({"template": str(tpl)[:40]} if tpl else {})
        if code:
            srv = str(f.get("server.py") or "").strip()
            if srv:
                try:
                    compile(srv, "server.py", "exec")
                except SyntaxError as e:
                    probs.append(f"server.py — ошибка в коде Python: {e.msg} (строка {e.lineno})")
                if "tools/list" not in srv:
                    probs.append("server.py — не MCP-сервер (нет tools/list); бери заготовку")
                man["mcp"] = {"main": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"]}}
            else:
                man.pop("mcp", None)
                f.pop("server.py", None)
        else:
            man.pop("mcp", None)
            f.pop("server.py", None)
            if re.search(r"dewiar\.(?:run|saveSettings)\s*\(", html):
                probs.append("dewiar.run — у плагина нет своей программы; храни в dewiar.store, данные — dewiar.data, просьбы — dewiar.ask")
        f["plugin.json"] = json.dumps(man, ensure_ascii=False, indent=1)
    sk = str(f.get("skill.md") or "").strip()
    if sk and man is not None:
        if not sk.startswith("---"):
            desc = (man.get("tagline") or man.get("name") or "")[:200].replace("\n", " ")
            sk = f"---\nname: {man['id']}\ndescription: Плагин «{man['name']}»: {desc}\n---\n" + sk
        f["skill.md"] = sk[:20000]
    else:
        f.pop("skill.md", None)
    f["ui.html"] = html
    return f, man, probs


def human_problems(probs):
    return "; ".join(dict.fromkeys(probs))[:400]


class Maker:
    def __init__(self, P, host=None, llm=None):
        self.P, self.host, self._llm = P, host, llm

    # ---------- модель ----------
    def llm(self, system, user):
        if self._llm:
            return self._llm(system, user)
        from llm import stream_chat
        h = self.host
        prof = h.s.active_llm() if h is not None else None
        if not (prof or {}).get("base_url") and (prof or {}).get("kind") != "ollama":
            raise MakerError("нет модели — выберите её в «Мозге»")
        return "".join(stream_chat(dict(prof, max_tokens=14000, temperature=0.35), system, [{"role": "user", "content": user}]))

    def _system(self, code):
        return (SYSTEM.replace("{SERVER_PART}", "=== server.py ===   ← только если нужна своя программа (см. ниже)" if code else "")
                .replace("{RUN_PART}", RUN_YES if code else RUN_NO))

    def generate(self, user, code=False, pid="", keep=None):
        """Попросить модель; не прошла проверку — одна повторная попытка с перечнем ошибок. -> (files, manifest)."""
        system = self._system(code)
        probs, raw = [], ""
        for attempt in (1, 2):
            ask = user if attempt == 1 else (user + "\n\nПРОШЛЫЙ ОТВЕТ НЕ ПОДОШЁЛ: " + "; ".join(probs) +
                                             ".\nИсправь это и пришли разделы целиком заново.\n\nПрошлый ответ:\n" + raw[:30000])
            try:
                raw = self.llm(system, ask)
            except MakerError:
                raise
            except Exception as e:  # noqa: BLE001
                raise MakerError(f"модель не ответила: {str(e)[:200]}") from e
            files = parse_reply(raw)
            for k, v in (keep or {}).items():               # правка: раздел не прислан — остаётся прежний
                files.setdefault(k, v)
            files, man, probs = check(files, code, pid)
            if not probs:
                return files, man
            log.info("плагин: попытка %d не прошла проверку: %s", attempt, probs)
        raise MakerError("не получилось собрать плагин: модель дважды прислала то, что нельзя ставить (" + human_problems(probs) +
                         "). Попробуйте описать проще или выберите модель посильнее в «Мозге».")

    # ---------- папки и версии ----------
    def _dir(self, pid):
        return PL.USER_DIR / pid

    def _free_id(self, pid):
        base, n = pid, 2
        while pid in self.P.items or self._dir(pid).exists():
            pid = f"{base}-{n}"
            n += 1
        return pid

    def _vdir(self, pid):
        return self._dir(pid) / ".versions"

    def _index(self, pid):
        try:
            d = json.loads((self._vdir(pid) / "index.json").read_text(encoding="utf-8"))
            return d if isinstance(d, list) else []
        except (OSError, ValueError):
            return []

    def _save_index(self, pid, idx):
        p = self._vdir(pid) / "index.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")

    def _current(self, pid):
        """Файлы плагина сейчас -> {plugin.json, ui.html, skill.md?, server.py?}."""
        d, out = self._dir(pid), {}
        for name, rel in (("plugin.json", "plugin.json"), ("ui.html", "ui.html"), ("server.py", "server.py"), ("skill.md", f"skills/{pid}/SKILL.md")):
            try:
                out[name] = (d / rel).read_text(encoding="utf-8")
            except OSError:
                pass
        return out

    def _write(self, pid, files, label, to=None):
        """Файлы -> папка плагина + новая версия. -> номер версии."""
        d = self._dir(pid)
        d.mkdir(parents=True, exist_ok=True)
        for name, rel in (("plugin.json", "plugin.json"), ("ui.html", "ui.html"), ("server.py", "server.py"), ("skill.md", f"skills/{pid}/SKILL.md")):
            p = d / rel
            if name in files and files[name]:
                p.parent.mkdir(parents=True, exist_ok=True)
                tmp = p.with_name(p.name + ".tmp")
                tmp.write_text(files[name], encoding="utf-8")
                tmp.replace(p)
            elif p.exists():
                p.unlink()
        if not files.get("skill.md"):
            shutil.rmtree(d / "skills", ignore_errors=True)
        idx = self._index(pid)
        v = (max((x["v"] for x in idx), default=0)) + 1
        vd = self._vdir(pid) / str(v)
        vd.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            if files.get(name):
                (vd / name).write_text(files[name], encoding="utf-8")
        man = json.loads(files["plugin.json"])
        e = {"v": v, "at": int(time.time()), "label": str(label or "")[:160], "code": bool(files.get("server.py")), "name": man.get("name")}
        if to is not None:
            e["to"] = to
        idx.append(e)
        while len(idx) > KEEP:
            old = idx.pop(0)
            shutil.rmtree(self._vdir(pid) / str(old["v"]), ignore_errors=True)
        self._save_index(pid, idx)
        return v

    def versions(self, pid):
        idx = self._index(pid)
        cur = idx[-1]["v"] if idx else 0
        return {"items": [dict(x, current=x["v"] == cur) for x in reversed(idx)], "current": cur, "keep": KEEP}

    def _made(self, pid):
        p = self.P.items.get(pid)
        if not p or p["builtin"] or not p.get("made"):
            raise MakerError("этот плагин сделан не Лирой — его можно только настроить" if p else "нет такого плагина")
        return p

    # ---------- создать, изменить, вернуть ----------
    def create(self, describe, code=False, name=""):
        describe = " ".join(str(describe or "").split())
        if len(describe) < 6:
            raise MakerError("опишите словами, что должен делать плагин: что на странице и зачем")
        user = (f"Сделай плагин. Описание человека: «{describe[:3000]}»" + (f". Название: «{name}»" if name else "") +
                ". Пришли разделы plugin.json и ui.html (и skill.md, если нужно).")
        files, man = self.generate(user, code=code)
        return self._install_new(files, man, "Сделала по описанию: " + describe[:120])

    def _install_new(self, files, man, label):
        pid = self._free_id(man["id"])
        if pid != man["id"]:
            man["id"] = pid
            files["plugin.json"] = json.dumps(man, ensure_ascii=False, indent=1)
            if files.get("skill.md"):
                files["skill.md"] = re.sub(r"(?m)^name:.*$", f"name: {pid}", files["skill.md"], count=1)
        try:
            self._write(pid, files, label)
            self.P.reload()
            if pid not in self.P.items:
                raise MakerError("плагин не прочитался после записи")
            self.P.install(pid, {})
        except Exception:
            shutil.rmtree(self._dir(pid), ignore_errors=True)
            self.P.reload()
            raise
        return self.info(pid)

    def change(self, pid, request, code=False):
        p = self._made(pid)
        request = " ".join(str(request or "").split())
        if not request or UNDO_RX.search(request):
            return self.undo(pid)
        cur = self._current(pid)
        allow = bool(code)
        keep = {}
        if not allow and cur.get("server.py"):
            keep_code = cur["server.py"]                      # код — только с согласия; без него остаётся прежний
        else:
            keep_code = None
        parts = [f"=== {k} ===\n{v}" for k, v in cur.items() if k != "server.py" or allow]
        user = (f"Вот плагин «{p['name']}». Человек просит изменить: «{request[:2000]}».\nСделай это, сохрани всё остальное, "
                "что работало, и дизайн. Пришли ИЗМЕНЁННЫЕ разделы целиком (неизменённые можно не присылать).\n\n" + "\n".join(parts))
        for k in ("plugin.json", "ui.html", "skill.md"):
            if cur.get(k):
                keep[k] = cur[k]
        files, man = self.generate(user, code=allow or bool(keep_code), pid=pid, keep=keep)
        if keep_code is not None:
            files["server.py"] = keep_code
            man["mcp"] = json.loads(cur["plugin.json"]).get("mcp") or {"main": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"]}}
            man["made"] = {"by": "lira", "code": True}
            files["plugin.json"] = json.dumps(man, ensure_ascii=False, indent=1)
        v = self._write(pid, files, request[:160])
        self.P.reload()
        return dict(self.info(pid), v=v, said=f"Изменила: {request[:120]}")

    def restore(self, pid, v):
        self._made(pid)
        idx = self._index(pid)
        e = next((x for x in idx if x["v"] == int(v)), None)
        if not e:
            raise MakerError("такой версии уже нет (хранятся последние 10)")
        vd = self._vdir(pid) / str(e["v"])
        files = {n: (vd / n).read_text(encoding="utf-8") for n in FILES if (vd / n).is_file()}
        cur = self._current(pid)
        if files.get("server.py") and not cur.get("server.py"):
            raise MakerError("в той версии была своя программа — вернуть её можно только с вашего разрешения: попросите Лиру")
        self._write(pid, files, f"Вернула версию {e['v']}", to=e["v"])
        self.P.reload()
        return dict(self.info(pid), said=f"Вернула версию {e['v']}")

    def undo(self, pid):
        self._made(pid)
        idx = self._index(pid)
        if not idx:
            raise MakerError("у плагина нет прежних версий")
        eff = idx[-1].get("to", idx[-1]["v"])
        prev = [x for x in idx if x["v"] < eff and "to" not in x]
        if not prev:
            raise MakerError("это первая версия — раньше ничего не было")
        r = self.restore(pid, prev[-1]["v"])
        return dict(r, said=f"Вернула как было (версия {prev[-1]['v']})")

    def info(self, pid):
        p = self.P.items.get(pid) or {}
        idx = self._index(pid)
        return {"id": pid, "name": p.get("name"), "icon": p.get("icon"), "color": p.get("color"), "tagline": p.get("tagline"),
                "data": p.get("data") or [], "theme": bool(p.get("theme")), "code": bool(p.get("made_code")),
                "version": idx[-1]["v"] if idx else 1}

    def find(self, ref=""):
        """Сделанный Лирой плагин по названию или id; пусто — последний изменённый."""
        made = [p for p in self.P.items.values() if p.get("made")]
        if not made:
            raise MakerError("сделанных Лирой плагинов пока нет")
        ref = str(ref or "").strip().lower().replace("ё", "е")
        if ref:
            for p in made:
                if ref in (p["id"], p["name"].lower().replace("ё", "е")):
                    return p["id"]
            for p in made:
                if ref in p["name"].lower().replace("ё", "е") or p["name"].lower().replace("ё", "е") in ref:
                    return p["id"]
        return max(made, key=lambda p: (self._index(p["id"]) or [{"at": 0}])[-1]["at"])["id"]

    # ---------- шаблоны ----------
    def templates(self):
        out = []
        for d in sorted(TEMPLATES_DIR.glob("*/plugin.json")) if TEMPLATES_DIR.is_dir() else []:
            try:
                m = json.loads(d.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.append({"id": d.parent.name, "name": m.get("name"), "icon": m.get("icon"), "color": m.get("color"),
                        "tagline": m.get("tagline"), "description": m.get("description"), "data": m.get("data") or [],
                        "theme": bool(m.get("theme")), "order": m.get("order", 9),
                        "installed": [p["id"] for p in self.P.items.values() if p.get("made_from") == d.parent.name]})
        return sorted(out, key=lambda x: x["order"])

    def from_template(self, tid):
        d = TEMPLATES_DIR / PL._id(tid)
        if not (d / "plugin.json").is_file():
            raise MakerError("нет такого шаблона")
        files = {"plugin.json": (d / "plugin.json").read_text(encoding="utf-8"), "ui.html": (d / "ui.html").read_text(encoding="utf-8")}
        if (d / "skill.md").is_file():
            files["skill.md"] = (d / "skill.md").read_text(encoding="utf-8")
        try:
            m0 = json.loads(files["plugin.json"])
            m0["made"] = {"by": "lira", "code": False, "template": d.name}
            files["plugin.json"] = json.dumps(m0, ensure_ascii=False)
        except ValueError:
            pass
        files, man, probs = check(files, False)
        if probs:                                            # шаблон проверяется теми же правилами (tests/plugin_creator1103)
            raise MakerError("шаблон не прошёл проверку: " + human_problems(probs))
        return self._install_new(files, man, "Из готовых: " + man["name"])
