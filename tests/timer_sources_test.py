"""Идеи 16.10 (как у Алисы и «локальный RAG»):
— таймер с обратным отсчётом: «поставь таймер на 5 минут» — в виджете крупные цифры, круг-прогресс и дуга вокруг
  облика, у значка — цифры поверх круга; голосом без модели: «сколько осталось?», «добавь минуту», «отмени таймер»;
  на телефоне — то же под обликом (и тикающий отсчёт в шторке — TimerNote.java);
— поиск по своим папкам (кроме «Знаний»): папки выбираются в студии, читаются в фоне с пределами (служебные и скрытые
  папки — мимо), ищутся вместе со «Знаниями»; домашнюю папку целиком не берём;
— ссылка на источник: ответ по документам — под ним файлы, названные в ответе; нажать — открыть (только файлы из поиска)."""
import json, os, shutil, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright
from websockets.sync.client import connect
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []
SHOT = os.environ.get("TS_SHOT")


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
# ---------- свои папки: сам индекс ----------
import knowledge as K  # noqa: E402
from workspace import Workspace  # noqa: E402


class FS:
    def __init__(self, d): self.d = d
    def get(self, *k, default=None): return str(self.d) if k == ("workspace", "path") else default


docs = tmp / "Документы"
(docs / "Договоры").mkdir(parents=True)
(docs / "Договоры" / "Аренда офиса.txt").write_text("Договор аренды офиса. Арендная плата вносится до пятого числа каждого месяца. "
                                                     "Залог — две месячные платы.", encoding="utf-8")
(docs / "Отпуск.md").write_text("# Отпуск\nЕжегодный оплачиваемый отпуск — 28 календарных дней, заявление за две недели.", encoding="utf-8")
(docs / ".git").mkdir(); (docs / ".git" / "секрет.txt").write_text("аренда тайное", encoding="utf-8")
(docs / "node_modules").mkdir(); (docs / "node_modules" / "readme.md").write_text("аренда пакета", encoding="utf-8")
(docs / "фото.jpg").write_bytes(b"\xff\xd8")
folders = [str(docs)]
kn = K.Knowledge(Workspace(FS(tmp / "ws")), tmp / "kn.json", folders=lambda: folders)
ok(not kn.has_files(), "пусто — искать негде")
n = kn.refresh_folders()
st = kn.folders_state()[0]
ok(n == 2 and st["files"] == 2 and st["chunks"] >= 2 and not st["busy"], f"своя папка прочитана: только документы, без .git и node_modules: {st}")
r = kn.search("арендная плата")
ok(r and r[0]["path"] == "Документы/Договоры/Аренда офиса.txt" and r[0]["key"].startswith("@") and not any("секрет" in x["path"] or "node_modules" in x["path"] for x in r),
   f"поиск — вместе со своей папкой, путь понятный: {[x['path'] for x in r]}")
ok(kn.file_path(r[0]["key"]) == docs / "Договоры" / "Аренда офиса.txt" and kn.file_path("@/etc/passwd") is None, "открыть можно только найденное")
ok(kn.has_files() and kn.list() == [], "в списке «Знаний» — только сама папка «Знаний»")
(docs / "Отпуск.md").unlink()
kn.refresh_folders()
ok(not kn.search("отпуск"), "удалили файл — из поиска пропал")
folders.clear(); kn.refresh_folders()
ok(not kn.search("аренда") and not kn.folders_state(), "убрали папку — её файлы больше не ищутся")
# скорость: тысячи отрывков
big = tmp / "Много"; big.mkdir()
for i in range(400):
    (big / f"док {i}.txt").write_text((f"Раздел {i}. " + "Поставка оборудования, гарантия и сервис по договору. " * 40), encoding="utf-8")
