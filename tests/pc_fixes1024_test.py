"""№226 (24.10, Windows) — подробный список от человека:
1. длинный рассказ без имени после ответа отбрасывался жёстким порогом — теперь можно включить audio.follow_long;
2. подстройка паузы росла до +900 мс и почти не таяла — потолок +600, тает вдвое быстрее (pause_learn_test), «Вернуть обычную»;
3. «Обновить» на Windows ставил новую версию в %LOCALAPPDATA%\\Programs\\Dewiar, даже если Dewiar в другой папке — /D=папка;
5. OpenAI напрямую, GPT-5: 400 — нужен max_completion_tokens и без temperature (и повтор так, если сервер сам попросил)."""
import ast, json, os, re, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# 1. длинное без имени — по выбору человека
ea = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok(re.search(r'long_ = \(dur is not None and dur > FOLLOW_MAX_S\) or len\(ws\) > FOLLOW_MAX_WORDS\n\s+if self\.s\.get\("audio", "follow_long"\):\s+[^\n]*\n\s+long_ = False', ea) is not None,
   "audio.follow_long — длинная фраза без имени тоже мне")
import settings  # noqa: E402
ok(settings.DEFAULTS["audio"]["follow_long"] is False if hasattr(settings, "DEFAULTS") else '"follow_long": False' in (ROOT / "core/settings.py").read_text(encoding="utf-8"),
   "по умолчанию — выключено, как раньше")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('data-k="audio.follow_long"' in html and "pause-reset" in (ROOT / "ui/studio/brain.js").read_text(encoding="utf-8"),
   "в студии: переключатель «Отвечать и на длинный рассказ без имени» и «Вернуть обычную» паузу")

# 6. слабый компьютер: разовый перенос Piper → Vosk TTS не трогает Piper в лёгком режиме
eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok('"engine": "piper" if self.s.get("device", "light") else "vosk", "v2": True' in eng, "лёгкий режим — Piper остаётся (Vosk TTS там 17–36 с на фразу)")

# №218: модель имён Vosk на медленной связи — докачка с места обрыва, как у голосов
_li = (ROOT / "core/listen.py").read_text(encoding="utf-8")   # 0.53: скачивание — общее для моделей Vosk (ensure_model)
ok("download(url, zip_path, sha256=sha256, tries=6)" in _li and "ensure_model(VOSK_NAME, VOSK_URLS, VOSK_SHA256" in _li, "модель имён докачивается (Range), а не с нуля")

# пакет 24.10: «No module named 'sounddevice'» — человеку понятная записка, что делать
ok('isinstance(e, ImportError) and "sounddevice" in str(e)' in ea and "pipewire-pulse" in ea, "нет звуковой прослойки — записка «что установить», а не трассировка")

# №222: задача с проектом на сетевой папке — файл с ключами без доступа не роняет шаг
import shutil  # noqa: E402
import codework  # noqa: E402
cd = Path(tempfile.mkdtemp()); (cd / "p").mkdir(); (cd / "p/a.py").write_text("x = 1"); (cd / "p/lmstudio.env").write_text("k")
_cp = shutil.copy2


def _deny(src, dst, **k):
    if str(src).endswith(".env"):
        raise PermissionError(13, "Access is denied", str(src))
    return _cp(src, dst, **k)


_ct = shutil.copytree
shutil.copytree = lambda *a, **k: _ct(*a, **dict(k, copy_function=_deny))   # copy2 у copytree — по умолчанию, подменяем так
try:
    cw = codework.CodeWork(cd / "p", cd / "w"); cw.prepare(); lst = cw.list("")
except Exception as e:  # noqa: BLE001
    lst = f"сбой: {e!r}"
shutil.copytree = _ct
ok("a.py" in lst and "lmstudio.env" not in lst, f"файл без доступа пропущен, остальное — в работе: {lst!r}")
ok("except OSError as e:" in (ROOT / "core/tasks.py").read_text(encoding="utf-8"), "ошибка доступа в шаге задачи — «Ошибка: нет доступа…», а не отчёт о сбое")

