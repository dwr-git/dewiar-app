"""№557 (ПК 0.84.0, 05.11): на «Главной» в «Утре с Лирой» и в «Дальше сегодня» вместо имени дела плагина «Дача и огород»
шло поручение модели целиком — «19:00 — Посмотри прогноз погоды (weather) для города «Балашов» на 2 дня. Если ночью до 0°…».
Теперь у дела по расписанию есть имя для людей: у плагина — short из plugin.json («Дача: заморозки и полив»; у уже
заведённых — по settings.plugins.on), у своего — первая фраза поручения без «(weather)»; его видят календарь, «Утро»,
«Дальше сегодня», уведомление и телефон («Мой день»).
№559 (05.11): «чтобы скриншот делался без окна персонажа» — на время снимка для жалобы виджет прячется (ui/app.py
shot_hide) и возвращается всегда, даже если страница не вернула его сама.
Идея №142 (05.11): погода без названного города — город «Утра», потом из памяти («живу в Балашове», «я из Минска»);
«Утро» на «Главной» показывает погоду по городу из памяти (city_mem); «Дача и огород» без «Где дача» — тот же город."""
import json, os, re, sys, tempfile, time
from pathlib import Path
from unittest import mock
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tools as T  # noqa: E402
import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import weatherq as W  # noqa: E402
import morning as MO  # noqa: E402
from engine_tools import ToolsMixin  # noqa: E402

RAW = ("Посмотри прогноз погоды (weather) для города «Балашов» на 2 дня. Если ночью до 0° и ниже — предупреди укрыть: …; "
       "если жара от +28 без дождя — напомни полить. Иначе ничего не сообщай")

# ---------- имя дела из поручения ----------
ok(T.job_short(RAW) == "Посмотри прогноз погоды для города «Балашов» на 2 дня", f"первая фраза без «(weather)»: {T.job_short(RAW)!r}")
ok(T.job_short("Проверяй почту и сообщай о важном") == "Проверяй почту и сообщай о важном", "короткое поручение — как есть")
long_ = T.job_short("Собери дайджест по темам: ИИ, космос — пять самых важных новостей за последние сутки, по одной строке на каждую, со ссылками")
ok(len(long_) <= 81 and long_.endswith("…") and " " not in long_[-2:], f"длинное — до 80 знаков по слову, с «…»: {long_!r}")
ok(T.job_short("Смотри https://x.test/a и (web_search, read_webpage) пиши") == "Смотри и пиши", "без ссылок и списка инструментов")

# ---------- плагины: short в каталоге, имя дела по id напоминания ----------
s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s)
d = next(x for x in P.catalog() if x["id"] == "dacha")
ok(d["jobs"][0]["short"] == "Дача: заморозки и полив", "в plugin.json «Дачи» — короткое имя дела")
ok(all(j.get("short") for p in P.catalog() if p.get("builtin") for j in p.get("jobs") or []), "у всех готовых плагинов с делами — короткие имена")
P.install("dacha", {"city": "", "grows": "томаты"})
task, when = P.job_text("dacha", "frost", fallback={"city": "Балашове"})
ok("«Балашове»" in task and "«…»" not in task, f"«Где дача» пусто — город человека (идея №142): {task[:70]!r}")
task2, _ = P.job_text("dacha", "frost")
ok("«…»" in task2, "без города совсем — как раньше, «…»")
P.job_mark("dacha", "frost", "abc123")
ok(P.job_label_by_rid("abc123") == "Дача: заморозки и полив" and P.job_label_by_rid("zzz") == "", "уже заведённое дело плагина узнаётся по id")

# ---------- напоминания: title хранится, переписали поручение — title прочь ----------
R = T.Reminders(on_fire=lambda it: None)
R.items = []
out = T.t_schedule_job({"task": RAW, "when": "каждый день в 19", "title": "Дача: заморозки и полив"}, {"reminders": R})
rid = re.search(r"\(id ([^)]+)\)", out).group(1)
ok(R.get(rid).get("title") == "Дача: заморозки и полив", "дело плагина заводится с именем для людей")
R.update(rid, {"text": "Проверь почту"})
ok("title" not in R.get(rid), "поручение переписали — старое имя ему не подходит, убрано")

