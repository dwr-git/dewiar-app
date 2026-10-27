"""Home Assistant — второй умный дом рядом с Яндексом: подключение по адресу и долгосрочному токену (верный, неверный,
нет связи, не тот адрес), разбор и выполнение «включи свет в спальне», «свет на кухне на 30 процентов», «кондиционер
на 22», «закрой шторы», «запусти сценарий спокойной ночи», «какая температура в спальне»; оба дома сразу — команда идёт
туда, где нашлось устройство; инструмент smart_home list; студия (блок, «Подключить», число устройств, токен не
показывается); токен не попадает в журнал; адрес в своей сети — напрямую, мимо прокси системы. HA — заглушка."""
import asyncio, http.server, json, os, socket, stat, subprocess, sys, tempfile, threading, time
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


from homeassistant import HAHome, Homes, norm_url  # noqa: E402
from smarthome import Home, HomeError, parse  # noqa: E402
from tools import t_smart_home  # noqa: E402

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJkZXdpYXJ0ZXN0In0.c2VjcmV0X3NpZ25hdHVyZV9mb3JfZGV3aWFy"
NOW = "2026-10-27T10:00:00.000000+00:00"                     # значение давно то же (last_updated) …
FRESH = datetime.now(timezone.utc).isoformat()   # … но датчик на связи
STATES = [
    {"entity_id": "light.spalnia_liustra", "state": "off", "last_updated": NOW, "attributes": {
        "friendly_name": "Люстра", "supported_color_modes": ["color_temp"], "min_color_temp_kelvin": 2700,
        "max_color_temp_kelvin": 6500, "color_temp_kelvin": 4000, "brightness": None}},
    {"entity_id": "light.spalnia_nochnik", "state": "off", "last_updated": NOW, "attributes": {"friendly_name": "Ночник", "supported_color_modes": ["onoff"]}},
    {"entity_id": "light.kukhnia", "state": "on", "last_updated": NOW, "attributes": {"friendly_name": "Лампа", "supported_color_modes": ["brightness"], "brightness": 128}},
    {"entity_id": "switch.chainik", "state": "off", "last_updated": NOW, "attributes": {"friendly_name": "Розетка чайника", "device_class": "outlet"}},
    {"entity_id": "climate.kondicioner", "state": "off", "last_updated": NOW, "attributes": {
        "friendly_name": "Кондиционер", "hvac_modes": ["off", "cool", "heat"], "temperature": 24, "current_temperature": 25}},
    {"entity_id": "cover.shtory", "state": "open", "last_updated": NOW, "attributes": {"friendly_name": "Шторы", "supported_features": 15, "current_position": 100}},
    {"entity_id": "sensor.spalnia_temperatura", "state": "22.46", "last_updated": NOW, "last_reported": FRESH, "attributes": {
        "friendly_name": "Датчик спальни Температура", "device_class": "temperature", "unit_of_measurement": "°C"}},
    {"entity_id": "sensor.spalnia_vlazhnost", "state": "41", "last_updated": NOW, "attributes": {
        "friendly_name": "Датчик спальни Влажность", "device_class": "humidity", "unit_of_measurement": "%"}},
    {"entity_id": "sensor.liustra_power", "state": "12.5", "last_updated": NOW, "attributes": {
        "friendly_name": "Люстра Мощность", "device_class": "power", "unit_of_measurement": "W"}},
    {"entity_id": "sensor.firmware", "state": "1.2.3", "attributes": {"friendly_name": "Прошивка"}},
    {"entity_id": "binary_sensor.door", "state": "off", "attributes": {"friendly_name": "Дверь"}},
    {"entity_id": "automation.night", "state": "on", "attributes": {"friendly_name": "Ночь"}},
    {"entity_id": "scene.spokoinoi_nochi", "state": "unknown", "attributes": {"friendly_name": "Спокойной ночи"}},
    {"entity_id": "script.utro", "state": "off", "attributes": {"friendly_name": "Доброе утро"}},
]
AREAS = [{"id": "spalnia", "name": "Спальня", "e": ["light.spalnia_liustra", "light.spalnia_nochnik", "sensor.spalnia_temperatura",
                                                    "sensor.spalnia_vlazhnost", "sensor.liustra_power"]},
         {"id": "kukhnia", "name": "Кухня", "e": ["light.kukhnia", "switch.chainik"]},
         {"id": "gostinaia", "name": "Гостиная", "e": ["climate.kondicioner", "cover.shtory"]}]
