"""№989 (24.11, телефон): «Не получилось связаться с мозгом: модель ответила 400: Invalid Unicode (unpaired surrogate)» —
на каждый вопрос. Обрезка текста по длине (slice) рвёт эмодзи пополам, половинка в запросе — сервер его не принимает.
Теперь перед отправкой половинки заменяются «�» — и на телефоне (08-brain-stream.js), и на компьютере (llm.stream_events)."""
import http.server, json, os, subprocess, sys, tempfile, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "android/www-src/app/08-brain-stream.js").read_text(encoding="utf-8")
i, j = src.index("const wfStr"), src.index("async function llmStream")
js = src[i:j] + """
const cut = "Привет 😀".slice(0, 8);   // половинка эмодзи
const r = wellFormed({ messages: [{ role: "user", content: cut }, { role: "assistant", content: "ок 👍" }], n: 1 });
console.log(JSON.stringify([r.messages[0].content === "Привет \\ufffd", r.messages[1].content === "ок 👍", r.n === 1]));"""
jf = tmp / "w.js"; jf.write_text(js, encoding="utf-8")
out = subprocess.run(["node", str(jf)], capture_output=True, text=True, timeout=30)
ok(out.stdout.strip() == "[true,true,true]", f"телефон: половинка — «�», целые эмодзи и числа как есть: {out.stdout.strip() or out.stderr[:200]}")
ok("body = wellFormed(body);" in src, "телефон: чистится каждый запрос к модели")
got = []


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"])).decode()
        got.append(raw)
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
import llm  # noqa: E402
prof = {"kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m", "api_key": "k"}
list(llm.stream_events(prof, "Ты помощник.", [{"role": "user", "content": "Привет \ud83d как дела 😀"}]))
ok(got and "\\ud83d " not in got[0] and ("\\ufffd" in got[0] or "\ufffd" in got[0]), "компьютер: в запросе нет половинок")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
