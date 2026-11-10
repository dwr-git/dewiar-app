"""Telegram и прокси, который просит логин (407 Proxy Authentication Required) — письмо владельцу 10.11: «бот готовит
ответ, а при отправке — ошибка 407; проверка подключения Telegram показывает то же самое».
До Telegram такой запрос не доходит, поэтому Dewiar пробует напрямую: связь есть — отправляет и полчаса ходит мимо
прокси; связи нет — говорит, чей прокси просит логин и как его вписать. Telegram и прокси — поддельные, на 127.0.0.1."""
import json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
for k in [k for k in os.environ if k.lower().endswith("_proxy")]:
    os.environ.pop(k)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
TOKEN = "123456789:AAHfakeTokenForDewiarTests_abcdefghijk"
SEEN = {"tg": 0, "proxy": 0}


class TG(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_POST(self):
        SEEN["tg"] += 1
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        m = self.path.rsplit("/", 1)[-1]
        res = {"id": 1, "username": "test_bot", "first_name": "Тест"} if m == "getMe" else [] if m == "getUpdates" else True
        b = json.dumps({"ok": True, "result": res}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    do_GET = do_POST


class Need407(BaseHTTPRequestHandler):
    """Прокси с логином: на любой запрос — 407."""
    def log_message(self, *a): pass

    def _no(self):
        SEEN["proxy"] += 1
        self.send_response(407); self.send_header("Proxy-Authenticate", 'Basic realm="proxy"')
        self.send_header("Content-Length", "0"); self.end_headers()

    do_GET = do_POST = do_CONNECT = _no


def serve(h):
    s = ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


tgs, pxs = serve(TG), serve(Need407)
API = f"http://127.0.0.1:{tgs.server_port}"
PX = f"http://127.0.0.1:{pxs.server_port}"

from telegram import Telegram, TelegramError  # noqa: E402

tg = Telegram(path=tmp / "cfg/telegram.json")
tg.connect(TOKEN, API)
tg.data["proxy"] = PX                                   # сохранён, когда ещё работал (потом срок платного прокси вышел)

before = SEEN["tg"]
r = tg._call("sendMessage", chat_id=1, text="привет")
ok(r is True and SEEN["tg"] > before and SEEN["proxy"] >= 1, "прокси в настройках Telegram просит логин (407) — ответ всё равно ушёл, напрямую")
p0 = SEEN["proxy"]
tg._call("sendMessage", chat_id=1, text="ещё")
ok(SEEN["proxy"] == p0, "дальше — сразу напрямую, без лишнего круга через прокси")

# прокси компьютера (переменные окружения, как Windows отдаёт «Параметры → Сеть → Прокси»)
tg2 = Telegram(path=tmp / "cfg/telegram2.json")
tg2.connect(TOKEN, API)
tg2.data.pop("proxy", None)
os.environ["HTTP_PROXY"] = os.environ["http_proxy"] = PX
os.environ["NO_PROXY"] = os.environ["no_proxy"] = ""
p0, before = SEEN["proxy"], SEEN["tg"]
r = tg2._call("sendMessage", chat_id=1, text="привет")
ok(r is True and SEEN["tg"] > before, "прокси компьютера просит логин — ответ ушёл напрямую")

# напрямую Telegram не открывается — понятные слова
tgs.shutdown(); tgs.server_close()
tg3 = Telegram(path=tmp / "cfg/telegram3.json")
tg3.data.update(token=TOKEN, api=API, proxy=PX)
msg = ""
try:
    tg3._call("sendMessage", chat_id=1, text="привет")
except TelegramError as e:
    msg = str(e)
ok("407" in msg and "логин" in msg and "Telegram" in msg and "http://логин:пароль@" in msg,
   f"Telegram напрямую закрыт — сказано, чей прокси просит логин и как вписать: «{msg[:120]}»")
ok("anna" not in msg and "s3cret" not in msg, "в тексте ошибки нет чужих паролей")