folders.append(str(big)); kn.refresh_folders()
t0 = time.time(); kn.search("гарантия сервис"); t1 = time.time(); kn.search("поставка оборудования"); t2 = time.time()
ok(t2 - t1 < 0.6, f"поиск по {sum(len(e['chunks']) for e in kn.index.values())} отрывкам — быстро: первый {t1 - t0:.2f} с, дальше {t2 - t1:.2f} с")

# ---------- ядро: модель-заглушка ----------
SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]; SEEN.append(body)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        if msgs[-1]["role"] == "tool":
            send({"content": "По договору «Аренда офиса» плата вносится до пятого числа."}); send({}, "stop")
        else:
            send({"tool_calls": [{"index": 0, "id": "s1", "type": "function", "function": {"name": "search_documents",
                  "arguments": json.dumps({"query": "арендная плата"}, ensure_ascii=False)}}]}); send({}, "tool_calls")
        self.wfile.write(b"data: [DONE]\n\n")


UP, P = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{UP}/v1"
cfg = tmp / "cfg"; cfg.mkdir()
docs2 = tmp / "Работа"; docs2.mkdir()
(docs2 / "Аренда офиса.txt").write_text("Договор аренды офиса. Арендная плата вносится до пятого числа каждого месяца.", encoding="utf-8")
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False},
    "ui": {"intro": "done", "news_seen": "99.0.0", "welcome": "done"}, "welcome": {"on": False}, "report": {"pulse": False}, "team": {"route": False},
    "llm": {"active": "m", "tools_probe_v": 2, "tools_modes": {f"{base}|m": "native"}, "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}))
DRY = tmp / "dry.jsonl"
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(P), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws2"), DEWIAR_DRY_TOOLS=str(DRY), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
env.pop("DEWIAR_WORKSPACE", None)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)


class C:
    def __init__(self, tok):
        self.ws = connect(f"ws://127.0.0.1:{P}", open_timeout=5, max_size=None)
        self.ws.send(json.dumps({"cmd": "hello", "token": tok})); self.ws.recv(timeout=10)
        self.n, self.ev, self.rep, self.lk = 0, [], {}, threading.Lock()
        threading.Thread(target=self._rd, daemon=True).start()

    def _rd(self):
        while True:
            try:
                m = json.loads(self.ws.recv())
            except Exception:  # noqa: BLE001
                return
            with self.lk:
                (self.rep.__setitem__(m["id"], m) if m.get("type") == "reply" else self.ev.append(m))

    def call(self, cmd, args=None, timeout=20):
        self.n += 1; n = self.n
        self.ws.send(json.dumps({"id": n, "cmd": cmd, "args": args or {}}))
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lk:
                if n in self.rep:
                    m = self.rep.pop(n)
                    if not m.get("ok", True):
                        raise RuntimeError(m.get("error"))
                    return m.get("data")
            time.sleep(0.05)
        raise TimeoutError(cmd)

    def answer(self, after, timeout=25):
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self.lk:
                d = [e for e in self.ev[after:] if e.get("type") == "answer" and e.get("done")]
            if d:
                return d[-1]
            time.sleep(0.1)
        return {}


