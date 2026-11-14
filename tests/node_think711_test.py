"""№711 (14.11, Роман): «Нода Лиры: не видит ответа модели. Хотя модель работает и отвечает за 0,6 сек.» — LM Studio
с Qwen 3.5: chat_template_kwargs он не понимает, модель тратила весь предел на размышления, ответ пустой — «модель
ответила пусто». Теперь нода повторяет с «/no_think» и получает ответ; модель, которая думает всё равно, — честная
причина и что сделать. Обычная модель — с первого раза, без повтора."""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "core"))
import liranode as L  # noqa: E402
fails, calls, MODE = [], [], {"m": "lmstudio"}


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        calls.append(b)
        user = b["messages"][-1]["content"]
        if MODE["m"] == "plain" or (MODE["m"] == "lmstudio" and user.endswith("/no_think")):
            msg = {"role": "assistant", "content": "Небо голубое из-за рассеяния света."}
        else:                                        # думает до предела: ответа нет, только размышления
            msg = {"role": "assistant", "content": "", "reasoning_content": "Хм, пользователь спрашивает про небо… " * 30}
        out = json.dumps({"choices": [{"message": msg, "finish_reason": "length" if not msg["content"] else "stop"}],
                          "usage": {"completion_tokens": 300}}, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(out)))
        self.end_headers(); self.wfile.write(out)


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}/v1"
r = L.speed_test(base, "qwen/qwen3.5-9b")
ok(r["ok"] and "рассеяния" in r["text"] and len(calls) == 2 and calls[1]["messages"][-1]["content"].endswith("/no_think"),
   f"Qwen в LM Studio думал до предела — нода повторила с /no_think и видит ответ: {r}")
calls.clear(); MODE["m"] = "always"
r = L.speed_test(base, "qwen/qwen3.5-9b")
ok(not r["ok"] and "Thinking" in r["error"] and len(calls) == 2, f"думает всегда — честная причина и что сделать: {r['error']}")
calls.clear(); MODE["m"] = "plain"
r = L.speed_test(base, "llama")
ok(r["ok"] and len(calls) == 1 and not calls[0]["messages"][-1]["content"].endswith("/no_think"), "обычная модель — с первого раза, без повтора")
srv.shutdown()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
