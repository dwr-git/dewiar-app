"""Отчёт №362 (27.10): весь вечер «облако Dewiar не ответило» (WinError 10060) — провайдер или сеть не пускали к
dewiar.pro, а прокси человек не включал; модель не отвечала, человек жал «стоп». Запасной путь: прокси Dewiar берётся
заранее, пока сайт открывается (вошедшим или с ключом, если раздача включена на сайте), а запросы к Dewiar идут
напрямую; не соединилось — тот же запрос через этот прокси, 15 минут дальше — сразу через него, человеку — одно
сообщение в чат. Свой прокси или галочка «Использовать прокси Dewiar» — как раньше (запасной не нужен)."""
import os, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import proxykit  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
K = proxykit.start(tmp)
os.environ["SSL_CERT_FILE"] = K.CA
SOCKS = f"socks5://anna:s3cret@127.0.0.1:{K.SP}"
URL = "https://dewiar.pro/dwrapp/latest.json"
sys.path.insert(0, str(ROOT / "core"))
import httpx  # noqa: E402
import net  # noqa: E402
net.install()
told = []
net.on_reserve = lambda h: told.append(h)


def get(url):
    try:
        r = httpx.get(url, timeout=6)
        return r.status_code, r.text
    except Exception as e:  # noqa: BLE001
        return 0, type(e).__name__


conf = {"v": ("", [], SOCKS)}
net.bind(lambda: conf["v"])
s0 = K.SEEN["socks"]
d = get(URL)
ok(d[0] == 200 and '"0.0.1"' in d[1] and K.SEEN["socks"] == s0 + 1, f"dewiar.pro напрямую не открылся — ответ запасным путём: {d[0] or d[1]}")
ok(told == ["dewiar.pro"] and net._reserve_bad.get("dewiar.pro", 0) > time.time(), "человеку — одно сообщение; 15 минут — сразу запасным")
t0 = time.time(); d = get(URL)
ok(d[0] == 200 and K.SEEN["socks"] == s0 + 2 and told == ["dewiar.pro"], f"второй раз — сразу через прокси, без нового сообщения ({time.time() - t0:.2f} с)")
# сайт открывается напрямую — запасной путь не трогаем
df = net._DirectFirst(SOCKS, True, None)
s1 = K.SEEN["socks"]
r = df.handle_request(httpx.Request("GET", f"http://127.0.0.1:{K.PLAIN}/dwrapp/latest.json")); r.read()
ok(r.status_code == 200 and K.SEEN["socks"] == s1, "напрямую открывается — напрямую, прокси не трогаем")
# запасной тоже не пускает — честная ошибка, а не зависание
net._reserve_bad.clear(); told.clear()
conf["v"] = ("", [], f"socks5://127.0.0.1:{K.DEAD}")
d = get(URL)
ok(d[0] == 0 and not told, f"ни напрямую, ни запасным — ошибка как раньше: {d[1]}")
# свой прокси — главнее: запасной не нужен
conf["v"] = (SOCKS, [], f"socks5://127.0.0.1:{K.DEAD}")
ok(net.reserve() == "", "свой прокси (или галочка «прокси Dewiar») — запасной не используется")
net._reserve_bad.clear()

# ядро: настройки и получение прокси заранее
from engine_brain import BrainMixin  # noqa: E402
st = {"net": {"reserve": True, "dewiar_secret": "socks5://u:p@1.2.3.4:1080", "dewiar": False, "proxy": ""}, "cloud": {"key": ""}}


class Sett:
    def get(self, *k, default=None):
        v = st
        for x in k:
            v = (v or {}).get(x) if isinstance(v, dict) else None
        return default if v is None else v

    def update(self, patch):
        for k, v in patch.items():
            st.setdefault(k, {}).update(v)


fake = SimpleNamespace(s=Sett(), account=SimpleNamespace(logged_in=lambda: False, token=lambda: "", data={}, service_url=lambda k: ""), _net_try="")
c = BrainMixin._net_conf(fake)
ok(c[0] == "" and c[2] == "socks5://u:p@1.2.3.4:1080", f"по умолчанию: напрямую, прокси Dewiar — запасным: {c[0]!r}, {net.hide(c[2])}")
st["net"]["reserve"] = False
ok(BrainMixin._net_conf(fake)[2] == "", "запасной путь выключен — его нет")
st["net"]["reserve"] = True
ok(BrainMixin._dewiar_proxy_fetch(fake) == "" and not st["net"].get("dewiar_try"), "без входа и ключа — прокси заранее не спрашиваем и не жалуемся")
defaults = (ROOT / "core/settings.py").read_text(encoding="utf-8")
ok('"reserve": True' in defaults, "запасной путь включён по умолчанию")
ui = (ROOT / "ui/settings.html").read_text(encoding="utf-8") + (ROOT / "ui/studio/dewiar.js").read_text(encoding="utf-8")
ok('id="dw-rv"' in ui and 'core.call("net_reserve"' in ui and "Сейчас работает: dewiar.pro напрямую не открывался" in ui,
   "студия → «Dewiar.pro» → «Сеть»: переключатель «Запасной путь» и что сейчас с ним")
eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok("net.on_reserve = lambda h: self.chat.notify(" in eng, "сообщение в чат, когда запасной путь сработал")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
