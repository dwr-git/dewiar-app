"""«Утро с Лирой» (0.57; согласовано с владельцем 28.10: одна утренняя сводка — погода, день, дела, сотрудники, клиенты,
которые ждут, важная почта; на компьютере и на телефоне).
Ядро: morning.gather — погода числами (Open-Meteo через tools.t_weather), встречи и дела, «Поручения» (просрочено, ждут
проверки, написали за ночь), «Клиенты» (шаг просрочен, сегодня), почта (от людей — по именам, рассылки — числом), задачи;
выключенный раздел — молчит; сломалась почта — раздела нет. _brief_context — всё это для модели, утро уходит своему
телефону; поручение сводки — «погода уже здесь». Студия: карточка «Утро с Лирой» на главной — погода, строки, город,
«Расскажи утро», «Каждое утро в 8:00», «Скрыть до завтра». Телефон: утро с компьютера → сводка дня с погодой, клиентами,
почтой и сотрудниками."""
import json, os, shutil, subprocess, sys, tempfile, time, types
from datetime import datetime, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_HOME=str(tmp / "home"))
sys.path.insert(0, str(ROOT / "core"))
fails = []
SHOTS = os.environ.get("DEWIAR_SHOTS")


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import clients as CL  # noqa: E402
import engine_music as EM  # noqa: E402
import morning as MO  # noqa: E402
import team as TM  # noqa: E402
import tools as T  # noqa: E402
from settings import Settings  # noqa: E402

calls = {"w": 0}
import weatherq as WQ  # noqa: E402


def fake_get(url, params, via=None):
    if "geocoding" in url:
        calls["w"] += 1
        if params["name"].startswith("Нигде"):
            return {}
        return {"results": [{"name": "Минск", "latitude": 53.9, "longitude": 27.56, "admin1": "Минск", "country": "Беларусь", "population": 2000000}]}
    return {"current": {"temperature_2m": -3.2, "apparent_temperature": -7, "weather_code": 3, "wind_speed_10m": 12},
            "daily": {"time": [datetime.now().date().isoformat()], "weather_code": [71], "temperature_2m_min": [-5], "temperature_2m_max": [1],
                      "precipitation_probability_max": [60]}}


WQ._get = fake_get

now = datetime.now()


class Mail:
    fail = False
    def configured(self): return True
    def inbox(self, limit=10, unread=False):
        if self.fail:
            raise RuntimeError("IMAP не отвечает")
        return [{"from": "Ольга Смирнова <olga@romashka.by>", "subject": "Счёт за октябрь"},
                {"from": "Яндекс Маркет <no-reply@market.yandex.ru>", "subject": "Скидки недели"},
                {"from": "\"Иван\" <ivan@sklad.by>", "subject": "Поставка задерживается"}]


class Eng:
    _brief_context, morning_share = EM.MusicMixin._brief_context, EM.MusicMixin.morning_share

    def __init__(self):
        self.s = Settings(tmp / "settings.json"); self.s.update({"features": {"team": True, "clients": True}, "morning": {"city": "Минск"}})
        self.team = TM.Team(types.SimpleNamespace(s=self.s, emit=lambda *a, **k: None, push=lambda *a, **k: None, announce=lambda *a: None,
                                                  close=None, credentials=lambda: ("", "")), tmp / "team.json", tmp / "team_bot.json")
        self.team._send = lambda *a, **k: "sent"
        self.team.st["members"] = {"m1": {"id": "m1", "name": "Анна Ким", "tg": {"id": "1", "chat": "1", "ch": "tg"}},
                                   "m2": {"id": "m2", "name": "Иван Петров", "tg": {"id": "2", "chat": "2", "ch": "tg"}}}
        self.team.st["app_on"] = False
        self.team.connected = lambda: True
        self.clients = CL.Clients(tmp / "clients.json")
        self.mail = Mail()
        self.tasks = types.SimpleNamespace(list=lambda: [{"title": "Обзор конкурентов", "status": "done", "updated": (now - timedelta(hours=3)).isoformat(timespec="seconds")},
                                                         {"title": "План отпуска", "status": "waiting", "question": "Какие даты?"}])
        self.money = types.SimpleNamespace(summary=lambda a, b: {"by_currency": []})
        self.night = types.SimpleNamespace(morning_note=lambda: "")
        self.shared = []
        self.close = types.SimpleNamespace(_own_quiet=lambda body: self.shared.append(body))

    def device_name(self): return "Рабочий"

    def calendar_month(self, y, m):
        k = now.date().isoformat()
        return {"days": {k: [{"type": "event", "time": "10:00", "title": "Планёрка", "place": "офис"},
                             {"type": "reminder", "time": "15:00", "title": "Забрать посылку"},
                             {"type": "reminder", "time": "09:00", "title": "Сделано уже", "done": True}]}}


