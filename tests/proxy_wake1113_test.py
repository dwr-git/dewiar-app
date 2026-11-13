"""13.11 (владелец, 21:30): после сна компьютера Лира на каждый вопрос говорила «Не получилось: прокси не пустил: просит
логин и пароль (407)…», проверка обновлений — «latest.json: 407 Proxy Authentication Required»; помогли два перезапуска.
Логин прокси Dewiar (запасной путь или галочка «Использовать прокси Dewiar») устарел, а программа продолжала ходить через
него. Теперь: 407 от прокси Dewiar — до свежего логина к серверам Dewiar напрямую (без прокси); 407, а напрямую нет связи —
показываем настоящую причину (нет сети), а не «прокси»; проснулись — пути к серверам заново, свежий логин."""
import os, sys, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import httpx  # noqa: E402
import net  # noqa: E402
import engine_brain as EB  # noqa: E402
cls = next(c for c in vars(EB).values() if isinstance(c, type) and hasattr(c, "_proxy_auth_stale"))


class S:
    def __init__(self, d): self.d = d
    def get(self, a, k=None): v = self.d.get(a); return v if k is None else (v or {}).get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]


st = S({"net": {"dewiar": True, "dewiar_secret": "http://u:old@px.example:3128", "dewiar_at": time.time()}, "cloud": {}, "updates": {}})
fetched = []
e = types.SimpleNamespace(s=st, account=None, _net_try="", _dewiar_proxy_fetch=lambda force=False: fetched.append(force))
conf = lambda: cls._net_conf(e)  # noqa: E731
ok(conf()[0] == "http://u:old@px.example:3128", "до 407 — через прокси Dewiar (галочка включена)")
cls._proxy_auth_stale(e)
ok(conf()[0] == "" and conf()[2] == "", f"407 — до свежего логина напрямую, без прокси Dewiar: {conf()[:3]}")
cls._proxy_auth_stale(e)
ok(e._px_stale and len(fetched) <= 1, "повторный 407 в те же 10 минут — без лишних запросов, но и без прокси")
own = S({"net": {"proxy": "http://me:pw@my:8080", "dewiar_secret": "http://u:old@px:1"}, "cloud": {}, "updates": {}})
e2 = types.SimpleNamespace(s=own, account=None, _net_try="", _dewiar_proxy_fetch=lambda force=False: None)
ok(cls._proxy_auth_stale(e2) is False and cls._net_conf(e2)[0] == "http://me:pw@my:8080", "свой прокси человека не трогаем")
src = (ROOT / "core/engine_brain.py").read_text(encoding="utf-8")
ok("self._px_stale = False" in src.split("def _dewiar_proxy_fetch")[1].split("def _proxy_auth_stale")[0], "свежий логин получен — снова через прокси")

# 407, а напрямую нет связи — настоящая причина
lz = net._Lazy("http://u:old@127.0.0.1:9", True, None)


class T407:
    def handle_request(self, req): raise httpx.ProxyError("407 Proxy Authentication Required")


class NoNet:
    def handle_request(self, req): raise httpx.ConnectError("[Errno -3] Temporary failure in name resolution")


lz.t, lz.d = T407(), NoNet()
old = net.on_proxy_auth
net.on_proxy_auth = None
try:
    lz.handle_request(httpx.Request("GET", "https://dewiar.pro/dwrapp/latest.json"))
    ok(False, "ошибка наружу")
except httpx.ConnectError as x:
    ok("name resolution" in str(x), f"407 и нет сети — «нет связи», а не «прокси не пустил»: {x}")
except httpx.ProxyError as x:
    ok(False, f"407 и нет сети — «нет связи», а не «прокси не пустил»: {x}")
net.on_proxy_auth = old

# проснулись — пути заново
net._reserve_bad["dewiar.pro"] = time.time() + 900
net._direct_ok["dewiar.pro"] = time.time() + 900
net.wake_reset()
ok(not net._reserve_bad and not net._direct_ok, "проснулись — забыли, что знали о путях до сна")
tsrc = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("net.wake_reset()" in tsrc.split("def _reminders_wake")[1][:1500] and "self._px_auth_at = 0" in tsrc, "при пробуждении — сброс и свежий логин")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
