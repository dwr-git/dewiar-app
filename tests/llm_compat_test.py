"""Совместимость «мозга» с реальными серверами: размышляющие модели, шлюзы без потока, только API Ollama,
списки моделей с эмбеддингами. Каждая строка — один режим имитации (как ведут себя vLLM/Ollama/шлюзы)."""
import json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import llm
THINK = "Хм, пользователь просит ответить. Надо подумать, как лучше сформулировать. " * 12   # ~900 симв.
ANSWER = "Привет! У меня всё хорошо."
MODE = {"m": ""}; SEEN = []

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, obj, ctype="application/json"):
        b = (json.dumps(obj, ensure_ascii=False, indent=2) if not isinstance(obj, bytes) else obj)
        b = b.encode() if isinstance(b, str) else b
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        m = MODE["m"]
        if self.path == "/v1/models" and m != "ollama_only":
            return self._send(200, {"data": [{"id": "embed"}, {"id": "qwen-reranker"}, {"id": "chat"}, {"id": "qwen36-27b"}]})
        if self.path == "/api/tags":
            return self._send(200, {"models": [{"name": "embed"}, {"name": "deepseek-ocr:3b"}, {"name": "chat"}]})
        self._send(404, {"error": "not found"})
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        SEEN.append((self.path, body)); m = MODE["m"]
        if body.get("model") in ("embed", "qwen-reranker"):
            return self._send(400, {"error": {"message": "model does not support chat"}})
        if self.path == "/v1/chat/completions" and m == "ollama_only":
            return self._send(404, {"error": "not found"})
        if self.path == "/v1/messages":                      # Anthropic: кэш системного промпта/инструментов + обрезка истории
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for w in ANSWER.split(" "):
                self.wfile.write((f"data: {json.dumps({'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': w + ' '}})}\n\n").encode())
            self.wfile.write((f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}})}\n\n").encode())
            return
        if self.path == "/api/chat":
            think = body.get("think", True)
            self.send_response(200); self.send_header("Content-Type", "application/x-ndjson"); self.end_headers()
            limit = body["options"]["num_predict"]
            if think:
                for i in range(0, min(len(THINK), limit * 3), 60):
                    self.wfile.write((json.dumps({"message": {"role": "assistant", "content": "", "thinking": THINK[i:i + 60]}, "done": False}) + "\n").encode())
                if limit * 3 < len(THINK):
                    self.wfile.write((json.dumps({"message": {"content": ""}, "done": True, "done_reason": "length"}) + "\n").encode()); return
            for w in ANSWER.split(" "):
                self.wfile.write((json.dumps({"message": {"role": "assistant", "content": w + " "}, "done": False}, ensure_ascii=False) + "\n").encode())
            self.wfile.write((json.dumps({"message": {"content": ""}, "done": True, "done_reason": "stop"}) + "\n").encode()); return
        # /v1/chat/completions
        thinking_off = (body.get("chat_template_kwargs") or {}).get("enable_thinking") is False and m != "gate_strips_kwargs"
        limit = body.get("max_tokens", 16)
        if m == "json_only":                                   # шлюз игнорирует stream и отдаёт JSON целиком
            return self._send(200, {"choices": [{"message": {"role": "assistant", "content": ANSWER}, "finish_reason": "stop"}]})
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        def ev(d, fin=None):
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': d, 'finish_reason': fin}]}, ensure_ascii=False)}\n\n".encode())
        if m in ("reasoning_field", "gate_strips_kwargs") and not thinking_off:
            budget = limit * 3                                  # ~3 символа на токен
            for i in range(0, min(len(THINK), budget), 60):
                ev({"reasoning_content": THINK[i:i + 60]})
            if budget < len(THINK):
                ev({}, "length"); self.wfile.write(b"data: [DONE]\n\n"); return
        if m == "think_in_content" and not thinking_off:
            for i in range(0, min(len(THINK), limit * 3), 60):
                ev({"content": ("<think>" if i == 0 else "") + THINK[i:i + 60]})
            if limit * 3 < len(THINK):
                ev({}, "length"); self.wfile.write(b"data: [DONE]\n\n"); return
            ev({"content": "</think>"})
        for w in ANSWER.split(" "):
            ev({"content": w + " "})
        ev({}, "stop"); self.wfile.write(b"data: [DONE]\n\n")

srv = ThreadingHTTPServer(("127.0.0.1", 8161), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
ok = True
def run(mode, prof, label):
    global ok
    MODE["m"] = mode; SEEN.clear(); llm._model_cache.clear(); llm._native.clear(); llm._no_tools.clear()
    try:
        text = "".join(llm.stream_chat(prof, "Ты помощник.", [{"role": "user", "content": "Как дела? Привет."}])).strip()
        err = ""
    except llm.LLMError as e:
        text, err = "", str(e)
    good = text == ANSWER
    ok &= good
    print(("✅" if good else "❌"), label, "→", repr(text or err)[:90], f"(запросов: {len(SEEN)}, модель: {SEEN[-1][1].get('model') if SEEN else '-'})")
P = {"name": "gate", "kind": "openai", "base_url": "http://127.0.0.1:8161/v1", "model": ""}
run("plain", P, "обычный поток, модель не указана — выбрана «chat», не «embed»")
run("reasoning_field", dict(P, max_tokens=600), "vLLM: размышления в reasoning_content съели лимит → повтор без них")
run("reasoning_field", dict(P, disable_thinking=True, max_tokens=600), "vLLM: размышления выключены сразу")
run("gate_strips_kwargs", dict(P, max_tokens=600), "шлюз выкидывает chat_template_kwargs → повтор с большим лимитом")
run("think_in_content", dict(P, max_tokens=600), "<think> прямо в тексте съел лимит → повтор")
run("json_only", P, "шлюз отдаёт JSON целиком вместо потока")
run("ollama_only", P, "есть только API Ollama (/api/chat) → переход сам, размышления выключены")
run("ollama_only", dict(P, kind="ollama", base_url="http://127.0.0.1:8161", max_tokens=100), "профиль Ollama с малым лимитом → повтор без размышлений")

ANTH_P = {"name": "claude", "kind": "anthropic", "base_url": "http://127.0.0.1:8161/v1", "api_key": "test-key", "model": ""}
run("anthropic", ANTH_P, "Anthropic: поток событий Claude разбирается")
body = SEEN[-1][1]
cached = isinstance(body.get("system"), list) and body["system"][0].get("cache_control") == {"type": "ephemeral"}
print("✅" if cached else "❌", "Anthropic: cache_control на системном промпте")
ok &= cached

long_history = [{"role": "user", "content": "первая просьба"}]
for i in range(60):
    long_history += [{"role": "assistant", "content": f"шаг {i}"}, {"role": "user", "content": f"ответ {i}"}]
trimmed = llm._anthropic_trim_history(long_history, keep=10)
kept_first = trimmed[0] == long_history[0]
short_enough = len(trimmed) <= 12          # первое сообщение + заглушка + keep
print("✅" if kept_first and short_enough else "❌", "Anthropic: длинная история обрезается, начало задачи сохраняется",
      f"({len(long_history)} → {len(trimmed)})")
ok &= kept_first and short_enough

MODE["m"] = "gate_strips_kwargs"; llm._model_cache.clear()
t = llm.test_profile(dict(P))
print(("✅" if t["ok"] and t["model"] == "chat" and t["reply"] else "❌"), "кнопка «Проверить»:", {k: t[k] for k in ("ok", "model", "reply", "api")})
ok &= t["ok"]
print("ALL OK" if ok else "FAIL"); sys.exit(0 if ok else 1)
