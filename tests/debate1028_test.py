"""«Спор моделей» (0.62; план «Идей Лиры»: «две модели обсуждают трудный вопрос, а Лира подводит итог: где они согласны и
в чём разошлись»). Вторая модель — другой профиль «Мозга», иначе другая модель того же сервиса; нет — подсказка, где
добавить. Два круга (сначала каждая сама, потом — ответ на доводы другой); итог — модели разговора, с именами моделей."""
import json, os, socket, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


SEEN = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "alpha"}, {"id": "beta"}, {"id": "text-embedding-3"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        m, sysm, user = body.get("model"), body["messages"][0]["content"], body["messages"][-1]["content"]
        SEEN.append((m, "второй" if "другой модели" in user else "первый"))
        text = (f"{m}: да, стоит — меньше выгорания." if m == "alpha" else f"{m}: нет, не стоит — страдают сроки.") if "другой модели" not in user \
            else f"{m}: согласна про выгорание, но сроки важнее." if m == "beta" else f"{m}: про сроки — решается планированием."
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': text}}]}, ensure_ascii=False)}\n\ndata: [DONE]\n\n".encode())


s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
srv = ThreadingHTTPServer(("127.0.0.1", PORT), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{PORT}/v1"


class St:
    def __init__(self, d): self.d = d
    def get(self, k, *a): return self.d.get(k)


import debate as DB  # noqa: E402
import tools as TL  # noqa: E402
two = St({"llm": {"active": "m1", "profiles": {"m1": {"name": "Первый", "kind": "openai", "base_url": BASE, "model": "alpha"},
                                                "m2": {"name": "Второй", "kind": "openai", "base_url": BASE, "model": "beta"}}}})
a, b = DB.pick_pair(two)
ok(a["model"] == "alpha" and b["model"] == "beta", "вторая — другой профиль «Мозга»")
one = St({"llm": {"active": "m1", "profiles": {"m1": {"name": "Первый", "kind": "openai", "base_url": BASE, "model": "alpha"}}}})
a, b = DB.pick_pair(one)
ok(b["model"] == "beta", "один профиль — другая модель того же сервиса (не эмбеддинги)")
r = TL.TOOLS["debate"][3]({"question": "Стоит ли компании переходить на четырёхдневную неделю?"}, {"settings": two})
ok(r.startswith("[Спор моделей]") and "alpha (первый ответ): alpha: да, стоит" in r and "beta (первый ответ): beta: нет" in r
   and "beta отвечает на доводы alpha: beta: согласна про выгорание" in r and "Подведи итог" in r, f"два круга и просьба подвести итог: {r[:160]}")
ok(sorted(SEEN) == sorted([("alpha", "первый"), ("beta", "первый"), ("alpha", "второй"), ("beta", "второй")]), f"каждая — дважды: {SEEN}")
solo = St({"llm": {"active": "m1", "profiles": {"m1": {"name": "Один", "kind": "openai", "base_url": f"http://127.0.0.1:9/v1", "model": "x"}}}})
try:
    TL.TOOLS["debate"][3]({"question": "Кто прав?"}, {"settings": solo}); ok(False, "нет второй модели — подсказка")
except TL.ToolError as e:
    ok("«Мозг»" in str(e), f"нет второй модели — где добавить: {e}")
srv.shutdown()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
