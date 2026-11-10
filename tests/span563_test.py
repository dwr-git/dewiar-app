"""№563 (ПК 0.84.2, 05.11): «Уведомления о встречах приходят в минутах. Если это больше часа, сложно понять, например,
87 минут. Гораздо проще: 1 ч 27 мин». Теперь напоминание о встрече из календаря — «Через 1 ч 27 мин — 14:30» (текст) и
«Через час 27 минут: …» (голос); таймеры в виджете и на телефоне — так же."""
import os, re, subprocess, sys
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from when import span  # noqa: E402
T = {87: "1 ч 27 мин", 45: "45 мин", 60: "1 ч", 120: "2 ч", 121: "2 ч 1 мин", 1: "1 мин", 0: "0 мин"}
ok(all(span(k) == v for k, v in T.items()), f"текст: {[(k, span(k)) for k in T]}")
V = {87: "час 27 минут", 21: "21 минуту", 3: "3 минуты", 60: "час", 125: "2 часа 5 минут", 300: "5 часов", 61: "час 1 минуту"}
ok(all(span(k, voice=True) == v for k, v in V.items()), f"голос: {[(k, span(k, voice=True)) for k in V]}")

# сам цикл календаря: встреча через 87 минут, напоминать за 120
import engine_audio  # noqa: E402


class Cal:
    def items(self):
        return [1]

    def refresh(self):
        pass

    def public(self):
        return {}

    def events(self, a, b):
        return [{"cid": "c", "title": "Созвон с бухгалтером", "start": datetime.now().replace(second=0, microsecond=0) + timedelta(minutes=88),
                 "allday": False, "place": ""}]


class S:
    def get(self, *k):
        return 120


class Stop:
    n = 0

    def is_set(self):
        return self.n > 1

    def wait(self, t):
        self.n += 1
        return self.n > 1


os.environ["DEWIAR_CAL_TICK"] = "0.01"
mix = next(v for k, v in vars(engine_audio).items() if isinstance(v, type) and hasattr(v, "_calendar_loop"))
got = {"push": [], "say": []}
o = type("X", (mix,), {})()
o.calendars, o.s, o.stopping, o.state, o.meeting = Cal(), S(), Stop(), "idle", None
o.push = lambda t, x="", **k: got["push"].append(t)
o.announce = lambda t, **k: got["say"].append(t)
o.emit = lambda *a, **k: None
o._calendar_loop()
p, s = (got["push"] or [""])[0], (got["say"] or [""])[0]
ok(re.search(r"Через 1 ч 2\d мин — \d\d:\d\d", p) and "87" not in p and "88" not in p, f"уведомление: {p}")
ok(re.match(r"Через час 2\d минут[уы]?: Созвон", s), f"голосом: {s}")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
js = ("const tmrWords = " + re.search(r"const tmrWords = (.+?);", hud).group(1) + ";\n"
      + re.search(r"const spanRu = .+?;\n", app).group(0)
      + "console.log(JSON.stringify([tmrWords(87), tmrWords(60), tmrWords(120), tmrWords(25), spanRu(87), spanRu(45), spanRu(120)]))")
out = subprocess.run(["node", "-e", js], capture_output=True, text=True).stdout.strip()
ok(out == '["1 ч 27 мин","час","2 ч","25 мин","1 ч 27 мин","45 мин","2 ч"]', f"таймер в виджете и на телефоне: {out}")
ok("таймер на ${spanRu(mins)}" in app, "телефон: «таймер на 1 ч 27 мин»")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
