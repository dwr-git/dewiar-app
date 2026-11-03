"""Страница плагина в студии (владелец 03.11: «плагин включён — появляются команды для запуска, а должен быть целый раздел
под плагин, где его можно настраивать и взаимодействовать. Каждый плагин — своя страничка: свой интерфейс, свои функции,
настройки. А то Лира что-то начинает делать — и на этом всё, не работает НИЧЕГО»):
— у каждого действия встроенных плагинов человеческое название и подписи полей (plugin.json ui), сырых art_draw / query нет;
— ядро: plugin_run вызывает действие плагина напрямую, без модели, и отдаёт ответ данными; чужое действие — нельзя;
  ошибка — словами; файлы — только из папок плагина; plugin_values перезапускает сервер плагина с новыми настройками;
— студия: в меню группа «Плагины» с пунктом на каждый установленный (появляется без перезапуска), страница с шапкой и
  состоянием, «Сделать сейчас» — форма из inputSchema, «Выполнить» показывает результат, ошибка — словами;
  «Попросить Лиру» и «Сказать Лире» — фраза в «Чат»; «Настройки» сохраняются сразу; «Файлы»;
— своя страница «Рекрутёра» (ui.html) во фрейме-песочнице: через мост вызывает свои действия (кандидаты, карточка,
  сопоставление с вакансией, этап), а чужое действие и чужой файл — нельзя.
SHOTS=<папка> — сохранить снимки страниц."""
import asyncio, json, os, re, socket, subprocess, sys, tempfile, time, zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("SHOTS")
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp / "ws")
os.environ["DEWIAR_TENDERS_FIXTURES"] = str(Path(__file__).resolve().parent / "fixtures/tenders")   # «Тендеры» — сохранённые страницы площадок, без сети
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- резюме для «Рекрутёра» ----------
CV = tmp / "Резюме"
CV.mkdir()
(CV / "ivanov.txt").write_text("""Иванов Пётр Сергеевич
Мужчина, 41 год
+375 (29) 123-45-67
ivanov.p@example.com
Проживает: Минск
Желаемая должность и зарплата
Главный бухгалтер
3 500 BYN на руки
Опыт работы — 12 лет 4 месяца
ООО «Альфа» — главный бухгалтер. Ведение учёта в 1С:Бухгалтерия 8.3, налоговая отчётность, МСФО, закрытие месяца.
Английский — B1
""", encoding="utf-8")
doc = ("<w:document xmlns:w='x'><w:body>" + "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in [
    "Петрова Анна Викторовна", "Женщина, 23 года", "Telegram: @anna_petrova", "Город: Гродно", "Должность: Senior бухгалтер",
    "Опыт работы 2 года 6 месяцев", "Бухгалтер-кассир, первичная документация, Excel, 1С.", "<script>alert(1)</script> <img src=x onerror=alert(2)>"]) + "</w:body></w:document>")
with zipfile.ZipFile(CV / "petrova.docx", "w") as z:
    z.writestr("word/document.xml", doc.replace("<script>alert(1)</script> <img src=x onerror=alert(2)>", "&lt;script&gt;alert(1)&lt;/script&gt; &lt;img src=x onerror=alert(2)&gt;"))
(CV / "sidorov.txt").write_text("Сидоров Иван\nPython developer\nОпыт работы — 3 года\nPython, Django, PostgreSQL, Docker\nsidorov@example.org\nГород: Брест\n", encoding="utf-8")

# ---------- plugin.json: человеческие названия у всех встроенных ----------
import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import mcp as M  # noqa: E402
import plugin_pages as PP  # noqa: E402
s = ST.Settings(tmp / "s.json")
s.update({"workspace": {"path": str(tmp / "ws")}})
P = PL.Plugins(s)
for pid in ("recruiter", "tenders", "artist", "kitchen"):
    P.install(pid, {"folder": str(CV)} if pid == "recruiter" else {"queries": "видеонаблюдение"} if pid == "tenders" else {})
mgr = M.MCPManager(s)
mgr.reconcile()
for _ in range(200):
    if all(mgr.plugin_info(x)["state"] != "connecting" for x in ("recruiter", "tenders", "artist")):
        break
    time.sleep(0.1)
WS = tmp / "ws"
WS.mkdir(exist_ok=True)
raw = []
for pid in ("recruiter", "tenders", "artist"):
    pg = PP.page(P, mgr, pid, WS)
    ok(pg["state"] == "ok" and pg["tools"], f"«{pg['plugin']['name']}»: сервер работает, действий {len(pg['tools'])}")
    for t in pg["tools"]:
        if t["hidden"] or t["page_only"]:
            continue
        if not t["title"] or re.search(r"[a-z]_[a-z]", t["title"]) or not t["hint"]:
            raw.append(f"{pid}.{t['name']}: название/подсказка")
        req = (t["schema"].get("required") or [])
        for k in (t["schema"].get("properties") or {}):
            f = t["fields"].get(k)
            if f is False and k not in req:
                continue
            if not f or not f.get("label") or re.fullmatch(r"[a-z_]+", f["label"]):
                raw.append(f"{pid}.{t['name']}.{k}")
ok(not raw, f"у каждого действия и поля — человеческая подпись (plugin.json ui): {raw}")
for pid, p in P.items.items():
    ok(p["builtin"] and (p["ui"]["asks"] or p["mcp"]) and all("{" not in a["say"] or a["fields"] for a in p["ui"]["asks"]),
       f"«{p['name']}»: на странице есть что сделать — действия или «Попросить Лиру»")