POSTS, SEEN = [], []


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _send(self, code, obj, ctype="application/json"):
        b = (json.dumps(obj, ensure_ascii=False) if not isinstance(obj, str) else obj).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def _auth(self):
        SEEN.append(self.headers.get("Authorization", ""))
        if self.headers.get("Authorization") != "Bearer " + TOKEN:
            self._send(401, "401: Unauthorized", "text/plain"); return False
        return True

    def do_GET(self):
        if not self._auth(): return
        if self.path == "/api/": return self._send(200, {"message": "API running."})
        if self.path == "/api/states": return self._send(200, STATES)
        self._send(404, "404: Not Found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        if not self._auth(): return
        if self.path == "/api/template":
            ok_tpl = "areas()" in body.get("template", "") and "area_entities" in body.get("template", "")
            return self._send(200 if ok_tpl else 400, json.dumps(AREAS, ensure_ascii=False) if ok_tpl else "bad", "text/plain")
        if self.path.startswith("/api/services/"):
            POSTS.append((self.path[len("/api/services/"):], body))
            if self.path.endswith("/broken"):
                return self._send(400, {"message": "Service not found."})
            return self._send(200, [])
        self._send(404, "404: Not Found", "text/plain")


class NotHA(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = b"<html>router</html>"; self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


HA_PORT, OTHER_PORT = free(), free()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", HA_PORT), H)
other = http.server.ThreadingHTTPServer(("127.0.0.1", OTHER_PORT), NotHA)
for s in (srv, other):
    threading.Thread(target=s.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{HA_PORT}"

# ---------- адрес и токен ----------
ok(norm_url("homeassistant.local") == "http://homeassistant.local:8123" and norm_url("192.168.1.20:8123/lovelace/0") == "http://192.168.1.20:8123"
   and norm_url("https://my.ui.nabu.casa/") == "https://my.ui.nabu.casa", "адрес: без схемы — http и :8123, путь из браузера отрезан, https — как есть")
import net  # noqa: E402
ok(net._private_host("homeassistant") and net._private_host("homeassistant.local") and net._private_host("192.168.1.20")
   and not net._private_host("my.ui.nabu.casa"), "имя без точки и *.local — своя сеть (как «не использовать прокси для локальных адресов»)")

h = HAHome(tmp / "ha.json")


def err(url, tok):
    try:
        h.connect(url, tok); return ""
    except HomeError as e:
        return str(e)


free_port = free()
e_tok = err(URL, "eyJ" + "x" * 40 + ".bad.token")
e_net = err(f"http://127.0.0.1:{free_port}", TOKEN)
e_not = err(f"http://127.0.0.1:{OTHER_PORT}", TOKEN)
e_fmt = err(URL, "abc")
e_ya = err(URL, "y0_AgAAAAB" + "x" * 40)
e_url = err("", TOKEN)
ok("токен не подходит" in e_tok and "Долгосрочные токены доступа" in e_tok, f"неверный токен — где взять новый: {e_tok}")
ok("нет связи" in e_net and "8123" in e_net, f"нет связи — проверить адрес и порт: {e_net}")
ok("не Home Assistant" in e_not, f"по адресу не HA: {e_not}")
ok("не похоже на токен" in e_fmt and "Яндекса" in e_ya and "адрес" in e_url, f"обрывок, ключ Яндекса, пустой адрес — понятно: {e_fmt} | {e_ya} | {e_url}")
ok(not h.connected() and not (tmp / "ha.json").exists(), "после ошибок не подключён и ничего не сохранено")
try:
    Home(tmp / "ya.json").connect(TOKEN); e_y = ""
except HomeError as e:
    e_y = str(e)
ok("Home Assistant" in e_y, f"токен HA вставили в поле Яндекса — подсказка, куда его: {e_y}")

# прокси системы (переменные окружения) — к своему HA всё равно напрямую
saved = {k: os.environ.get(k) for k in ("HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy")}
os.environ["HTTP_PROXY"] = os.environ["http_proxy"] = f"http://127.0.0.1:{free_port}"
for k in ("NO_PROXY", "no_proxy"):
    os.environ.pop(k, None)
try:
    pub = h.connect(" " + URL + "/lovelace/0 ", "Bearer " + TOKEN)
except HomeError as e:
    pub = {"error": str(e)}
for k, v in saved.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v
ok(pub.get("connected") and pub.get("url") == URL, f"подключён, хотя в окружении прокси, которого нет (адрес в своей сети — напрямую): {pub.get('error', '')}")
ok(len(pub.get("devices", [])) == 6 and len(pub.get("rooms", [])) == 3 and pub.get("scenarios") == ["Спокойной ночи", "Доброе утро"]
   and len(pub.get("sensors", [])) == 3, f"видно: 6 устройств, 3 комнаты, 2 сценария, 3 датчика — {len(pub.get('devices', []))}/{pub.get('rooms')}/{pub.get('scenarios')}")
ok(TOKEN not in json.dumps(pub) and "token" not in pub, "студии токен не отдаётся")
mode = stat.S_IMODE(os.stat(tmp / "ha.json").st_mode)
ok(os.name == "nt" or mode == 0o600, f"файл с токеном — только владельцу (0600): {oct(mode)}")

# ---------- на свои устройства (engine_tools.own_snapshot: «ha» — конвертом, как ключ Яндекса) ----------
sh = h.share()
h2 = HAHome(tmp / "ha2.json")
took = h2.adopt(sh["url"], sh["token"], sh["at"])
again = h2.adopt(sh["url"], sh["token"], sh["at"])
older = h2.adopt("http://10.0.0.9:8123", TOKEN, sh["at"] - 1000)
ok(took and h2.connected() and h2.data["url"] == URL and not again and not older, "другой свой компьютер берёт адрес и токен; старое и то же — не берёт")
ok(h2.adopt("", "", sh["at"] + 1) and not h2.connected(), "отключили там позже — отключился и здесь")

# ---------- кого имели в виду и что ушло в HA ----------
m = lambda q: sorted(d["id"] for d in h.match(q))  # noqa: E731
cases = {"свет в спальне": ["light.spalnia_liustra", "light.spalnia_nochnik"], "люстру": ["light.spalnia_liustra"],
         "весь свет": ["light.kukhnia", "light.spalnia_liustra", "light.spalnia_nochnik"], "кондиционер": ["climate.kondicioner"],
         "шторы": ["cover.shtory"], "розетку чайника": ["switch.chainik"], "свет на кухне": ["light.kukhnia"], "музыку": [], "компьютер": []}
bad = {q: m(q) for q, v in cases.items() if m(q) != v}
ok(not bad, "поиск как у Яндекса: по названию, по типу, по комнате; датчик мощности люстры — не люстра" + (f" — ошибки: {bad}" if bad else ""))


def run(text):
    c = parse(text)
    POSTS.clear()
    if c["op"] == "scenario":
        h.run_scenario(h.scenario(c["target"]))
    else:
        h.act(h.match(c["target"]), c["op"], c.get("value"))
    return list(POSTS)


p = run("включи свет в спальне")
ok(p == [("light/turn_on", {"entity_id": ["light.spalnia_liustra", "light.spalnia_nochnik"]})], f"«включи свет в спальне» — одна служба на обе лампы: {p}")
p = run("свет на кухне на 30 процентов")
ok(p == [("light/turn_on", {"entity_id": "light.kukhnia", "brightness_pct": 30})], f"«свет на кухне на 30 процентов» — brightness_pct: {p}")
p = run("кондиционер на 22")
ok(p == [("climate/turn_on", {"entity_id": "climate.kondicioner"}), ("climate/set_temperature", {"entity_id": "climate.kondicioner", "temperature": 22})],
   f"«кондиционер на 22» — включить и 22°: {p}")
p = run("закрой шторы")
ok(p == [("cover/close_cover", {"entity_id": "cover.shtory"})], f"«закрой шторы» — close_cover: {p}")
p = run("сделай люстру теплее")
ok(p == [("light/turn_on", {"entity_id": "light.spalnia_liustra", "color_temp_kelvin": 3200})], f"«теплее» — color_temp_kelvin −800: {p}")
p = run("запусти сценарий спокойной ночи")
ok(p == [("scene/turn_on", {"entity_id": "scene.spokoinoi_nochi"})], f"сценарий — сцена: {p}")
p = run("запусти сценарий доброе утро")
ok(p == [("script/turn_on", {"entity_id": "script.utro"})], f"сценарий — скрипт: {p}")
found, vals = h.readings("в спальне", "temperature")
ok(found and vals and vals[0]["value"] == 22.46 and vals[0]["device"] == "Датчик спальни Температура", f"температура в спальне — с датчика: {vals[:1]}")
found, vals = h.readings("в гостиной", "temperature")
ok(found and vals and vals[0]["value"] == 25, "в гостиной датчика нет — знает кондиционер (current_temperature)")
ok(h.readings("в москве", "temperature") == (False, []), "«в Москве» — не дом")

# ---------- оба дома ----------
YI = {"rooms": [{"id": "r1", "name": "Детская"}], "groups": [],
      "devices": [{"id": "y1", "name": "Лампа", "room": "r1", "type": "devices.types.light",
                   "capabilities": [{"type": "devices.capabilities.on_off", "state": {"instance": "on", "value": False}}]}],
      "scenarios": [{"id": "ys", "name": "Кино", "is_active": True}]}
YP = []
y = Home(tmp / "ya.json")
y.data = {"token": "y0_test_token_0123456789abcdef"}


def y_req(method, path, body=None):
    if path == "/user/info":
        return json.loads(json.dumps(YI))
    YP.append((path, body))
    return {"status": "ok", "devices": []}


y._req = y_req
both = Homes(h, y)
info = both.info()
own = lambda q: sorted((d["_home"].NAME, d["id"]) for d in both.match(q, info))  # noqa: E731
ok(own("свет в детской") == [("Умный дом Яндекса", "y1")], f"«свет в детской» — комната есть только у Яндекса: {own('свет в детской')}")
ok([x[0] for x in own("свет в спальне")] == ["Home Assistant"] * 2, "«свет в спальне» — в Home Assistant")
ok({x[0] for x in own("весь свет")} == {"Home Assistant", "Умный дом Яндекса"} and len(own("весь свет")) == 4, "«весь свет» — в обоих домах")
POSTS.clear(); YP.clear()
n = both.act(both.match("весь свет", info), "off")
ok(n == 4 and POSTS and POSTS[0][0] == "light/turn_off" and YP and YP[0][0] == "/devices/actions", f"«выключи весь свет» — каждому дому своё: {n}, {POSTS}, {YP}")
sc = both.scenario("кино", info)
ok(sc and sc["_home"] is y and both.run_scenario(sc) == "Кино" and YP[-1][0] == "/scenarios/ys/actions", "сценарий «Кино» — у Яндекса")
summ = t_smart_home({"action": "list"}, {"home": both})
ok("Home Assistant:" in summ and "Умный дом Яндекса:" in summ and "Датчик спальни Температура (Спальня) — температура 22,5°" in summ
   and "Спокойной ночи" in summ, f"smart_home list — оба дома с показаниями: {summ[:200]}")
ok("Готово" in t_smart_home({"action": "on", "target": "свет в детской"}, {"home": both}), "smart_home on — в дом, где нашлось")
summ1 = t_smart_home({"action": "list"}, {"home": Homes(h, Home(tmp / "none.json"))})
ok(summ1.startswith("Устройства:") and "Люстра (Спальня) — выкл" in summ1, f"только HA — список как у Яндекса: {summ1[:120]}")

# ---------- ядро: студия, голос, журнал ----------
import websockets  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
PORT, LLM_PORT = free(), free()
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "ui": {"news_seen": "99.0.0", "welcome": "done"}, "updates": {"auto_check": False},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"),
           NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)])
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(200):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
R = {}
SHOTS = os.environ.get("DEWIAR_SHOTS")
try:
    errs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(); pg = b.new_page(viewport={"width": 1300, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="connect"]'); time.sleep(1)
        ok(pg.is_visible("#ha-box") and pg.is_visible("#ha-url") and pg.is_visible("#ha-token") and "Долгосрочные токены доступа" in pg.inner_text("#ha-box"),
           "студия: блок «Home Assistant» — адрес, токен и где его взять")
        ok(pg.get_attribute("#ha-token", "type") == "password", "поле токена — скрытое")
        pg.fill("#ha-url", URL); pg.fill("#ha-token", "eyJ" + "q" * 30 + ".wrong.token"); pg.click("#ha-go")
        pg.wait_for_function("document.querySelector('#ha-res').className.includes('bad')", timeout=15000)
        ok("токен не подходит" in pg.inner_text("#ha-res") and pg.is_visible("#ha-setup"), f"студия: неверный токен — понятно: {pg.inner_text('#ha-res')}")
        pg.fill("#ha-token", TOKEN); pg.click("#ha-go")
        pg.wait_for_function("document.querySelector('#ha-on').style.display !== 'none'", timeout=15000)
        st = pg.inner_text("#ha-state")
        ok("устройств 6" in st and "комнат 3" in st and "сценариев 2" in st and "датчиков 3" in st, f"студия: после «Подключить» — сколько найдено: {st}")
        chips = pg.inner_text("#ha-devs")
        ok("Люстра" in chips and "Спальня" in chips and "Спокойной ночи" in chips and "22,5°" in chips, "студия: устройства с комнатами, датчики, сценарии")
        ok(pg.input_value("#ha-token") == "" and TOKEN not in pg.content(), "студия: токена на странице нет — поле очищено")
        if SHOTS:
            pg.evaluate("document.querySelector('#ha-box').scrollIntoView()"); time.sleep(0.3)
            pg.screenshot(path=os.path.join(SHOTS, "ha-studio.png"))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="connect"]'); time.sleep(1)
        ok(pg.is_visible("#ha-on") and "устройств 6" in pg.inner_text("#ha-state"), "студия: открыли заново — подключён (ha_get)")
        b.close()
    ok(not errs, f"студия без ошибок страницы: {errs[:3]}")

    async def go():
        async with websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None) as w:
            await w.send(json.dumps({"cmd": "hello", "token": tok}))
            n, events, replies = [0], [], {}

            async def reader():
                async for raw in w:
                    e = json.loads(raw)
                    if e["type"] == "reply":
                        replies[e["id"]] = e
                    elif e["type"] != "level":
                        events.append(e)
            rd = asyncio.ensure_future(reader())

            async def call(cmd, **a):
                n[0] += 1; i = n[0]
                await w.send(json.dumps({"id": i, "cmd": cmd, "args": a}))
                for _ in range(600):
                    if i in replies:
                        return replies.pop(i)
                    await asyncio.sleep(0.05)

            async def say(text, pred, limit=8):
                events.clear(); POSTS.clear()
                await call("say", text=text)
                end = time.monotonic() + limit
                while time.monotonic() < end:
                    for e in events:
                        if e["type"] == "answer" and pred(e.get("text", "")):
                            return e["text"], list(POSTS)
                    await asyncio.sleep(0.1)
                return None, list(POSTS)
            await asyncio.sleep(1)
            R["get"] = (await call("ha_get"))["data"]
            R["on"] = await say("Включи свет в спальне", lambda t: "Включил" in t)
            R["br"] = await say("Свет на кухне на 30 процентов", lambda t: "30%" in t)
            R["ac"] = await say("Кондиционер на 22", lambda t: "22°" in t)
            R["sc"] = await say("Запусти сценарий спокойной ночи", lambda t: "Спокойной ночи" in t)
            R["temp"] = await say("Какая температура в спальне?", lambda t: "22,5" in t)
            R["tools"] = [t["name"] for t in (await call("tools"))["data"] if t.get("enabled")]
            R["bad"] = await call("ha_connect", url=f"http://127.0.0.1:{free_port}", token=TOKEN)
            R["off"] = (await call("ha_forget"))["data"]
            R["tools_off"] = [t["name"] for t in (await call("tools"))["data"] if t.get("enabled")]
            rd.cancel()
    asyncio.run(go())
