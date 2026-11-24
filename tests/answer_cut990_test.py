"""№990 (24.11): «в текстовом режиме длинные ответы обрываются» — ответ оборвался на «**Ссылайся на ст.»: модель упёрлась в
лимит длины (finish_reason=length; размышления съели часть лимита). Теперь обрыв по лимиту — одна просьба продолжить ровно
с того места (с бо́льшим лимитом), человек видит цельный ответ."""
import http.server, json, os, sys, tempfile, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


got = []


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        got.append(body)
        first = len(got) == 1
        if MODE[0] == "tool":                                   # №1044: лимит съел вызов действия на 27-м знаке
            return self.tool(first)
        parts = (["Как использовать в суде: 1. Скажи, что договор подписан обеими сторонами и что вторая сторона его нарушила. ", "2. Ссылайся на ст."] if first else ["атью 450 ГК — договор расторгнут без согласия."])
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for i, t in enumerate(parts):
            fin = ("length" if first else "stop") if i == len(parts) - 1 else None
            self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": t}, "finish_reason": fin}]}, ensure_ascii=False) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def tool(self, first):
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        if first:
            ev = [{"choices": [{"delta": {"content": "Сегодня сделаны 2 дела: обн"}}]},
                  {"choices": [{"delta": {"content": "<tool_call>{\"name\": \"money_report\", \"arguments\": {\"from\": \"2026-"},
                                "finish_reason": "length"}]}]           # вызов действия текстом — обрезан лимитом
        else:
            ev = [{"choices": [{"delta": {"content": "Сегодня сделаны 2 дела: обновился Opus и разобрался со счётом. "}}]},
                  {"choices": [{"delta": {"content": "На завтра дел нет."}, "finish_reason": "stop"}]}]
        for e in ev:
            self.wfile.write(("data: " + json.dumps(e, ensure_ascii=False) + "\n\n").encode())
        self.wfile.write(b"data: [DONE]\n\n")


MODE = ["text"]
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
import llm  # noqa: E402
prof = {"kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_address[1]}/v1", "model": "m", "api_key": "k"}
text = "".join(v for k, v in llm.stream_events(prof, "Ты помощник.", [{"role": "user", "content": "Как использовать в суде?"}]) if k == "text")
ok(text.endswith("атью 450 ГК — договор расторгнут без согласия.") and text.startswith("Как использовать"), f"обрыв по лимиту — ответ продолжен: {text!r}")
ok(len(got) == 2 and got[1]["messages"][-2]["content"].endswith("2. Ссылайся на ст.")
   and "Продолжи ровно" in got[1]["messages"][-1]["content"] and got[1]["max_tokens"] >= 4096,
   "продолжение — с уже сказанным и бо́льшим лимитом, один раз")
# №1044: оборвалось на 27-м знаке, потому что лимит съел вызов действия — не «продолжи» без действий (модель начинала заново
# и звучало дважды), а тот же запрос целиком с действиями и бо́льшим лимитом; уже показанное начало второй раз не показываем
MODE[0] = "tool"; got.clear()
tools = [{"name": "money_report", "description": "деньги", "parameters": {"type": "object", "properties": {}}}]
evs = list(llm.stream_events(prof, "Ты помощник.", [{"role": "user", "content": "Итог дня"}], None, tools)); print("EVS", evs[:6]) if os.environ.get("DBG") else None; text = "".join(v for k, v in evs if k == "text")
ok(text.count("Сегодня сделаны 2 дела") == 1 and text.endswith("На завтра дел нет."), f"итог дня — один раз, без повтора: {text!r}")
ok(len(got) == 2 and "tools" in got[1] and "Продолжи" not in json.dumps(got[1]["messages"], ensure_ascii=False) and got[1]["max_tokens"] >= 4096,
   "второй запрос — целиком, с действиями и бо́льшим лимитом")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
