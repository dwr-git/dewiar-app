"""№373 (28.10): своя маленькая модель (qwen2.5:1.5b) на «какая сейчас погода?» не звала прогноз и выдумывала
(«облачно с ветром», на «а температура?» — «утром, днём и вечером облачно»); человек назвал город, просил гисметео и
«найди в интернете» — полчаса без чисел. Теперь простой вопрос о погоде — сразу настоящие числа Open-Meteo, без модели
(weatherq.py, engine_music._weather_cmd): город — названный, из «Утра», из памяти; нет нигде — спросить; названный
запоминается; падеж («в Минске», «в Нижнем Новгороде») и область («Железногорск Курской области» — не красноярский);
«погода в доме» и «песню погода в доме» — не перехватываем; сервис молчит — честно. Для экзамена — событие weather."""
import os, sys, types
from datetime import date, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_music as EM  # noqa: E402
import weatherq as W  # noqa: E402

P = W.parse
ok(P("Какая сейчас погода?") == {"city": "", "day": 0, "pre": False}, "«какая сейчас погода?»")
ok(P("погода в минске завтра") == {"city": "Минске", "day": 1, "pre": True}, "«погода в минске завтра» — город с заглавной, завтра")
ok(P("какая погода в Железногорске Курской области")["city"] == "Железногорске Курской области", "город с областью")
ok(P("Погода Железногорск Курской области")["city"] == "Железногорск Курской области" and not P("Погода Железногорск Курской области")["pre"], "без «в»")
ok(P("И какая погода у меня в городе?")["city"] == "" and P("ну так найди в интернете информацию о погоде в моем городе!")["city"] == "", "«у меня в городе», «найди в интернете о погоде в моём городе»")
ok(P("сколько градусов на улице") and P("какая погода в Москве послезавтра")["day"] == 2, "«сколько градусов на улице», послезавтра")
for t in ("включи песню погода в доме", "погода влияет на настроение", "напомни про погоду", "какая погода будет в выходные", "каждое утро говори погоду", "что ты думаешь о климате"):
    ok(P(t) is None, f"не перехватываем: «{t}»")
# №412 (30.10): «Привет. Какая погода за окном?» — приветствие не мешает; город — из «Обо мне», а не догадка модели
ok(P("Привет. Какая погода за окном?") == {"city": "", "day": 0, "pre": False} and P("Доброе утро! Какая погода в Хабаровске?")["city"] == "Хабаровске",
   "приветствие в начале — погода всё равно сразу, без модели")
ok(W.memory_place("- Живу в Хабаровске\n- Работаю дома") == ("Хабаровске", True), "«живу в Хабаровске» — из памяти")
import tools as TL  # noqa: E402
_err = ""
_get = TL.httpx.get
TL.httpx.get = lambda *a, **k: (_ for _ in ()).throw(TL.httpx.ConnectTimeout("timed out"))   # сеть до сервиса погоды не пускает
try:
    TL.t_weather({"city": "Хабаровск"}, {"dewiar_web": lambda k, v: (_ for _ in ()).throw(RuntimeError("нет входа в аккаунт dewiar.pro и ключа Dewiar"))})
except Exception as e:  # noqa: BLE001
    _err = str(e)
TL.httpx.get = _get
ok("сервис погоды не отвечает" in _err and "dewiar.pro" not in _err.lower().replace("про dewiar", ""), f"прогноз не получить — без слов об аккаунте Dewiar: {_err!r}")
ok(W.memory_place("- Живёт в Минске\n- Любит чай") == ("Минске", True) and W.memory_place("Мой город — Гродно") == ("Гродно", False)
   and W.memory_city("город Железногорск Курской области") == "Железногорск Курской области", "город из памяти")

GEO = {"минск": [{"name": "Минск", "latitude": 53.9, "longitude": 27.5, "admin1": "Минск", "population": 2000000}],
       "нижний новгород": [{"name": "Нижний Новгород", "latitude": 56.3, "longitude": 44.0, "admin1": "Нижегородская область", "population": 1200000}],
       "железногорск": [{"name": "Железногорск", "latitude": 56.25, "longitude": 93.53, "admin1": "Красноярский край", "population": 85000},
                        {"name": "Железногорск", "latitude": 52.33, "longitude": 35.37, "admin1": "Курская область", "population": 30000}]}
asked = []


