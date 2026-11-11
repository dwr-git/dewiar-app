"""«Подкасты» (0.87) на настоящем ядре и студии: мозг — заглушка, голос — свой сервер голоса (заглушка /v1/audio/speech:
Лира — 440 Гц, Патрик — 180 Гц). В студии: тема → «Сделать подкаст» → ход по этапам → готовый выпуск с проигрывателем;
в папке ассистента — «Подкасты/…/*.mp3» и «Текст выпуска.md»; запросы голоса — с персонажем каждой реплики
(_voice_cfg → _engines_for_speech → _synth_mixed ядра); звук открывается в проигрывателе; podcast_delete убирает выпуск."""
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
FAILS = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        FAILS.append(m)


try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("⚠ playwright нет — проверка пропущена")
    sys.exit(0)
import numpy as np  # noqa: E402

SPEECH = []


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


SCRIPT = ("Лира: Почему небо голубое, а закат красный?\nПатрик: Ого. Правда, почему?\nЛира: Солнечный свет рассеивается в воздухе, "
          "и синий рассеивается сильнее красного.\nПатрик: То есть синего вокруг просто больше?\nЛира: Именно! А на закате свет идёт "
          "через толстый слой воздуха, и синий теряется по дороге.\nПатрик: Ага, понял.\nЛира: Главное: небо голубое из-за рассеяния, "
          "закат красный из-за длинного пути света. До встречи!")


class M(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        b = json.dumps({"data": [{"id": "mock"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if self.path.endswith("/audio/speech"):
            SPEECH.append((body.get("persona"), body.get("input")))
            f = 440.0 if body.get("persona") == "lira" else 180.0
            n = int(24000 * min(3.0, 0.3 + 0.02 * len(body.get("input") or "")))
            pcm = (np.sin(2 * np.pi * f * np.arange(n) / 24000) * 8000).astype(np.int16).tobytes()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            b = buf.getvalue()
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b)
            return
        sysm = next((m["content"] for m in body.get("messages", []) if m.get("role") == "system"), "")
        if "редактор живого" in sysm:
            text = '{"title": "Почему небо голубое", "hook": "Почему закат красный?", "blocks": [{"title": "Рассеяние", "points": ["синий сильнее"]}], "takeaways": ["рассеяние"]}'
        elif "автор сценариев" in sysm:
            text = SCRIPT
        else:
            text = "Ответ."
        try:
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for w in re.findall(r"\S+\s*", text):
                self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": w}}]}, ensure_ascii=False) + "\n\n").encode())
            self.wfile.write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        except OSError:
            pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), M)
threading.Thread(target=srv.serve_forever, daemon=True).start()
U = f"http://127.0.0.1:{srv.server_address[1]}/v1"
tmp = Path(tempfile.mkdtemp()); cfg = tmp / "cfg"; cfg.mkdir()
PORT = free()
(cfg / "settings.json").write_text(json.dumps({
    "persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done", "mode_seen": 1},
    "stt": {"engine": "vosk"}, "tts": {"engine": "remote", "remote": {"base_url": U, "model": "tts-1", "sample_rate": 24000}},
    "updates": {"auto_check": False}, "workspace": {"path": str(tmp / "ws")},
    "llm": {"active": "g", "profiles": {"g": {"name": "Мозг", "kind": "openai", "base_url": U, "model": "mock"}}}}), encoding="utf-8")
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_FAKE_OUTPUT_MUTED="0")
env.pop("DEWIAR_WORKSPACE", None)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="podcast"]'); time.sleep(1.5)
        ok("первый выпуск" in pg.inner_text("#pd-main"), "пустая страница — приглашение")
        ok(pg.eval_on_selector('#pd-hosts select[data-k="0"]', "s => s.value") == "lira"
           and pg.eval_on_selector('#pd-hosts select[data-k="1"]', "s => s.value") == "patrik", "ведут по умолчанию Лира и Патрик")
        pg.fill("#pd-topic", "Почему небо голубое")
        pg.click('#pd-len button[data-m="5"]')
        time.sleep(1.0)
        ok("Своя модель" in pg.inner_text("#pd-cost") and "голоса вашего сервера голоса" in pg.inner_text("#pd-cost"), f"цена: {pg.inner_text('#pd-cost')!r}")
        pg.click("#pd-go")
        pg.wait_for_selector("#pd-main .pd-steps", timeout=10000)
        ok(True, "пошёл ход работы")
        pg.wait_for_selector("#pd-main .pd-ep", timeout=90000)
        txt = pg.inner_text("#pd-main")
        ok("Почему небо голубое" in txt and pg.locator("#pd-main .pd-ln").count() == 7, "готовый выпуск: название и 7 реплик")
        pg.wait_for_function("document.querySelector('#pd-main audio').readyState >= 1", timeout=10000)
        d = pg.evaluate("document.querySelector('#pd-main audio').duration")
        ok(d > 5, f"звук открылся в проигрывателе: {d:.1f} с")
        ok([x[0] for x in SPEECH[:2]] == ["lira", "patrik"] and all((x[0] == "lira") == x[1].startswith(("Почему", "Солнечный", "Именно", "Главное"))
                                                                     for x in SPEECH), f"голос — каждой реплике свой персонаж: {[x[0] for x in SPEECH]}")
        mp3 = list((tmp / "ws" / "Подкасты").rglob("*.mp3"))
        md = list((tmp / "ws" / "Подкасты").rglob("Текст выпуска.md"))
        ok(len(mp3) == 1 and mp3[0].stat().st_size > 5000 and md and "**Патрик:**" in md[0].read_text(encoding="utf-8"),
           f"в папке ассистента — MP3 и текст выпуска: {mp3}")
        idx = json.loads((tmp / "st" / "podcasts.json").read_text(encoding="utf-8"))
        ok(len(idx) == 1 and Path(next(iter(idx.values()))) == mp3[0].resolve(), "список для сервера окон — путь к звуку")
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, "podcast-core.png"))
        pid = next(iter(idx))
        r = pg.evaluate("(id) => core.call('podcast_delete', {id}).then(() => 'ok', e => e.message)", pid)
        ok(r == "ok" and not list((tmp / "ws" / "Подкасты").rglob("*.mp3")), f"удаление выпуска: {r}")
        b.close()
finally:
    core.terminate()
    try:
        core.wait(10)
    except subprocess.TimeoutExpired:
        core.kill()
    srv.shutdown()
ok(not errs, f"без ошибок на странице: {errs[:2]}")
log = (tmp / "core.log").read_text(encoding="utf-8", errors="replace")
ok("Traceback" not in log, "в журнале ядра нет сбоев" + ("" if "Traceback" not in log else ": " + log[log.index("Traceback"):][:600]))
print("ИТОГ:", "всё прошло" if not FAILS else f"провалов {len(FAILS)}")
sys.exit(1 if FAILS else 0)
