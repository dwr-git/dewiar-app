"""04.11, владелец: «Занят: проверяет обновления — 113 с… то нормально работает, а то по 5 минут открывает сайт». Проверка
обновлений тут же качала установщик с сайта (виджет «занят» минутами), а сотни компьютеров качали новый выпуск с сайта
разом и забивали его канал. Теперь (0.82.2, владелец: «мой сайт основной, на GitHub не очень рассчитываем»):
- качаем с сайта; оборвалось — докачка с места обрыва (Range);
- GitHub — только запасной путь и только если в latest.json есть поле "github" (и не выключено updates.mirror_github):
  сайт не ответил, занят (503) или медленный; sha256 сверяется всегда — подменённый файл не принимается;
- сайт занят или медленный, а запасного пути нет — откладываем на час, не долбим;
- фоновая проверка качает через случайную задержку 0–6 ч (помнится между запусками), ручная — сразу;
- ручная проверка отвечает за секунды, скачивание идёт в фоне с ходом: «Скачиваю 0.82.2 — 45 % (с …)» — и в виджете;
- publish_update.py пишет "github", только если sha256 файла на GitHub тот же."""
import hashlib, json, os, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
for k in [k for k in os.environ if "proxy" in k.lower()]:
    os.environ.pop(k)
sys.path.insert(0, str(ROOT / "core"))
import updater as UP  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


DATA = os.urandom(300_000)
SHA = hashlib.sha256(DATA).hexdigest()
OTHER = os.urandom(300_000)
NAME = "dewiar-assistant_99.2.0_all.deb"
MODE = {"site": "ok", "gh": "ok"}          # ok | slow | silent | 503 | cut | other
HITS = []                                  # (кто, Range)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_GET(self):
        who = "gh" if self.path.startswith("/gh/") else "site"
        if self.path.endswith("latest.json"):
            body = json.dumps(LATEST).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        HITS.append((who, self.headers.get("Range")))
        mode = MODE[who]
        if mode == "503":
            self.send_response(503); self.send_header("Content-Length", "0"); self.end_headers(); return
        if mode == "silent":
            time.sleep(4); return
        data = OTHER if mode == "other" else DATA
        start = 0
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            start = int(rng[6:].split("-")[0])
            self.send_response(206); self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        else:
            self.send_response(200)
        part = data[start:]
        self.send_header("Content-Length", str(len(part))); self.end_headers()
        try:
            if mode == "cut" and not rng:                      # первый заход обрывается на трети
                self.wfile.write(part[:100_000]); self.wfile.flush(); self.close_connection = True
                self.connection.shutdown(2); return
            if mode == "slow":
                for i in range(0, len(part), 2000):
                    self.wfile.write(part[i:i + 2000]); self.wfile.flush(); time.sleep(0.05)
                return
            self.wfile.write(part)
        except OSError:
            pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_port}"
LATEST = {"version": "99.2.0", "deb": NAME, "sha256": SHA, "size": len(DATA), "github": f"{BASE}/gh/{NAME}"}
UP.SLOW_FOR, UP.SLOW_SPEED, UP.WAIT = 1, 200_000, 2      # «медленно» и «молчит» — за секунды, а не минуты


class S:
    def __init__(self, **kw):
        self.kw = kw

    def get(self, *k):
        if k == ("updates", "url"):
            return BASE + "/dwrapp/latest.json"
        if k == ("updates", "mirror_github"):
            return self.kw.get("mirror", True)
        return None


def client(name, **kw):
    ev = []
    u = UP.Updater(S(**kw), "0.82.1", tmp / name, emit=lambda *a, **k: ev.append(k.get("update")))
    return u, ev


def reset(site="ok", gh="ok"):
    MODE.update(site=site, gh=gh); HITS.clear()


# 1. сайт отвечает — качаем с сайта, GitHub не трогаем
reset()
u, ev = client("a")
i = u.check()
ok(i and Path(i["path"]).read_bytes() == DATA and i.get("from") == "127.0.0.1" and all(h[0] == "site" for h in HITS),
   f"сайт отвечает — скачано с сайта, GitHub не тронут: {i and i.get('from')}, {HITS}")

# 2. сайт медленный — запасной путь GitHub, sha сверен
reset(site="slow")
u, ev = client("b")
i = u.check()
ok(i and Path(i["path"]).read_bytes() == DATA and i.get("from") == "GitHub" and ("gh", None) in HITS,
   f"сайт отдаёт медленно — взято с GitHub, сумма сверена: {i and i.get('from')}")
ok(any(e and e.get("downloading") and e["downloading"]["from"] == "GitHub" for e in ev), "ход скачивания показывает, откуда — «с GitHub»")