try:
    for _ in range(150):
        time.sleep(0.2)
        if (cfg / "token").exists():
            break
    time.sleep(2)
    tok = (cfg / "token").read_text().strip()
    c = C(tok)
    try:
        c.call("knowledge_folder_add", {"path": str(Path.home())}); ok(False, "домашнюю папку целиком не берём")
    except RuntimeError as e:
        ok("целиком не берём" in str(e), f"домашнюю папку целиком не берём: {e}")
    c.call("knowledge_folder_add", {"path": str(docs2)})
    for _ in range(60):
        fs = c.call("knowledge_folders")
        if fs and fs[0].get("chunks"):
            break
        time.sleep(0.3)
    ok(fs and fs[0]["files"] == 1 and fs[0]["chunks"] >= 1 and fs[0]["name"] == "Работа", f"студия: своя папка прочитана в фоне: {fs}")
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 300, "height": 420}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.goto((ROOT / "ui/hud.html").as_uri() + f"?token={tok}&port={P}&mode=card"); time.sleep(2)
        m = len(c.ev)
        c.call("say", {"text": "До какого числа платить аренду офиса?"})
        a = c.answer(m)
        src = a.get("sources") or []
        ok(src and src[0]["name"] == "Аренда офиса.txt" and src[0]["label"] == "Работа/Аренда офиса.txt", f"ответ по документам — с источником: {src}")
        time.sleep(0.5)
        chips = pg.evaluate("() => [...document.querySelectorAll('#bot .srcs button')].map(x => x.textContent)")
        ok(chips == ["Аренда офиса.txt"], f"виджет: под ответом — кнопка файла: {chips}")
        pg.click("#bot .srcs button"); time.sleep(0.6)
        dry = DRY.read_text(encoding="utf-8") if DRY.exists() else ""
        ok("Аренда офиса.txt" in dry, f"нажали — файл открывается: {dry[-120:]!r}")
        hist = c.call("chat_list", {"limit": 5})
        last = [x for x in hist["items"] if x["role"] == "assistant"][-1]
        ok((last.get("att") or [{}])[0].get("key", "").startswith("@"), "«Чат»: источник у ответа — тоже кнопкой")
        if SHOT:
            pg.screenshot(path=str(Path(SHOT) / "sources.png"))
        # таймер
        m = len(c.ev)
        c.call("say", {"text": "Поставь таймер на 5 минут"}); time.sleep(1.5)
        r = pg.evaluate("() => [...document.querySelectorAll('#tmr .tr')].map(x => x.querySelector('.tt b').textContent + '|' + x.querySelector('.tt span').textContent)")
        ok(len(r) == 1 and r[0].startswith(("4:5", "5:00")) and r[0].endswith("|таймер на 5 мин"), f"виджет: обратный отсчёт: {r}")
        ok(pg.evaluate("document.getElementById('tarc').classList.contains('on')") and not pg.evaluate("document.getElementById('rem').classList.contains('show')"),
           "дуга вокруг облика; карточки «напоминание» для таймера нет")
        g = pg.evaluate("() => { const r = document.querySelector('#tmr .tr'); const b = r.querySelector('.bead'); return { grad: !!r.querySelector('linearGradient'), "
                        "ticks: r.querySelectorAll('.tick').length, bead: [+b.getAttribute('cx'), +b.getAttribute('cy')] }; }")
        ok(g["grad"] and g["ticks"] == 12 and g["bead"][0] < 22 and g["bead"][1] < 10,
           f"круг-циферблат (27.10): дуга градиентом, 12 рисок, бусина на кончике остатка (почти полный круг — у верха слева): {g}")
        if SHOT:
            pg.screenshot(path=str(Path(SHOT) / "timer.png"))
        m = len(c.ev); c.call("say", {"text": "Сколько осталось?"})
        ok(c.answer(m).get("text", "").startswith("Осталось 4 минуты"), f"«сколько осталось?» — без модели: {c.answer(m).get('text')}")
        m = len(c.ev); c.call("say", {"text": "Добавь минуту"})
        t = c.answer(m).get("text", "")
        ok(t.startswith("Добавила минуту. Теперь осталось 5 минут"), f"«добавь минуту»: {t}")
        time.sleep(0.6)
        r = pg.evaluate("() => document.querySelector('#tmr .tt b').textContent")
        ok(r.startswith("5:"), f"отсчёт сдвинулся: {r}")
        pm = b.new_page(viewport={"width": 96, "height": 96})
        pm.goto((ROOT / "ui/hud.html").as_uri() + f"?token={tok}&port={P}&mode=mini"); time.sleep(2)
        ok(pm.evaluate("getComputedStyle(document.getElementById('tmini')).display") == "block" and pm.evaluate("document.getElementById('tmini').textContent").startswith("5:"),
           "значок: цифры поверх круга")
        m = len(c.ev); c.call("say", {"text": "Отмени таймер"}); time.sleep(1.0)
        ok(c.answer(m).get("text") == "Таймер отменён." and not pg.evaluate("document.getElementById('tmr').classList.contains('on')"), "«отмени таймер» — отсчёт исчез")
        # 16.10: «сколько времени» — модель ответила «14:17» в 15:57 (повторила своё прошлое время из разговора); теперь — по часам
        from datetime import datetime as _dt
        m = len(c.ev); c.call("say", {"text": "Лира, сколько времени?"}); a1 = c.answer(m).get("text", "")
        m = len(c.ev); c.call("say", {"text": "Какое сегодня число?"}); a2 = c.answer(m).get("text", "")
        ok(a1 in (f"Сейчас {_dt.now():%H:%M}.", f"Сейчас {(_dt.now() - __import__('datetime').timedelta(minutes=1)):%H:%M}.")
           and a2.startswith("Сегодня ") and str(_dt.now().day) in a2, f"«сколько времени?» и «какое число?» — по часам, без модели: {a1!r} {a2!r}")
        m = len(c.ev); c.call("say", {"text": "Сколько осталось до Нового года?"}); a = c.answer(m)
        ok("Осталось" not in a.get("text", "")[:9] or "Нового" in a.get("text", ""), "без таймеров «сколько осталось…» — не к таймеру")
        ok(not errs, f"виджет без ошибок: {errs[:3]}")
        # телефон
        www = tmp / "www"
        shutil.copytree(ROOT / "android/assets/www", www)
        for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
            if (ROOT / "ui/assets" / x).exists():
                shutil.copy(ROOT / "ui/assets" / x, www / x)
        shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
        (www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                        capture_output=True, text=True, check=True).stdout, encoding="utf-8")
        ph = b.new_page(viewport={"width": 400, "height": 820}); perr = []
        ph.on("pageerror", lambda x: perr.append(str(x)))
        ph.goto((www / "index.html").as_uri()); ph.wait_for_timeout(900)
        q = ph.evaluate("async () => [(await quick('поставь таймер на 5 минут')).say, (await quick('поставь таймер на 12 минут')).say]")
        ph.wait_for_timeout(700)
        rows = ph.evaluate("() => [...document.querySelectorAll('#tmrs .tr')].map(r => r.querySelector('.tt b').textContent + '|' + r.querySelector('.tt span').textContent)")
        ok(q == ["Таймер на 5 минут.", "Таймер на 12 минут."] and len(rows) == 2 and rows[0].endswith("|таймер на 5 мин") and rows[1].startswith(("11:", "12:00")),
           f"телефон: два таймера — отсчёт под обликом: {rows}")
        v = ph.evaluate("async () => [(await quick('сколько осталось?')).say, (await quick('добавь минуту')).say, (await quick('отмени таймер')).say]")
        ok(v[0].startswith("Осталось: таймер на 5 минут — 4 минуты") and v[1].startswith("Добавила минуту") and v[2] == "Таймер отменён.", f"телефон: голосом: {v}")
        ph.wait_for_timeout(700)
        ok(ph.evaluate("document.querySelectorAll('#tmrs .tr').length") == 1, "телефон: отменённый таймер исчез")
        ph.click("#tmrs .x"); ph.wait_for_timeout(300)
        ok(ph.evaluate("document.getElementById('tmrs').hidden") and ph.evaluate("JSON.parse(D.alarms()).length") == 0, "телефон: ✕ — таймер отменён")
        ok(not perr, f"телефон без ошибок: {perr[:3]}")
        b.close()
finally:
    core.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
    srv.shutdown()
src = (ROOT / "android/src/pro/dewiar/app/TimerNote.java").read_text(encoding="utf-8")
ok("setChronometerCountDown" in src and "TimerNote.show" in (ROOT / "android/src/pro/dewiar/app/Alarms.java").read_text(encoding="utf-8"),
   "Android: идущий таймер — тикающий отсчёт в шторке")
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
