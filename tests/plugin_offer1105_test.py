"""«Нарисуй открытку» без «Художника» (04.11): Лира отвечала «Я не умею рисовать». Теперь просьба к выключенному готовому
плагину, без которого её не выполнить (Художник, Курсы и цены, Тендеры, Рекрутер), — в справке к вопросу: «это умеет плагин
X, предложи включить» и действие plugin_enable с кнопкой «Выполнить?»; отказался — тот же плагин не предлагаем 6 часов.
Слова — строже обычного: «открыть почту» — не «открытка»; рецепты и сказки — без навязывания плагинов."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st"); os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as ST  # noqa: E402
import plugins as PL  # noqa: E402
import tools as T  # noqa: E402
s = ST.Settings(tmp / "s.json")
P = PL.Plugins(s)
for q, want in (("Нарисуй открытку маме на день рождения", "artist"), ("Сделай открытку для бабушки", "artist"),
                ("Нарисуй логотип для кофейни", "artist"), ("Какой сейчас курс доллара?", "rates"), ("Найди тендеры на видеонаблюдение", "tenders"),
                ("Разбери резюме в папке", "recruiter"),
                ("Открой почту", None), ("Открыть файл отчёта", None), ("Расскажи сказку на ночь", None), ("Что приготовить из курицы?", None),
                ("Какая погода завтра?", None), ("Сколько будет 2+2?", None), ("Курсор завис", None)):
    got = (P.match_off(q) or {}).get("id")
    ok(got == want, f"«{q}» → {want or 'не предлагаем'} ({got})")
P.install("artist")
ok(P.match_off("Нарисуй открытку") is None, "включён — не предлагаем (дальше — обычная справка плагина)")
P.remove("artist")


import engine_answer as EA  # noqa: E402
mix = next(v for v in vars(EA).values() if isinstance(v, type) and hasattr(v, "_plugin_hint"))


class Eng2(mix):
    def __init__(self):
        self.plugins, self.mcp, self.calls = P, None, []

    def command(self, cmd, a):
        self.calls.append((cmd, a)); P.install(a["id"]); return {}


E = Eng2.__new__(Eng2); Eng2.__init__(E)
h = E._plugin_hint("Нарисуй открытку маме")
ok("«Художник»" in h and "plugin_enable" in h and "«artist»" in h and "не умею" in h, f"справка: предложить включить, а не «не умею»: {h[:90]}")
ok(E._plugin_hint("Нарисуй открытку маме") == "", "отказался — тот же плагин не предлагаем снова (6 часов)")
E._plugin_offered["artist"] = time.time() - 7 * 3600
ok("«Художник»" in E._plugin_hint("Нарисуй кота"), "через 6 часов — снова можно предложить")
E.mcp = type("M", (), {"plugin_tools": lambda self: {}, "plugin_errors": lambda self: {}})()
ok(E._plugin_keep("Нарисуй открытку") == {"plugin_enable"}, "в маленьком окне действие plugin_enable не выбрасывается")
v = T.TOOLS["plugin_enable"]
ok(v[2] == "confirm" and len(v) == 5 and isinstance(v[4], str), "plugin_enable — с вопросом «Выполнить?»")
r = v[3]({"id": "artist"}, {"engine": E})
ok(E.calls == [("plugin_install", {"id": "artist"})] and "artist" in {x["id"] for x in P.installed()} and "включён" in r,
   f"«Выполнить» — плагин включён как кнопкой в студии: {r[:60]}")
ok("уже включён" in v[3]({"id": "artist"}, {"engine": E}), "второй раз — «уже включён», ничего не ломает")
try:
    v[3]({"id": "nope"}, {"engine": E}); ok(False, "неизвестный — ошибка")
except T.ToolError as e:
    ok("Готового плагина" in str(e) and "Художник" in str(e), "неизвестный плагин — понятная ошибка со списком готовых")
r = v[3]({"id": "tenders"}, {"engine": E})
ok("нужны настройки" in r and "tenders" not in {x["id"] for x in P.installed()}, "плагину нужны настройки — не включаем молча, говорим, где заполнить")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
