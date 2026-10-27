"""Умный дом Яндекса: подключение по ключу, разбор фраз и поиск устройств («свет в спальне» — обе лампы спальни,
«весь свет», «торшер», «кондиционер на 22», «свет на кухне на 30 процентов», сценарий), голосом без модели;
«включи музыку» и «выключи компьютер» — не умный дом; ключ без прав — понятная ошибка. Яндекс — заглушка."""
import asyncio, http.server, json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp())
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
sys.path.insert(0, str(ROOT / "core"))
IOT = 8159
os.environ["DEWIAR_YANDEX_IOT"] = f"http://127.0.0.1:{IOT}/v1.0"
from smarthome import Home, parse, HomeError  # noqa: E402

ONOFF = {"type": "devices.capabilities.on_off", "state": {"instance": "on", "value": False}}
BR = {"type": "devices.capabilities.range", "parameters": {"instance": "brightness"}, "state": {"instance": "brightness", "value": 60}}
TEMP = {"type": "devices.capabilities.range", "parameters": {"instance": "temperature"}, "state": {"instance": "temperature", "value": 24}}
CT = {"type": "devices.capabilities.color_setting", "parameters": {"temperature_k": {"min": 2700, "max": 6500}}, "state": {"instance": "temperature_k", "value": 4500}}
INFO = {"status": "ok", "rooms": [{"id": "r1", "name": "Спальня"}, {"id": "r2", "name": "Кухня"}, {"id": "r3", "name": "Гостиная"}],
        "devices": [
            {"id": "d1", "name": "Люстра", "room": "r1", "type": "devices.types.light", "capabilities": [ONOFF, BR]},
            {"id": "d2", "name": "Ночник", "room": "r1", "type": "devices.types.light", "capabilities": [ONOFF]},
            {"id": "d3", "name": "Лампа", "room": "r2", "type": "devices.types.light", "capabilities": [ONOFF, BR]},
            {"id": "d4", "name": "Розетка чайника", "room": "r2", "type": "devices.types.socket", "capabilities": [ONOFF]},
            {"id": "d5", "name": "Кондиционер", "room": "r3", "type": "devices.types.thermostat.ac", "capabilities": [ONOFF, TEMP]},
            {"id": "d6", "name": "Торшер", "room": "r3", "type": "devices.types.light", "capabilities": [ONOFF, BR, CT]},
            {"id": "d7", "name": "Яндекс Станция", "room": "r3", "type": "devices.types.media_device.smart_speaker", "capabilities": []},
            {"id": "d8", "name": "Датчик климата", "room": "r1", "type": "devices.types.sensor.climate", "capabilities": [], "properties": [
                {"type": "devices.properties.float", "parameters": {"instance": "temperature", "unit": "unit.temperature.celsius"},
                 "state": {"instance": "temperature", "value": 22.46}, "last_updated": time.time() - 60},
                {"type": "devices.properties.float", "parameters": {"instance": "humidity", "unit": "unit.percent"},
                 "state": {"instance": "humidity", "value": 41}, "last_updated": time.time() - 60}]}],
        "groups": [], "scenarios": [{"id": "s1", "name": "Спокойной ночи", "is_active": True}]}
POSTS = []


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _j(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        tok = self.headers.get("Authorization", "")
        if tok.endswith("noscope_token_0123456789abcdef"): return self._j(403, {"status": "error", "message": "forbidden"})
        if not tok.endswith("good_token_0123456789abcdef"): return self._j(401, {"status": "error"})
        if self.path == "/v1.0/user/info": return self._j(200, INFO)
        self._j(404, {})
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        POSTS.append((self.path, body))
        if self.path == "/v1.0/devices/actions":
            return self._j(200, {"status": "ok", "devices": [{"id": d["id"], "capabilities": [{"type": a["type"], "state": {"instance": a["state"]["instance"], "action_result": {"status": "DONE"}}} for a in d["actions"]]} for d in body["devices"]]})
        self._j(200, {"status": "ok"})


srv = http.server.ThreadingHTTPServer(("127.0.0.1", IOT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["NO_PROXY"] = os.environ["no_proxy"] = "127.0.0.1,localhost"

h = Home(tmp / "sh.json")
errs = []
for t in ("", "bd46169129964deea1f608cf45f7122a", "abc"):
    try:
        h.connect(t); errs.append("")
    except HomeError as e:
        errs.append(str(e))
ok("Получить ключ" in errs[0] and "ClientID" in errs[1] and "y0_" in errs[1] and "y0_" in errs[2] and not h.connected(),
   f"пусто, ClientID вместо ключа, обрывок — понятно, что делать: {errs}")
ok("client_id=bd46169129964deea1f608cf45f7122a" in h.public()["auth_url"], "«Получить ключ» сразу ведёт в общее приложение Dewiar — своё создавать не нужно")
try:
    h.connect("noscope_token_0123456789abcdef"); e1 = ""
except HomeError as e:
    e1 = str(e)
ok("iot:control" in e1 and not h.connected(), f"ключ без прав — понятная ошибка: {e1}")
pub = h.connect("https://oauth.yandex.ru/verification_code#access_token=good_token_0123456789abcdef&token_type=bearer")
ok(pub["connected"] and len(pub["devices"]) == 8 and "Спокойной ночи" in pub["scenarios"], "вставили всю ссылку после входа — ключ найден, устройства и сценарии видны")
m = lambda q: sorted(d["id"] for d in h.match(q))
cases = {"свет в спальне": ["d1", "d2"], "весь свет": ["d1", "d2", "d3", "d6"], "торшер": ["d6"], "люстру": ["d1"],
         "кондиционер": ["d5"], "свет на кухне": ["d3"], "розетку чайника": ["d4"], "музыку": [], "компьютер": []}
bad = {q: m(q) for q, v in cases.items() if m(q) != v}
ok(not bad, "кого имели в виду: свет в спальне — обе лампы спальни, весь свет, торшер, кондиционер; музыка — не дом" + (f" — ошибки: {bad}" if bad else ""))
h.act(h.match("свет в спальне"), "on")
ok(POSTS[-1][1]["devices"][0]["actions"][0]["state"] == {"instance": "on", "value": True} and len(POSTS[-1][1]["devices"]) == 2, "«включи» → on для двух ламп")
h.act(h.match("торшер"), "warm", -1)
ok(POSTS[-1][1]["devices"][0]["actions"][0]["state"]["instance"] == "temperature_k" and POSTS[-1][1]["devices"][0]["actions"][0]["state"]["value"] == 3700, "«теплее» — цветовая температура −800 K")

import websockets  # noqa: E402
PORT, LLM_PORT = 8825, 8155
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)])
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
events, R = [], {}