finally:
    for p in (core, mock):
        p.terminate()
    core.wait()
    srv.shutdown(); other.shutdown()

g = R.get("get") or {}
ok(g.get("connected") and TOKEN not in json.dumps(g), "ha_get — подключён, без токена")
ok(R.get("on", (None,))[0] and ("light/turn_on", {"entity_id": ["light.spalnia_liustra", "light.spalnia_nochnik"]}) in R["on"][1],
   f"голосом без модели: «Включи свет в спальне» — {R.get('on', (None,))[0]}")
ok(R.get("br", (None,))[0] and ("light/turn_on", {"entity_id": "light.kukhnia", "brightness_pct": 30}) in R["br"][1], f"«Свет на кухне на 30 процентов» — {R.get('br', (None,))[0]}")
ok(R.get("ac", (None,))[0] and ("climate/set_temperature", {"entity_id": "climate.kondicioner", "temperature": 22}) in R["ac"][1], f"«Кондиционер на 22» — {R.get('ac', (None,))[0]}")
ok(R.get("sc", (None,))[0] and ("scene/turn_on", {"entity_id": "scene.spokoinoi_nochi"}) in R["sc"][1], f"«Запусти сценарий спокойной ночи» — {R.get('sc', (None,))[0]}")
ok((R.get("temp", (None,))[0] or "").startswith("В спальне 22,5°") and "давно" not in R["temp"][0],
   f"«Какая температура в спальне?» — без «давно не присылал» (last_reported свежий): {R.get('temp', (None,))[0]}")
ok("smart_home" in (R.get("tools") or []) and "smart_home" not in (R.get("tools_off") or ["smart_home"]),
   "инструмент smart_home есть, пока подключён HA (и только Яндекс не нужен); отключили — пропал")
ok(not (R.get("bad") or {}).get("ok", True) and "нет связи" in str((R.get("bad") or {}).get("error")), f"ha_connect без связи — ошибка словами: {(R.get('bad') or {}).get('error')}")
ok(R.get("off", {}).get("connected") is False, "«Отключить» — отключён")
logtxt = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
for f in (tmp / "st").rglob("*.log*"):
    logtxt += f.read_text(encoding="utf-8", errors="replace")
ok("Home Assistant подключён" in logtxt and TOKEN not in logtxt and TOKEN[-20:] not in logtxt, "в журнале — что подключён, но не токен")
ok(all(x in ("Bearer " + TOKEN,) or "wrong" in x or "bad" in x for x in SEEN), "токен уходит только в заголовке Authorization к своему HA")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
