"""«Дозор» (0.58; владелец 28.10: «хожу по дому и раз в 5–10 минут смотрю, нет ли ответа… вот бы Лира так умела — смотрела
на экран по заданию и, если выполнено, сообщала на компе и на телефоне»; «описать везде, в уроках, в курсе… и показать»).
Ядро: дозор за папкой (новый докачанный файл), страницей (слово или изменение), экраном (сначала своё сравнение, модель —
только если экран изменился; «ДА — …» — готово); срок — сам кончается; «Стоп». Готово — голос, уведомление, конверт
своему телефону, Telegram. Голосом — инструмент watch. Студия — раздел «Дозор» и значок на «Главной»; виджет — глаз."""
import io, os, re, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
SHOTS = os.environ.get("DEWIAR_SHOTS")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import watch as W  # noqa: E402
from PIL import Image  # noqa: E402

tmp = Path(tempfile.mkdtemp())
NOW = [1_800_000_000.0]
ws = W.Watches(tmp / "watch.json", now=lambda: NOW[0])
# --- папка ---
dl = tmp / "Загрузки"; dl.mkdir()
(dl / "старое.pdf").write_bytes(b"x")
f = ws.add("file", folder=str(dl), pattern="*.mp4")
ok(f["base"] == [] and f["title"] == "новый файл в «Загрузки» (*.mp4)", f"дозор за папкой: что было — запомнено, название понятное: {f['title']}")
x = ws.get(f["id"])
(dl / "фильм.mp4.part").write_bytes(b"1" * 10)
ok(ws.check_file(x) == (False, "новых файлов нет"), "недокачанный (.part) — не считается")
(dl / "фильм.mp4").write_bytes(b"1" * 100)
r1 = ws.check_file(x)
r2 = ws.check_file(x)
ok(not r1[0] and "качается" in r1[1] and r2 == (True, "появился файл «фильм.mp4»"), f"новый файл — когда размер перестал меняться: {r1}, {r2}")
ok(W.known_folder("Загрузки").name in ("Загрузки", "Downloads"), "«Загрузки» — системная папка загрузок")
# --- страница ---
p = ws.add("page", what="Одобрено", url="https://example.com/zayavka")
y = ws.get(p["id"])
ok(ws.check_page(y, "<html><b>На рассмотрении</b></html>") == (False, "пока нет") and ws.check_page(y, "<p>Статус: <i>одобрено</i></p>")[0],
   "страница: ждёт слово (без учёта регистра и разметки)")
p2 = ws.get(ws.add("page", url="https://example.com/price")["id"])
ws.check_page(p2, "<p>Цена 100</p>")
ok(ws.check_page(p2, "<p>Цена 100</p>") == (False, "без изменений") and ws.check_page(p2, "<p>Цена 90</p>") == (True, "страница изменилась"),
   "страница без слова — любое изменение текста")
# --- экран ---
try:
    ws.add("screen", what=""); bad = False
except ValueError:
    bad = True
ok(bad, "экран без «чего ждать» — понятная просьба уточнить")


def png(color, box=None):
    im = Image.new("RGB", (1280, 720), color)
    if box:
        Image.Image.paste(im, (20, 200, 60), box)
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


A, B = png((240, 240, 240)), png((240, 240, 240), (100, 100, 900, 600))
s1, s2 = W.screen_sig(A), W.screen_sig(B)
sc = ws.get(ws.add("screen", what="Claude закончил и написал ответ", every=120)["id"])
ok(ws.screen_changed(sc, s1) and not ws.screen_changed(sc, s1) and ws.screen_changed(sc, s2), "экран: первый раз и после изменения — спросить модель; без изменений — не спрашивать")
ok(W.parse_verdict("ДА — внизу ответ Claude") == (True, "внизу ответ Claude") and W.parse_verdict("<think>…</think>НЕТ: идёт генерация")[0] is False
   and W.parse_verdict("**Да**, всё готово")[0], "ответ модели «ДА — …» / «НЕТ — …»")
