"""«Ведущий» (0.74; владелец 30.10: «режим диджея, как у Алисы — с настройкой: может злить человека ближайшее дело или
письмо, чтобы галочками ставить, что допустимо»; и на снимке ведущий объявлял трек «6»).
Между песнями — одна полезная фраза по галочкам (по умолчанию время и погода; дела и письма — выключены) и название,
если оно со смыслом: «6», «Track 05», «VID-2023…» не произносим. Частота — раз в 1/2/3/5 песен. Голосом: «веди эфир»,
«хватит болтать». На радио — раз в 25 минут, в тихую минуту. Студия → «Музыка»: карточка «Ведущий» с галочками."""
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import mymusic as MM  # noqa: E402
import settings as SET  # noqa: E402

# ---------- названия без смысла ----------
for s in ("6", "01", "Track 05", "Новая запись 3", "VID-20230101-WA0001", "a8f9c0d1e2f3", "Unknown", "Неизвестный исполнитель", "Audio_12"):
    ok(not MM.meaningful(s), f"«{s}» — не произносим")
for s in ("Кино", "Ты", "Звезда по имени Солнце", "Song 2", "99 Luftballons"):
    ok(MM.meaningful(s), f"«{s}» — название")
ok(MM.intro({"title": "6", "artist": ""}) == "", "трек «6» без исполнителя — ведущий его не объявляет")
ok(MM.intro({"title": "6", "artist": ""}, first=True, what="музыку из вашей папки") == "Включаю музыку из вашей папки.",
   "первый трек «6» — только «Включаю музыку…», без «Начнём с «6»»")
x = MM.intro({"title": "Track 05", "artist": "Кино"}, rnd=__import__("random").Random(1))
ok("Кино" in x and "Track" not in x and "«" not in x, f"номер дорожки — нет, исполнитель — да: {x}")
x = MM.intro({"title": "07", "artist": "Кино"}, prev={"title": "Группа крови", "artist": "Кино"})
ok(x == "И снова Кино.", f"тот же исполнитель, название — номер: {x}")

# ---------- что сказать между песнями ----------
d = SET.DEFAULTS["music"] if hasattr(SET, "DEFAULTS") else None
o = MM.dj_opts({})
ok(o == {"track": True, "time": True, "weather": True, "tasks": False, "mail": False}, f"по умолчанию: название, время, погода; дела и письма — нет: {o}")
ok(MM.dj_opts({"dj_say": {"tasks": True, "junk": 1}})["tasks"] and "junk" not in MM.dj_opts({"dj_say": {"junk": 1}}), "галочки поверх умолчаний")
now = time.time()
task = ("r:1", "Напоминаю: через 40 минут — созвон.")
facts = {"task": task, "mail": 2, "weather": "За окном плюс 5°, облачно."}
ok(MM.dj_extra(o, facts, {}, now) == ("weather", facts["weather"]), "дела и письма выключены — о них ни слова; погода — да")
ok(MM.dj_extra(dict(o, tasks=True, mail=True), facts, {}, now)[0] == "tasks", "дело включено — оно важнее всего")
ok(MM.dj_extra(dict(o, tasks=True, mail=True), facts, {"tasks_said": ["r:1"]}, now) == ("mail", "Кстати, пришло 2 новых письма."),
   "то же дело второй раз не повторяет; письма — числом, без отправителя")
ok(MM.dj_extra(o, facts, {"weather": now - 600}, now)[0] == "time", "погода была 10 минут назад — теперь время")
ok(MM.dj_extra(o, facts, {"weather": now - 600, "time": now - 300}, now) == ("", ""), "и время было недавно — только название")
ok(MM.dj_extra(dict(o, time=False, weather=False), facts, {}, now) == ("", ""), "всё снято — ничего лишнего")
n0 = datetime(2026, 10, 30, 14, 0)
ok(MM.say_task("Созвон с Андреем", n0 + timedelta(minutes=40), n0) == "Напоминаю: через 40 минут — Созвон с Андреем.", "дело — через сколько минут")
ok(MM.say_task("Встреча", n0 + timedelta(minutes=95), n0) == "Напоминаю: в 15:35 — Встреча.", "дело дальше часа — во сколько")
ok(MM.say_time(datetime(2026, 10, 30, 9, 5)) == "На часах 9:05." and MM.say_mail(1) == "Кстати, пришло новое письмо.", "время и одно письмо")
ok(MM.say_weather({"now": -3, "sky": "снег"}) == "За окном минус 3°, снег.", "погода — с настоящим числом")
ok(SET.DEFAULTS["music"]["dj_say"]["tasks"] is False and SET.DEFAULTS["music"]["dj_radio"] is False if hasattr(SET, "DEFAULTS") else True,
   "в настройках по умолчанию дела выключены, ведущий на радио — тоже")


