"""Опыт 9 (аудит Fable 25.11, переключатель llm.force_call, выключен): модель пообещала и не сделала — после просьбы «сделай,
а не обещай» следующий шаг уходит с tool_choice «required» (Claude — {"type": "any"}): ответить можно только действием.
Сервер, который так не умеет (старый vLLM, часть шлюзов), — повтор без этого и больше не просим. Без флага шага — «auto»."""
import json, os, socket, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


SEEN, OLD = [], {"on": False}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append(body)
        if OLD["on"] and body.get("tool_choice") == "required":
            b = b'{"error":{"message":"tool_choice \\"required\\" is not supported"}}'
            self.send_response(400); self.end_headers(); self.wfile.write(b); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        d = {"tool_calls": [{"index": 0, "id": "c1", "type": "function", "function": {"name": "set_reminder", "arguments": "{\"text\": \"маме\"}"}}]}
        self.wfile.write(f"data: {json.dumps({'choices': [{'delta': d}]})}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = ThreadingHTTPServer(("127.0.0.1", port), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
P = {"kind": "openai", "base_url": f"http://127.0.0.1:{port}/v1", "model": "chat", "tools_mode": "native"}
T = [{"name": "set_reminder", "description": "Напоминание", "parameters": {"type": "object", "properties": {"text": {"type": "string"}}}}]
M = [{"role": "user", "content": "напомни позвонить маме"}]

list(llm.stream_events(P, "Ты помощник.", M, tools=T))
ok(SEEN[-1].get("tool_choice") == "auto", "обычный шаг — tool_choice auto")
ev = list(llm.stream_events(dict(P, _force_call=True), "Ты помощник.", M, tools=T))
ok(SEEN[-1].get("tool_choice") == "required" and any(k == "tools" for k, _ in ev), "шаг после обещания — required, и вызов пришёл")
OLD["on"] = True
n = len(SEEN)
ev = list(llm.stream_events(dict(P, _force_call=True), "Ты помощник.", M, tools=T))
ok(len(SEEN) == n + 2 and SEEN[n].get("tool_choice") == "required" and SEEN[n + 1].get("tool_choice") == "auto" and any(k == "tools" for k, _ in ev),
   "сервер не умеет required — повтор с auto")
list(llm.stream_events(dict(P, _force_call=True), "Ты помощник.", M, tools=T))
ok(SEEN[-1].get("tool_choice") == "auto" and len(SEEN) == n + 3, "и больше не просим (запомнили сервер)")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('turn.force_call = self.s.get("llm", "force_call") is True' in src and 'dict(prof, _force_call=True) if getattr(turn, "force_call", False) and specs' in src,
   "ход: флаг ставит просьба «сделай, а не обещай», и только при llm.force_call")
ok('"force_call": False' in (ROOT / "core/settings.py").read_text(encoding="utf-8"), "переключатель по умолчанию выключен")
ok('body["tool_choice"] = {"type": "any"}' in (ROOT / "core/llm.py").read_text(encoding="utf-8"), "Claude — tool_choice any")
srv.shutdown()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
print("ALL OK" if not fails else "")
sys.exit(1 if fails else 0)