# --- срок и стоп ---
NOW[0] += 3 * 3600 + 5
due, gone = ws.due()
ok(len(gone) == 4 and not due and all(ws.get(g["id"])["status"] == "expired" for g in gone), "через 3 часа дозор кончается сам (по умолчанию)")
z = ws.add("file", folder=str(dl))
ok(ws.stop(z["id"]) == 1 and ws.get(z["id"])["status"] == "stopped" and not ws.active(), "«Стоп»")
ok(W.Watches(tmp / "watch.json").get(z["id"])["status"] == "stopped", "дозоры переживают перезапуск")

# --- ядро: готово → голос, уведомление, телефон, Telegram; экран — модель со зрением ---
from engine_watch import WatchMixin  # noqa: E402
import llm  # noqa: E402


class Sett:
    def __init__(self): self.d = {"tools": {}, "privacy": {}, "llm": {}}
    def get(self, a, b=None):
        v = self.d.get(a)
        return v if b is None else (v or {}).get(b)
    def snapshot(self): return self.d
    def active_llm(self): return {"kind": "openai", "base_url": "http://127.0.0.1:9/v1", "model": "vision"}


class Close:
    def __init__(self): self.sent = []; self.st = {"me": {"pid": "pme"}}; self.up = []
    def _own_quiet(self, body): self.sent.append(body)
    def _upload(self, p, path): self.up.append((p["pid"], path.name, path.stat().st_size)); return {"id": "f1", "key": "k", "name": path.name, "size": path.stat().st_size, "type": "image/jpeg"}


class Chat:
    def __init__(self): self.sent = []
    def notify_on(self): return True
    def notify(self, t): self.sent.append(t)


class E(WatchMixin):
    def __init__(self):
        self.s, self.watches, self.close, self.chat = Sett(), W.Watches(tmp / "w2.json"), Close(), Chat()
        self.events, self.said, self.stopping = [], [], threading.Event()
    def emit(self, ev, **k): self.events.append((ev, k))
    def announce(self, t): self.said.append(t)
    def device_name(self): return "Рабочий"


e = E()
dl2 = tmp / "d2"; dl2.mkdir()
it = e.watch_add({"kind": "file", "folder": str(dl2)})
time.sleep(0.3)
(dl2 / "отчёт.pdf").write_bytes(b"%PDF" * 10)
e._watch_check(e.watches.get(it["id"])); e._watch_check(e.watches.get(it["id"]))
time.sleep(0.4)
ok(e.watches.get(it["id"])["status"] == "done" and any(ev == "watch_done" for ev, _ in e.events), "файл появился — дозор «готово»")
ok(e.said and "отчёт.pdf" in e.said[0], f"сказала голосом: {e.said[:1]}")
ok(e.close.sent and e.close.sent[0]["ping"]["title"] == "👁 Дозор: готово" and "отчёт.pdf" in e.close.sent[0]["ping"]["text"], "своему телефону — уведомление (конверт своим устройствам)")
ok(e.chat.sent and "отчёт.pdf" in e.chat.sent[0], "в Telegram — тоже")
# экран: модель со зрением
os.environ["DEWIAR_FAKE_SCREEN"] = str(tmp / "screen.png"); (tmp / "screen.png").write_bytes(A)
asked = []


def fake_stream(prof, system, msgs, cancel=None, tools=None):
    asked.append(msgs)
    yield ("text", "НЕТ — Claude ещё пишет" if len(asked) == 1 else "ДА — Claude написал ответ и ждёт")


llm.stream_events = fake_stream
e2 = E()
s_ = e2.watch_add({"kind": "screen", "what": "Claude закончил и написал ответ", "every_minutes": 2})
time.sleep(0.5)
x2 = e2.watches.get(s_["id"])
ok(len(asked) == 1 and x2["status"] == "active" and x2["note"] == "Claude ещё пишет" and isinstance(asked[0][0]["content"], list),
   f"первый взгляд сразу: модель получила снимок и ответила «нет»: {x2['note']!r}")
