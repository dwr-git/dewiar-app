"""«Первая минута» (1.0.26; воронка 17.11: из 965 свежих компьютеров с мозгом 416 так и не получили ни одного ответа — 217
закрыли программу в первые 10 минут, ни о чём не спросив; телефон — 257 из 749). На компьютере первое знакомство шло
полторы-две минуты (имя, город, утро, кнопки, мозг) и кончалось «зови меня по имени», а рядом студия открывала «Первые
шаги» с вопросами — два рассказа разом. Теперь при первом запуске — одна фраза голосом и сразу слушаю вопрос без имени;
ответ приходит в окно «Первые шаги» (событие heard). Полное знакомство — по кнопке «Познакомиться голосом».
На телефоне после приветствия «Говорите сразу…» фразы-примеры не показывались (экран не пуст) — теперь показываются.
Настоящие engine_intro (IntroMixin), ui/studio/welcome.js в settings.html и app.js телефона."""
import inspect, os, re, sys, threading, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_intro import IntroMixin  # noqa: E402


class S:
    def __init__(self, ui):
        self.d = {"ui": dict(ui), "persona": "lira", "llm": {}}

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
    FIRST_NUDGE_S = 999

    def __init__(self, mic=True):
        self.s, self.said, self.events, self.listened = S({"intro": "", "first_ask": None}), [], [], []
        self.turn, self.state, self.stopping, self.mic_voice_t, self.muted = None, "idle", threading.Event(), 0.0, False
        self.personas = types.SimpleNamespace(get=lambda pid: {"name": "Лира"})
        self.wav_input, self._audio_thread, self._mic = None, object(), mic

    def emit(self, kind, **k):
        self.events.append((kind, k))

    def ensure_voice(self, pid):
        pass

    def _intro_say(self, text, step, **extra):
        self.said.append((step, text)); self.emit("intro", step=step, text=text, **extra); return True

    def _mic_absent(self):
        return not self._mic

    def listen_for_command(self, seconds=None):
        self.listened.append(seconds)


e = E()
e._intro_run(True)
steps = [s for s, _ in e.said]
ok(steps == ["hello"] and "Спросите меня о чём угодно" in e.said[0][1] and len(e.said[0][1]) < 110,
   f"первый запуск — одна короткая фраза: {e.said}")
ok(e.listened == [25], "и сразу слушаю вопрос 25 секунд — без имени")
ok(("intro", {"step": "try", "phrases": e.first_try()}) in e.events, "под портретом — те же три вопроса")
ok(e.s.get("ui", "intro") == "done" and e.s.get("ui", "first_ask") is False, "знакомство отмечено, новичок — до первого вопроса")
ok(not any(s in ("mic", "city", "morning", "buttons", "brain") for s in steps), "ни имени, ни города, ни рассказа о кнопках")
n = E(mic=False)
n._intro_run(True)
ok([s for s, _ in n.said] == ["hello", "mic_none"] and not n.listened, f"без микрофона — как писать, не слушаю: {n.said}")
src = inspect.getsource(IntroMixin.intro_auto)
ok("intro_start(short=True)" in src, "сам при первом запуске — короткий вариант")
ok("_intro_script" in inspect.getsource(IntroMixin._intro_run), "кнопкой «Познакомиться голосом» — полное знакомство, как было")

# студия: «Первые шаги» — те же вопросы, услышанная без имени фраза — ответ сюда
js = (ROOT / "ui/studio/welcome.js").read_text(encoding="utf-8")
qs = re.search(r"const WLC_QS = (\[.*?\]);", js).group(1)
ok(all(q.rstrip("?") in qs for q in ["Какая завтра погода", "Напомни через 5 минут проверить чайник", "что ты умеешь"]),
   f"«Первые шаги» — те же три вопроса, что в виджете: {qs}")
from playwright.sync_api import sync_playwright  # noqa: E402
CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
  core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
  core.connected = true; window.calls = []; core.call = async (c, a) => { calls.push([c, a]); return c === "llm_test" ? { ok: true } : {}; }; }; ready(); })();"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1200, "height": 800}); pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort()); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(900)
    pg.evaluate("() => { S = S || {}; S.llm = { active: 'd', profiles: { d: { cloud: true } } }; S.ui = S.ui || {}; wlcOpen(); }")
    pg.wait_for_timeout(300)
    pg.evaluate("() => core.emit('heard', { text: 'какая завтра погода' })"); pg.wait_for_timeout(150)
    ok(pg.is_visible("#wlc-ans") and pg.evaluate("document.querySelector('#wlc-ans').classList.contains('wait')"),
       "сказали вопрос без имени — в «Первых шагах» сразу «думаю…»")
    pg.evaluate("() => core.emit('answer', { text: 'Завтра в Минске +3 и дождь.', done: true })"); pg.wait_for_timeout(150)
    ok("+3" in pg.inner_text("#wlc-ans") and pg.is_visible("#wlc-done"), "ответ — здесь же, и кнопка «Готово»")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()

# телефон: после приветствия первого запуска фразы-примеры видны
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("greetOnly = true" in app and "(quiet || greetOnly)" in app and "greet(gfix(" in app, "телефон: приветствие первого запуска не прячет фразы-примеры")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
