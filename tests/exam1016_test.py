"""Экзамены 16.10 (компьютер 0.38.60 — 44 из 52, телефон 0.6.52 — 44 из 50): что было настоящей ошибкой и что — ошибкой
самого экзамена.
- компьютер: «Какая погода завтра в Минске?» — искал сайт погоды, сайт отдал меню, модель выдумала «+7…+12». Теперь
  инструмент weather (Open-Meteo, как на телефоне): настоящие числа или честная ошибка;
- телефон: «Посмотри сайт https://www.python.org/» — шесть вызовов read_webpage без адреса. Теперь адрес — из слов человека;
- экзамен компьютера: память, заметки, напоминания и фоновые задачи прошлых испытаний попадали в следующие («на тебе
  висит отчёт», «Отчёт по продажам готова» вместо презентации) — теперь каждое испытание с чистого листа;
- экзамен телефона: таймеры прошлых испытаний («сколько осталось?» — три таймера), имя и память владельца — тоже."""
import asyncio, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- компьютер: погода ----------
import datetime as dt  # noqa: E402
import httpx  # noqa: E402
import tools as T  # noqa: E402


class R:
    def __init__(self, d): self.d = d
    def json(self): return self.d
    def raise_for_status(self): return None


seen = []


def fake_get(url, params=None, **k):
    seen.append(url)
    if "geocoding" in url:
        return R({"results": [{"name": "Минск", "latitude": 53.9, "longitude": 27.56}]})
    days = [(dt.date.today() + dt.timedelta(days=i)).isoformat() for i in range(int(params.get("forecast_days", 3)))]
    return R({"current": {"temperature_2m": 9.4, "apparent_temperature": 7.1, "weather_code": 3, "wind_speed_10m": 11},
              "daily": {"time": days, "temperature_2m_min": [4.2] * len(days), "temperature_2m_max": [11.6] * len(days),
                        "weather_code": [61] * len(days), "precipitation_probability_max": [70] * len(days)}})


real_get, httpx.get = httpx.get, fake_get
try:
    out = T.t_weather({"city": "Минск", "days": 2}, {})
finally:
    httpx.get = real_get
ok("Минск: сейчас 9°" in out and "(завтра): 4…12°, небольшой дождь, осадки 70%" in out and "Называй только эти числа" in out,
   f"компьютер: погода — настоящий прогноз по дням, «завтра» помечено: {out[:160]!r}")


def bad_get(*a, **k):
    raise httpx.ConnectError("нет сети")


httpx.get = bad_get
try:
    try:
        T.t_weather({"city": "Минск"}, {})
        err = ""
    except T.ToolError as e:
        err = str(e)
finally:
    httpx.get = real_get
ok("не придумывай" in err, f"нет связи — честная ошибка, а не числа: {err}")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("weather" in T.TOOLS and '"weather"' in src.split("INFO_TOOLS", 1)[1][:200] and "инструментом weather" in src
   and "погода — инструментом weather" in T.TOOLS["web_search"][0],
   "погода — инструментом weather (в списке инструментов, подсказке и описании поиска)")

# ---------- экзамен компьютера: с чистого листа ----------
import exam as X  # noqa: E402


class FakeCore:
    def __init__(self, tmp):
        self.tmp, self.calls = tmp, []

    async def call(self, cmd, **a):
        self.calls.append((cmd, a))
        return {"reminders": [{"id": "r1"}], "money_list": [{"id": "m1"}],
                "tasks_list": [{"id": "t1", "status": "running"}, {"id": "t2", "status": "done"}]}.get(cmd, {})


tmp = Path(tempfile.mkdtemp())
(tmp / "ws" / "Заметки").mkdir(parents=True)
(tmp / "ws" / "Заметки" / "Позвонить Ольге.md").write_text("# Позвонить Ольге\n", encoding="utf-8")
fc = FakeCore(tmp)
asyncio.run(X.reset_state(fc))
cs = [(c, a.get("id"), a.get("text")) for c, a in fc.calls]
ok(("memory_set", None, "") in cs and ("reminder_cancel", "r1", None) in cs and ("money_delete", "m1", None) in cs
   and ("task_stop", "t1", None) in cs and ("task_delete", "t1", None) in cs and ("task_delete", "t2", None) in cs
   and not (tmp / "ws" / "Заметки").exists(),
   f"экзамен компьютера: перед испытанием — без памяти, заметок, напоминаний, расходов и задач прошлых: {cs}")
ok("await reset_state(core)" in (ROOT / "core/exam.py").read_text(encoding="utf-8"), "сброс — перед каждым испытанием")

# ---------- телефон: адрес страницы из слов человека; экзамен телефона с чистого листа ----------
from playwright.sync_api import sync_playwright  # noqa: E402
www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "speechnorm.js"):
    shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    r = pg.evaluate("""async () => { const got = []; window.http = async (m, u) => { got.push(u); return { status: 200, body: '<main><h1>Welcome to Python.org</h1><p>' + 'Python is a programming language that lets you work quickly. Downloads, Documentation, Community, Success Stories, News, Events. '.repeat(4) + '</p></main>' }; };
        turnAsk = "Посмотри сайт https://www.python.org/ и коротко напиши, что там есть и какие разделы";
        const t1 = await runTool("read_webpage", {});
        turnAsk = "Открой python.org и расскажи, что там нового";
        await runTool("read_webpage", { url: "" });
        turnAsk = "Прочитай страницу";
        const t3 = await runTool("read_webpage", {});
        return { got, t1: String(t1).slice(0, 80), t3: String(t3) }; }""")
    ok(r["got"][:2] == ["https://www.python.org/", "https://python.org"] and "Welcome to Python.org" in r["t1"],
       f"телефон: модель не передала адрес — он берётся из слов человека: {r['got']}")
    ok(r["t3"].startswith("Ошибка: не пришёл адрес"), f"адреса нет и в словах — понятная ошибка модели, а не «Invalid host»: {r['t3'][:60]}")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
js = (ROOT / "android/assets/www/exam.js").read_text(encoding="utf-8")
ok(re.search(r"EXAM\.alarms = \[\]; EXAM\.calendar = \[\]; S\.memory = \[\]; S\.user_name = \"\";", js) and 'SANDBOX.files[f] = "[]"' in js,
   "экзамен телефона: каждое испытание — без таймеров, памяти, имени, заметок и расходов прошлых (в песочнице)")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