ok(P.items["recruiter"]["page"] and not P.items["kitchen"]["page"], "своя страница (ui.html) — у «Рекрутёра»")
ok("recruit_board" not in json.dumps(mgr.specs()), "действие только для страницы (recruit_board) помощнице не показывается")

# ---------- plugin_run: напрямую, без модели ----------
r = PP.run(P, mgr, "recruiter", "recruit_add", {}, WS)
d = r["parts"][0]["data"] if r["parts"] else {}
ok(r["ok"] and sorted(x["name"] for x in d.get("added", [])) == ["Иванов Пётр Сергеевич", "Петрова Анна Викторовна", "Сидоров Иван"],
   f"«Разобрать резюме» без модели — три резюме из папки настроек: {str(d)[:160]}")
r = PP.run(P, mgr, "recruiter", "recruit_board", {}, WS)
b = r["parts"][0]["data"]
ok(r["ok"] and len(b["cands"]) == 3 and b["stages"][0] == "новый" and b["folder"] == str(CV), "сводка для своей страницы: кандидаты, этапы, папка")
# «Рекрутер» как в модуле владельца: закинуть файлы (и ZIP), подбор турниром и сравнение двоих — без модели
import base64, io  # noqa: E401,E402
zb = io.BytesIO()
with zipfile.ZipFile(zb, "w") as z:
    z.writestr("пачка/orlov.txt", "Орлов Глеб\nМужчина, 29 лет\nГород: Минск\nДолжность: Бухгалтер\nОпыт работы — 4 года\n1С, налоговая отчётность, акты сверки\ngleb@example.org\n")
    z.writestr("../../evil.txt", "Злой Файл\nбез контактов " * 20)
    z.writestr("run.sh", "rm -rf /")
r = PP.run(P, mgr, "recruiter", "recruit_import", {"files": [{"name": "../../пачка.zip", "b64": base64.b64encode(zb.getvalue()).decode()}]}, WS)
d = r["parts"][0]["data"]
ok(r["ok"] and {x["name"] for x in d["added"]} == {"Орлов Глеб", "Злой Файл"} and (CV / "orlov.txt").exists() and (CV / "evil.txt").exists()
   and not (tmp / "evil.txt").exists() and not list(CV.glob("run.sh")), f"ZIP с резюме — в папку резюме, без путей наружу и чужих форматов: {d.get('added')}")
r = PP.run(P, mgr, "recruiter", "recruit_vacancy", {"title": "Главбух", "text": "1С, налоговая отчётность, МСФО, опыт от трёх лет, Минск, английский B1"}, WS)
vid = r["parts"][0]["data"]["id"]
r = PP.run(P, mgr, "recruiter", "recruit_tournament", {"vacancy": vid}, WS)
t = r["parts"][0]["data"]
ok(r["ok"] and t["ranking"][0]["name"] == "Иванов Пётр Сергеевич" and len(t["podium"]) == 3 and t["rounds"][-1]["name"] == "Финал"
   and t["rounds"][0]["name"] == "Четвертьфинал" and len(t["rounds"]) == 3 and t["vacancy"]["need_years"] == 3, f"подбор турниром без модели: {[(x['name'], x['total']) for x in t['ranking']]}")
iv = t["ranking"][0]["id"]; pe = next(x["id"] for x in t["ranking"] if x["name"].startswith("Петрова"))
r = PP.run(P, mgr, "recruiter", "recruit_compare", {"a": pe, "b": iv, "vacancy": vid}, WS)
c = r["parts"][0]["data"]
ok(r["ok"] and c["winner"] == "B" and c["winner_id"] == iv and any(x["name"] == "Стаж" and x["winner"] == "B" for x in c["parameters"]) and "решило" in c["reason"],
   f"сравнение двоих: кто сильнее и почему: {c.get('reason')}")
r = PP.run(P, mgr, "recruiter", "recruit_edit", {"id": pe, "fields": {"age": "сорок"}}, WS)
ok(r["is_error"] and "числом" in r["error"], f"правка карточки — проверка ввода словами: {r['error']}")
for x in ("Орлов Глеб", "Злой Файл"):
    PP.run(P, mgr, "recruiter", "recruit_update", {"id": next(c_["id"] for c_ in PP.run(P, mgr, "recruiter", "recruit_board", {}, WS)["parts"][0]["data"]["cands"] if c_["name"] == x), "remove": True}, WS)
for f in ("orlov.txt", "evil.txt"):
    (CV / f).unlink()
r = PP.run(P, mgr, "recruiter", "recruit_get", {"id": "нет"}, WS)
ok(r["is_error"] and r["error"] == "Нет такого кандидата", f"ошибка плагина — словами: {r['error']}")
r = PP.run(P, mgr, "recruiter", "tenders_list", {}, WS)
ok(r["is_error"] and "нет такого действия" in r["error"].lower(), f"чужое действие (Тендеров) от имени Рекрутёра — нельзя: {r['error']}")
r = PP.run(P, mgr, "artist", "art_gallery", {"open": False}, WS)
ok(r["ok"] and any(f["kind"] == "folder" or f["name"] == "Рисунки" for f in r["files"]), f"папка из ответа — кнопкой «Открыть»: {r['files'][:2]}")
try:
    PP.run(P, mgr, "kitchen", "x", {}, WS); ok(False, "плагин без своего кода — понятный отказ")