e2._watch_check(x2)
ok(len(asked) == 1 and x2["note"] == "экран не изменился", "экран не изменился — модель не спрашиваем (дёшево)")
(tmp / "screen.png").write_bytes(B)
e2._watch_check(x2); time.sleep(0.3)
ok(len(asked) == 2 and x2["status"] == "done" and "Claude написал ответ" in e2.said[0], f"экран изменился — спросили, «да» — позвала: {e2.said[:1]}")
# 28.10 (владелец): дозор начали в студии — на экране сама страница «Дозор» с текстом условия, и модель с первого
# взгляда сказала «да». Первое «да» сразу после начала — не «готово»: перепроверим, когда экран сменится
asked.clear(); (tmp / "screen.png").write_bytes(A)
llm.stream_events = lambda prof, system, msgs, cancel=None, tools=None: (asked.append(msgs) or iter([("text", "ДА — в правой панели «Дозор» виден текст условия")]))
e4 = E()
s4 = e4.watch_add({"kind": "screen", "what": "Claude ответил и дал файлы", "every_minutes": 2}); time.sleep(0.5)
x4 = e4.watches.get(s4["id"])
ok(len(asked) == 1 and x4["status"] == "active" and "окно Dewiar" in x4["note"] and not e4.said, f"«да» по панели «Дозор» самой Dewiar — не готово: {x4['note']!r}")
x5 = e4.watches.get(e4.watch_add({"kind": "screen", "what": "загрузка закончилась", "every_minutes": 2})["id"])
llm.stream_events = lambda prof, system, msgs, cancel=None, tools=None: (asked.append(msgs) or iter([("text", "ДА — в окне загрузок 100%")]))
e4._watch_check(x5); time.sleep(0.3)
ok(x5["status"] == "active" and "проверю ещё раз" in x5["note"], f"первое «да» сразу после начала — перепроверю: {x5['note']!r}")
e4.watches.stop(x5["id"]); asked.clear()
llm.stream_events = lambda prof, system, msgs, cancel=None, tools=None: (asked.append(msgs) or iter([("text", "ДА — в правой панели «Дозор» виден текст условия")]))
ok("Окна самой Dewiar" in W.VERDICT_SYSTEM, "модели сказано: окна Dewiar (студия, «Дозор») с текстом условия — не результат")
(tmp / "screen.png").write_bytes(B); e4._watch_check(x4); time.sleep(0.3)
ok(len(asked) == 1 and x4["status"] == "active" and "окно Dewiar" in x4["note"], f"«да» по панели «Дозор» самой Dewiar (три экрана) — не результат: {x4['note']!r}")
llm.stream_events = lambda prof, system, msgs, cancel=None, tools=None: (asked.append(msgs) or iter([("text", "ДА — в браузере Claude: ответ и кнопки скачать ARK и ZIP")]))
(tmp / "screen.png").write_bytes(A); e4._watch_check(x4); time.sleep(0.3)
ok(len(asked) == 2 and x4["status"] == "done", "в окне Claude появились файлы — готово")
time.sleep(0.5)
pg_ = [b["ping"] for b in e4.close.sent if "ping" in b]
ok(pg_ and pg_[-1].get("shot", {}).get("id") == "f1" and pg_[-1]["wid"] == x4["id"] and e4.close.up and e4.close.up[-1][0] == "pme",
   f"телефону — «готово» со снимком экрана (файл себе, шифрованный) и что увидела: {pg_[-1:] if pg_ else None}")
ok(e4.watch_more(x4["id"]) and x4["status"] == "active" and x4.get("wrong"), "с телефона «Не то — ждать дальше» — дозор снова на посту, ошибка запомнена")
llm.stream_events = lambda prof, system, msgs, cancel=None, tools=None: (asked.append(msgs) or iter([("text", "НЕТ — Claude ещё пишет")]))
(tmp / "screen.png").write_bytes(B); e4._watch_check(x4); time.sleep(0.3)
qtxt = str(asked[-1][-1]["content"])
ok("ошибочно приняла" in qtxt and "ARK и ZIP" in qtxt, "в следующем вопросе модели — «это НЕ оно»")
e3 = E(); e3.s.d["tools"] = {"enabled": {"look_at_screen": False}}
try:
    e3.watch_add({"kind": "screen", "what": "готово"}); locked = False
except ValueError as ex:
    locked = "Безопасности" in str(ex)