# ---------- job_label: что видит человек ----------
class E(ToolsMixin):
    def __init__(self):
        self.plugins = P
eng = E()
ok(eng.job_label({"id": "abc123", "kind": "job", "text": RAW}) == "Дача: заморозки и полив", "старое дело «Дачи» (без title) — «Дача: заморозки и полив»")
ok(eng.job_label({"id": "q", "kind": "job", "text": RAW, "title": "Свой"}) == "Свой", "своё имя — первым")
ok(eng.job_label({"id": "q", "kind": "job", "text": "x", "preset": "evening"}) == "Итог дня", "готовое дело — название карточки")
ok(eng.job_label({"id": "q", "kind": "job", "text": RAW}) == "Посмотри прогноз погоды для города «Балашов» на 2 дня", "своё без имени — первая фраза")
ok(eng.job_title({"id": "q", "kind": "job", "text": RAW}) == RAW, "двойники (_on_reminder) по-прежнему сравниваются по полному поручению")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok('title = self.job_label(r) if job else r["text"]' in src and 'e["title"] = self.job_label(item)' in src,
   "календарь, «Утро», «Дальше сегодня» и журнал «прозвенело» — по job_label")
sy = (ROOT / "core/sync.py").read_text(encoding="utf-8")
ok('h.job_label(r)' in sy and '"title": title' in sy, "телефону («Мой день») уходит имя дела")
from engine_music import MusicMixin  # noqa: E402
ok(MusicMixin.job_name({"text": RAW, "title": "Дача: заморозки и полив"}) == "Дача: заморозки и полив", "уведомление — тоже по имени дела")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok('esc(jobShort(j))' in app and 'split(":")[0].slice(0, 80)' not in app, "телефон: «По расписанию — делает компьютер» — имя дела, а не поручение")

# ---------- идея №142: город из памяти ----------
for text, want in [("Живу в Балашове. Люблю чай", "Балашове"), ("Мой город — Гродно", "Гродно"), ("Я из Минска, работаю программистом", "Минска"),
                   ("Пользователь родом из Санкт-Петербурга", "Санкт-Петербурга"), ("я из тех, кто любит чай", ""), ("Работаю в Сбербанке", "")]:
    ok(W.memory_place(text)[0] == want, f"память «{text}» → «{want}»")
ok("Москва" in W._stems("Москвы"), "«из Москвы» → Москва")


class WS:
    def __init__(self, mem):
        self.mem = mem

    def memory_get(self):
        return self.mem


class Eng:
    def __init__(self, city="", mem=""):
        self.s = {"morning": {"city": city}}
        self.workspace = WS(mem)

    def calendar_month(self, y, m):
        return {"days": {}}
ok(T.home_city(Eng("Минск")) == ("Минск", "settings"), "город «Утра» — первым")
ok(T.home_city(Eng("", "Живу в Балашове")) == ("Балашове", "memory"), "нет — из памяти")
ok(T.home_city(Eng()) == ("", "") and T.home_city(None) == ("", ""), "нигде нет — пусто (спросит)")


class Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data
asked = []


def fake_get(url, params=None, **k):
    asked.append(params.get("name") if params and "name" in params else url)
    if "geocoding" in url:
        n = params["name"]
        return Resp({"results": [{"name": "Балашов", "latitude": 51.55, "longitude": 43.17, "admin1": "Саратовская область"}]} if n == "Балашов" else {})
    return Resp({"current": {"temperature_2m": 3, "apparent_temperature": 0, "weather_code": 3, "wind_speed_10m": 4},
                 "daily": {"time": [time.strftime("%Y-%m-%d")], "weather_code": [3], "temperature_2m_max": [6], "temperature_2m_min": [1],
                           "precipitation_probability_max": [20]}})
with mock.patch.object(T.httpx, "get", side_effect=fake_get), mock.patch.object(W.httpx, "get", side_effect=fake_get):
    w = T.t_weather({"city": "", "days": 1}, {"engine": Eng("", "Живу в Балашове")})
