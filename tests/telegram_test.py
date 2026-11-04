"""Telegram: подключение бота, код владельца, чужие не проходят, вопрос текстом/голосом/файлом, подтверждение кнопками,
файл из папки ассистента, напоминание и уведомление приходят в Telegram. Telegram — поддельный (DEWIAR_TG_API)."""
import asyncio, json, os, re, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
PY = os.environ.get("DEWIAR_PY") or sys.executable
TESTS = Path(__file__).resolve().parent
A = Path(os.environ.get("DEWIAR_TEST_AUDIO", "/tmp/dewiar-test-audio"))
tmp = Path(tempfile.mkdtemp())
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
import websockets  # noqa: E402
PORT, LLM_PORT, TG_PORT = 8806, 8136, 8977
TOKEN = "123456789:AAHfakeTokenForDewiarTests_abcdefghijk"
OWNER, STRANGER = 501, 777

# ---------- поддельный Telegram ----------
class TG:
    updates, sent, files, lock, uid = [], [], {}, threading.Lock(), [100]

    @classmethod
    def push(cls, frm, text=None, **extra):
        with cls.lock:
            cls.uid[0] += 1
            m = {"message_id": cls.uid[0], "chat": {"id": frm, "type": "private"},
                 "from": {"id": frm, "first_name": "Анна" if frm == OWNER else "Чужой", "username": f"u{frm}"}, "date": int(time.time())}
            if text is not None:
                m["text"] = text
            m.update(extra)
            cls.updates.append({"update_id": cls.uid[0], "message": m})

    @classmethod
    def callback(cls, frm, data):
        with cls.lock:
            cls.uid[0] += 1
            cls.updates.append({"update_id": cls.uid[0], "callback_query": {"id": str(cls.uid[0]), "from": {"id": frm}, "data": data}})


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def out(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        m = re.match(r"/file/bot([^/]+)/(.+)", self.path)
        if m and m.group(1) == TOKEN and m.group(2) in TG.files:
            b = TG.files[m.group(2)]
            self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        self.out(404, {"ok": False})

    def do_POST(self):
        m = re.match(r"/bot([^/]+)/(\w+)", self.path)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        if not m or m.group(1) != TOKEN:
            return self.out(401, {"ok": False, "error_code": 401, "description": "Unauthorized"})
        meth = m.group(2)
        ctype = self.headers.get("Content-Type", "")
        params = json.loads(raw or b"{}") if "json" in ctype else {"_multipart": True, "_size": len(raw),
                                                                     "_names": re.findall(rb'filename="([^"]+)"', raw)}
        if meth == "getMe":
            return self.out(200, {"ok": True, "result": {"id": 1, "is_bot": True, "first_name": "Девиар", "username": "dewiar_test_bot"}})
        if meth == "getUpdates":
            off = params.get("offset", 0)
            end = time.time() + min(2, params.get("timeout", 0))
            while time.time() < end:
                with TG.lock:
                    got = [u for u in TG.updates if u["update_id"] >= off]
                if got:
                    break
                time.sleep(0.05)
            return self.out(200, {"ok": True, "result": got})
        if meth == "getFile":
            return self.out(200, {"ok": True, "result": {"file_id": params["file_id"], "file_path": params["file_id"]}})
        with TG.lock:
            TG.sent.append((meth, params))
        return self.out(200, {"ok": True, "result": {"message_id": 1}})


srv = ThreadingHTTPServer(("127.0.0.1", TG_PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

# ---------- ядро ----------
(tmp / "cfg").mkdir()
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "dewiar", "stt": {"engine": "vosk"}, "tts": {"engine": "espeak"}, "audio": {"sounds": False, "follow_up_seconds": 6},
    "llm": {"active": "m", "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM_PORT}/v1", "model": "chat"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT),
           DEWIAR_ASSUME_AEC="1", DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_TG_API=f"http://127.0.0.1:{TG_PORT}")
sil = TESTS / "silence90.wav"
if not sil.exists():
    import wave
    with wave.open(str(sil), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 16000 * 90)
voice = (A / "d.ogg").read_bytes() if (A / "d.ogg").exists() else None   # готовое (Windows без ffmpeg в PATH)
import shutil  # noqa: E402
if voice is None and (A / "d.wav").exists() and shutil.which("ffmpeg"):
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(A / "d.wav"), "-c:a", "libopus", "-f", "ogg", "pipe:1"], capture_output=True)
    voice = r.stdout if r.returncode == 0 and r.stdout else None