# 3. сайт молчит — GitHub
reset(site="silent")
u, ev = client("c")
t0 = time.time()
i = u.check()
ok(i and i.get("from") == "GitHub" and time.time() - t0 < 15, f"сайт молчит — через {time.time() - t0:.0f} с взято с GitHub")

# 4. сайт занят, GitHub подсунул другой файл — отказ, ничего не скачано, попытка через час
reset(site="503", gh="other")
u, ev = client("d")
i = u.check()
ok(i is None and not list((tmp / "d" / "updates").glob("*.deb")) and "с GitHub пришёл другой файл" in u.last["error"],
   f"GitHub отдал другой файл — не принят: {u.last['error'][:120]}")

# 5. сайт занят, запасного пути нет — откладываем на час, не долбим
LATEST.pop("github")
reset(site="503")
u, ev = client("e")
i = u.check(manual=False)
u.last["next"] = 0
spread = json.loads((tmp / "e" / "updates" / "spread.json").read_text())
spread["at"] = time.time() - 1                              # случайная задержка уже прошла
(tmp / "e" / "updates" / "spread.json").write_text(json.dumps(spread))
reset(site="503")
i = u.check(manual=False)
ok(i is None and 3500 < u.public()["next"] - time.time() <= 3600 and "через час" in u.last["error"] and len(HITS) == 1,
   f"сайт занят, без GitHub — следующая попытка через час, без повторов: {u.last['error']!r}, запросов {len(HITS)}")
reset(site="ok")
ok(u.check(manual=False) is None and not HITS, "в этот час фоновая проверка сайт не дёргает")
ok(u.check() and HITS, "а «Проверить обновления» руками — сразу")

# 6. без поля "github" и при выключенной настройке GitHub не трогаем вовсе
reset(site="slow")
u, ev = client("f")
i = u.check(manual=False)                                    # фоновая: тут и задержка, и медленный сайт
spread = json.loads((tmp / "f" / "updates" / "spread.json").read_text()); spread["at"] = 0
(tmp / "f" / "updates" / "spread.json").write_text(json.dumps(spread))
i = u.check(manual=False)
ok(i is None and not any(h[0] == "gh" for h in HITS) and "медленно" in u.last["error"], f"нет поля «github» — GitHub не тронут: {u.last['error'][:90]}")
LATEST["github"] = f"{BASE}/gh/{NAME}"
reset(site="503")
u, ev = client("g", mirror=False)
ok(u.check() is None and not any(h[0] == "gh" for h in HITS), "updates.mirror_github = false — GitHub не тронут")

# 7. обрыв — докачка с места обрыва
reset(site="cut")
u, ev = client("h")
i = u.check()
resumed = [int(h[1][6:-1]) for h in HITS if h[1]]
ok(i and Path(i["path"]).read_bytes() == DATA and len(HITS) == 2 and resumed and 0 < resumed[0] <= 100_000,
   f"оборвалось — докачано с места обрыва (Range): {HITS}")

# 8. фоновая проверка — случайная задержка 0–6 ч, помнится; ручная — сразу
reset()
u, ev = client("i")
t0 = time.time()
i = u.check(manual=False)
nxt = u.public()["next"]
ok(i is None and not HITS and t0 <= nxt <= t0 + UP.SPREAD + 1, f"фоновая: не качает сразу, а около {time.strftime('%H:%M', time.localtime(nxt))}")
u2, _ = client("i")
u2.check(manual=False)
ok(abs(u2.public()["next"] - nxt) < 1, "после перезапуска — то же время (жребий не перебрасывается)")
ats = set()
for n in range(6):
    x, _ = client(f"r{n}")
    x.check(manual=False); ats.add(round(x.public()["next"]))
ok(len(ats) == 6, "у каждого компьютера своё время")
src = (ROOT / "core/updater.py").read_text(encoding="utf-8")
ok("self.check(manual=False)" in src and "nxt - time.time()" in src, "фоновый цикл проверяет с manual=False и просыпается к своему времени")

# 9. ручная проверка — ответ за секунды, скачивание в фоне с ходом
reset(site="slow")
LATEST.pop("github")
u, ev = client("j")
t0 = time.time()
i = u.check(wait=False)
dt = time.time() - t0
pub = u.public()
ok(i and i.get("downloading") and not i.get("path") and dt < 2 and pub["downloading"]["version"] == "99.2.0",
   f"«Проверить обновления» ответила за {dt:.1f} с, скачивание идёт в фоне")
for _ in range(200):
    if u.available:
        break
    time.sleep(0.05)
pcts = [e["downloading"]["pct"] for e in ev if e and e.get("downloading")]
ok(u.available and Path(u.available["path"]).read_bytes() == DATA and ev[-1].get("available"), "скачалось — событие «Доступна версия»")
ok(len(set(pcts)) >= 3 and max(pcts) > 50 and all(e["downloading"]["from"] == "127.0.0.1" for e in ev if e and e.get("downloading")),
   f"по дороге — ход в процентах и источник: {sorted(set(pcts))[:6]}…")
