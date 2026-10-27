"""№258 (пакет 25.10): «загрузил qwen3:4b и qwen3:8b, нажимаю список моделей — только сообщение, что модель не умеет
разговаривать, выбора нет». В Ollama была лишь nomic-embed-text, а qwen3 — в LM Studio. Теперь: «Проверить» и ошибка
модели объясняют, что в Ollama нет модели для разговора и как её скачать; если LM Studio на этом компьютере отвечает
и в ней есть модели для разговора — называет их. Сервер, где модели для разговора есть, — по-прежнему."""
import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer as HTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import llm  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


MODELS = {"v": ["nomic-embed-text:latest"]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _j(self, code, d):
        b = json.dumps(d).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.endswith("/models"):
            return self._j(200, {"data": [{"id": m} for m in MODELS["v"]]})
        self._j(404, {})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        self._j(400, {"error": {"message": '"nomic-embed-text:latest" does not support chat'}})


srv = HTTPServer(("127.0.0.1", 0), H); port = srv.server_port
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}/v1"
p = {"kind": "openai", "base_url": base, "model": ""}
r = llm.test_profile(p)
ok(not r["ok"] and "нет модели для разговора" not in r["error"] and "nomic-embed-text" in r["error"] and "для поиска по смыслу" in r["error"],
   f"«Проверить» без модели для разговора — объясняет, что есть только модель для поиска: {r['error'][:110]!r}")
ok("Загрузите" in r["error"] or "ollama pull" in r["error"], "и что делать")
r = llm.test_profile(dict(p, model="nomic-embed-text:latest"))
ok(not r["ok"] and "для поиска по смыслу" in r["error"], "выбрана сама embed-модель — то же объяснение, а не «модель не ответила»")
# ошибка модели при разговоре: 400 «does not support chat» — с советом, где взять модель
h = llm._humanize(Exception("x"), base, "nomic-embed-text:latest")
e = None
try:
    for _ in llm.stream_chat(dict(p, model="nomic-embed-text:latest"), "s", [{"role": "user", "content": "привет"}]):
        pass
except llm.LLMError as x:
    e = str(x)
ok(e and "не умеет разговаривать" in e and "для поиска по смыслу" in e, f"разговор с embed-моделью — с объяснением: {str(e)[:120]!r}")
h = llm.no_chat_help("http://127.0.0.1:11434/v1", ["nomic-embed-text:latest"])
ok("ollama pull qwen3:4b" in h and "Командная строка" in h, f"для Ollama — как скачать модель: {h[:100]!r}")
ok("LM Studio" not in h or "«" in h.split("LM Studio")[1][:60], "LM Studio упоминается, только если в ней нашлись модели")
# есть модель для разговора — обычный путь (ни подсказок, ни отказа на этапе выбора)
MODELS["v"] = ["nomic-embed-text:latest", "qwen3:4b"]
ok(llm.pick_model(MODELS["v"]) == "qwen3:4b", "есть qwen3 — выбирается она")
ok(llm.chat_models(MODELS["v"]) == ["qwen3:4b"], "chat_models отсеивает embed")
srv.shutdown()
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