# ---------- ядро без звука ----------
class S:
    def __init__(self):
        self.d = {"music": {"folder": "", "favs": [], "dj_talk": True, "dj_every": 2}, "morning": {"city": ""}}

    def get(self, *ks, default=None):
        v = self.d
        for k in ks:
            v = v.get(k) if isinstance(v, dict) else None
        return default if v is None else v

    def update(self, patch):
        for k, v in patch.items():
            self.d.setdefault(k, {}).update(v)


class FakeRadio:
    def __init__(self):
        self.station, self.paused, self.played, self.on_end = None, None, [], None

    def play(self, st):
        self.station, self.paused = st, None
        self.played.append(st)

    def status(self):
        return {"playing": bool(self.station)}


class Rem:
    def __init__(self):
        self.at = time.time() + 30 * 60

    def occurrences(self, days=14, limit=400):
        return [{"id": "7@x", "at": int(self.at), "text": "Позвонить маме"}]


from engine_mymusic import MyMusicMixin  # noqa: E402

tmp = Path(tempfile.mkdtemp())


class E(MyMusicMixin):
    def __init__(self):
        self.s, self.radio, self.said, self.dj_said = S(), FakeRadio(), [], []
        self.turn, self.state, self.stopping = None, "idle", threading.Event()
        self.reminders = Rem()
        self._mine_init(tmp / "state")
        self._dj_say = lambda t: self.dj_said.append(t)

    def _say_quick(self, msg, said, **kw):
        self.said.append(msg)

    def emit(self, *a, **k):
        pass

    def _g(self, t):
        return t


e = E()
tracks = [{"title": "Группа крови", "artist": "Кино", "path": "/m/1.mp3"}, {"title": "6", "artist": "", "path": "/m/6.mp3"},
          {"title": "Выхода нет", "artist": "Сплин", "path": "/m/3.mp3"}, {"title": "Track 05", "artist": "", "path": "/m/5.mp3"}] + \
         [{"title": f"Песня про лето {i}", "artist": "Мумий Тролль", "path": f"/m/l{i}.mp3"} for i in range(20)]   # очередь не кончится
e.mylib.tracks = list(tracks)
e.dj.start(tracks, "", shuffle=False)
e.radio.play(e.dj.station(e.dj.current()))
for _ in range(4):
    e._mine_ended(e.radio.station)
ok(len(e.dj_said) == 2, f"раз в 2 песни: {e.dj_said}")
ok(all("«6»" not in x and "Track" not in x for x in e.dj_said), f"«6» и «Track 05» не объявлены: {e.dj_said}")
ok(e.dj_said and e.dj_said[0].startswith("На часах "), f"первая пауза — время (погоды нет: город не указан): {e.dj_said[:1]}")
ok(not any("маме" in x for x in e.dj_said), "дела выключены — про «Позвонить маме» ни слова")
e.s.update({"music": {"dj_say": {"tasks": True}}})
e.dj_said.clear()
for _ in range(2):
    e._mine_ended(e.radio.station)
ok(e.dj_said and "через 30 минут — Позвонить маме" in e.dj_said[0], f"галочка «Ближайшее дело» — напомнит: {e.dj_said}")
e.dj_said.clear()
for _ in range(2):
    e._mine_ended(e.radio.station)
ok(not any("маме" in x for x in e.dj_said), f"то же дело — один раз: {e.dj_said}")

# голосом
e.said.clear()
ok(e._mine_cmd("хватит болтать") and e.s.get("music", "dj_talk") is False and "только музыка" in e.said[-1], "«хватит болтать» под музыку — ведущий молчит")
e.dj_said.clear()
for _ in range(4):
    e._mine_ended(e.radio.station)
ok(not e.dj_said, "и правда молчит")
ok(e._mine_cmd("Лира, веди эфир") and e.s.get("music", "dj_talk") is True and "Веду эфир" in e.said[-1] and "2 песни" in e.said[-1],
   f"«веди эфир» — снова говорит: {e.said[-1]}")
e.radio.station = None
ok(not e._mine_cmd("хватит болтать"), "«хватит болтать» без музыки — это не про ведущего, дальше — разговор")
ok(e._mine_cmd("будь моим диджеем") and e.radio.station and e.radio.station.get("_mine") and e.said[-1].startswith("Веду эфир!"),
   f"«будь моим диджеем», когда ничего не играет, — включает музыку из папки: {e.said[-1]}")

# радио: раз в 25 минут, поверх станции
import engine_mymusic as EM  # noqa: E402

e.dj_said.clear()
e.s.update({"music": {"dj_radio": True, "dj_say": {"tasks": False}}})
e.radio.station = {"name": "Ретро FM", "url": "http://r"}
e._dj_last.clear()
EM.RADIO_HOST_S = 0.5
e.stopping.set()
e.stopping = threading.Event()
orig_wait = e.stopping.wait
e.stopping.wait = lambda t: orig_wait(0.3)
threading.Thread(target=e._dj_radio_loop, daemon=True).start()
time.sleep(1.6)
e.stopping.set()
ok(e.dj_said and e.dj_said[0].startswith("Вы слушаете «Ретро FM».") and "На часах" in e.dj_said[0], f"ведущий на радио: {e.dj_said[:1]}")

