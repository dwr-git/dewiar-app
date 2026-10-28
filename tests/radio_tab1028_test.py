"""Вкладка «Радио» в «Музыке» (0.64; владелец 28.10: «у нас есть раздел МУЗЫКА, может ещё радио добавить или как-то
совместить»). Одна страница — две вкладки «Моя музыка» / «Радио» и общий плеер:
- «Популярные» — наш список станций плитками; значки — favicon из каталога (ядро ищет их в фоне), нет — буквы;
- жанры и поиск по каталогу radio-browser: без повторов одной станции, свои совпадения — первыми;
- нажали плитку — играет именно она; в плеере значок, «В эфире», ◀ ▶ — соседние станции, ♥ — в «Мои станции»;
- ♥ на плитке — станция в «Моих станциях» (и голосом её можно включить по названию), второе нажатие — убрать;
- каталог не отвечает — понятная фраза; свои станции по ссылке — под «Своя станция по ссылке»."""
import json, math, os, socket, struct, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
SHOTS = os.environ.get("DEWIAR_SHOTS", "")
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
sys.path.insert(0, str(ROOT / "core"))
import radio as R  # noqa: E402

# значки нашего списка: точное название, иначе начало; нет — пусто и не спрашиваем снова месяц
lg = R.Logos(tmp / "lg.json")
asked = []
cat = {"Русское Радио": [{"name": "Русское Радио Москва", "logo": "https://x/rr.png"}, {"name": "Русское Радио", "logo": "https://x/rr0.png"}],
       "Вести ФМ": [{"name": "Вести FM", "logo": ""}], "Рекорд": [{"name": "Радио Рекорд", "logo": "https://x/rec.png"}]}
n = lg.fill(list(cat), find=lambda q: asked.append(q) or cat[q])
ok(n == 2 and lg.get("Русское Радио") == "https://x/rr0.png" and lg.get("Рекорд") == "https://x/rec.png" and lg.get("Вести ФМ") == "",
   f"значки: точное название, «Радио Рекорд» = «Рекорд», без значка — пусто ({lg.data})")
ok(lg.fill(list(cat), find=lambda q: asked.append(q) or []) == 0 and len(asked) == 3 and R.Logos(tmp / "lg.json").get("Рекорд"), "второй раз каталог не спрашиваем, хранится на диске")
ok(R._rows([{"name": "A", "url": "http://a", "favicon": "javascript:x"}, {"name": "B", "url_resolved": "http://b", "favicon": "https://b/i.png"}])[0]["logo"] == ""
   and R._rows([{"name": "B", "url_resolved": "http://b", "favicon": "https://b/i.png"}])[0]["logo"] == "https://b/i.png", "значок — только http(s)")

# --- поток (минута тона в WAV), каталог и значки — свой сервер
RATE = 22050
pcm = b"".join(struct.pack("<h", int(6000 * math.sin(2 * math.pi * 440 * i / RATE))) for i in range(RATE))
WAV = b"RIFF" + struct.pack("<I", 36 + len(pcm) * 60) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16) + b"data" + struct.pack("<I", len(pcm) * 60)
SEARCH, MODE = [], {"down": False}
CAT = [{"name": "Jazz Groove", "url_resolved": "", "favicon": ""},
       {"name": "Smooth Jazz 24", "url_resolved": "STREAM/sj", "favicon": "ICON/sj.svg", "tags": "jazz,smooth", "countrycode": "US"},
       {"name": "Smooth Jazz 24", "url_resolved": "STREAM/sj2", "favicon": "", "tags": "jazz", "countrycode": "US"},
       {"name": "Jazz Radio", "url_resolved": "STREAM/jr", "favicon": "ICON/missing.png", "tags": "jazz", "countrycode": "FR"}]
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="12" fill="#1e88e5"/><circle cx="32" cy="32" r="14" fill="#fff"/></svg>'


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/json/stations/search"):
            q = parse_qs(u.query); SEARCH.append(q)
            if MODE["down"]:
                self.send_response(503); self.end_headers(); return
            base = f"http://127.0.0.1:{self.server.server_port}"
            rows = [dict(x, url_resolved=x["url_resolved"].replace("STREAM", base + "/s"), favicon=x["favicon"].replace("ICON", base + "/i")) for x in CAT]
            body = json.dumps(rows).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
        elif u.path.startswith("/i/sj.svg"):
            self.send_response(200); self.send_header("Content-Type", "image/svg+xml"); self.send_header("Content-Length", str(len(SVG))); self.end_headers(); self.wfile.write(SVG)
        elif u.path.startswith("/s/"):
            self.send_response(200); self.send_header("Content-Type", "audio/wav"); self.end_headers()
            try:
                self.wfile.write(WAV)
                for _ in range(60):
                    self.wfile.write(pcm); time.sleep(0.5)
            except OSError:
                pass
        else:
            self.send_response(404); self.end_headers()