except PP.PageError as e:
    ok("через разговор" in str(e), f"плагин без своего кода — понятный отказ: {e}")
ok(PP.human_error("сервер MCP не ответил вовремя").startswith("Плагин думал слишком долго"), "таймаут — словами")
ok(PP.safe_path(P, "recruiter", WS, str(CV / "ivanov.txt")).name == "ivanov.txt", "файл из папки с резюме открыть можно")
for bad in ("/etc/passwd", str(CV / ".." / ".." / "x"), "../../etc/hostname"):
    try:
        PP.safe_path(P, "recruiter", WS, bad); ok(False, f"«{bad}» вне папок плагина — нельзя")
    except PP.PageError:
        ok(True, f"«{bad}» вне папок плагина — нельзя")
try:
    PP.safe_path(P, "kitchen", WS, str(CV / "ivanov.txt")); ok(False, "папка с резюме Рекрутёра чужому плагину — нельзя")
except PP.PageError:
    ok(True, "папка с резюме Рекрутёра чужому плагину — нельзя")
fl = PP.files(P, "recruiter", WS)
ok({x["name"] for x in fl["items"]} >= {"ivanov.txt", "sidorov.txt"} and not any(x["name"].endswith(".json") for x in fl["items"]),
   f"«Файлы»: резюме из папки, без внутреннего учёта плагина: {[x['name'] for x in fl['items']]}")
srv = M.Server("recruiter-main", {"plugin": "recruiter"}); srv.status, srv.error = "error", "не найдена программа «python9»"
keep = mgr.servers; mgr.servers = {"recruiter-main": srv}
pg = PP.page(P, mgr, "recruiter", WS)
ok(pg["state"] == "error" and "python9" in pg["error"], f"не запустился — причина на странице: {pg['error']}")
mgr.servers = keep


# ---------- настоящее ядро: команды plugin_page / plugin_run / plugin_values ----------
def free():
    so = socket.socket(); so.bind(("127.0.0.1", 0)); p = so.getsockname()[1]; so.close(); return p


import websockets  # noqa: E402
PORT = free()
cfg = tmp / "core-cfg"
cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False}, "workspace": {"path": str(tmp / "cws")},
    "plugins": {"on": {"recruiter": {"at": 1, "values": {"folder": str(tmp / "пусто")}, "jobs": {}}}},
    "mcp": {"servers": {"recruiter-main": {"type": "stdio", "command": "{python}", "args": ["{plugin_dir}/server.py"], "env": {},
                                           "plugin": "recruiter", "enabled": True}}}}, ensure_ascii=False), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "core-st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "cws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_DRY_TOOLS=str(tmp / "launch.txt"))
R = {}