async def run():
    ws_ = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try: ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError: continue
    await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    n = [0]; replies = {}
    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws_.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies: return replies.pop(i)
            await asyncio.sleep(0.05)
    async def wait_for(pred, limit):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            for e in events:
                if pred(e): return e
            await asyncio.sleep(0.1)
    async def reader():
        async for raw in ws_:
            e = json.loads(raw)
            if e["type"] == "reply": replies[e["id"]] = e
            elif e["type"] != "level": events.append(e)
    rd = asyncio.ensure_future(reader())
    await asyncio.sleep(2)
    R["conn"] = (await call("home_connect", token="good_token_0123456789abcdef"))["data"]
    POSTS.clear()
    await call("say", text="Включи свет в спальне")
    R["on"] = await wait_for(lambda e: e["type"] == "answer" and "Включил" in e.get("text", ""), 8)
    events.clear()
    await call("say", text="Свет на кухне на 30 процентов")
    R["br"] = await wait_for(lambda e: e["type"] == "answer" and "30%" in e.get("text", ""), 8)
    events.clear()
    await call("say", text="Кондиционер на 22")
    R["ac"] = await wait_for(lambda e: e["type"] == "answer" and "22°" in e.get("text", ""), 8)
    events.clear()
    await call("say", text="Запусти сценарий спокойной ночи")
    R["sc"] = await wait_for(lambda e: e["type"] == "answer" and "Спокойной ночи" in e.get("text", ""), 8)
    events.clear()
    await call("say", text="Какая температура в спальне?")
    R["temp"] = await wait_for(lambda e: e["type"] == "answer" and "22,5" in e.get("text", ""), 8)
    events.clear()
    await call("say", text="Сколько градусов на кухне")
    R["notemp"] = await wait_for(lambda e: e["type"] == "answer" and "нет датчика" in e.get("text", ""), 8)
    events.clear()
    await call("say", text="Какая температура в Москве?")
    await asyncio.sleep(3)
    R["moscow"] = [e.get("text", "") for e in events if e["type"] == "answer"]
    events.clear()
    await call("say", text="Выключи компьютер")
    R["pc"] = await wait_for(lambda e: e["type"] == "power", 6)
    await call("say", text="Отмени выключение")
    await asyncio.sleep(1)
    R["tools"] = [t["name"] for t in (await call("tools"))["data"] if t.get("enabled")]
    R["phone"] = (await call("phone_config"))["data"]
    R["homeqr"] = (await call("phone_home"))["data"]
    rd.cancel()

try:
    asyncio.run(run())
finally:
    for p in (core, mock):
        p.terminate()
    core.wait()
    srv.shutdown()
paths = [p for p, _ in POSTS]
ok(R.get("conn", {}).get("connected") and R.get("on") and "/v1.0/devices/actions" in paths, f"«включи свет в спальне» — сразу, без модели: {R.get('on', {}).get('text')}")
ok(R.get("br") and R.get("ac") and R.get("sc") and "/v1.0/scenarios/s1/actions" in paths, "яркость, кондиционер, сценарий — голосом")
ok(R.get("temp") and R["temp"]["text"].startswith("В спальне 22,5°"), f"«какая температура в спальне» — датчик, без модели (№362): {(R.get('temp') or {}).get('text')}")
ok(R.get("notemp") is not None, f"в комнате нет датчика — так и сказать: {(R.get('notemp') or {}).get('text')}")
ok(not any("датчик" in x for x in R.get("moscow", [])), f"«температура в Москве» — не умный дом: {R.get('moscow')}")
ok(R.get("pc") is not None, "«выключи компьютер» — это компьютер, а не умный дом")
ok("smart_home" in (R.get("tools") or []), "у модели появился инструмент «Умный дом» (для сложных просьб)")
import base64  # noqa: E402
ph = R.get("phone") or {}
c = ph.get("url", "").split("c=", 1)[-1]
d = json.loads(base64.urlsafe_b64decode(c + "=" * (-len(c) % 4)).decode()) if c else {}
ok(d.get("llm", {}).get("profiles", {}).get("p", {}).get("model") == "chat" and d.get("home", {}).get("token") == "good_token_0123456789abcdef"
   and ph.get("apk", "").endswith("/Dewiar.apk") and ph.get("lan"), "QR для телефона: мозг и умный дом этого компьютера, ссылка на приложение")
hq = (R.get("homeqr") or {}).get("url", "").split("c=", 1)[-1]
dh = json.loads(base64.urlsafe_b64decode(hq + "=" * (-len(hq) % 4)).decode()) if hq else {}
ok(dh == {"dewiar": 1, "home": {"token": "good_token_0123456789abcdef"}}, f"«На телефон»: в коде только умный дом, без мозга и ключей: {sorted(dh)}")