E = Eng()
t1 = E.team.assign("Анна", "Обновить прайс", "2020-01-01T12:00")
t2 = E.team.assign("Иван", "Пересчитать склад")
E.team.st["tasks"][t2["id"]].update(state="done", report={"t": "готово"})
E.team.st.setdefault("inbox", []).append({"ts": time.time() - 3600, "who": "m2", "t": "Можно уйти пораньше?"})
E.team.st["inbox"].append({"ts": time.time() - 3 * 86400, "who": "m1", "t": "старое"})
c1 = E.clients.add("Сергей Иванов", "Ромашка")
E.clients.set_next(c1["id"], "перезвонить про 200 коробок", now - timedelta(days=1))
c2 = E.clients.add("Мария Лис")
E.clients.set_next(c2["id"], "отправить договор", now.replace(hour=23, minute=0))
c3 = E.clients.add("Пётр Далёкий")
E.clients.set_next(c3["id"], "встреча", now + timedelta(days=5))

d = MO.gather(E)
ok(d["weather"] and d["weather"]["now"] == -3 and d["weather"]["min"] == -5 and d["weather"]["max"] == 1 and d["weather"]["rain"] == 60 and "Минск: сейчас -3°" in d["weather"]["line"],
   f"погода числами: {d['weather']}")
ok([x["title"] for x in d["today"]["meet"]] == ["Планёрка"] and [x["title"] for x in d["today"]["todo"]] == ["Забрать посылку"], "встречи и несделанные дела на сегодня")
ok([x["title"] for x in d["team"]["late"]] == ["Обновить прайс"] and [x["title"] for x in d["team"]["check"]] == ["Пересчитать склад"]
   and [x["t"] for x in d["team"]["msgs"]] == ["Можно уйти пораньше?"], f"сотрудники: просрочено, ждут проверки, свежие сообщения: {d['team']}")
ok([x["name"] for x in d["clients"]["over"]] == ["Сергей Иванов («Ромашка»)"] and [x["name"] for x in d["clients"]["today"]] == ["Мария Лис"],
   f"клиенты: просрочено и сегодня, без далёких: {d['clients']}")
ok(d["mail"]["unread"] == 3 and [x["from"] for x in d["mail"]["people"]] == ["Ольга Смирнова", "Иван"] and d["mail"]["bulk"] == 1, f"почта: люди по именам, рассылка — числом: {d['mail']}")
ok(d["tasks"]["done"] == ["Обзор конкурентов"] and d["tasks"]["wait"][0]["title"] == "План отпуска", "задачи: готово за ночь, ждёт ответа")
n0 = calls["w"]; MO.gather(E)
ok(calls["w"] == n0, "погода — из кэша, не каждый раз в сеть")
ctx = MO.context(d)
for part in ("Погода (уже узнана, искать не нужно): Минск", "Встречи сегодня: 10:00 Планёрка (офис)", "просрочено — Анна Ким: «Обновить прайс»",
             "ждут вашей проверки — Иван Петров: «Пересчитать склад»", "Клиенты ждут (срок шага прошёл): Сергей Иванов («Ромашка») — перезвонить",
             "Почта: непрочитанных 3. От людей: Ольга Смирнова — «Счёт за октябрь»"):
    ok(part in ctx, f"для модели: «{part[:50]}…»")