sys.path.insert(0, str(TESTS))
from vosk_have import vosk_missing  # noqa: E402
NO_VOSK = vosk_missing(ROOT)
if NO_VOSK:      # голосовое распознаёт заглушка (/v1/audio/transcriptions) — путь тот же: ogg → звук → распознавание → ответ
    print("ℹ " + NO_VOSK + " — голосовое распознаёт заглушка")
    st = json.loads((tmp / "cfg/settings.json").read_text())
    st["stt"] = {"engine": "remote", "remote": {"base_url": f"http://127.0.0.1:{LLM_PORT}/v1"}}
    (tmp / "cfg/settings.json").write_text(json.dumps(st))
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM_PORT)] + (["Как дела?"] if NO_VOSK else []))
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(sil), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
R = {}


def texts(pred=lambda t: True):
    with TG.lock:
        return [p.get("text", "") for m, p in TG.sent if m == "sendMessage" and pred(p.get("text", ""))]


async def until(pred, limit=20):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if pred():
            return True
        await asyncio.sleep(0.1)
    return False


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
    rd = asyncio.ensure_future(reader())
    R["bad"] = await call("tg_connect", token="просто текст")
    r = await call("tg_connect", token=TOKEN)
    R["conn"] = r.get("data") or {}
    code = R["conn"].get("code", "")
    TG.push(STRANGER, "привет")
    R["ask_code"] = await until(lambda: any("код" in t for t in texts()), 10)
    TG.push(OWNER, f"/start {code}")
    R["paired"] = await until(lambda: any(t.startswith("Готово") for t in texts()), 10)
    R["pub"] = (await call("tg_get")).get("data") or {}
    TG.sent.clear()
    TG.push(STRANGER, "Как дела?")
    await until(lambda: any("личный ассистент" in t for t in texts()), 10)
    await asyncio.sleep(1)
    R["stranger"] = texts() == ["Это личный ассистент — он отвечает только своему владельцу."]
    TG.sent.clear()
    TG.push(OWNER, "Как дела у тебя?")
    R["answer"] = await until(lambda: any("Вы сказали" in t and "Как дела у тебя" in t for t in texts()), 25)
    R["typing"] = any(m == "sendChatAction" for m, _ in TG.sent)
    TG.files["doc1"] = "Пароль от вайфая: кот123".encode()
    TG.sent.clear()
    TG.push(OWNER, None, caption="что в файле?", document={"file_id": "doc1", "file_name": "список.txt", "file_size": 40})
    R["doc"] = await until(lambda: any("вайфая" in t for t in texts()), 25)
    R["inbox"] = (tmp / "ws/Входящие/список.txt").exists()
    if not R["doc"]:
        print("   ответы бота:", [t[:160] for t in texts()][-4:])
    if voice:
        TG.files["v1"] = voice
        TG.sent.clear()
        TG.push(OWNER, None, voice={"file_id": "v1", "duration": 2, "file_size": len(voice)})
        R["voice"] = await until(lambda: any(t.startswith("🎙") for t in texts()), 40)
        R["voice_text"] = texts(lambda t: t.startswith("🎙")) or texts()[-3:]
        R["voice_reply"] = await until(lambda: any(m == "sendVoice" for m, _ in TG.sent), 30)
    TG.sent.clear()
    TG.push(OWNER, "пришли в телеграм список")
    R["file"] = await until(lambda: any(m == "sendDocument" for m, _ in TG.sent), 25)
    R["file_names"] = [p.get("_names") for m, p in TG.sent if m == "sendDocument"]
    TG.sent.clear()
    TG.push(OWNER, "выполни команду")
    R["buttons"] = await until(lambda: any(m == "sendMessage" and p.get("reply_markup") for m, p in TG.sent), 25)
    TG.callback(OWNER, "yes")
    R["confirmed"] = await until(lambda: any("Результат" in t for t in texts()), 25)
    TG.sent.clear()
    TG.push(OWNER, "напомни про чайник")
    R["reminder"] = await until(lambda: any(t.startswith("⏰") for t in texts()), 30)
    with TG.lock:
        mk = [p.get("reply_markup") for m, p in TG.sent if m == "sendMessage" and p.get("text", "").startswith("⏰")]
    btns = [b["callback_data"] for row in (mk[0]["inline_keyboard"] if mk and mk[0] else []) for b in row]
    snooze = next((b for b in btns if b.startswith("alarm:snooze:")), "")
    TG.sent.clear()
    TG.callback(OWNER, snooze)
    R["alarm_btn"] = bool(snooze) and await until(lambda: any(t.startswith("Хорошо, напомню") for t in texts()), 10)
    TG.sent.clear()
    TG.push(OWNER, "/status")
    R["status"] = await until(lambda: any("на связи" in t for t in texts()), 10)
    TG.sent.clear()
    TG.push(OWNER, "хватит")
    R["stop"] = await until(lambda: any("молчу" in t for t in texts()), 10)
    R["test"] = (await call("tg_test")).get("ok")
    R["forget"] = (await call("tg_forget")).get("data") or {}
    rd.cancel()