# 3. обновление на Windows — в ту же папку
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
src = ast.get_source_segment(app, next(n for n in ast.parse(app).body if isinstance(n, ast.FunctionDef) and n.name == "_update_cmd"))
ns = {"Path": Path, "winshell": None}; exec(src, ns)
d = Path(tempfile.mkdtemp()) / "Мои программы" / "Dewiar"; (d / "app/ui").mkdir(parents=True); (d / "app/ui/app.py").write_text("")
cmd = ns["_update_cmd"](Path("C:/t/Dewiar-Setup.exe"), d)
ok(isinstance(cmd, str) and cmd.endswith(f" /S /UPDATE /D={d}") and '"/D=' not in cmd, f"установщик получает папку /D= последней и без кавычек: {cmd}")
c2 = ns["_update_cmd"](Path("C:/t/x.exe"), Path(tempfile.mkdtemp()))
ok(isinstance(c2, list) and c2[1:] == ["/S", "/UPDATE"], f"не установка Dewiar (запуск из исходников) — без /D: {c2}")
ok("Popen(_update_cmd(p)" in app, "_install_update_win запускает установщик так")

# 5. GPT-5 напрямую
import llm  # noqa: E402
seen = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        b = json.loads(self.rfile.read(int(self.headers["Content-Length"]))); seen.append(b)
        if "max_tokens" in b and self.server.strict:
            msg = json.dumps({"error": {"message": "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.",
                                        "type": "invalid_request_error", "code": "unsupported_parameter"}}).encode()
            self.send_response(400); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(msg))); self.end_headers()
            self.wfile.write(msg); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": "Привет!"}}]}) + "\n\ndata: [DONE]\n\n").encode())


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); srv.strict = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
p = {"kind": "openai", "base_url": f"http://127.0.0.1:{srv.server_port}/v1", "model": "gpt-5-nano", "disable_thinking": True}
out = list(llm.stream_events(p, "Ты ассистент.", [{"role": "user", "content": "Привет"}]))
text = "".join(v for k, v in out if k == "text")
ok(text == "Привет!" and len(seen) == 2 and "max_completion_tokens" in seen[1] and "temperature" not in seen[1],
   f"сервер попросил max_completion_tokens — повтор так, ответ есть: {text!r}, запросов {len(seen)}")
# пакет 24.10: «503 … high demand» (Gemini) 7 раз сырым JSON — один тихий повтор, затем понятная фраза
os.environ["DEWIAR_BUSY_WAIT"] = "0.1"
busy = [0]


class B(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        if busy[0] > 0:
            busy[0] -= 1
            msg = b'[{"error": {"code": 503, "message": "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.", "status": "UNAVAILABLE"}}]'
            self.send_response(503); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(msg))); self.end_headers()
            self.wfile.write(msg); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": "Готово"}}]}) + "\n\ndata: [DONE]\n\n").encode())


bs = ThreadingHTTPServer(("127.0.0.1", 0), B); threading.Thread(target=bs.serve_forever, daemon=True).start()
pb = {"kind": "openai", "base_url": f"http://127.0.0.1:{bs.server_port}/v1", "model": "gemini-2.5-flash", "disable_thinking": True}
busy[0] = 1
out = list(llm.stream_events(pb, "s", [{"role": "user", "content": "q"}]))
ok("".join(v for k, v in out if k == "text") == "Готово", "503 один раз — тихий повтор, ответ есть")
busy[0] = 5
try:
    list(llm.stream_events(pb, "s", [{"role": "user", "content": "q"}])); err = ""
except Exception as e:  # noqa: BLE001
    err = str(e)
ok("перегружен" in err and "{" not in err, f"503 снова — понятно, без JSON: {err}")

# сразу правильно для api.openai.com: смотрим тело, которое ушло бы
body = {}
real = llm._stream_retry


class Stop(Exception): pass


def cap(method, url, json=None, **k):
    body.update(json); raise Stop()


llm._stream_retry = cap
try:
    list(llm.stream_events({"kind": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-5-mini", "api_key": "x"}, "s", [{"role": "user", "content": "q"}]))
except Exception:  # noqa: BLE001 — тело уже поймано
    pass
ok("max_completion_tokens" in body and "max_tokens" not in body and "temperature" not in body, f"api.openai.com + gpt-5 — сразу max_completion_tokens: {sorted(body)}")
body.clear()
try:
    list(llm.stream_events({"kind": "openai", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key": "x"}, "s", [{"role": "user", "content": "q"}]))
except Exception:  # noqa: BLE001 — тело уже поймано
    pass
ok("max_tokens" in body and "temperature" in body, "gpt-4o — как раньше")
llm._stream_retry = real

if fails:
    raise SystemExit(1)