ok("Скидки недели" not in ctx, "рассылки не перечисляются")
# выключенное — молчит; почта сломалась — раздела нет
E.s.update({"features": {"team": False, "clients": False}, "morning": {"mail": False}})
d2 = MO.gather(E)
ok(d2["team"] is None and d2["clients"] is None and d2["mail"] is None, "«Поручения», «Клиенты» выключены, почта в утре выключена — их нет")
E.s.update({"features": {"team": True, "clients": True}, "morning": {"mail": True}})
E.mail.fail = True
d3 = MO.gather(E, fresh=True)
ok(d3["mail"] is None and d3["weather"], "почта не ответила — раздела нет, остальное на месте")
E.mail.fail = False; MO._cache.clear()
E.s.update({"morning": {"city": "Нигде"}})
ok(MO.gather(E)["weather"] is None, "погоду не получить — раздела нет, цифр не придумываем")
E.s.update({"morning": {"city": "Минск"}}); MO._cache.clear()
# _brief_context и поручение сводки
bc = E._brief_context()
ok("Дела и напоминания на сегодня: 15:00 Забрать посылку." in bc and "Встречи и события из календаря: 10:00 Планёрка (офис)." in bc and "Погода (уже узнана" in bc
   and "Клиенты ждут" in bc and "Задача ждёт ответа пользователя: «План отпуска»" in bc and bc.count("Готово за ночь") == 1 and bc.count("ждёт ответа") == 1, "сводка для модели — всё вместе, без повторов")
ok(E.shared and E.shared[0]["morning"]["dev"] == "Рабочий" and E.shared[0]["morning"]["clients"]["over"] and "today" not in E.shared[0]["morning"],
   "утро — своему телефону (клиенты, почта, погода; без дел — у телефона свои)")
E._brief_context(); time.sleep(0.2)
ok(len(E.shared) == 1, "своему телефону — не чаще раза в полчаса")
jp = EM.MusicMixin._job_prompt(types.SimpleNamespace(_brief_context=lambda: "X"), {"brief": True})
ok("[Утро с Лирой]" in jp and "если она есть в данных, бери оттуда" in jp and "рассылки не перечисляй" in jp, "поручение сводки: погода из данных, сотрудники, клиенты, письма")
import presence  # noqa: E402
pp = presence.prompt({"kind": "day", "facts": [], "gone": "9 ч"}, "ctx")
ok("что ждёт от сотрудников и клиентов" in pp, "сводка дня у компьютера — тоже про сотрудников и клиентов")