ok(w.startswith("Балашов: сейчас 3°") and "из памяти" in w and "Запомнить город" in w, f"погода без города — по памяти, «Балашове» найден по основам, предложено запомнить: {w[:60]!r} … {w[-120:]!r}")
try:
    T.t_weather({"city": ""}, {"engine": Eng()})
    err = ""
except T.ToolError as e:
    err = str(e)
ok("спроси" in err, "нигде нет — спросить город, не угадывать")

# «Утро» на «Главной»: города нет — погода по памяти, город «Утра» не меняется сам
with mock.patch.object(MO, "weather", side_effect=lambda c, e=None: {"city": "Балашов", "place": "Балашов, Саратовская область", "now": 3}), \
     mock.patch.object(MO, "_mail", return_value=None):
    g = MO.gather(Eng("", "Живу в Балашове"))
ok(g["city"] == "" and g["city_mem"] == "Балашове" and g["weather"]["place"] == "Балашов, Саратовская область",
   f"«Утро»: погода по городу из памяти, сам город «Утра» не задан (карточка предложит «Запомнить город»): {g.get('city_mem')}")

# «Дача и огород» без «Где дача»: дело получает город человека
ec = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('P.job_text(pid, jid, fallback={"city": home_city(self)[0]})' in ec and '"title": P.job_label(pid, jid)' in ec,
   "дело «Дачи» заводится с городом из «Утра»/памяти и с именем для людей")

# ---------- №559: снимок для жалобы — без виджета ----------
os.environ.setdefault("DEWIAR_NO_GTK", "1")
sys.path.insert(0, str(ROOT / "ui"))
try:
    import app as UI  # noqa: E402
    imported = True
except Exception as e:  # noqa: BLE001
    imported = False
    print("   (интерфейс не импортируется здесь:", e, ")")
if imported:
    log_ = []
    a = UI.Api.__new__(UI.Api)
    a.in_tray, a.mode = False, "card"
    a._hide_now = lambda: log_.append("hide")
    a.show = lambda: log_.append("show")
    a.SHOT_WAIT, a.SHOT_BACK = 0.01, 0.3
    ok(a.shot_hide(True) is True and log_ == ["hide"], "перед снимком виджет прячется")
    ok(a.shot_hide(True) is False and log_ == ["hide"], "второй раз подряд — не прячем дважды")
    ok(a.shot_hide(False) is True and log_ == ["hide", "show"], "после снимка — сразу обратно")
    ok(a.shot_hide(False) is False and log_ == ["hide", "show"], "лишний «вернуть» — ничего не делает")
    a.shot_hide(True); time.sleep(0.6)
    ok(log_[-2:] == ["hide", "show"] and not a._shot_hid, "страница не вернула виджет (упала) — он возвращается сам")
    a.in_tray = True; n = len(log_)
    ok(a.shot_hide(True) is False and len(log_) == n, "виджет в трее — его и так нет на снимке, ничего не трогаем")
    a.in_tray = False; a.shot_hide(True); a.in_tray = True; a.shot_hide(False)
    ok(log_[-1] == "hide", "ушёл в трей, пока снимали, — не показываем")

    def boom():
        raise RuntimeError("нет окна")
    a.in_tray, a._shot_hid = False, False
    a._hide_now = boom
    ok(a.shot_hide(True) is False and not a._shot_hid, "окно не спряталось — снимаем как есть, без ошибки")
js = (ROOT / "ui/assets/dewiar.js").read_text(encoding="utf-8")
ok("async shot(args = {})" in js and "finally { if (hid)" in js, "core.shot: вернуть виджет — в finally (и при ошибке снимка)")
for f in ("ui/hud.html", "ui/studio/icons.js", "ui/studio/links.js"):
    t = (ROOT / f).read_text(encoding="utf-8")
    # снимает экран — только core.shot; core.call("bug_shot", { image }) — вставленная картинка, экран не снимается
    ok(not re.search(r'core\.call\("bug_shot"(?:\)|, \{ add)', t) and "core.shot(" in t, f"{f}: снимок для жалобы — через core.shot (без виджета)")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
