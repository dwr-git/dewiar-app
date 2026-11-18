"""Плагин «Расшифровка» (1.0.33; владелец: «ОЧЕНЬ КРУТО, НУЖНО ДЕЛАТЬ», 18.11: «не должен быть сложным»).
Ядро core/transcribe.py со «слухом»-заглушкой:
- без плагина — ни команд, ни действий модели (модуль «transcribe» не готов) — понятный отказ;
- файл — в очередь, ход работы событием, готово — текст с метками [мм:сс], .srt и копии в «Мои файлы» → «Расшифровки»;
- не аудио — отказ; две подряд — по очереди; «Стоп» — сохраняет, что успела; поиск по тексту всех записей с метками;
- действия модели: transcribe (начала — скажу, когда готово; голосом — Лира говорит сама), transcripts (список, поиск, текст);
- перетащили небольшой файл — копия у нас и расшифровка.
Студия: вкладка «Расшифровки» на странице плагина — пусто, ход с «Стоп», готовая запись с метками, поиск с переходом к месту.
DEWIAR_SHOTS=<папка> — снимки transcribe-list.png, transcribe-rec.png."""
import base64, json, os, re, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import transcribe as TRM  # noqa: E402
import modules  # noqa: E402

tmp = Path(tempfile.mkdtemp())
SEGS = [(0.0, 21.5, "Добрый день, начинаем созвон по проекту."), (21.5, 43.0, "Сроки сдачи переносим на пятницу."),
        (43.0, 70.2, "Юрист пришлёт договор до среды.")]


class WS:
    root = tmp / "ws"


class Plugins:
    def __init__(self):
        self.on = False

    def installed(self):
        return [{"id": "transcribe"}] if self.on else []


class Host:
    def __init__(self):
        self.plugins, self.workspace, self.events, self.said = Plugins(), WS(), [], []
        self.gate = threading.Event()
        self.gate.set()

    def emit(self, t, **kw):
        self.events.append((t, kw))

    def announce(self, text, tag=""):
        self.said.append(text)

    def transcribe_file(self, path, cancel=None, progress=None):
        out = []
        for a, b, t in SEGS:
            self.gate.wait(5)
            if cancel is not None and cancel.is_set():
                break
            out.append((a, b, t))
            if progress:
                progress(b, 70.2)
        return out


H = Host()
T = TRM.Transcripts(H, root=tmp / "st")
audio = tmp / "Созвон с юристом.m4a"
audio.write_bytes(b"\0" * 100)
try:
    T.start(audio); ok(False, "без плагина начала")
except ValueError as e:
    ok("включите плагин" in str(e), f"без плагина — понятный отказ: {e}")
ok(not modules.ready(modules.of("transcribe"), "transcribe", {"transcripts": T}, {}), "без плагина действия модели скрыты")
H.plugins.on = True
ok(modules.ready(modules.of("transcribe"), "transcribe", {"transcripts": T}, {}), "плагин включён — действия модели видны")
bad = tmp / "отчёт.pdf"; bad.write_bytes(b"%PDF")
try:
    T.start(bad); ok(False, "pdf принят")
except ValueError as e:
    ok("не аудио" in str(e), "не аудио — отказ")


def wait_state(tid, states, sec=8):
    end = time.time() + sec
    while time.time() < end:
        x = T.get(tid)
        if x["state"] in states:
            return x
        time.sleep(0.05)
    return T.get(tid)


