"""Погода без модели на телефоне (0.63; на компьютере — с 0.62, weatherq.py, №373: маленькая модель погоду не искала и
выдумывала). «Какая погода?», «погода в Минске завтра», «сколько градусов на улице?» — сразу числа Open-Meteo, модель не
спрашиваем; город: названный → запомненный → «Утро» с компьютера → память («живу в …»); нет — спросить; «погода в доме» и
песни — не перехватываем; область выбирает тот Железногорск; сервис молчит — честно."""
import json, os, shutil, subprocess, sys, tempfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


GEO = {"минск": [{"name": "Минск", "latitude": 53.9, "longitude": 27.5, "admin1": "Минск", "population": 2000000}],
       "гродно": [{"name": "Гродно", "latitude": 53.7, "longitude": 23.8, "admin1": "Гродненская область", "population": 360000}],
       "железногорск": [{"name": "Железногорск", "latitude": 56.25, "longitude": 93.53, "admin1": "Красноярский край", "population": 85000},
                        {"name": "Железногорск", "latitude": 52.33, "longitude": 35.37, "admin1": "Курская область", "population": 30000}]}
SEEN, LLM, MODE = [], [], {"down": False}


def meteo(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if MODE["down"]:
        return route.abort()
    if "geocoding" in u.netloc:
        SEEN.append(q["name"][0])
        return route.fulfill(status=200, body=json.dumps({"results": GEO.get(q["name"][0].lower(), [])}), headers={"Content-Type": "application/json"})
    SEEN.append(("fc", float(q["latitude"][0])))
    d0 = date.today()
    route.fulfill(status=200, headers={"Content-Type": "application/json"}, body=json.dumps({
        "current": {"temperature_2m": -3.4, "apparent_temperature": -8, "weather_code": 3, "wind_speed_10m": 14},
        "daily": {"time": [(d0 + timedelta(days=i)).isoformat() for i in range(3)], "weather_code": [71, 0, 63],
                  "temperature_2m_min": [-5, -8, 0], "temperature_2m_max": [1, -2, 4], "precipitation_probability_max": [60, 5, 80]}}))


def llm(route):
    LLM.append(1)
    route.fulfill(status=200, headers={"Content-Type": "text/event-stream"},
                  body='data: {"choices":[{"delta":{"content":"Ответ модели."}}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
from playwright.sync_api import sync_playwright  # noqa: E402
try:
    with sync_playwright() as p:
        b = p.chromium.launch(); errs = []
        pg = b.new_page(viewport={"width": 400, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("https://geocoding-api.open-meteo.com/**", meteo); pg.route("https://api.open-meteo.com/**", meteo)
        pg.route("https://llm.test/**", llm)
        pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
        P = lambda t: pg.evaluate("(t) => wqParse(t)", t)   # noqa: E731
        ok(P("Какая сейчас погода?") == {"city": "", "day": 0, "pre": False}, "«какая сейчас погода?»")
        ok(P("погода в минске завтра") == {"city": "Минске", "day": 1, "pre": True}, "«погода в минске завтра» — город с заглавной, завтра")
        ok(P("какая погода в Железногорске Курской области")["city"] == "Железногорске Курской области", "город с областью")
        ok(P("сколько градусов на улице") and P("какая погода в Москве послезавтра")["day"] == 2, "«сколько градусов на улице», послезавтра")
        for t in ("включи песню погода в доме", "погода влияет на настроение", "напомни про погоду", "какая погода будет в выходные", "что ты думаешь о климате"):
            ok(P(t) is None, f"не перехватываем: «{t}»")
        pg.evaluate("""() => { document.querySelectorAll('.sheet.on').forEach(s => s.classList.remove('on')); S.textMode = true; S.memory = []; delete S.weatherCity;
            S.llm = Object.assign({}, DEF.llm, { name: 'Своя', base_url: 'https://llm.test/v1', model: 'm' }); saveS(); }""")

        def ask(t):
            pg.evaluate("(t) => ask(t)", t); pg.wait_for_function("!busy", timeout=20000); pg.wait_for_timeout(250)
            return pg.evaluate("() => document.getElementById('bot').textContent")

        a = ask("Какая погода?")
        ok("В каком вы городе" in a and not LLM, f"города нет нигде — спросить, без модели: {a!r}")
        a = ask("погода в Минске")
        ok("Сейчас в Минске минус 3°, пасмурно, ощущается как минус 8, ветер 14 км/ч" in a and "Днём от минус 5 до плюс 1°" in a and not LLM, f"«погода в Минске» — числа сразу: {a!r}")
        ok(pg.evaluate("S.weatherCity") == "Минск", "названный город запомнен")
        a = ask("а какая погода завтра")
        ok(a.startswith("Минск, завтра: от минус 8 до минус 2°, ясно, вероятность осадков 5%") and not LLM, f"дальше — без названия: {a!r}")
        a = ask("Железногорск Курской области погода")
        a2 = ask("какая погода в Железногорске Курской области")
        ok(("fc", 52.33) in SEEN and "Железногорске Курской области" in a2, f"область выбирает тот Железногорск: {a2!r}")
        pg.evaluate("() => { delete S.weatherCity; S.memory = ['Живу в Гродно', 'Любит чай']; saveS(); }")
        a = ask("сколько градусов на улице")
        ok(a.startswith("Сейчас в Гродно минус 3°"), f"город из памяти: {a!r}")
        n = len(LLM); a = ask("погода в доме у Петровых")
        ok(len(LLM) == n + 1, f"«погода в доме у Петровых» — не город: отвечает модель ({a!r})")
        MODE["down"] = True; a = ask("погода в Минске")
        ok("сервис погоды не отвечает" in a, f"сервис молчит — честно: {a!r}")
        b.close()
    ok(not errs, "без ошибок JavaScript" + (f": {errs[:3]}" if errs else ""))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
