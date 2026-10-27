"""№359 (27.10): «включи радио ЖелезоФМ» играло Groove Salad и «Вести ФМ», «включи радио Железо-ФМ https://…» — ничего,
файл fefm.m3u со словами «включи радио с файла» — Radio Swiss Pop. «Где можно добавлять потоки радио? В моём случае это
радио нашего города». Теперь:
- ссылка на поток в просьбе или плейлист .m3u/.pls во вложении + «включи» — играет именно он и запоминается своей
  станцией («запомни» — только запоминает); дальше — «включи Железо-ФМ»;
- своя станция не подменяется чужой, если не отвечает; модель тоже может передать ссылку (play_radio url);
- каталог не подсовывает станцию без общего слова с запросом; не нашли — так и сказать и подсказать, как добавить;
- студия → «Музыка» → «Свои радиостанции»: список, «Включить», убрать, добавить по ссылке."""
import json, os, socket, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TESTS = Path(__file__).resolve().parent
PY = os.environ.get("DEWIAR_PY") or sys.executable
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


def free():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "ucfg"), DEWIAR_STATE_DIR=str(tmp / "ust"))
sys.path.insert(0, str(ROOT / "core"))
from radio import pick  # noqa: E402
CAT = [{"name": "Groove Salad"}, {"name": "Radio Swiss Pop"}, {"name": "Европа Плюс Москва"}, {"name": "Smooth Jazz"}]
ok(pick(CAT, "железо фм") is None and pick(CAT, "с файла") is None, "каталог: без общего слова с запросом — не подсовываем случайную")
ok(pick(CAT, "европа плюс")["name"] == "Европа Плюс Москва" and pick(CAT, "джаз")["name"] == "Groove Salad", "по названию и по жанру — как раньше")

from music import Catalog  # noqa: E402
(tmp / "b.json").write_text(json.dumps({"stations": [{"name": "Радио Дача", "url": "http://x/dacha", "tags": "русское"}]}), encoding="utf-8")
own = [{"name": "Железо-ФМ", "url": "https://online.fefm.ru:8443/fefm"}]
cat = Catalog(lambda: "http://127.0.0.1:9/none", tmp / "c.json", tmp / "b.json", custom_fn=lambda: own)
cat._loaded_at = time.time(); cat._data = cat._read(tmp / "b.json")
m = cat.match("железо фм")
ok(m and m[0]["name"] == "Железо-ФМ" and m[0].get("own"), f"своя станция находится по названию: {[x['name'] for x in m]}")

from engine_music import MusicMixin  # noqa: E402
saved, said, played = {}, [], []


class Sett:
    def get(self, *k, default=None):
        return saved.get(k[0], default) if k else default

    def update(self, patch):
        saved.update(patch)


fake = SimpleNamespace(s=Sett(), radio=SimpleNamespace(status=lambda: {}), emit=lambda *a, **k: None,
                       _say_quick=lambda t, *a: said.append(t), _play_station=lambda c, t, p: played.append((c, p)))
fake._URL_RX, fake._NAME_DROP = MusicMixin._URL_RX, MusicMixin._NAME_DROP
fake.radio_custom_save = lambda n, u: MusicMixin.radio_custom_save(fake, n, u)
run = lambda t: MusicMixin._radio_url_cmd(fake, t)  # noqa: E731
ok(run("Включи радио Железо-ФМ https://online.fefm.ru:8443/fefm") and played[-1][0][0]["url"] == "https://online.fefm.ru:8443/fefm"
   and played[-1][0][0]["name"] == "Железо-ФМ" and "Запомнил" in played[-1][1], f"ссылка в просьбе — играет она и запоминается: {played[-1]}")