try:
    asyncio.run(run())
finally:
    core.terminate(); mock.terminate(); core.wait(); mock.wait(); srv.shutdown()
ok(not R.get("bad", {}).get("ok"), "не токен — понятная ошибка, ничего не сохранено")
ok(R["conn"].get("bot") == "dewiar_test_bot" and re.fullmatch(r"\d{6}", R["conn"].get("code", "")) and not R["conn"].get("paired"),
   "бот подключён, студия показывает код владельца")
ok(R.get("ask_code"), "до привязки бот просит код")
ok(R.get("paired") and R["pub"].get("paired") and R["pub"].get("owner") == "Анна" and not R["pub"].get("code"), "код из студии — и бот ваш")
ok(R.get("stranger"), "чужому — одна вежливая фраза, модель не спрашивается")
ok(R.get("answer") and R.get("typing"), "вопрос текстом — ответ модели в Telegram («печатает…»)")
ok(R.get("doc") and R.get("inbox"), "документ — во «Входящие», текст ушёл модели")
if voice:
    ok(R.get("voice") and any(t.startswith("🎙") and "как" in t.lower() for t in R.get("voice_text", [])), f"голосовое распознано: {R.get('voice_text')}")
    import shutil
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        ok(R.get("voice_reply"), "на голосовое — ответ и голосовым сообщением")
else:
    print("нет тестового голоса — голосовое пропускаю")
ok(R.get("file") and R.get("file_names") == [[b"\xd1\x81\xd0\xbf\xd0\xb8\xd1\x81\xd0\xbe\xd0\xba.txt"]], "send_telegram прислал файл из папки ассистента")
ok(R.get("buttons") and R.get("confirmed"), "подтверждение действия — кнопками «Да/Нет» в Telegram")
ok(R.get("reminder"), "напоминание пришло в Telegram")
ok(R.get("alarm_btn"), "кнопка «Через 10 мин» под напоминанием — отложено")
ok(R.get("status"), "/status — что сейчас делает")
ok(R.get("stop"), "«хватит» — молчу, без модели")
ok(R.get("test") and not R["forget"].get("connected") and not (tmp / "cfg/telegram.json").exists(), "проверка связи и «Отключить» — всё стёрто")