ok(locked, "замок «Экран: нельзя» — дозор за экраном не начинается, сказано почему")
# голосом — инструмент watch
import tools as TL  # noqa: E402
e4 = E(); e4.watches = W.Watches(tmp / "w4.json")
dl4 = tmp / "d4"; dl4.mkdir()
out = TL.t_watch({"kind": "file", "folder": str(dl4)}, {"watch": e4})
ok("Дозор начат" in out and "новый файл" in out, f"голосом: «скажи, когда появится файл» — дозор начат: {out[:80]}")
ok("Идут дозоры: новый файл" in TL.t_watch({"action": "list"}, {"watch": e4}), "«что ты сейчас ждёшь?»")
ok(TL.t_watch({"action": "stop"}, {"watch": e4}) == "Остановлено дозоров: 1." and "watch" in TL.SAFE_CORE, "«хватит присматривать» — все дозоры остановлены")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('cmd == "watch_add"' in src and '"watch": self.watch_public()' in src and '"watch_add",' in src, "ядро: watch_get/add/stop, в hello; в детском режиме — закрыто")

# --- студия, «Главная», виджет ---
import json  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
ST = {"items": [{"id": "a1", "kind": "screen", "what": "Claude ответил", "title": "Claude ответил", "status": "active", "every": 300,
                 "until": int(time.time()) + 3600, "created": int(time.time()) - 600, "last": int(time.time()) - 60, "note": "экран не изменился", "checks": 3},
                {"id": "b2", "kind": "file", "title": "новый файл в «Загрузки»", "status": "done", "every": 20, "until": 0, "created": 0,
                 "last": 0, "done_at": int(time.time()) - 3000, "result": "появился файл «фильм.mp4»"}], "active": 1}
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1000}); pg.on("pageerror", lambda e_: errs.append(str(e_)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""(st) => { window._calls = []; window._st = st;
      core.call = (c, a) => { _calls.push([c, a]);
        if (c === 'watch_get') return Promise.resolve(_st);
        if (c === 'watch_add') { _st = JSON.parse(JSON.stringify(_st)); _st.items.unshift({ id: 'c3', kind: a.kind, title: a.what || 'страница', status: 'active', every: (a.every_minutes || 5) * 60, until: Date.now() / 1000 + 3600, created: Date.now() / 1000, last: 0, note: '' }); return Promise.resolve(_st); }
        if (c === 'watch_stop') { _st = JSON.parse(JSON.stringify(_st)); _st.items.forEach(x => { if (x.id === a.id) x.status = 'stopped'; }); return Promise.resolve(_st); }
        return Promise.resolve({}); };
      $('nav button[data-p="watch"]').click(); }""", ST)
    pg.wait_for_timeout(600)
    t = pg.inner_text("#p-watch")
    ok("Лира присмотрит и скажет, когда готово" in t and "Claude ответил" in t and "смотрела в" in t and "появился файл «фильм.mp4»" in t,
       "раздел «Дозор»: что это, что ждёт сейчас (с последней проверкой), чем кончилось")
    ok(pg.evaluate("document.querySelector('#wt-dot').classList.contains('on')"), "в меню — точка, пока идёт дозор")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-watch.png"), full_page=True)
    pg.click('#wt-try button >> nth=0'); pg.click("#wt-go"); pg.wait_for_timeout(300)
    ok(["watch_add", {"kind": "screen", "what": "Claude закончил и написал ответ", "hours": 3, "every_minutes": 5}] in pg.evaluate("_calls"),
       "пример «Скажи, когда Claude ответит» → «Начать дозор» — за экраном, раз в 5 минут, до 3 часов")
    pg.click('.wt-kind [data-kind="page"]'); pg.wait_for_timeout(100)
    ok(pg.is_visible("#wt-url") and not pg.is_visible("#wt-folder") and not pg.is_visible("#wt-safe"), "«Страница» — адрес вместо папки")
    pg.click('#wt-act [data-stop="a1"]'); pg.wait_for_timeout(300)
    ok(["watch_stop", {"id": "a1"}] in pg.evaluate("_calls"), "«Стоп»")
    ok(pg.evaluate("HM_APPS.some(a => a.id === 'watch') && HM_DEFAULT.includes('watch')"), "на «Главной» — значок «Дозор»")
    nav = pg.evaluate("[...document.querySelectorAll('nav > *')].map(x => x.dataset.p || x.textContent)")
    i = nav.index("Лира делает сама")
    ok(nav[i + 1:i + 3] == ["tasks", "watch"], f"в меню — группа «Лира делает сама»: «Задачи» и «Дозор» (28.10, владелец: «где разместить разумно»): {nav[i:i + 3]}")
    pg.set_viewport_size({"width": 720, "height": 1000}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    # виджет
    h = b.new_page(viewport={"width": 420, "height": 700}); h.on("pageerror", lambda e_: errs.append(str(e_)))
    h.route(re.compile(r"^https?://"), lambda r: r.abort())
    h.add_init_script("window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { (window.apiCalls = window.apiCalls || []).push([k, ...a]); return Promise.resolve(true); } }) };")
    h.add_init_script("""(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
        core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
        core.call = async () => ({}); setTimeout(() => core.emit("hello", {}), 200); }; ready(); })();""")
    h.goto((ROOT / "ui/hud.html").as_uri()); h.wait_for_timeout(1200)
    ok(h.evaluate("document.getElementById('b-watch').hidden"), "виджет: дозоров нет — глаза нет")
    h.evaluate("(st) => core.emit('watch', st)", ST); h.wait_for_timeout(200)
    ok(not h.evaluate("document.getElementById('b-watch').hidden") and "Claude ответил" in h.evaluate("document.getElementById('b-watch').title"),
       "идёт дозор — у виджета глаз, в подсказке — что Лира ждёт")
    h.click("#b-watch"); h.wait_for_timeout(100)
    calls = h.evaluate("window.apiCalls || []")      # с 0.71 — toggle_settings: второе нажатие сворачивает студию
    ok(["open_settings", "watch"] in calls or ["toggle_settings", "watch"] in calls, f"нажали на глаз — «Дозор» в студии: {calls[-2:]}")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")

# --- телефон: «готово» карточкой со снимком, «Не то — ждать дальше» ---
import subprocess  # noqa: E402
www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
with sync_playwright() as p:
    b = p.chromium.launch(); perr = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: perr.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    r = pg.evaluate("""async () => { window.sentOwn = []; devOwnSend = async (b) => { sentOwn.push(b); return true; };
      clFileBytes = async () => Uint8Array.from(atob('/9j/4AAQSkZJRgABAQ=='), c => c.charCodeAt(0));
      ownApply({ ts: Date.now(), ping: { title: '👁 Дозор: готово', text: 'Claude — файлы', wid: 'w1', what: 'Claude даст файлы ARK и ZIP', note: 'в окне Claude: кнопки скачать ARK и ZIP', dev: 'Рабочий', shot: { id: 'f1', key: 'k' } } });
      await new Promise(r => setTimeout(r, 300));
      const c = document.querySelector('.wcard'); return [c ? c.innerText : '', !!document.querySelector('#wshot img')]; }""")
    ok("Лира увидела: в окне Claude" in r[0] and "Не то — ждать дальше" in r[0] and r[1], f"телефон: карточка «Дозор» — что ждали, что увидела, снимок: {r[0][:80]!r}")
    pg.click("#w-more"); pg.wait_for_timeout(200)
    ok(pg.evaluate("sentOwn") == [{"watch_more": {"id": "w1", "why": "в окне Claude: кнопки скачать ARK и ZIP"}}], "«Не то — ждать дальше» — компьютеру")
    b.close()
ok(not perr, f"телефон без ошибок: {perr[:2]}")

# --- описано везде ---
import course  # noqa: E402
guide = {a["id"]: a for a in json.loads((ROOT / "data/guide.json").read_text(encoding="utf-8"))}
tricks = json.loads((ROOT / "data/tricks.json").read_text(encoding="utf-8"))
ok("watch" in guide and any(l["title"].startswith("Дозор") and any(s_.get("open") == "watch" for s_ in l["steps"]) for c in course.COURSES for l in c["lessons"])
   and any(g["id"] == "watch" for g in tricks["groups"]) and re.search(r"\n  watch: \{", (ROOT / "ui/assets/help.js").read_text(encoding="utf-8")),
   "описано: статья в справке, урок в курсе «Лира для работы», «Что я умею», «?» в разделе")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