def fake_get(url, params, via=None):
    if "geocoding" in url:
        asked.append(params["name"])
        if FAIL:
            raise W.httpx.ConnectError("нет сети")
        return {"results": GEO.get(params["name"].lower(), [])}
    asked.append(("fc", params["latitude"]))
    d0 = date.today()
    return {"current": {"temperature_2m": -3.4, "apparent_temperature": -8, "weather_code": 3, "wind_speed_10m": 14},
            "daily": {"time": [(d0 + timedelta(days=i)).isoformat() for i in range(3)], "weather_code": [71, 0, 63],
                      "temperature_2m_min": [-5, -8, 0], "temperature_2m_max": [1, -2, 4], "precipitation_probability_max": [60, 5, 80]}}


FAIL = False
W._get = fake_get
ok(W.geocode("Минске")["name"] == "Минск" and W.geocode("Нижнем Новгороде")["name"] == "Нижний Новгород", "падеж: «Минске», «Нижнем Новгороде»")
g = W.geocode("Железногорске Курской области")
ok(g["admin1"] == "Курская область" and W.stored(g) == "Железногорск, Курская область" and W.geocode("Железногорск, Курская область")["latitude" if False else "lat"] == 52.33,
   "область выбирает тот Железногорск; хранится с областью")
ok(W.geocode("Доме У Петровых") is None, "«дом у Петровых» — не город")


class Settings:
    def __init__(self): self.d = {"morning": {"city": ""}}
    def get(self, k, *a): return self.d.get(k)
    def update(self, p): [self.d.setdefault(k, {}).update(v) for k, v in p.items()]


class Eng:
    _weather_cmd = EM.MusicMixin._weather_cmd

    def __init__(self, mem=""):
        self.s = Settings(); self.said = []; self.ev = []
        self.workspace = types.SimpleNamespace(memory_get=lambda: mem)
    def _say_quick(self, msg, said, via=None, note=None): self.said.append((msg, note))
    def emit(self, *a, **k): self.ev.append((a, k))


E = Eng()
ok(E._weather_cmd("Какая сейчас погода?") and "В каком вы городе?" in E.said[-1][0], "города нет нигде — спрашивает город")
ok(E._weather_cmd("погода в Железногорске Курской области"), "назвал город — ответ без модели")
msg = E.said[-1][0]
ok(msg.startswith("Сейчас в Железногорске Курской области минус 3°, пасмурно, ощущается как минус 8, ветер 14 км/ч.") and "Днём от минус 5 до плюс 1°, небольшой снег, осадки 60%." in msg,
   f"настоящие числа, по-русски: {msg}")
ok(E.s.d["morning"]["city"] == "Железногорск, Курская область", "город запомнен для погоды и «Утра»")
ok(any(a == ("tool",) and k["name"] == "weather" and k["status"] == "done" for a, k in E.ev) and "ветер 14 км/ч" in (E.said[-1][1] or ""),
   "событие weather (экзамен) и прогноз — в истории для «а ветер?»")
asked.clear()
ok(E._weather_cmd("И какая погода у меня в городе?") and E.said[-1][0].startswith("Железногорск, сейчас минус 3°"), f"дальше — сразу по своему городу: {E.said[-1][0][:60]}")
ok(E._weather_cmd("что с погодой завтра") and E.said[-1][0] == "Железногорск, завтра: от минус 8 до минус 2°, ясно, вероятность осадков 5%.", f"завтра: {E.said[-1][0]}")
E2 = Eng("- Живёт в Минске")
ok(E2._weather_cmd("сколько градусов на улице") and E2.said[-1][0].startswith("Сейчас в Минске минус 3°") and E2.s.d["morning"]["city"] == "", "город из памяти — «в Минске», не перезаписывая «Утро»")
E3 = Eng()
ok(E3._weather_cmd("Какая погода в доме у Петровых") is False and not E3.said, "не город — вопрос уходит модели")
FAIL = True
E4 = Eng("живу в Минске")
ok(E4._weather_cmd("какая погода?") and "сервис погоды не отвечает" in E4.said[-1][0], "сеть упала — честно, без выдумок")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("self._weather_cmd(text, via)" in src and src.index("self._home_cmd(text, via)") < src.index("self._weather_cmd(text, via)"),
   "в разговоре: после умного дома («температура в спальне» — датчик), до модели")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
