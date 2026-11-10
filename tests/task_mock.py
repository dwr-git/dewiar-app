"""Общее для проверок «Больших задач» (выпуск 1, docs/HARNESS.md): модель-заглушка со сценарием на каждую задачу, которая
записывает КАЖДЫЙ запрос целиком (подсказка, инструменты, сообщения), и хозяин задач без ядра (как в long_task_test).
Окно модели — как у vLLM: GET /v1/models отдаёт max_model_len, запрос длиннее окна (с max_tokens) — ошибка 400
«maximum context length». Токены считаются грубо — как llm.est_tokens (знаки / 3)."""
import json
import os
import re
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TMP = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(TMP / "ws"), DEWIAR_STATE_DIR=str(TMP / "st"), DEWIAR_CONFIG_DIR=str(TMP / "cfg"),
                  DEWIAR_TASK_RETRY="0.03,0.03,0.03", DEWIAR_TASK_RESUME_SEC="1", DEWIAR_BUSY_WAIT="0.1")
sys.path.insert(0, str(ROOT / "core"))
from workspace import Workspace  # noqa: E402
import tools as T  # noqa: E402

FAILS = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


def done():
    print("ИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
    sys.exit(1 if FAILS else 0)


def wait_for(cond, sec=30):
    end = time.time() + sec
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    return False


def tok(x):
    return len(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)) // 3 + 1


class Mock:
    """SCRIPTS: название задачи -> [(инструмент, аргументы) | callable(запрос) -> (инструмент, аргументы)]; «@explore» —
    сценарий разведчика (выпуск 6); шаг (None, текст) — ответ текстом без вызова."""

    def __init__(self, scripts, window=None):
        self.scripts, self.window = scripts, window
        self.pos, self.reqs, self.over, self.side = {}, [], [], []
        self.force_ctx = 0                       # столько следующих запросов задачи — ошибка «не хватило окна»
        self.fail_503 = 0
        self.side_fn = None                      # служебные запросы (без инструментов): fn(подсказка, тело) -> ответ | None
        self.lock = threading.Lock()
        mock = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                if self.path.startswith("/v1/models") and mock.window:
                    return self._json(200, {"data": [{"id": "m", "max_model_len": mock.window}]})
                if self.path.startswith("/search"):
                    return mock.search(self)
                self._json(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                mock.handle(self, body)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}/v1"

    def search(self, h):
        return h._json(200, {"results": []})

    def send(self, h, text="", call=None):
        h.send_response(200)
        h.send_header("Content-Type", "text/event-stream")
        h.end_headers()
        chunks = []
        if text:
            chunks.append({"choices": [{"delta": {"content": text}}]})
        if call:
            chunks.append({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": f"c{len(self.reqs)}", "type": "function",
                                                                  "function": {"name": call[0], "arguments": json.dumps(call[1], ensure_ascii=False)}}]}}]})
        chunks.append({"choices": [], "usage": {"prompt_tokens": tok(json.dumps(self.last_body, ensure_ascii=False)), "completion_tokens": 7,
                                                "prompt_tokens_details": {"cached_tokens": 100}}})
        for c in chunks:
            h.wfile.write(f"data: {json.dumps(c, ensure_ascii=False)}\n\n".encode())
        h.wfile.write(b"data: [DONE]\n\n")

    def handle(self, h, body):
        self.last_body = body
        sysm = body["messages"][0]["content"]
        size = tok(body["messages"]) + (tok(body["tools"]) if body.get("tools") else 0)
        with self.lock:
            if self.fail_503 > 0 and body.get("tools"):
                self.fail_503 -= 1
                h.send_response(503)
                h.end_headers()
                h.wfile.write(b"overloaded")
                return
            if self.window and size + int(body.get("max_tokens") or 0) > self.window:
                self.over.append(size)
                return h._json(400, {"error": {"message": f"This model's maximum context length is {self.window} tokens. However, you "
                                                          f"requested {size + int(body.get('max_tokens') or 0)} tokens."}})
            if body.get("tools") and self.force_ctx > 0:
                self.force_ctx -= 1
                self.over.append(-size)
                return h._json(400, {"error": {"message": f"This model's maximum context length is {self.window or 8192} tokens."}})
            if not body.get("tools"):
                self.side.append({"system": sysm, "size": size})
                if self.side_fn is not None:
                    out = self.side_fn(sysm, body)
                    if out is not None:
                        return self.send(h, out)
                if sysm.startswith("Ты — строгий"):
                    return self.send(h, '{"verdict": "ok"}')
                if sysm.startswith("Ты — аналитик"):
                    return self.send(h, '{"lessons": []}')
                return self.send(h, "# Блокнот задачи\n\n## Что известно\n- сжато из ранних шагов\n")
            m = re.search(r"ЗАДАЧА: (.+)", sysm)
            title = m.group(1).strip() if m else "?"
            if sysm.startswith("Ты — разведчик"):           # выпуск 6: разведчик задачи — свой сценарий «@explore»
                title = "@explore"
            i = self.pos.get(title, 0)
            self.pos[title] = i + 1
            sc = self.scripts.get(title, [])
            step = sc[i] if i < len(sc) else ("finish", {"summary": "Готово."})
            req = {"title": title, "i": i, "system": sysm, "tools": body.get("tools") or [], "messages": body["messages"][1:],
                   "size": size, "max_tokens": body.get("max_tokens")}
            self.reqs.append(req)
        if callable(step):
            step = step(req)
        if step and step[0] is None:                   # ответ текстом, без вызова
            return self.send(h, step[1])
        self.send(h, f"Шаг {i + 1}. ", step)

    def of(self, title):
        return [r for r in self.reqs if r["title"] == title]


class FakeS:
    def get(self, *k):
        return {} if k[0] == "tools" else None


class Host:
    def __init__(self, mock, **prof):
        self.mock = mock
        self.workspace = Workspace(None)
        self.toolbox = T.Toolbox(FakeS(), None)
        self.toolbox.hooks["workspace"] = self.workspace
        self.said, self.pushes, self.stopping = [], [], threading.Event()
        self.prof = dict({"name": "mock", "kind": "openai", "base_url": mock.url, "model": "m"}, **prof)

    def persona_name(self):
        return "Лира"

    def memory(self):
        return ""

    def llm_profile(self):
        return dict(self.prof)

    def max_steps(self):
        return 80

    def code_auto_run(self):
        return True

    def confirm(self, q, cancel=None):
        return True

    def ask_user(self, t, q):
        pass

    def announce(self, text):
        self.said.append(text)

    def push(self, title, text="", critical=False, file=None):
        self.pushes.append((title, text, critical))

    def emit(self, *a, **k):
        pass