M3U = "включи радио с файла\n\nВложения:\n[Файл «fefm.m3u», сохранён в папке ассистента: Входящие/fefm.m3u]\n#EXTM3U\n\n#EXTINF:-1,FeFm Radio 99,0 Zheleznogorsk\n\nhttps://online.fefm.ru:8443/fefm"
ok(run(M3U) and played[-1][0][0]["name"] == "FeFm Radio 99,0 Zheleznogorsk", f"файл .m3u + «включи» — его поток, название из файла: {played[-1][0][0]}")
ok(len(saved["radio_custom"]) == 1 and saved["radio_custom"][0]["name"] == "FeFm Radio 99,0 Zheleznogorsk", f"та же ссылка — одна запись: {saved['radio_custom']}")
n = len(played)
ok(run("запомни станцию Дача http://listen13.vdfm.ru:8000/dacha") and len(played) == n and "Запомнил станцию «Дача»" in said[-1], f"«запомни» — без включения: {said[-1]}")
ok(not run("вот статья https://habr.com/ru/articles/1/") and not run("Посмотри вложения\n\nВложения:\n[x]\n#EXTM3U\nhttps://a/b"),
   "просто ссылка в разговоре и файл без «включи» — не радио")
src = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok('not s.get("own")' in src and "не подменяем её чужой" in src and "Не нашёл станцию" in src, "своя не подменяется чужой; не нашли — подсказка")
ok('"url": {"type": "string"' in (ROOT / "core/tools.py").read_text(encoding="utf-8"), "модель может передать ссылку (play_radio url)")

# студия
LLM, PORT = free(), free()
mock = subprocess.Popen([sys.executable, str(TESTS / "mock_llm.py"), str(LLM)], env=dict(os.environ, MOCK_LOG=str(tmp / "a.log")))
cfg = tmp / "cfg"; cfg.mkdir()
(cfg / "settings.json").write_text(json.dumps({"persona": "lira", "audio": {"sounds": False}, "ui": {"news_seen": "99.0.0", "welcome": "done"},
                                               "stt": {"engine": "vosk"}, "tts": {"engine": "off"}, "updates": {"auto_check": False},
                                               "radio_custom": [{"name": "Железо-ФМ", "url": "https://online.fefm.ru:8443/fefm"}],
                                               "llm": {"active": "m", "profiles": {"m": {"name": "Мок", "kind": "openai", "base_url": f"http://127.0.0.1:{LLM}/v1", "model": "mock"}}}}))
env = dict(os.environ, DEWIAR_CONFIG_DIR=str(cfg), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_PORT=str(PORT), DEWIAR_ASSUME_AEC="1",
           DEWIAR_WORKSPACE_DIR=str(tmp / "ws"), DEWIAR_FAKE_RAM_GB="16", DEWIAR_FAKE_CORES="8")
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
        pg.click('nav button[data-p="music"]'); time.sleep(1.2)
        ok("Железо-ФМ" in pg.inner_text("#rc-list"), f"«Свои радиостанции» — список: {pg.inner_text('#rc-list')[:80]!r}")
        pg.evaluate("() => { const c0 = core.call.bind(core); core.call = (c, a) => c === 'radio_custom_add' ? c0(c, Object.assign({}, a, { play: false })) : c0(c, a); }")
        pg.fill("#rc-name", "Радио Город"); pg.fill("#rc-url", "http://127.0.0.1:9/city"); pg.click("#rc-add button"); time.sleep(1.0)
        ok("Радио Город" in pg.inner_text("#rc-list"), "добавить по названию и ссылке")
        pg.fill("#rc-name", "Плохая"); pg.fill("#rc-url", "ftp://x"); pg.click("#rc-add button"); time.sleep(0.8)
        ok("Плохая" not in pg.inner_text("#rc-list"), "не ссылка на поток — не добавляется")
        pg.click("#rc-list [data-rcd='http://127.0.0.1:9/city']"); time.sleep(0.4)
        pg.click("#rc-list [data-rcd='http://127.0.0.1:9/city']"); time.sleep(0.8)
        ok("Радио Город" not in pg.inner_text("#rc-list"), "«×» дважды — убрана")
        st = json.loads((cfg / "settings.json").read_text())
        ok([x["name"] for x in st.get("radio_custom", [])] == ["Железо-ФМ"], f"в настройках: {st.get('radio_custom')}")
        ok(not errs, f"без ошибок на странице: {errs[:2]}")
        b.close()
finally:
    core.terminate(); mock.terminate()

print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