r = T.start(audio)
x = wait_state(r["id"], ("done", "err"))
ok(x["state"] == "done" and x["n"] == 3 and x["dur"] == 70.2, f"готово: 3 фрагмента, 70 с: {x['state']} {x['n']} {x['dur']}")
ok(any(t == "transcribe" and (kw.get("item") or {}).get("pct") for t, kw in H.events), "ход работы — событием с процентами")
txt = T.text(x["id"])
ok(txt.startswith("[00:00] Добрый день") and "[00:21] Сроки" in txt and "[00:43] Юрист" in txt, "текст с метками [мм:сс]")
srt = T.text(x["id"], "srt")
ok("1\n00:00:00,000 --> 00:00:21,500\nДобрый день" in srt and "3\n00:00:43,000 --> 00:01:10,200" in srt, "субтитры .srt по правилам")
ok(x["files"] == ["Расшифровки/Созвон с юристом.txt", "Расшифровки/Созвон с юристом.srt"]
   and (WS.root / "Расшифровки" / "Созвон с юристом.srt").read_text(encoding="utf-8") == srt, f"копии в «Мои файлы» → «Расшифровки»: {x['files']}")
ok(not H.said, "из студии — Лира молчит (студия покажет сама)")
s = T.list("сроки пятниц")
ok(len(s["hits"]) == 1 and s["hits"][0]["t"] == "00:21" and s["hits"][0]["name"] == "Созвон с юристом", f"поиск по тексту — место и время: {s['hits']}")
ok(T.list("кошка")["hits"] == [], "нет такого — пусто")
# голосом: действие модели; две подряд — очередь; «Стоп»
H.gate.clear()
msg = T.tool_start(str(audio), "Планёрка")
ok("Начала расшифровку «Планёрка»" in msg and "скажу" in msg, f"transcribe: начала, скажу, когда готово: {msg[:70]}")
r2 = T.start(audio, "Вторая")
ok(T.get(r2["id"])["state"] == "wait", "вторая — ждёт очереди")
first = next(i for i in T.list()["items"] if i["name"] == "Планёрка")
T.stop(r2["id"])
ok(T.get(r2["id"])["state"] == "stop", "«Убрать» из очереди — остановлено")
H.gate.set()
x2 = wait_state(first["id"], ("done",))
time.sleep(0.2)
ok(x2["state"] == "done" and any("Расшифровала «Планёрка»" in t for t in H.said), f"голосом — готово, Лира говорит сама: {H.said}")
ok((WS.root / "Расшифровки" / "Планёрка.txt").is_file(), "своё имя — свой файл")
found = json.loads(T.tool_find(q="договор"))
ok(found["hits"] and found["hits"][0]["t"] == "00:43", "transcripts query — место с меткой времени")
full = json.loads(T.tool_find(name="планёр"))
ok(full["name"] == "Планёрка" and "[00:21] Сроки" in full["text"], "transcripts name — весь текст для выжимки")
lst = json.loads(T.tool_find())
ok({i["name"] for i in lst["items"]} >= {"Планёрка", "Созвон с юристом", "Вторая"}, "transcripts — список")
# «Стоп» во время работы — сохраняет, что успела
H.gate.clear()
r3 = T.start(audio, "Длинная")
time.sleep(0.2); H.gate.set(); time.sleep(0.01)
T.stop(r3["id"])
x3 = wait_state(r3["id"], ("stop", "done"))
ok(x3["state"] in ("stop", "done"), f"«Стоп» во время работы — запись остаётся: {x3['state']} {x3['n']}")
# перетащили небольшой файл
up = T.upload("голосовое.ogg", "data:audio/ogg;base64," + base64.b64encode(b"OggS" + b"\0" * 64).decode())
x4 = wait_state(up["id"], ("done",))
ok(x4["state"] == "done" and Path(x4["src"]).parent == T.dir / "files", "перетащили небольшой файл — копия у нас, расшифровано")
T.rename(x4["id"], "Голосовое от Анны")
ok(T.get(x4["id"])["name"] == "Голосовое от Анны", "переименовать")
T.delete(x4["id"])
ok(all(i["id"] != x4["id"] for i in T.list()["items"]), "удалить")
try:
    T.get("../../etc")
    ok(False, "чужой путь принят")
except ValueError:
    ok(True, "id — только свой (без путей)")

