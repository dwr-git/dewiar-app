"""Радио как у колонки: пока играет, одно слово без имени — «громче», «тише», «дальше»; с именем — «давай дальше»,
«громче» (меняется громкость самого радио, а не системы). Ничего не играет — слова без имени ничего не делают."""
import asyncio, http.server, json, os, shutil, socket, subprocess, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
tmp = Path(tempfile.mkdtemp())
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
ff = shutil.which("ffmpeg")
if not ff or not shutil.which("espeak-ng"):
    print("нет ffmpeg/espeak-ng — пропускаю"); print("ALL OK"); sys.exit(0)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from vosk_have import skip_without_vosk  # noqa: E402
skip_without_vosk(ROOT)                                 # «тише», «следующую» из WAV слышит модель Vosk
www = tmp / "www"; www.mkdir()
subprocess.run([ff, "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=120", "-ac", "1", "-b:a", "64k",
                str(www / "a.mp3")], check=True)
s = socket.socket(); s.bind(("127.0.0.1", 0)); WP = s.getsockname()[1]; s.close()


class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/radio.json"):
            b = json.dumps({"genres": ["джаз"], "stations": [
                {"name": "Jazz One", "url": f"http://127.0.0.1:{WP}/a.mp3?1", "tags": "джаз"},
                {"name": "Jazz Two", "url": f"http://127.0.0.1:{WP}/a.mp3?2", "tags": "джаз"}]}, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b); return
        self.path = self.path.split("?")[0]
        return super().do_GET()


srv = http.server.ThreadingHTTPServer(("127.0.0.1", WP), lambda *a, **k: H(*a, directory=str(www), **k))
threading.Thread(target=srv.serve_forever, daemon=True).start()

# запись микрофона: 14 с тишины (успеваем включить радио) → «тише» → 5 с → «следующую» → 30 с
# («дальше» голосом espeak Vosk не узнаёт — синтезатор произносит его слишком нечётко; живой голос — да)
words = {}
for w in ("тише", "следующую"):
    subprocess.run(["espeak-ng", "-v", "ru", "-s", "140", "-w", str(tmp / f"{w}.raw.wav"), w], check=True)
    subprocess.run([ff, "-loglevel", "error", "-y", "-i", str(tmp / f"{w}.raw.wav"), "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
                    str(tmp / f"{w}.wav")], check=True)
import wave  # noqa: E402
def pcm(p):
    with wave.open(str(p)) as w: return w.readframes(w.getnframes())
sil = lambda sec: b"\0\0" * int(16000 * sec)
with wave.open(str(tmp / "mic.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(sil(14) + pcm(tmp / "тише.wav") + sil(5) + pcm(tmp / "следующую.wav") + sil(30))

import websockets  # noqa: E402
PORT = 8811
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False, "follow_up_seconds": 0},
    "workspace": {"path": str(tmp / "ws")}, "radio_url": f"http://127.0.0.1:{WP}/radio.json", "ui": {"welcome": "done"}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_RADIO_API=f"http://127.0.0.1:{WP}", DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(tmp / "mic.wav"), "--null-audio"] + (["--debug"] if os.environ.get("DBG") else []), env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
R, events = {}, []


async def run():
    ws = None
    for _ in range(300):
        await asyncio.sleep(0.2)
        if (tmp / "cfg/token").exists():
            try: ws = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
            except OSError: continue
    await ws.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
    n = [0]; replies = {}
    async def call(cmd, **args):
        n[0] += 1; i = n[0]; await ws.send(json.dumps({"id": i, "cmd": cmd, "args": args}))
        for _ in range(600):
            if i in replies: return replies.pop(i)
            await asyncio.sleep(0.05)
    async def reader():
        async for raw in ws:
            e = json.loads(raw)
            if e["type"] == "reply": replies[e["id"]] = e
            elif e["type"] != "level": events.append(e)
    rd = asyncio.ensure_future(reader())
    t0 = None
    for _ in range(300):                                   # слух запущен — запись пошла
        st = await call("status")
        if ((st or {}).get("data") or {}).get("input"): t0 = time.monotonic(); break
        await asyncio.sleep(0.2)
    for _ in range(60):
        lst = (await call("radio_list"))["data"]
        if any(x["name"] == "Jazz One" for x in lst["stations"]): break
        await asyncio.sleep(0.25)
    await call("say", text="Включи радио Jazz One")
    for _ in range(60):
        R["on"] = (await call("radio_status"))["data"]
        if R["on"]["playing"]: break
        await asyncio.sleep(0.25)
    R["on_t"] = time.monotonic() - (t0 or time.monotonic())
    # голосом без имени: «тише» (~14 с записи), «следующую» (~20 с)
    await asyncio.sleep(max(0, 18 - (time.monotonic() - t0)))
    R["quiet"] = (await call("radio_status"))["data"]
    await asyncio.sleep(max(0, 27 - (time.monotonic() - t0)))
    R["next"] = (await call("radio_status"))["data"]
    # текстом, как после имени
    await call("say", text="Громче"); await asyncio.sleep(1)
    R["loud"] = (await call("radio_status"))["data"]
    await call("say", text="Давай дальше"); await asyncio.sleep(3)
    R["next2"] = (await call("radio_status"))["data"]
    await call("say", text="Стоп"); await asyncio.sleep(1.5)
    R["paused"] = (await call("radio_status"))["data"]
    await call("say", text="Дальше"); await asyncio.sleep(3)
    R["next3"] = (await call("radio_status"))["data"]
    rd.cancel()

try:
    asyncio.run(run())
finally:
    core.terminate(); core.wait(); srv.shutdown()
dry = (tmp / "dry.jsonl").read_text(encoding="utf-8") if (tmp / "dry.jsonl").exists() else ""
saved = json.loads((tmp / "cfg/settings.json").read_text()).get("audio", {}).get("radio_volume")
ok(R.get("on", {}).get("playing"), f"радио играет ({R.get('on', {}).get('station')}, через {R.get('on_t', 0):.1f} с)")
ok(R.get("quiet", {}).get("volume") == 0.6, f"«тише» без имени — радио тише ({R.get('quiet', {}).get('volume')})")
ok(R.get("next", {}).get("playing") and R["next"]["station"] != R["on"]["station"], f"«следующую» без имени — другая станция ({R.get('next', {}).get('station')})")
ok(R.get("loud", {}).get("volume") == 0.8 and '"volume"' not in dry, f"«громче» при радио — громче само радио, система не тронута ({R.get('loud', {}).get('volume')})")
ok(R.get("next2", {}).get("playing") and R["next2"]["station"] != R["next"]["station"], f"«давай дальше» — ещё одна станция ({R.get('next2', {}).get('station')})")
ok(R.get("paused", {}).get("paused") and R.get("next3", {}).get("playing") and R["next3"]["station"] != R["paused"]["paused"],
   f"на паузе «дальше» — следующая станция, а не та же ({R.get('paused', {}).get('paused')} → {R.get('next3', {}).get('station')})")
ok(saved == 0.8, f"громкость радио запомнена ({saved})")
