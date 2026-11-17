"""Пакет 17.11, №805: «настраивал MCP-сервер программы pen.dev — Лира подключалась, управлять не удавалось, и она
молчала, пока я не спрашивал». Ответ MCP-инструмента считался «действием»: на тишину модели выходило «Готово.» (или
ничего). Теперь результат программы — то, о чём надо рассказать: модель просят ответить по нему словами.
Живое ядро, модель-заглушка, настоящий MCP-сервер (tests/mcp_test_server.py)."""
import asyncio, json, os, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import websockets
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


import answer_rules as AR  # noqa: E402
ok(AR.told(["mcp_pen_get_state", "set_reminder"]) == {"mcp_pen_get_state"} and AR.told(["web_search"]) == {"web_search"},
   "результат MCP и справочные — «есть что рассказать», напоминание — нет")
# №816 (пакет 17.11 10:30): разбор таблицы кодом в «Лаборатории», ход кончился, модель замолчала — «Готово.» вместо цифр
ok(AR.told(["lab_write", "lab_run"]) == {"lab_run"} and AR.told(["run_python"]) == {"run_python"},
   "вывод запуска кода (lab_run, run_python) — тоже «есть что рассказать», запись файла — нет")
SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "m"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        msgs = body["messages"]; SEEN.append(body); last = msgs[-1]
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()

        def send(delta, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': delta, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        if last["role"] == "user" and "Ответь мне сейчас словами" in str(last["content"]):
            send({"content": "Подключилась к pen: программа ответила «эхо: состояние», но управлять холстом через неё не вышло."}); send({}, "stop")
        elif last["role"] == "tool":           # результат программы получен — и модель молчит
            send({}, "stop")
        else:
            send({"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "mcp_pen_echo",
                  "arguments": json.dumps({"text": "состояние"})}}]}); send({}, "tool_calls")
        self.wfile.write(b"data: [DONE]\n\n")


UP, PORT = free(), free()
srv = ThreadingHTTPServer(("127.0.0.1", UP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = Path(tempfile.mkdtemp()); (tmp / "cfg").mkdir()
base = f"http://127.0.0.1:{UP}/v1"
(tmp / "cfg/settings.json").write_text(json.dumps({
    "persona": "lira", "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "audio": {"sounds": False}, "ui": {"intro": "done"},
    "report": {"pulse": False}, "team": {"route": False},
    "mcp": {"servers": {"pen": {"type": "stdio", "command": sys.executable, "args": [str(TESTS / "mcp_test_server.py")]}}},
    "llm": {"active": "m", "tools_probe_v": 2, "tools_modes": {f"{base}|m": "native"},
            "profiles": {"m": {"name": "mock", "kind": "openai", "base_url": base, "model": "m"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
OUT = {}


async def session():
    core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                            stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
    try:
        ws_ = None
        for _ in range(300):
            await asyncio.sleep(0.2)
            if (tmp / "cfg/token").exists():
                try:
                    ws_ = await websockets.connect(f"ws://127.0.0.1:{PORT}", max_size=None); break
                except OSError:
                    continue
        await ws_.send(json.dumps({"cmd": "hello", "token": (tmp / "cfg/token").read_text().strip()}))
        await ws_.recv()
        await asyncio.sleep(3)                                     # MCP-сервер поднимается в фоне
        await ws_.send(json.dumps({"id": 1, "cmd": "say", "args": {"text": "Подключись к pen и посмотри, что там на холсте"}}))
        t0 = time.time()
        while time.time() - t0 < 60:
            e = json.loads(await asyncio.wait_for(ws_.recv(), 60))
            if e.get("type") == "answer" and e.get("done"):
                OUT["text"] = e.get("text", "")
                break
        await ws_.close()
    finally:
        core.terminate()
        try:
            core.wait(10)
        except subprocess.TimeoutExpired:
            core.kill()

asyncio.run(session())
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
tool_msgs = [m for b in SEEN for m in b["messages"] if m.get("role") == "tool"]
ok(tool_msgs and "эхо: состояние" in str(tool_msgs[0].get("content")), "MCP-инструмент вызван, модель видит его ответ")
t = OUT.get("text", "")
ok("Подключилась к pen" in t and t.strip() != "Готово.", f"после ответа программы и молчания модели — рассказ, а не «Готово.»: {t[:100]!r}")
ok("Модель замолчала после поиска и чтения" in log, "в журнале — почему переспросили")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