# ---------- студия ----------
from playwright.sync_api import sync_playwright  # noqa: E402
items = [T._pub(T._load(i["id"])) for i in T.list()["items"]]
REC = T.get(x["id"])
CORE = r"""
(() => { window.calls = []; window.ITEMS = %s; window.REC = %s;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "transcribe_list") { if (a.q) return { items: ITEMS.filter(i => i.id === REC.id), hits: [{ id: REC.id, name: REC.name, at_s: 21.5, t: "00:21", text: "Сроки сдачи переносим на пятницу." }] };
        return { items: ITEMS }; }
      if (c === "transcribe_get") return REC;
      if (c === "transcribe_text") return { text: "[00:00] Добрый день" };
      if (c === "transcribe_start") { ITEMS.unshift({ id: "aaaaaaaaaa", name: "Новая", state: "run", pct: 42, n: 0, at: Date.now() / 1000, src: a.path }); return ITEMS[0]; }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
""" % (json.dumps(items, ensure_ascii=False), json.dumps(REC, ensure_ascii=False))
FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'pick_file' ? (() => Promise.resolve('/home/u/Лекция.mp4')) : (...a) => Promise.resolve(true) }) };"
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1400)
    pg.evaluate("""() => { document.querySelectorAll('section.cur').forEach(s => s.classList.remove('cur'));
        const s = document.getElementById('p-plg'); s.classList.add('cur'); const box = document.getElementById('plp');
        box.style.setProperty('--pc', '#4F8DF7'); box.innerHTML = '<div id="plp-body"></div>'; trPage(document.getElementById('plp-body')); }""")
    pg.wait_for_timeout(400)
    t = pg.inner_text("#plp-body")
    ok("Перетащите запись сюда" in t and "Созвон с юристом" in t and "Планёрка" in t, "вкладка: поле для файла и список записей")
    pg.click("#tr-pick"); pg.wait_for_timeout(300)
    ok(["transcribe_start", {"path": "/home/u/Лекция.mp4"}] in pg.evaluate("calls"), "«Выбрать файл» — расшифровка начата")
    ok(pg.locator(".tr-item.run .tr-bar").count() == 1 and "42%" in pg.inner_text(".tr-item.run") and pg.locator(".tr-item.run [data-stop]").count() == 1,
       "идёт — полоса с процентами и «Стоп»")
    if SHOT:
        Path(SHOT).mkdir(parents=True, exist_ok=True); pg.locator(".tr").screenshot(path=str(Path(SHOT) / "transcribe-list.png"))
    pg.fill("#tr-q", "сроки"); pg.wait_for_timeout(500)
    ok(pg.locator(".tr-hits button").count() == 1 and "00:21" in pg.inner_text(".tr-hits") and pg.locator(".tr-hits mark").count() >= 1, "поиск — место с меткой и подсветкой")
    pg.click(".tr-hits button"); pg.wait_for_timeout(300)
    ok(pg.locator(".tr-segs li.hit").count() == 1 and "Сроки сдачи" in pg.inner_text(".tr-segs li.hit"), "нажали на место — запись открыта на нём")
    ok(all(pg.is_visible(s) for s in ("#tr-ask", "#tr-copy", "#tr-srt", "#tr-dir", "#tr-del")), "кнопки записи: спросить, скопировать, субтитры, папка, удалить")
    if SHOT:
        pg.locator(".tr").screenshot(path=str(Path(SHOT) / "transcribe-rec.png"))
    pg.click("#tr-back"); pg.wait_for_timeout(300)
    ok(pg.locator(".tr-list").count() == 1, "«Все расшифровки» — назад к списку")
    pg.set_viewport_size({"width": 720, "height": 900}); pg.wait_for_timeout(150)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
pj = json.loads((ROOT / "data/plugins/transcribe/plugin.json").read_text(encoding="utf-8"))
ok(pj["id"] == "transcribe" and not pj.get("mcp") and pj["skills"] == ["transcribe"], "плагин — без своей программы: распознаёт ядро")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
