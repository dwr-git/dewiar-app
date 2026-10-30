"""«Сервер вернул ответ без текста» (пакет 30.10: своя модель у стороннего сервиса — qwen3.8-omni-flash, 27 раз, 14
компьютеров). Сервис в потоке присылал пустоту (finish stop, ни текста, ни вызова), и после повтора программа сдавалась.
Облако Dewiar такие ответы спасает, переспрашивая «целиком», без потока; теперь и программа так делает последней попыткой."""
import http.server, json, os, socket, sys, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


for k in [k for k in os.environ if "proxy" in k.lower()]:
    os.environ.pop(k)
import llm  # noqa: E402

llm.time.sleep = lambda s: None
SEEN = []
MODE = {"whole": "text"}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        SEEN.append(body.get("stream"))
        if body.get("stream"):
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            self.wfile.write(b'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
            return
        if MODE["whole"] == "tool":
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_time", "arguments": "{}"}}]}
        else:
            msg = {"role": "assistant", "content": "Сейчас 22:40."}
        b = json.dumps({"choices": [{"message": msg, "finish_reason": "stop"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
P = {"kind": "openai", "base_url": f"http://127.0.0.1:{PORT}/v1", "api_key": "x", "model": "qwen3.8-omni-flash"}
ev = list(llm.stream_events(P, "ты помощник", [{"role": "user", "content": "который час?"}]))
ok(ev == [("text", "Сейчас 22:40.")], f"поток дважды пустой — ответ получен целиком: {ev}")
ok(SEEN[-1] is False and SEEN.count(True) >= 2, f"последняя попытка — без потока: {SEEN}")
SEEN.clear(); MODE["whole"] = "tool"
tools = [{"name": "get_time", "description": "время", "parameters": {"type": "object", "properties": {}}}]
ev = list(llm.stream_events(dict(P, tools_mode="native"), "ты помощник", [{"role": "user", "content": "который час?"}], tools=tools))
ok(ev and ev[-1][0] == "tools" and ev[-1][1][0]["name"] == "get_time", f"и вызов действия целиком тоже доходит: {ev}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