# ---------- студия ----------
pub = MO.public(MO.gather(E))
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 950}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) }; Date.prototype.getHours = function () { return 8; };")
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("""(d) => { window._calls = []; window._d = Object.assign({}, d, { settings: { city: 'Минск' }, daily: null, mail_on: true });
      core.call = (c, a) => { _calls.push([c, a || {}]);
        if (c === 'morning_get') return Promise.resolve(_d);
        if (c === 'morning_set') { if (a.hide) _d = Object.assign({}, _d, { settings: { hide: a.hide } }); if ('city' in a) _d = Object.assign({}, _d, { city: a.city }); return Promise.resolve(_d); }
        if (c === 'job_add') { _d = Object.assign({}, _d, { daily: { id: 'j1', at_hm: '07:30' } }); return Promise.resolve({ repeat_text: 'каждый день' }); }
        return Promise.resolve(null); };
      document.querySelector('nav button[data-p=home]').click(); loadHome(); }""", pub)
    pg.wait_for_timeout(900)
    r = pg.evaluate("""() => [document.querySelector('#hm-morning').hidden, document.querySelector('#hm-morning h2').textContent, document.querySelector('.mn-t').textContent,
      document.querySelector('.mn-w').className, [...document.querySelectorAll('.mn-rows b')].map(x => x.textContent), [...document.querySelectorAll('.mn-rows button')].map(x => x.dataset.mgo)]""")
    ok(r[0] is False and r[1] == "Утро с Лирой" and r[2] == "-3°" and "sky-snow" in r[3], f"на главной — «Утро с Лирой», −3°, снежное небо: {r[:4]}")
    ok(r[4][0].startswith("1 встреча, 1 дело") and r[4][1] == "Сотрудники: 1 просрочено · 1 ждёт проверки · 1 сообщение" and r[4][2] == "Клиенты ждут: 1"
       and r[4][3] == "Почта: 3 новых" and r[5][:4] == ["calendar", "team", "clients", "connect"], f"строки ведут в разделы: {r[4]}")
    if SHOTS: pg.screenshot(path=str(Path(SHOTS) / "studio-morning.png"), clip={"x": 240, "y": 0, "width": 1160, "height": 560})
    pg.click("#mn-say"); pg.wait_for_timeout(200)
    ok(["job_run", {"task": "Утренняя сводка", "brief": True, "deliver": "voice"}] in pg.evaluate("_calls"), "«Расскажи утро» — сводка голосом сейчас")
    pg.fill("#mn-at", "7:30"); pg.click(".mn-daily .tg"); pg.wait_for_timeout(400)
    ok(any(c[0] == "job_add" and c[1].get("preset") == "brief" and "07:30" in c[1]["phrase"] for c in pg.evaluate("_calls")) and pg.evaluate("document.querySelector('#mn-dly').checked"),
       "«Каждое утро в 7:30» — дело по расписанию (та же карточка, что в «Делах по расписанию»)")
    pg.click("#mn-cedit"); pg.wait_for_timeout(150)
    pg.fill("#mn-city", "Гродно"); pg.click("#mn-cgo"); pg.wait_for_timeout(300)
    ok(["morning_set", {"city": "Гродно"}] in pg.evaluate("_calls"), "сменить город — morning_set")
    pg.click("#mn-hide"); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.querySelector('#hm-morning').hidden"), "«Скрыть до завтра»")
    ok(pg.evaluate("[mnWith('Лира'), mnWith('Патрик'), mnWith('Эва'), mnWith('Гастон')]") == ["Лирой", "Патриком", "Эвой", "Гастоном"], "«Утро с Патриком», «с Эвой»")
    pg.evaluate("() => { _d = Object.assign({}, _d, { city: '', weather: null, settings: {} }); mnLoad(); }"); pg.wait_for_timeout(300)
    ok(pg.locator("#mn-city").count() == 1 and "Скажите, где вы" in pg.inner_text("#hm-morning"), "нет города — поле «Город»")
    pg.evaluate("() => { Date.prototype.getHours = function () { return 15; }; mnLoad(); }"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#hm-morning').hidden"), "днём карточки утра нет")
    b.close()
ok(not errs, "студия без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))

# ---------- телефон ----------
www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js", "closecrypto.js", "qrcode.js", "codes.js", "rich.js", "speechnorm.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / Path(f).name)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)], capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 852}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    body = E.shared[0]
    r = pg.evaluate("""async (body) => {
      ownApply(body); const R = {};
      R.facts = await mornFacts();
      ownApply({ morning: Object.assign({}, body.morning, { at: 1, clients: null }) });       // старое — не затирает
      R.kept = (await mornFacts()).some(x => x.startsWith('Клиенты ждут'));
      const asked = []; window.ask = async (t, o) => { asked.push(t); }; window.ensureBrain = async () => {}; S.llm.base_url = 'http://127.0.0.1:9/v1';
      window.mind = () => ({ tasks: {} }); D.alarms = () => '[]';
      const real = Date.now, d0 = new Date(); d0.setHours(8, 30, 0, 0); const shift = d0.getTime() - real.call(Date);
      Date.now = () => real.call(Date) + shift;
      S.welcome = { on: true, seen: Date.now() - 10 * 3600000, at: Date.now() - 20 * 3600000 };
      R.fired = await welcomeCheck(Date.now() - 100);
      Date.now = real;
      R.prompt = asked[0] || '';
      return R; }""", body)
    f = " ".join(r["facts"])
    ok("Погода (уже узнана): Минск: сейчас -3°" in f and "Клиенты ждут (с компьютера «Рабочий»): Сергей Иванов" in f and "Почта (с компьютера «Рабочий»): непрочитанных 3. От людей: Ольга Смирнова" in f
       and "Сотрудники: просрочено — Анна Ким: «Обновить прайс»" in f, f"телефон: утро с компьютера — погода, клиенты, почта, сотрудники: {r['facts']}")
    ok(r["kept"], "старое утро свежее не затирает")
    ok(r["fired"] and "Клиенты ждут" in r["prompt"] and "что ждёт от сотрудников и клиентов" in r["prompt"], f"сводка дня на телефоне — с ними: {r['prompt'][:120]!r}")
    b.close()
ok(not errs, "телефон без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
