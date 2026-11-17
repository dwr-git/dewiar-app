"""Пакет 17.11 13:46.
№821: «Музыка» — «C:\\Users\\777\\Desktop\\Муза» → «такой папки нет», хотя папка есть; «Нода Лиры» не видит Strata на
127.0.0.1 (сервер отвечает на /models только с ключом профиля).
№819: виджет полчаса «Подключаюсь…» — попытка подключиться, зависшая во время перезапуска ядра, больше не повторялась.
№818: «скачать версию с руками — ссылка не работает» (постоянного файла на сайте нет — сайт уводил по кругу).
№820: нет звука в Bluetooth-наушниках после слушания их микрофоном — канал гарнитуры выключаем и старым способом; в отчёт
телефона — громкость и куда идёт звук.
Идея №300: объявление о новой версии со ссылкой на «Скачать» — в программе это обновление на месте."""
import json, os, socket, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "ucfg"), DEWIAR_STATE_DIR=str(tmp / "ust"), HOME=str(tmp / "home"))
(tmp / "home").mkdir()
sys.path.insert(0, str(ROOT / "core"))

# ---------- №821: папка, вписанная руками
import workspace  # noqa: E402
muza = tmp / "home" / "Desktop" / "Муза"; muza.mkdir(parents=True)
ok(workspace.user_dir(f'"{muza}"') == muza, "кавычки от «Копировать как путь» — не помеха")
ok(workspace.user_dir("~/Desktop/Муза") == muza, "~ — домашняя папка")
ok(workspace.user_dir("$HOME/Desktop/Муза") == muza, "переменные окружения (%USERPROFILE% в Windows)")
ok(workspace.user_dir(str(tmp / "нет такой")) is None, "несуществующая — None")
od = tmp / "home" / "OneDrive" / "Desktop" / "Песни"; od.mkdir(parents=True)
ok(workspace.user_dir(str(tmp / "home" / "Desktop" / "Песни")) == od, "рабочий стол в OneDrive — находится")
ok("С:\\x"[0].translate(workspace._LOOKS_LAT) == "C", "русская «С» в букве диска → латинская C")
src = (ROOT / "core/engine_mymusic.py").read_text(encoding="utf-8")
ok("user_dir(folder)" in src and "не нашла папку «{folder[:120]}»" in src, "«Музыка»: тот же разбор и честное «не нашла папку «…»»")
ok("user_dir(raw)" in (ROOT / "core/commands_sync.py").read_text(encoding="utf-8"), "«Мои файлы» → своя папка — тот же разбор")

# ---------- №821: своя модель с ключом (Strata) — «Нода Лиры» её видит
KEY = "k-test-123"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/keyed/v1/models"):
            if self.headers.get("Authorization") != f"Bearer {KEY}":
                self.send_response(401); self.end_headers(); return
            body = json.dumps({"data": [{"id": "gyro-gyro-s"}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
            return
        self.send_response(404); self.end_headers()


srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_port}"
import llm  # noqa: E402
ok(llm._models_at(base + "/keyed/v1", 2) is None, "без ключа сервер молчит — как было у Strata")
ok(llm._models_at(base + "/keyed/v1", 2, key=KEY) == ["gyro-gyro-s"], "с ключом профиля — список моделей")
ok(llm._models_at(base + "/plain/v1", 2, known="m1") == ["m1"], "нет /models, но сервер отвечает — модель профиля")
import liranode  # noqa: E402
eng = SimpleNamespace(s=SimpleNamespace(get=lambda *a: {"p": {"kind": "openai", "base_url": base + "/keyed/v1", "api_key": KEY, "model": "gyro-gyro-s"}}
                                        if a == ("llm", "profiles") else None))
got = liranode.models_here(eng)
ok(any(f["base_url"] == base + "/keyed/v1" and "gyro-gyro-s" in f["models"] for f in got), f"«Нода Лиры» видит Strata: {got}")
ok(liranode.own_key(eng, base + "/keyed/v1/") == KEY and liranode.own_key(eng, "http://127.0.0.1:1/v1") == "", "ключ — только своего адреса")
ln = (ROOT / "core/liranode.py").read_text(encoding="utf-8")
ok("key=own_key(self.e, pick[\"base\"])" in ln and "key=own_key(self.e, self.st.get(\"base\")" in ln,
   "замер скорости и задания сети идут к своей модели с её ключом")
srv.shutdown()

# ---------- №819: сторож подключения виджета
js = (ROOT / "ui/assets/dewiar.js").read_text(encoding="utf-8")
ok("DEWIAR_WS_WAIT" in js and "ws.readyState === 0" in js and "clearTimeout(guard)" in js, "dewiar.js: зависшая попытка подключения — заново")
hang = socket.socket(); hang.bind(("127.0.0.1", 0)); hang.listen(16)     # принимает соединение и молчит — как зависшее ядро
port = hang.getsockname()[1]
from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    page = tmp / "w.html"
    page.write_text(f'<html><body><script>window.DEWIAR_WS_WAIT = 400;</script><script src="{(ROOT / "ui/assets/dewiar.js").as_uri()}"></script></body></html>', encoding="utf-8")
    pg.goto(page.as_uri() + f"?port={port}")
    pg.wait_for_timeout(500)
    n = 0
    hang.settimeout(5)
    try:
        while n < 3:
            c, _ = hang.accept(); n += 1
    except socket.timeout:
        pass
    ok(n >= 2, f"зависшая попытка брошена — виджет подключается снова (попыток за 5 с: {n})")
    b.close()
hang.close()

# ---------- идея №300: объявление «вышла версия» — обновление на месте
nw = (ROOT / "ui/studio/news.js").read_text(encoding="utf-8")
ok('go.textContent = "Обновить"' in nw and "#up-check" in nw and "download" in nw, "объявление со ссылкой на «Скачать» → «Обновить» в программе")

# ---------- №818, №820: телефон
tools = (ROOT / "android/www-src/app/10-tools.js").read_text(encoding="utf-8")
ok("HANDS_APK" not in tools and "a.hands_apk" in tools and "UPD_URL" in tools.split("async function handsUrl")[1][:300],
   "«с руками» — файл из описания выпуска, нет его — страница «Скачать» и подсказка")
bt = (ROOT / "android/src/pro/dewiar/app/BtMic.java").read_text(encoding="utf-8")
off = bt.split("static void offNow")[1]
ok("clearCommunicationDevice" in off and "stopBluetoothSco" in off.split("clearCommunicationDevice")[-1], "канал гарнитуры выключается и старым способом")
ok("static String info(" in bt and "audioInfo" in (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8"),
   "отчёт телефона знает громкость и куда идёт звук")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("audio: audioInfo()" in app and "async function handsUrl" in app, "app.js пересобран из частей")

print("\n" + ("❌ Ошибок: %d" % len(fails) if fails else "✅ Всё в порядке"))
sys.exit(1 if fails else 0)
