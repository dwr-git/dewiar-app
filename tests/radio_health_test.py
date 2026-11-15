"""Радио: какие станции у пользователя реально играют (его сеть, его провайдер) — проверка в фоне, молчащие — в конец,
чтобы не ждать на каждой по 11 секунд, когда большая часть станций у него не играет. Станция, которую назвали,
но которая молчит, — честно: «сейчас не отвечает — включаю …»."""
import http.server, os, socket, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
for k in [k for k in os.environ if k.lower().endswith("_proxy")]:
    os.environ.pop(k)
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
from radio import StationHealth, probe  # noqa: E402


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == "/live.mp3":
            self.send_response(200); self.send_header("Content-Type", "audio/mpeg"); self.end_headers()
            try:
                for _ in range(40):
                    self.wfile.write(b"\xff\xfb" + b"\x11" * 1022); self.wfile.flush()
            except OSError:
                pass                                       # проверка прочла начало и закрыла — так и надо
        elif self.path == "/portal":
            b = b"<!doctype html><html><body>Wi-Fi login</body></html>"
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)
        elif self.path == "/hang":
            self.send_response(200); self.send_header("Content-Type", "audio/mpeg"); self.end_headers(); self.wfile.flush()
            time.sleep(12)
        else:
            self.send_response(404); self.end_headers()


s = socket.socket(); s.bind(("127.0.0.1", 0)); P = s.getsockname()[1]; s.close()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", P), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
U = lambda p: f"http://127.0.0.1:{P}{p}"
r = {p: probe(U(p), timeout=4) for p in ("/live.mp3", "/portal", "/none", "/hang")}
ok(r["/live.mp3"] == (True, ""), f"станция со звуком — играет: {r['/live.mp3']}")
ok(r["/portal"][0] is False and "веб-страница" in r["/portal"][1], f"страница входа в Wi-Fi вместо звука — не играет: {r['/portal']}")
ok(r["/none"] == (False, "ответ 404"), f"404 — не играет: {r['/none']}")
ok(r["/hang"][0] is False, f"станция молчит — не играет: {r['/hang']}")
tmp = Path(tempfile.mkdtemp())
st = [{"name": n, "url": U(p)} for n, p in (("Рекорд", "/none"), ("Медляк", "/live.mp3"), ("Портал", "/portal"), ("Джаз", "/live.mp3"))]
h = StationHealth(tmp / "health.json")
t0 = time.monotonic()
n = h.check_all(st)
ok(n == 4 and time.monotonic() - t0 < 10, f"фоновая проверка всего списка параллельно ({time.monotonic() - t0:.1f} с)")
ok([s["name"] for s in h.order(st)] == ["Медляк", "Джаз", "Рекорд", "Портал"], f"молчащие — в конце: {[s['name'] for s in h.order(st)]}")
ok(h.check_all(st) == 0, "повторно раньше 12 часов не проверяем")
h2 = StationHealth(tmp / "health.json")
ok(h2.dead(U("/none")) and not h2.dead(U("/live.mp3")), "результаты сохраняются между запусками")
h2.mark(U("/none"), True)
ok(not h2.dead(U("/none")), "станция заиграла — снова в начале")

# ядро: названную, но молчащую станцию — честно пропускаем
import engine as E  # noqa: E402
from types import SimpleNamespace  # noqa: E402
e = E.Engine.__new__(E.Engine)
e.radio_health = h
said = []
e._say_quick = lambda msg, s_, via=None: said.append(msg)
e.radio = SimpleNamespace(play=lambda s_: None, _gen=1, playing=False, paused=None, got=0, failed="", volume=0.8, stop=lambda: None)
e.note = lambda t: None
import engine_music as EM  # noqa: E402 — музыка живёт здесь (engine.py разбит на части)
EM.threading = SimpleNamespace(Thread=lambda **k: SimpleNamespace(start=lambda: None))     # без фонового потока
E.Engine._play_station(e, [st[0], st[1]], "включи рекорд", "Включаю «{}».")
# 15.11: станция списка молчит — сначала она же по новому адресу из каталога (не дольше 4 с), потом другая
ok(said == ["Включаю «Рекорд»."], f"названная станция молчит — сначала она же из каталога: {said}")
said.clear()
E.Engine._play_station(e, [dict(st[0], own=True), st[1]], "включи рекорд", "Включаю «{}».")
ok(said == ["«Рекорд» сейчас не отвечает — включаю «Медляк»."], f"своя станция по ссылке молчит — сразу живая: {said}")
