"""Первый вопрос (0.74; воронка 30.10: из 70 новых компьютеров, где не было ни одного ответа, 63 так ничего и не спросили —
не сломалось, а просто не знали, с чего начать). Новичку после знакомства, пока он ничего не спросил, под портретом —
три фразы-кнопки; через 2,5 минуты тишины персонаж один раз мягко напомнит о себе. Первый вопрос — голосом, текстом или
кнопкой — убирает всё навсегда. У прежних пользователей (ui.first_ask == None) ничего не появляется."""
import inspect, json, os, re, sys, threading, time, types
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import settings as SET  # noqa: E402
from engine_answer import AnswerMixin  # noqa: E402
from engine_intro import IntroMixin  # noqa: E402

ok(SET.DEFAULTS["ui"]["first_ask"] is None, "по умолчанию (прежние пользователи) — None: подсказок нет")
ok("first_asked(self)" in inspect.getsource(AnswerMixin.ask), "любой вопрос (голос, текст, кнопка) отмечает «первый вопрос задан»")


class S:
    def __init__(self, ui):
        self.d = {"ui": dict(ui), "persona": "lira"}

    def get(self, *k, default=None):
        v = self.d
        for x in k:
            v = v.get(x) if isinstance(v, dict) else None
        return default if v is None else v

    def update(self, p):
        for k, v in p.items():
            if isinstance(v, dict):
                self.d.setdefault(k, {}).update(v)
            else:
                self.d[k] = v


class E(IntroMixin):
    FIRST_NUDGE_S = 0.6

    def __init__(self, ui):
        self.s, self.said, self.events = S(ui), [], []
        self.turn, self.state, self.stopping, self.mic_voice_t = None, "idle", threading.Event(), 0.0
        self.personas = types.SimpleNamespace(get=lambda pid: {"name": "Лира"})
        self.wav_input = None

    def emit(self, kind, **k):
        self.events.append((kind, k))

    def _dj_say(self, t):
        self.said.append(t)


IntroMixin.stopping_wait = None
e = E({"intro": "done", "first_ask": False})
orig = e.stopping.wait
e.stopping.wait = lambda t: orig(0.1)
e.intro_auto()
time.sleep(1.5)
ok(len(e.said) == 1 and "Спросите что угодно" in e.said[0] and "Лира" in e.said[0] and e.s.get("ui", "first_nudged"),
   f"познакомились и молчат — один раз мягко напомнила: {e.said}")
ok(("first_ask", {"on": True, "phrases": e.first_try()}) in e.events, "и снова показала фразы-кнопки")
e.intro_auto(); time.sleep(1.0)
ok(len(e.said) == 1, "второй раз — не напоминает")
e.first_asked()
ok(e.s.get("ui", "first_ask") is True and ("first_ask", {"on": False}) in e.events, "спросили — подсказки убраны навсегда")

old = E({"intro": "done", "first_ask": None})
old.stopping.wait = lambda t: threading.Event().wait(0.1)
old.intro_auto(); time.sleep(1.2)
old.first_asked()
ok(not old.said and old.s.get("ui", "first_ask") is None, "прежний пользователь — ни напоминания, ни отметок")

busy = E({"intro": "done", "first_ask": False})
busy.state = "speaking"
busy.stopping.wait = lambda t: threading.Event().wait(0.1)
busy.intro_auto(); time.sleep(1.2)
ok(not busy.said, "занят разговором — не перебивает")
busy.stopping.set()

# ---------- виджет ----------
CORE = """(() => { window.calls = []; const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); return {}; };
    setTimeout(() => { core.emit("hello", { version: "0.74.0", settings: { ui: { first_ask: FA }, features: {}, tts: {}, privacy: {} }, personas: [], muted: false, reminders: [] });
                       core.emit("state", { state: "idle" }); }, 200); };
  ready(); })();"""
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    for fa in ("false", "null"):
        pg = b.new_page(viewport={"width": 340, "height": 520}); pg.on("pageerror", lambda x: errs.append(str(x)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE.replace("FA", fa))
        pg.goto((ROOT / "ui/hud.html").as_uri()); pg.wait_for_timeout(1500)
        if fa == "null":
            ok(not pg.is_visible("#fq"), "прежний пользователь — в виджете ничего лишнего")
            pg.close(); continue
        ok(pg.is_visible("#fq") and pg.locator("#fq button").count() == 3 and "погода" in pg.inner_text("#fq"), "новичок — три фразы-кнопки под портретом")
        if SHOT:
            pg.screenshot(path=str(Path(SHOT) / "first-ask.png"))
        pg.evaluate("core.emit('state', { state: 'thinking' })"); pg.wait_for_timeout(100)
        ok(not pg.is_visible("#fq"), "пока думает и отвечает — не мешают")
        pg.evaluate("core.emit('state', { state: 'idle' })"); pg.wait_for_timeout(100)
        pg.locator("#fq button").nth(1).click(); pg.wait_for_timeout(200)
        ok(["say", {"text": "Напомни через 5 минут проверить чайник"}] in pg.evaluate("calls") and not pg.is_visible("#fq"), "нажали — фраза ушла ассистенту, кнопки пропали")
        pg.evaluate("core.emit('first_ask', { on: true, phrases: ['Который час?', 'Что ты умеешь?', 'Расскажи анекдот'] })"); pg.wait_for_timeout(100)
        ok(pg.is_visible("#fq") and "Который час" in pg.inner_text("#fq"), "напоминание ядра — снова видны")
        pg.evaluate("core.emit('first_ask', { on: false })"); pg.wait_for_timeout(100)
        ok(not pg.is_visible("#fq"), "спросили — пропали")
        pg.close()
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