async def session():
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
    try:
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (cfg / "token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
                except OSError:
                    continue
        await ws_.send(json.dumps({"cmd": "hello", "token": (cfg / "token").read_text().strip()}))
        cnt, replies = [0], {}

        async def reader():
            async for raw_ in ws_:
                e = json.loads(raw_)
                if e["type"] == "reply":
                    replies[e["id"]] = e
        rd = asyncio.ensure_future(reader())

        async def call(cmd, **args):
            cnt[0] += 1; i = cnt[0]
            await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
            for _ in range(1200):
                if i in replies:
                    return replies.pop(i)
                await asyncio.sleep(0.05)
        for _ in range(100):
            R["page"] = await call("plugin_page", id="recruiter")
            if (R["page"].get("data") or {}).get("state") not in ("connecting", None):
                break
            await asyncio.sleep(0.2)
        R["empty"] = await call("plugin_run", id="recruiter", tool="recruit_add", args={})
        R["values"] = await call("plugin_values", id="recruiter", values={"folder": str(CV), "company": ""})
        for _ in range(60):                                  # сервер перезапускается с новой папкой
            await asyncio.sleep(0.25)
            R["add"] = await call("plugin_run", id="recruiter", tool="recruit_add", args={})
            if "Иванов" in json.dumps(R["add"], ensure_ascii=False):
                break
        R["foreign"] = await call("plugin_run", id="recruiter", tool="art_draw", args={})
        R["open_bad"] = await call("plugin_open", id="recruiter", path="/etc/passwd")
        R["open_ok"] = await call("plugin_open", id="recruiter", path=str(CV / "sidorov.txt"))
        R["ui"] = await call("plugin_ui", id="recruiter")
        rd.cancel()
        await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

asyncio.run(session())
pg = (R.get("page") or {}).get("data") or {}
ok(pg.get("state") == "ok" and any(t["name"] == "recruit_add" and t["title"] == "Разобрать резюме" for t in pg.get("tools", [])),
   f"ядро: plugin_page — состояние и действия с названиями ({pg.get('state')}, {(R.get('page') or {}).get('error')})")
e1 = (R.get("empty") or {}).get("data") or {}
ok(e1.get("is_error") and "Не нашла" in e1.get("error", ""), f"ядро: папки нет — ответ словами: {e1.get('error')}")
add = (R.get("add") or {}).get("data") or {}
ok(add.get("ok") and len(((add.get("parts") or [{}])[0].get("data") or {}).get("added") or []) == 3,
   f"ядро: plugin_run без модели; новая папка из настроек дошла до сервера без перезапуска программы: {str(add)[:200]}")
ok(((R.get("foreign") or {}).get("data") or {}).get("is_error"), "ядро: чужое действие — отказ")
ok("вне папок плагина" in str((R.get("open_bad") or {}).get("error")), f"ядро: /etc/passwd не открыть: {(R.get('open_bad') or {}).get('error')}")
ok(str((R.get("open_ok") or {}).get("data", "")).endswith("sidorov.txt") and "sidorov.txt" in (tmp / "launch.txt").read_text(encoding="utf-8")
   if (tmp / "launch.txt").exists() else False, "ядро: резюме из папки плагина открывается")
ok("dewiar.run" in str(((R.get("ui") or {}).get("data") or {}).get("html")), "ядро: plugin_ui отдаёт страницу плагина")

# ---------- студия: настоящие плагины через мост к ядру этой проверки ----------
CALLS = []


def backend(cmd, args):
    """core.call студии → те же функции ядра (Plugins, MCPManager, plugin_pages), что в настоящей программе."""
    CALLS.append([cmd, args])
    a = args or {}
    try:
        if cmd == "plugins":
            return {"plugins": json.loads(json.dumps(P.catalog(), default=str)), "skills": [], "guide": ""}
        if cmd == "plugin_page":
            return json.loads(json.dumps(PP.page(P, mgr, a["id"], WS), default=str))
        if cmd == "plugin_run":
            return PP.run(P, mgr, a["id"], a["tool"], a.get("args") or {}, WS)
        if cmd == "plugin_ui":
            return {"html": PP.ui_html(P, a["id"])}
        if cmd == "plugin_files":
            return PP.files(P, a["id"], WS, a.get("limit") or 12)
        if cmd == "plugin_open":
            return str(PP.safe_path(P, a["id"], WS, a.get("path")))
        if cmd == "plugin_values":
            P.set_values(a["id"], a.get("values") or {}); mgr.reconcile()        # как ядро: сервер плагина — с новыми настройками
            return {"plugins": json.loads(json.dumps(P.catalog(), default=str)), "skills": []}
        if cmd == "plugin_install":
            P.install(a["id"], a.get("values")); mgr.reconcile()
            return {"plugins": json.loads(json.dumps(P.catalog(), default=str)), "skills": []}
        if cmd == "art_list":
            return {"items": []}
    except (PP.PageError, PL.PluginError, KeyError) as e:
        return {"__err": str(e)}
    return {}


FAKE = """(() => { window.calls = []; window.asked = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "settings_save") return S;
      const r = await window.pyCall(c, a || {}); if (r && r.__err) throw new Error(r.__err); return r; };
    setTimeout(() => core.emit("hello", { settings: { llm: {}, ui: { intro: "done" }, plugins: { on: {} } }, personas: [], persona: "lira", presets: {}, piper_voices: {}, status: {} }), 200); };
  ready(); })();"""
errs = []
shots = Path(SHOTS) if SHOTS else tmp
shots.mkdir(parents=True, exist_ok=True)
def shot(name):
    """Снимок страницы плагина целиком: окно повыше, чтобы фрейм и шапка влезли."""
    if not SHOTS:
        return
    vp = st.viewport_size
    st.set_viewport_size({"width": 1360, "height": 2300}); st.evaluate("() => document.querySelector('main').scrollTo(0, 0)"); st.wait_for_timeout(500)
    st.screenshot(path=str(shots / name)); st.set_viewport_size(vp); st.wait_for_timeout(200)


NAMES = ["Иванов Пётр Сергеевич", "Петрова Анна Викторовна", "Сидоров Иван"]
with sync_playwright() as pw:
    br = pw.chromium.launch()
    st = br.new_page(viewport={"width": 1360, "height": 940})
    st.on("pageerror", lambda e: errs.append(f"{e} @ {(e.stack or '').splitlines()[1:2]}"))
    st.expose_function("pyCall", backend)
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("() => { const w = document.querySelector('#wlc'); if (w) w.remove(); window.qaAsk = (t) => asked.push(t); }")
    try:
        st.wait_for_function("() => document.querySelectorAll('#nav-plugins .nav-plg').length >= 4", timeout=8000)
    except Exception:  # noqa: BLE001
        pass
    nav = lambda: st.evaluate("() => [...document.querySelectorAll('#nav-plugins .nav-plg')].filter(b => b.offsetParent).map(b => b.querySelector('span').textContent.trim())")
    ok(st.is_visible("#nav-plg-h") and sorted(nav()) == sorted(["Художник", "Кухня", "Рекрутер", "Тендеры"]), f"в меню — группа «Плагины» с установленными: {nav()}")
    st.evaluate("() => core.call('plugin_install', { id: 'travel', values: {} }).then(plgSet)"); st.wait_for_timeout(600)
    ok("Путешествие" in nav(), f"установили «Путешествие» — пункт меню появился сразу: {nav()}")
    # «Тендеры»: форма из inputSchema с человеческими подписями
    st.click('#nav-plugins [data-plg="tenders"]'); st.wait_for_timeout(1200)
    ok(st.evaluate("document.querySelector('#p-plg').classList.contains('cur')") and "Тендеры" in st.inner_text("#plp-head h1")
       and st.evaluate("document.querySelector('#nav-plugins [data-plg=\"tenders\"]').classList.contains('cur')"), "пункт меню открывает страницу плагина")
    head = st.inner_text("#plp-head")
    ok("Работает" in head and "Перезапустить" in head, f"шапка: состояние «Работает», «Перезапустить»: {head[:120]}")
    ok(st.inner_text("#plp .plp-tabs").startswith("Лента тендеров"), "у «Тендеров» первой — своя страница (лента)")
    st.click('#plp .plp-tabs [data-tab="do"]'); st.wait_for_timeout(300)
    body = st.inner_text("#plp-body")
    ok("Найти новые тендеры" in body and "Найденные тендеры" in body and "Только непросмотренные" in body and "Балл не ниже" in body,
       "карточки действий и поля — человеческими словами")
    ok(not re.search(r"\b(tenders_\w+|only_new|min_score|limit|query)\b", body), "нет сырых имён действий и полей")
    ok(st.evaluate("!!document.querySelector('[data-tool=\"tenders_list\"] input[type=checkbox][data-a=\"only_new\"]') && !!document.querySelector('[data-tool=\"tenders_list\"] input[type=number][data-a=\"limit\"]')"),
       "boolean — переключатель, integer — число")
    ok("Отметить тендеры" not in body, "действие только для помощницы (отметить по id) на странице не показано")
    ok("Разобрать тендер" in body and "Есть новые тендеры?" in body, "«Попросить Лиру» и «Сказать Лире» — на месте")
    st.click('[data-tool="tenders_list"] [data-run]'); st.wait_for_timeout(1500)
    out = st.inner_text('[data-tool="tenders_list"] .plp-out')
    ok("Всего" in out and "0" in out, f"«Показать» — результат: {out[:100]!r}")
    ok(any(c[0] == "plugin_run" and c[1]["tool"] == "tenders_list" and c[1]["args"].get("only_new") is False for c in st.evaluate("calls")),
       "«Выполнить» — plugin_run напрямую, переключатель уходит явно")
    st.click('[data-say="Есть новые тендеры?"]'); st.wait_for_timeout(200)
    ok(st.evaluate("asked").count("Есть новые тендеры?") == 1, "фраза «Сказать Лире» — в «Чат»")
    st.fill('.plp-ask [data-q="какой"]', "первый"); st.click(".plp-ask [data-askgo]"); st.wait_for_timeout(200)
    ok("Разбери тендер первый — стоит ли участвовать?" in st.evaluate("asked"), "«Попросить Лиру» — фраза из формы в «Чат»")
    # своя страница «Тендеров»: найти (сохранённые страницы площадок), лента с фильтрами, карточка, отметки, запросы
    st.evaluate("() => { window.opened = []; window.openExt = (u) => opened.push(u); }")
    st.click('#plp .plp-tabs [data-tab="page"]'); st.wait_for_timeout(2500)
    tf = next(f for f in st.frames if f != st.main_frame)
    tfl = st.frame_locator("#plp-frame")
    ok("Тендеров пока нет" in tfl.locator("#rows").text_content() or tfl.locator(".trow").count() > 0, "лента тендеров открылась")
    tfl.locator("#scan").click(); st.wait_for_timeout(4000)
    n_rows = tfl.locator(".trow").count()
    ok(n_rows >= 3 and "Новых тендеров" in tfl.locator("#msg").text_content(), f"«Найти новые тендеры» — лента: {n_rows}, {tfl.locator('#msg').text_content()!r}")
    tfl.locator(".trow").first.click(); st.wait_for_timeout(800)
    det = tfl.locator("#detail").text_content()
    ok("Что закупают" in det and "Заказчик" in det and "Срок подачи" in det and "Почему" in det, f"карточка тендера: {det[:200]!r}")
    if tfl.locator("#d-url").count():
        tfl.locator("#d-url").click(); st.wait_for_timeout(300)
        ok(len(st.evaluate("opened")) == 1 and st.evaluate("opened")[0].startswith("http"), f"«Открыть на площадке» — в браузере: {st.evaluate('opened')}")
    tid = tfl.locator(".trow.cur").get_attribute("data-id")
    tfl.locator('#detail [data-mark="watching"]').click(); st.wait_for_timeout(1200)
    tb = PP.run(P, mgr, "tenders", "tenders_board", {}, WS)["parts"][0]["data"]
    ok(next(t for t in tb["items"] if t["id"] == tid)["mark"] == "watching", "отметка «Интересно» — в учёт плагина")
    tfl.locator("#d-note").fill("позвонить заказчику"); st.wait_for_timeout(1500)
    tb = PP.run(P, mgr, "tenders", "tenders_board", {}, WS)["parts"][0]["data"]
    ok(next(t for t in tb["items"] if t["id"] == tid).get("note") == "позвонить заказчику", "заметка к тендеру сохраняется сама")
    tfl.locator("#f-sum").select_option("1000000"); st.wait_for_timeout(300)
    n_big = tfl.locator(".trow").count()
    tfl.locator("#f-sum").select_option("0"); st.wait_for_timeout(300)
    ok(n_big <= tfl.locator(".trow").count(), f"фильтр по сумме: {n_big} из {tfl.locator('.trow').count()}")
    shot("plugin-page-tenders.png")
    tfl.locator('.tabs [data-tab="board"]').click(); st.wait_for_timeout(500)
    ok("1" in tfl.locator('.col[data-col="watching"] h4').text_content() and tfl.locator('.col[data-col="watching"] .kc').count() == 1, "воронка: «Интересно» — отмеченный тендер")
    tfl.locator('.tabs [data-tab="q"]').click(); st.wait_for_timeout(800)
    tfl.locator('[data-add="plus"]').fill("монтаж"); tfl.locator('[data-addb="plus"]').click()
    for _ in range(80):                                   # сервер плагина перезапускается с новыми настройками
        st.wait_for_timeout(250)
        if "монтаж" in tfl.locator("#qgrid").text_content():
            break
    ok("монтаж" in str(P.values("tenders").get("plus")) and "монтаж" in tfl.locator("#qgrid").text_content(), f"«Мои запросы»: плюс-слово сохранено в настройках плагина: {P.values('tenders').get('plus')!r} {tfl.locator('#msg').text_content()!r} {tfl.locator('#qgrid').text_content()[:200]!r}")
    shot("plugin-page-tenders-queries.png")
    # «Рекрутер»: «Сделать сейчас», ошибка словами, результат таблицей
    st.click('#nav-plugins [data-plg="recruiter"]'); st.wait_for_timeout(1200)
    tabs = st.inner_text("#plp .plp-tabs")
    ok(tabs.startswith("Резюме и подбор"), f"вкладки: своя страница первой: {tabs!r}")
    st.click('#plp .plp-tabs [data-tab="do"]'); st.wait_for_timeout(300)
    st.fill('[data-tool="recruit_add"] [data-a="path"]', str(tmp / "нет-такой-папки")); st.click('[data-tool="recruit_add"] [data-run]')
    st.wait_for_selector('[data-tool="recruit_add"] .plp-err', timeout=8000)
    err = st.inner_text('[data-tool="recruit_add"] .plp-out')
    ok("Не получилось" in err and "Не нашла" in err and "{" not in err, f"ошибка — словами: {err[:120]}")
    ok(st.evaluate("!!document.querySelector('[data-tool=\"recruit_add\"] [data-pick=\"file\"]') && !!document.querySelector('[data-tool=\"recruit_add\"] [data-pick=\"folder\"]')"),
       "поле пути — кнопки «Файл…» и «Папка…»")
    ok(st.evaluate("!!document.querySelector('[data-tool=\"recruit_vacancy\"] textarea[data-a=\"text\"]')"), "длинное поле (требования) — многострочное")
    st.fill('[data-tool="recruit_vacancy"] [data-a="title"]', "Бухгалтер")
    st.fill('[data-tool="recruit_vacancy"] [data-a="text"]', "1С, налоговая отчётность, МСФО, опыт от трёх лет, Минск, английский B1")
    st.click('[data-tool="recruit_vacancy"] [data-run]'); st.wait_for_timeout(1500)
    st.click('[data-tool="recruit_list"] [data-run]'); st.wait_for_timeout(1500)
    out = st.inner_text('[data-tool="recruit_list"] .plp-out')
    ok(NAMES[0] in out and "Имя" in out and "Этап" in out and "Готово за" in st.inner_text('[data-tool="recruit_list"] .plp-run'),
       f"«Кандидаты» — таблицей с подписями, «Готово за … с»: {out[:140]}")
    ok(st.evaluate("document.querySelector('[data-tool=\"recruit_list\"]').classList.contains('has-out')"), "карточка с результатом — на всю ширину")
    st.click('[data-tool="recruit_tournament"] [data-run]'); st.wait_for_timeout(1500)
    out = st.inner_text('[data-tool="recruit_tournament"] .plp-out')
    ok("Рейтинг" in out and "Балл" in out and "Честность" in out and NAMES[0] in out, f"«Подбор лучших» без модели — рейтингом: {out[:140]}")
    shot("plugin-page-recruiter-do.png")
    # «Настройки» — сразу
    st.click('#plp .plp-tabs [data-tab="set"]'); st.wait_for_timeout(300)
    st.fill('#plp-body [data-k="company"]', "ООО «Пример»"); st.wait_for_timeout(1200)
    ok(P.values("recruiter").get("company") == "ООО «Пример»", "настройка сохраняется сразу, без кнопки")
    st.click('#plp .plp-tabs [data-tab="files"]'); st.wait_for_timeout(800)
    ok("ivanov.txt" in st.inner_text("#plp-body") and "Папка с резюме" in st.inner_text("#plp-body"), "«Файлы» — резюме из папки плагина")
    # своя страница «Рекрутёра»: закинуть резюме, каталог, карточка, правка, подбор, сравнение
    st.click('#plp .plp-tabs [data-tab="page"]'); st.wait_for_timeout(2500)
    ok(st.get_attribute("#plp-frame", "sandbox") == "allow-scripts", "фрейм-песочница: только скрипты, без same-origin")
    frame = next(f for f in st.frames if f != st.main_frame)
    fr = st.frame_locator("#plp-frame")
    names = fr.locator(".cand .who b").all_inner_texts()
    ok(sorted(names) == NAMES, f"ui.html Рекрутёра — каталог кандидатов через мост: {names}")
    # закинуть резюме: как перетаскивание — файлы в поле выбора
    fr.locator("#file").set_input_files([{"name": "kozlova.txt", "mimeType": "text/plain", "buffer": "Козлова Мария Игоревна\nЖенщина, 34 года\n+375 33 765-43-21\nГород: Минск\nДолжность: Бухгалтер\nОпыт работы — 8 лет\n1С 8.3, налоговая отчётность, МСФО, зарплата. Высшее, БГЭУ. Английский — B2\n".encode()},
                                        {"name": "virus.exe", "mimeType": "application/octet-stream", "buffer": b"MZ"}])
    st.wait_for_timeout(3000)
    q = fr.locator("#queue").inner_text()
    ok("Козлова Мария Игоревна" in q and "формат не читаю" in q, f"закинули файлы — очередь: добавлен / понятная причина отказа: {q!r}")
    ok((CV / "kozlova.txt").exists() and not (CV / "virus.exe").exists(), "резюме скопировано в папку резюме плагина, чужой формат — нет")
    ok(fr.locator(".cand").count() == 4 and "Козлова" in fr.locator("#detail h1").inner_text(), "новый кандидат — в каталоге и сразу открыт")
    fr.locator(".cand", has_text="Петрова").click(); st.wait_for_timeout(1500)
    det = fr.locator("#detail").text_content()
    flg = fr.locator("#detail .flags").inner_text() if fr.locator("#detail .flags").count() else ""
    ok("Петрова Анна Викторовна" in det and "Уточнить на собеседовании" in det and "senior" in flg.lower() and "Гродно" in det,
       f"карточка кандидата: факты и что уточнить: {flg!r} {det[:300]!r}")
    rtext = fr.locator("details.resume pre").text_content()
    ok(fr.locator("#detail img, #detail script").count() == 0 and "alert(1)" in rtext, f"текст резюме — только текстом, не разметкой: {rtext[-80:]!r}")
    fr.locator("#d-edit").click(); st.wait_for_timeout(800)
    fr.locator('#detail [data-f="city"]').fill("Минск"); fr.locator('#detail [data-f="exp_years"]').fill("5")
    fr.locator("#d-save").click(); st.wait_for_timeout(1500)
    det = fr.locator("#detail").inner_text()
    ok("Минск" in det and "5 г. 0 мес." in det and fr.locator("#detail .flags").count() == 0, f"«Поправить»: город и стаж сохранены, сигналы пересчитаны: {det[det.find('Уточнить'):][:80]!r}")
    fr.locator('#detail [data-stage="собеседование"]').click(); st.wait_for_timeout(1500)
    ok(fr.locator('#detail .stages .on').inner_text() == "собеседование", "этап — через мост в данные плагина")
    fr.locator("#d-qs").click(); st.wait_for_timeout(300)
    ok(any("Вопросы к собеседованию с кандидатом Петрова" in a for a in st.evaluate("asked")), "«Вопросы к собеседованию» — Лире в «Чат» по нажатию")
    shot("plugin-page-recruiter-ui.png")
    # подбор под вакансию: турнир без модели
    fr.locator('.tabs [data-tab="pick"]').click(); st.wait_for_timeout(500)
    fr.locator('#vacs .chip', has_text="Бухгалтер").click(); st.wait_for_timeout(300)
    ok("1С" in fr.locator("#vx").input_value(), "сохранённая вакансия — текстом в поле")
    fr.locator("#go").click(); st.wait_for_timeout(2500)
    res = fr.locator("#res").text_content()
    pod = fr.locator(".pod b").all_inner_texts()
    ok(len(pod) == 3 and pod[0] in ("Иванов Пётр Сергеевич", "Козлова Мария Игоревна") and "Рейтинг" in res and "Турнир лучших" in res and "Финал" in res,
       f"«Подобрать лучших»: тройка, рейтинг, турнир попарно — без модели: {pod} {res[:600]!r}")
    ok(not any(c[0] == "say" for c in st.evaluate("calls")), "подбор — без Лиры")
    shot("plugin-page-recruiter-pick.png")
    fr.locator("#top2").click(); st.wait_for_timeout(2000)
    cres = fr.locator("#cres").inner_text()
    ok("Рекомендован" in cres and "Совпадение с требованиями" in cres and "Стаж" in cres and "Честность анкеты" in cres, f"сравнение двоих: параметры и кто сильнее: {cres[:200]}")
    shot("plugin-page-recruiter-compare.png")
    fr.locator("#cask").click(); st.wait_for_timeout(300)
    ok(any(a.startswith("Сравни кандидатов") for a in st.evaluate("asked")), "«Попросить Лиру сравнить словами» — в «Чат»")
    # мост: чужое действие, чужой файл, хранилища, сеть — нельзя
    probe = """(async () => { const out = {};
        try { await dewiar.run('tenders_scan', {}); out.foreign = 'прошло'; } catch (e) { out.foreign = e.message; }
        try { await dewiar.run('recruit_board', {}); out.own = 'ok'; } catch (e) { out.own = e.message; }
        try { await dewiar.open('/etc/passwd'); out.file = 'открылось'; } catch (e) { out.file = e.message; }
        try { localStorage.getItem('x'); out.storage = 'есть'; } catch (e) { out.storage = 'нет'; }
        try { out.parent = String(parent.document.title); } catch (e) { out.parent = 'нет доступа'; }
        try { await fetch('https://example.com'); out.net = 'есть'; } catch (e) { out.net = 'нет'; }
        try { const s = await dewiar.settings(); out.keys = Object.keys(s.values).sort().join(','); } catch (e) { out.keys = e.message; }
        return out; })()"""
    got = frame.evaluate(probe)
    # evaluate playwright сам считается нажатием — фразу шлём из таймера, когда «нажатие» остыло (в Chromium — 5 с)
    frame.evaluate("setTimeout(() => dewiar.ask('без нажатия').then(() => { document.title = 'ушло'; }, (e) => { document.title = e.message; }), 5600)")
    st.wait_for_timeout(6300)
    dlg = st.locator(".dwq").last
    ok(dlg.is_visible() and "хочет спросить Лиру" in dlg.inner_text() and "без нажатия" not in st.evaluate("asked"),
       f"фраза в чат без нажатия — сначала вопрос человеку: {dlg.inner_text()[:120] if dlg.count() else ''!r}")
    dlg.locator("button", has_text="Отмена").click(); st.wait_for_timeout(400)
    got["ask"] = frame.evaluate("document.title")
    ok("не действие этого плагина" in got.get("foreign", ""), f"мост: чужое действие (Тендеров) — нельзя: {got.get('foreign')}")
    ok(got.get("own") == "ok", "мост: своё действие — можно")
    ok("вне папок плагина" in got.get("file", ""), f"мост: чужой файл — нельзя: {got.get('file')}")
    ok(got.get("storage") == "нет" and got.get("parent") == "нет доступа" and got.get("net") == "нет", f"песочница: ни хранилищ, ни студии, ни сети: {got}")
    ok(got.get("keys") == "company,folder", f"мост: только свои настройки плагина (без ключей облака): {got.get('keys')}")
    ok("не разрешил" in got.get("ask", "") and "без нажатия" not in st.evaluate("asked"), f"отказался — фраза не ушла: {got.get('ask')}")
    ok(not [c for c in st.evaluate("calls") if c[0] == "plugin_run" and c[1]["tool"] == "tenders_scan" and c[1]["id"] == "recruiter"], "чужое действие до ядра даже не дошло")
    frame.evaluate("location.href = 'about:blank#x'"); st.wait_for_timeout(500)
    ok(st.evaluate("PLP.frameLoads") >= 2, "фрейм сменил страницу — мост выключен")
    # «Художник» — вкладка «Рисунки»; «Кухня» — без своего кода: «Попросить Лиру»
    st.click('#nav-plugins [data-plg="artist"]'); st.wait_for_timeout(1200)
    ok(st.inner_text("#plp .plp-tabs").startswith("Рисунки") and "Рисунков пока нет" in st.inner_text("#plp-body"), "«Художник»: страница ведёт в его «Рисунки»")
    st.click('#plp .plp-tabs [data-tab="do"]'); st.wait_for_timeout(300)
    body = st.inner_text("#plp-body")
    ok("Галерея" in body and "Нарисовать" in body and "art_draw" not in body and "Svg" not in body, "«Художник»: код SVG — дело Лиры, человеку — «Нарисовать» и «Галерея»")
    st.click('#nav-plugins [data-plg="kitchen"]'); st.wait_for_timeout(1000)
    ok("Работает через разговор" in st.inner_text("#plp-head") and "Что приготовить" in st.inner_text("#plp-body"), "«Кухня» — без своего кода: понятное состояние и формы для Лиры")
    st.fill('.plp-ask [data-q="продукты"]', "курица, рис"); st.press('.plp-ask [data-q="продукты"]', "Enter"); st.wait_for_timeout(200)
    ok("Что приготовить из курица, рис?" in st.evaluate("asked"), "Enter в форме — фраза Лире")
    shot("plugin-page-kitchen.png")
    if SHOTS:                                         # тёмная тема: та же страница Рекрутёра
        sk = st.evaluate("() => document.documentElement.dataset.skin || ''")
        st.evaluate("() => studioSkin('brand')")
        st.click('#nav-plugins [data-plg="recruiter"]'); st.wait_for_timeout(2500)
        shot("plugin-page-recruiter-dark.png")
        if sk:
            st.evaluate("(s) => studioSkin(s)", sk)
    # «Плагины» → панель → «Открыть страницу плагина»
    st.evaluate("() => { document.querySelector('nav button[data-p=\"skills\"]').click(); }"); st.wait_for_timeout(800)
    st.evaluate("() => plgDrawer('tenders')"); st.wait_for_timeout(200)
    ok(st.is_visible("#pld-page"), "в панели плагина — «Открыть страницу плагина»")
    st.click("#pld-page"); st.wait_for_timeout(1000)
    ok(st.evaluate("document.querySelector('#p-plg').classList.contains('cur')") and "Тендеры" in st.inner_text("#plp-head h1"), "— и она открывается")
    # не запустился — причина и «Перезапустить»
    keep = mgr.servers
    srv = M.Server("tenders-main", {"plugin": "tenders"}); srv.status, srv.error = "error", "сервер MCP завершился"
    mgr.servers = {"tenders-main": srv}
    st.evaluate("() => plpLoad()"); st.wait_for_timeout(800)
    head = st.inner_text("#plp-head")
    ok("Не запустился" in head and "Программа плагина остановилась" in head and st.is_visible("#plp-restart"), f"не запустился — причина словами и «Перезапустить»: {head[:160]}")
    mgr.servers = keep
    st.set_viewport_size({"width": 760, "height": 900}); st.wait_for_timeout(300)
    ok(st.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 2"), "узкое окно — без вылезания")
    mine = [e for e in errs if "plugpage" in e or "srcdoc" in e or "about:" in e or "@ []" in e]
    ok(not mine, f"без ошибок JavaScript на странице плагина: {mine[:3]} (всего {len(errs)}: {errs[:2]})")
    br.close()
mgr.close()
for f in ("ui/studio/plugpage.js", "ui/studio/plugins.js", "ui/studio/home.js"):
    r = subprocess.run(["node", "--check", str(ROOT / f)], capture_output=True, text=True)
    ok(r.returncode == 0, f"{f} без ошибок синтаксиса {r.stderr[-200:]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