# ---------- студия: карточка «Ведущий» ----------
from playwright.sync_api import sync_playwright  # noqa: E402

ui = tmp / "ui"
shutil.copytree(ROOT / "ui", ui)
html = (ui / "settings.html").read_text(encoding="utf-8")
ok('data-k="music.dj_say.tasks"' in html and 'data-k="music.dj_radio"' in html and 'id="mm-every"' in html, "в студии — галочки, частота и ведущий на радио")
SHOT = os.environ.get("DEWIAR_SHOTS")
import json  # noqa: E402
ST = json.loads(json.dumps(SET.DEFAULTS))
ST["music"].update({"dj_every": 3, "dj_say": {"track": True, "time": True, "weather": True, "tasks": False, "mail": True}})
CORE = """(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mm_status") return { stats: { tracks: 0, artists: 0, genres: 0 }, busy: false, folder: "", now: null, live: null, mail_on: false, artists: [] };
      if (c === "mm_list") return [];
      if (c === "settings_save") { const m = (o, p) => { for (const k in p) { if (p[k] && typeof p[k] === "object" && !Array.isArray(p[k])) m(o[k] = o[k] || {}, p[k]); else o[k] = p[k]; } return o; };
        return m(JSON.parse(JSON.stringify(S)), a.patch); }
      return null; };
    setTimeout(() => core.emit("hello", { settings: ST, personas: [], persona: "lira", presets: {}, piper_voices: [] }), 200); };
  ready(); })();""".replace("ST", json.dumps(ST, ensure_ascii=False))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errs = []
    pg.on("pageerror", lambda x: errs.append(str(x) + " " + (x.stack or "")[:300]))
    pg.route(__import__("re").compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.add_init_script(CORE)
    pg.goto((ui / "settings.html").as_uri() + "?port=1")
    pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('#wlc') && document.querySelector('#wlc').remove()")  # окно «Добро пожаловать» — не про это
    pg.evaluate("document.querySelector('nav button[data-p=\"music\"]').click()")
    pg.wait_for_timeout(600)
    has = pg.evaluate("typeof mmHost === 'function' && !!document.querySelector('#mm-host')")
    ok(has, "mmHost и карточка на месте")
    if has:
        ok(pg.evaluate("document.querySelector('#mm-every [data-n=\"3\"]').getAttribute('aria-checked')") == "true", "частота «Раз в 3» отмечена")
        note = pg.evaluate("document.querySelector('#mm-hnote').textContent")
        ok("город" in note and "почта" in note, f"подсказки: погоды без города не будет, писем без почты — тоже: {note}")
        ok(pg.evaluate("document.querySelector('[data-k=\"music.dj_say.mail\"]').checked") and not pg.evaluate("document.querySelector('[data-k=\"music.dj_say.tasks\"]').checked"),
           "галочки показывают настройки")
        pg.evaluate("S.music.dj_talk = false; mmHost()")
        ok(pg.evaluate("document.querySelector('#mm-host').classList.contains('off')"), "ведущий выключен — блок бледный")
        pg.evaluate("S.music.dj_talk = true; mmHost()")
        bg = pg.evaluate("(s => s.backgroundImage !== 'none' ? s.backgroundImage : s.backgroundColor)(getComputedStyle(document.querySelector('[data-k=\"music.dj_say.mail\"] + span')))")
        bo = pg.evaluate("getComputedStyle(document.querySelector('[data-k=\"music.dj_say.mail\"] + span')).borderStyle")
        ok(bg not in ("rgba(0, 0, 0, 0)", "transparent") and bo in ("none", ""), f"отмеченная — залита цветом, без обводки: {bg} {bo}")
        pg.click("#mm-every [data-n='5']")
        pg.wait_for_timeout(300)
        ok(["settings_save", {"patch": {"music": {"dj_every": 5}}}] in pg.evaluate("calls")
           and pg.evaluate("document.querySelector('#mm-every [data-n=\"5\"]').getAttribute('aria-checked')") == "true", "«Раз в 5» — сохранено и отмечено")
        pg.click("[data-k='music.dj_say.tasks'] + span")
        pg.wait_for_timeout(300)
        ok(["settings_save", {"patch": {"music": {"dj_say": {"tasks": True}}}}] in pg.evaluate("calls"), "галочка «Ближайшее дело» — сохранена")
        if SHOT:
            pg.locator(".mm-hostcard").scroll_into_view_if_needed()
            pg.screenshot(path=str(Path(SHOT) / "dj-host.png"))
    b.close()
errs = [x for x in errs if "loadGallery" not in x]           # галерея персонажей без данных — заглушка, не про ведущего
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