srv = ThreadingHTTPServer(("127.0.0.1", 0), H); SP = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{SP}"

LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "a.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(tmp / "st").mkdir()
# наш список станций (копия с сайта): три станции, одна — с тем же потоком, что в каталоге
(tmp / "st" / "radio.json").write_text(json.dumps({"genres": ["джаз", "новости", "рок"], "stations": [
    {"name": "Радио Тест", "url": BASE + "/s/test", "tags": "русское поп"},
    {"name": "Джаз Тест", "url": BASE + "/s/jazz", "tags": "джаз спокойное"},
    {"name": "Вести Тест", "url": BASE + "/s/news", "tags": "новости разговорное"}]}), encoding="utf-8")
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False}, "radio_url": "http://127.0.0.1:9/none",
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8", DEWIAR_RADIO_API=BASE)
core = subprocess.Popen([PY, str(ROOT / "core/main.py"), "--wav", str(TESTS / "silence90.wav"), "--null-audio"], env=env,
                        stdout=open(tmp / "core.log", "w"), stderr=subprocess.STDOUT)
for _ in range(150):
    time.sleep(0.2)
    if (cfg / "token").exists():
        break
time.sleep(2)
tok = (cfg / "token").read_text().strip()
errs = []


def settings():
    return json.loads((cfg / "settings.json").read_text())