ok(u.public()["downloading"] is None, "скачалось — хода больше нет")

# 10. publish_update.py: "github" — только если на GitHub тот же файл
gh = tmp / "ghapi"
(gh / "repos/dwr-git/dewiar-app/releases/tags").mkdir(parents=True)
deb = tmp / NAME
deb.write_bytes(DATA)


class G(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.endswith("/v99.2.0"):
            body = json.dumps({"assets": [{"name": NAME, "digest": "sha256:" + GH_SHA[0], "browser_download_url": f"https://github.com/x/{NAME}"}]}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers()


GH_SHA = [SHA]
g = ThreadingHTTPServer(("127.0.0.1", 0), G)
threading.Thread(target=g.serve_forever, daemon=True).start()
penv = dict(os.environ, DWR_GH_API=f"http://127.0.0.1:{g.server_port}")
site = tmp / "site"
r = subprocess.run([sys.executable, str(ROOT / "tools/publish_update.py"), str(deb), str(site)], env=penv, capture_output=True, text=True)
L = json.loads((site / "latest.json").read_text())
ok(L.get("github") == f"https://github.com/x/{NAME}" and "запасной путь на GitHub — есть" in r.stdout, f"publish_update: тот же файл — «github» есть: {r.stdout[-200:]}")
GH_SHA[0] = "0" * 64
r = subprocess.run([sys.executable, str(ROOT / "tools/publish_update.py"), str(deb), str(site)], env=penv, capture_output=True, text=True)
L = json.loads((site / "latest.json").read_text())
ok("github" not in L and "другой файл" in r.stdout, "на GitHub другой файл — «github» нет (программы берут только с сайта)")
r = subprocess.run([sys.executable, str(ROOT / "tools/publish_update.py"), str(deb), str(site), "--no-github"], env=penv, capture_output=True, text=True)
ok("github" not in json.loads((site / "latest.json").read_text()) and "выключен" in r.stdout, "--no-github — без запасного пути")

# 11. виджет: честная подпись с ходом; скачалось по нажатию — ставится
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """window.apiCalls = []; window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => { apiCalls.push([k, ...a]);
  if (k === 'install_update') return Promise.resolve({ ok: true, started: false }); return Promise.resolve(true); } }) };"""
CORE = r"""
(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "update_check") return { current: "0.82.1", available: null, error: "", downloading: { version: "0.82.2", pct: 0, from: "dewiar.pro", manual: true } };
      return {}; };
    setTimeout(() => core.emit("hello", { version: "0.82.1" }), 200); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 300, "height": 420}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("http*://**", lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri()); pg.wait_for_timeout(1500)
    pg.hover("#card"); pg.click("#b-upd"); pg.wait_for_timeout(300)
    ok("Скачиваю 0.82.2 — 0 % (с dewiar.pro)" in pg.inner_text("#upd"), f"сразу после проверки — «Скачиваю…», а не «Проверяю» минутами: {pg.inner_text('#upd')!r}")
    pg.evaluate("core.emit('update', { update: { current: '0.82.1', available: null, downloading: { version: '0.82.2', pct: 45, from: 'GitHub', manual: true } } })")
    pg.wait_for_timeout(200)
    ok(pg.inner_text("#upd").strip() == "Скачиваю 0.82.2 — 45 % (с GitHub)", f"ход: {pg.inner_text('#upd')!r}")
    ok(not [c for c in pg.evaluate("apiCalls") if c[0] == "install_update"], "пока качается — не ставит")
    pg.evaluate("core.emit('update', { update: { current: '0.82.1', available: { version: '0.82.2', path: '/tmp/z.deb' }, downloading: null } })")
    pg.wait_for_timeout(500)
    inst = [c for c in pg.evaluate("apiCalls") if c[0] == "install_update"]
    ok(inst and inst[0][1] == "/tmp/z.deb", f"скачалось по нажатию значка — ставится, как раньше: {inst}")
    # фоновое скачивание (не по нажатию) виджет не показывает — только плашку, когда готово
    pg.reload(); pg.wait_for_timeout(1200)
    pg.evaluate("core.emit('update', { update: { current: '0.82.1', available: null, downloading: { version: '0.82.3', pct: 30, from: 'dewiar.pro', manual: false } } })")
    pg.wait_for_timeout(200)
    ok("Скачиваю" not in pg.inner_text("#upd") or not pg.is_visible("#upd"), "фоновое скачивание — тихо")
    ok(not errs, f"без ошибок на странице: {errs[:3]}")
    b.close()
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok("self.updater.check(wait=False)" in src, "команда update_check не ждёт скачивания")
srv.shutdown(); g.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
