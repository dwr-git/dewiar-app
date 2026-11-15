"""После сна — «Connection refused» к dewiar.pro три минуты (владелец 15.11, Ubuntu: «ушёл в сон, после включения — не могу
подключиться к dewiar.pro, а в браузере открывается… прошло 3 минуты и заработало»). Сайт стоит дома; «дома — напрямую»
проверили, пока сеть после сна ещё не поднялась, и 3 минуты (LAN_BAD_SEC) не пробовали, а по имени изнутри дома роутер не
пускает (нет «петли») — отказ. Теперь: 1) после сна домашний адрес проверяется заново при первом же запросе;
2) по имени отказали сразу («refused») — домашний адрес проверяется тут же, и запрос идёт туда; 3) приветствие «С
возвращением», которое человек не просил, при неготовой сети молчит, а не показывает ошибку."""
import os, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import httpx  # noqa: E402
import net  # noqa: E402

PUB, LAN = "https://dewiar-home.example/dwrapp/", "http://192.168.1.46:9099/dwrapp/"
net.set_lan(PUB, LAN, "lid-1")
net._lan["ok_until"], net._lan["bad_until"] = 0.0, time.time() + 170      # проверили при сне — «не дома» ещё 3 минуты
net.wake_reset()
ok(net._lan["bad_until"] == 0.0 and net._lan["ok_until"] == 0.0, "проснулись — домашний адрес проверить заново, а не ждать 3 минуты")


class Refused(httpx.BaseTransport):
    def handle_request(self, request):
        raise httpx.ConnectError("[Errno 111] Connection refused")


class Home(httpx.BaseTransport):
    seen = []

    def handle_request(self, request):
        Home.seen.append(str(request.url))
        return httpx.Response(200, json={"version": "1.0.4"})


checks = []
real = net._lan_ok
net._lan_ok = lambda st=None: checks.append(1) or len(checks) > 1     # первая проверка (до запроса) — нет, вторая — да
try:
    net._lan["ok_until"], net._lan["bad_until"] = 0.0, time.time() + 170
    t = net._LanFirst(Refused(), True, None)
    t.t = Home()
    r = t.handle_request(httpx.Request("GET", PUB + "latest.json"))
    ok(r.status_code == 200 and Home.seen == [LAN + "latest.json"] and len(checks) >= 2,
       f"по имени — «Connection refused»: домашний адрес проверен тут же, запрос ушёл туда ({Home.seen})")
    checks.clear()
    net._lan_ok = lambda st=None: checks.append(1) and False
    try:
        t.handle_request(httpx.Request("GET", PUB + "latest.json"))
        ok(False, "не дома и по имени отказ — ошибка как была")
    except httpx.ConnectError:
        ok(True, "не дома и по имени отказ — ошибка как была (не прячем)")

    class Timeout(httpx.BaseTransport):
        def handle_request(self, request):
            raise httpx.ConnectError("timed out")
    checks.clear()
    try:
        net._LanFirst(Timeout(), True, None).handle_request(httpx.Request("GET", PUB + "x"))
    except httpx.ConnectError:
        pass
    ok(checks == [1], "другая ошибка связи (не «отказ») — домашний адрес лишний раз не проверяем")
finally:
    net._lan_ok = real
    net.set_lan("", "", "")

src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
i = src.index("приветствие не вышло")
ok('getattr(turn, "greet", False) and why_kind(e) in ("connect", "timeout")' in src[i - 600:i] and 'turn.full, turn.error = "", ""' in src[i:i + 200],
   "приветствие «С возвращением» при неготовой сети — молчит, без ошибки на экране")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