try:
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + f"?token={tok}&port={PORT}"); time.sleep(3)
        pg.click('nav button[data-p="music"]'); time.sleep(1.2)
        ok(pg.get_attribute("#mmt-mine", "aria-selected") == "true" and pg.is_visible("#mm-mine") and not pg.is_visible("#rd-tab"), "сначала — «Моя музыка»")
        pg.click("#mmt-radio"); time.sleep(1.5)
        ok(pg.is_visible("#rd-tab") and not pg.is_visible("#mm-mine") and pg.is_visible("#mm-now") and pg.is_visible(".rd-side"),
           "«Радио»: свои плитки, тот же плеер, справа — как попросить")
        names = pg.eval_on_selector_all("#rd-top .rd-name", "e => e.map(x => x.textContent)")
        ok(names[:3] == ["Радио Тест", "Джаз Тест", "Вести Тест"], f"«Популярные» — наш список: {names}")
        ok(pg.eval_on_selector_all("#rd-top .rd-logo i", "e => e.map(x => x.textContent)")[:3] == ["Т", "ДТ", "ВТ"], "без значка — буквы (слово «радио» не считаем)")
        ok("Нажмите ♥" in pg.inner_text("#rd-mine"), "«Мои станции» пусто — подсказка")
        chips = pg.eval_on_selector_all("#rd-genres .chip", "e => e.map(x => x.textContent)")
        ok(chips == ["Популярные", "Джаз", "Новости", "Рок"], f"жанры: {chips}")

        # жанр: свои совпадения первыми, каталог без повторов и без станций без потока
        pg.click("#rd-genres .chip:nth-child(2)"); time.sleep(1.5)
        names = pg.eval_on_selector_all("#rd-top .rd-name", "e => e.map(x => x.textContent)")
        ok(names == ["Джаз Тест", "Smooth Jazz 24", "Jazz Radio"], f"«Джаз»: своя первой, каталог без повторов: {names}")
        ok(any(q.get("tag") == ["jazz"] for q in SEARCH), f"каталог спрошен по тегу jazz: {SEARCH[-1:]}")
        time.sleep(0.8)
        pics = pg.eval_on_selector_all("#rd-top .rd-logo", "e => e.map(x => [x.classList.contains('pic'), !!x.querySelector('img')])")
        ok(pics[1] == [True, True] and pics[2] == [False, False], f"значок из каталога; не загрузился — буквы: {pics}")
        ok(pg.get_attribute("#rd-genres .chip:nth-child(2)", "class").endswith("on"), "выбранный жанр подсвечен")
        if SHOTS:
            pg.locator("#p-music").screenshot(path=os.path.join(SHOTS, "radio-tab-jazz.png"))

        # нажали — играет именно она; плеер — «В эфире»
        pg.click("#rd-top .rd-t:nth-child(2) .rd-play"); time.sleep(4)
        st = pg.evaluate("core.call('radio_status')")
        ok(st.get("station") == "Smooth Jazz 24" and st.get("logo", "").endswith("/i/sj.svg"), f"играет нажатая станция из каталога: {st}")
        np_ = pg.inner_text("#mm-np")
        ok("В эфире" in np_ and "Smooth Jazz 24" in np_ and pg.evaluate("document.querySelector('#mm-pp').classList.contains('playing')"), f"плеер: {np_!r}")
        ok(pg.is_visible("#mm-cover .rd-logo img") and pg.is_hidden("#mm-time") and pg.get_attribute("#mm-next", "title") == "Следующая станция",
           "в плеере значок станции, без полосы времени, ▶ — следующая станция")
        ok("on" in pg.get_attribute("#rd-top .rd-t:nth-child(2)", "class"), "играющая плитка отмечена")
        if SHOTS:
            pg.locator("#p-music").screenshot(path=os.path.join(SHOTS, "radio-tab-playing.png"))

        # ♥ в плеере — в «Мои станции», с логотипом и жанром
        pg.click("#mm-heart"); time.sleep(1.5)
        rc = settings().get("radio_custom") or []
        ok(rc and rc[0]["name"] == "Smooth Jazz 24" and rc[0].get("logo", "").endswith("/i/sj.svg") and "jazz" in rc[0].get("tags", ""), f"♥ — в моих станциях: {rc}")
        ok(pg.eval_on_selector_all("#rd-mine .rd-name", "e => e.map(x => x.textContent)") == ["Smooth Jazz 24"] and "on" in pg.get_attribute("#mm-heart", "class"),
           "плитка в «Моих станциях», сердце в плеере закрашено")
        # ▶ — следующая станция по списку (мои + найденные)
        pg.click("#mm-next"); time.sleep(3.5)
        ok(pg.evaluate("core.call('radio_status')").get("station") == "Джаз Тест", f"▶ — следующая: {pg.evaluate('core.call(`radio_status`)')}")
        # пауза плиткой и «играть» в плеере
        pg.click("#rd-tab .rd-t.on .rd-play"); time.sleep(1.2)
        ok(not pg.evaluate("core.call('radio_status')").get("playing") and "на паузе" in pg.inner_text("#mm-np"), "нажать играющую плитку — пауза")
        pg.click("#mm-pp"); time.sleep(3)
        ok(pg.evaluate("core.call('radio_status')").get("station") == "Джаз Тест", "«играть» в плеере — та же станция снова")

        # голосом по названию — станция из «Моих»
        ok(any(x["name"] == "Smooth Jazz 24" and x.get("own") for x in pg.evaluate("core.call('radio_list')")["stations"]), "«Мои станции» знает и голос («включи Smooth Jazz 24»)")
        # второе ♥ на плитке — убрать
        pg.hover("#rd-mine .rd-t"); pg.click("#rd-mine .rd-fav"); time.sleep(1.2)
        ok(not settings().get("radio_custom") and "Нажмите ♥" in pg.inner_text("#rd-mine"), "♥ ещё раз — убрана")

        # поиск по названию и пустой запрос — снова «Популярные»; каталог молчит — понятно
        pg.fill("#rd-q", "Smooth"); pg.click("#rd-go"); time.sleep(1.5)
        ok(pg.inner_text("#rd-top-h") == "«Smooth»" and pg.eval_on_selector_all("#rd-top .rd-name", "e => e.map(x => x.textContent)")[:1] == ["Smooth Jazz 24"], "поиск по названию")
        ok(any(q.get("name") == ["smooth"] for q in SEARCH), "каталог спрошен по названию")
        pg.fill("#rd-q", ""); pg.dispatch_event("#rd-q", "input"); time.sleep(0.6)
        ok(pg.inner_text("#rd-top-h") == "Популярные", "очистили поиск — снова популярные")
        MODE["down"] = True
        pg.fill("#rd-q", "Минск"); pg.click("#rd-go"); time.sleep(2.5)
        ok("каталог радиостанций сейчас не отвечает" in pg.inner_text("#rd-top").lower(), f"каталог молчит — сказать: {pg.inner_text('#rd-top')!r}")
        # свои по ссылке — под раскрывашкой
        ok(not pg.is_visible("#rc-add") and pg.is_visible("#rc-panel summary"), "своя станция по ссылке — свёрнуто")
        # вкладка запоминается
        pg.reload(); time.sleep(3); pg.click('nav button[data-p="music"]'); time.sleep(1.2)
        ok(pg.get_attribute("#mmt-radio", "aria-selected") == "true" and pg.is_visible("#rd-tab"), "открылась та же вкладка, что в прошлый раз")
        pg.press("#mmt-radio", "ArrowLeft"); time.sleep(0.4)
        ok(pg.get_attribute("#mmt-mine", "aria-selected") == "true", "вкладки — и стрелками")
        # телефонная ширина: плитки не вылезают
        pg.set_viewport_size({"width": 560, "height": 900}); pg.click("#mmt-radio"); time.sleep(0.8)
        over = pg.evaluate("[...document.querySelectorAll('#rd-tab .rd-t')].some(t => t.getBoundingClientRect().right > document.documentElement.clientWidth + 1)")
        ok(not over, "узкое окно — плитки в ширину")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate(); srv.shutdown()

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
