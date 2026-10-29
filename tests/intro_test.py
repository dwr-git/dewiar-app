"""Знакомство при первом запуске (core/engine_intro.py): персонаж представляется, проверяет микрофон (следующая фраза
достаётся знакомству, а не модели), рассказывает о кнопках, предлагает фразы; без мозга — ведёт в студию.
«Пропустить» — замолкает. Сам начинается только при первом запуске (ui.intro == ""), у прежних пользователей — нет.
Без звука, модели и окон: голос и ядро — заглушки."""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine as E  # noqa: E402
import settings as ST  # noqa: E402
import audio_io  # noqa: E402
DEVICES = [{"name": "mic", "description": "Микрофон", "kind": "source"}, {"name": "out", "description": "Динамики", "kind": "sink"}]
audio_io.list_devices = lambda: DEVICES          # звук машины, где идут проверки, не важен: устройства — подменные


class S:
    def __init__(self, llm=True, intro=""):
        self.d = {"ui": {"intro": intro}, "audio": {"follow_up_seconds": 6}}
        self.llm = llm

    def get(self, sec, key=None):
        if sec == "persona":
            return "lira"
        v = self.d.get(sec, {})
        return v.get(key) if key else v

    def update(self, patch):
        for k, v in patch.items():
            self.d.setdefault(k, {}).update(v)

    def active_llm(self):
        return {"kind": "openai"} if self.llm else None


class P:
    def get(self, pid):
        return {"id": "lira", "name": "Лира", "gender": "female"}


def make(llm=True, muted=False, hearing=True):
    eng = E.Engine.__new__(E.Engine)
    eng.s = S(llm)
    eng.personas = P()
    eng.muted = muted
    eng._audio_thread = object() if hearing else None
    eng.stopping = threading.Event()
    eng._turn_lock = threading.RLock()
    eng.turn = None; eng.turn_n = 0; eng.state = "idle"; eng.follow_up_until = 0.0
    eng.wav_input = None; eng.server = False
    eng.events = []; eng.said = []
    eng.emit = lambda ev, **k: eng.events.append((ev, k))
    eng._cancel_locked = lambda: None
    eng.cancel_turn = lambda: None
    eng.play_tone = lambda kind: None
    eng.ensure_voice = lambda pid: None
    eng.set_state = lambda st: setattr(eng, "state", st)
    eng._is_self_echo = lambda t: False
    eng._intro_wait_s = 1.5
    eng._level_t = 0.0
    eng.asked = []
    eng.ask = lambda *a, **k: eng.asked.append(a)

    def speak(turn, q):
        while True:
            t = q.get()
            if t is None:
                break
            eng.said.append(t)
    eng._speak_worker = speak
    return eng


def steps(eng):
    return [k.get("step") for ev, k in eng.events if ev == "intro"]


def run(eng, voice=None, wait=20):
    """Запустить знакомство; voice — что «сказать» в микрофон, когда попросят: ("text", …) | ("peak", v) | None."""
    eng.intro_start()
    end = time.time() + wait
    sent = False
    while time.time() < end and eng._intro_running:
        if voice and not sent and eng._intro_ear is not None:
            time.sleep(0.2)
            if voice[0] == "text":
                eng.handle_text(voice[1], False, True)          # фраза без имени, как после «скажи что-нибудь»
            else:
                eng._level(voice[1], "mic")
            sent = True
        time.sleep(0.05)


# 1. услышала фразу
e = make()
import engine_intro  # noqa: E402
run(e, ("text", "Привет, Лира!"))
st = steps(e)
ok(st[:2] == ["start", "hello"] and "mic" in st and "mic_ok" in st and "buttons" in st and "try" in st and st[-1] == "done", f"шаги: {st}")
ok(any("Привет! Я Лира" in t for t in e.said), "представилась своим именем")
ok(any("Слышу тебя отлично: «Привет, Лира»" in t for t in e.said), "услышала фразу и повторила её")
ok(("heard", {"text": "Привет, Лира!"}) in e.events, "фраза показана в виджете как услышанная")
ok(not e.asked, "фраза не ушла модели")
tr = next(k for ev, k in e.events if ev == "intro" and k.get("step") == "try")
ok(len(tr["phrases"]) == 3 and "Лира, который час?" in tr["phrases"], f"фразы «попробуйте»: {tr['phrases']}")
bt = next(k for ev, k in e.events if ev == "intro" and k.get("step") == "buttons")
ok(bt["buttons"] == ["b-mic", "b-voice", "b-type"], "рассказ о кнопках — с подсветкой микрофона, динамика и клавиатуры")
ok(e.s.d["ui"]["intro"] == "done" and not e._intro_running and e._intro_ear is None, "знакомство закончено и запомнено")

# 1б. «первые пять минут» (0.58): имя — заодно проверка микрофона, город для погоды, утро по расписанию
from engine_intro import intro_name, intro_city  # noqa: E402
ok([intro_name(t) for t in ("Меня зовут Михаил", "миша", "я Ольга", "Привет, Лира!", "Галина Петровна", "раз два три")]
   == ["Михаил", "Миша", "Ольга", "", "Галина Петровна", ""], "имя из ответа: «меня зовут…», «я…», просто имя; «привет, Лира» — не имя")
ok(intro_city("В Минске") == ("Минске", "в Минске") and intro_city("гродно") == ("Гродно", "Гродно") and intro_city("нет") == ("", ""),
   "город из ответа; «нет» — пропустить")
import weatherq  # noqa: E402
weatherq.geocode = lambda phrase, via=None: {"name": "Минск"} if "минск" in phrase.lower() else None


class R:
    def __init__(self): self.items = []
    def add(self, at, text, rep=None, kind="reminder", extra=None):
        it = dict({"at": str(at), "text": text, "repeat": rep, "kind": kind}, **(extra or {})); self.items.append(it); return it


e = make(); e.reminders = R()
e.s.update = lambda patch: [e.s.d.__setitem__(k, v) if not isinstance(v, dict) else e.s.d.setdefault(k, {}).update(v) for k, v in patch.items()]
answers = ["Меня зовут Михаил", "В Минске", "Да, давай"]
e.intro_start()
end = time.time() + 25
while time.time() < end and e._intro_running:
    if answers and e._intro_ear is not None:
        time.sleep(0.2); e.handle_text(answers.pop(0), False, True)
    time.sleep(0.05)
st = steps(e)
ok(["mic", "mic_ok", "city", "city_ok", "morning", "morning_ok"] == [x for x in st if x in ("mic", "mic_ok", "city", "city_ok", "morning", "morning_ok")],
   f"знакомство: имя → город → утро: {st}")
ok(e.s.d.get("user_name") == "Михаил" and any("Очень приятно, Михаил!" in t for t in e.said), "имя запомнено, «Очень приятно, Михаил!»")
ok(e.s.d["morning"]["city"] == "Минск" and any("Запомнила: в Минске." in t for t in e.said), "город — «Минск» для погоды, ответ — «в Минске»")
ok(any(x["kind"] == "job" and x.get("preset") == "brief" for x in e.reminders.items) and any("завтра в восемь" in t for t in e.said),
   "«да» — каждое утро в 8:00 голосом (то же дело, что «Утро с Лирой»)")
ok(st[-1] == "done" and "try" in st, "и дальше — как раньше: кнопки, что попробовать")

# 2. голос есть, слов нет
e = make()
run(e, ("peak", 0.3), wait=30)
ok("mic_weak" in steps(e), f"голос слышен, слов нет — совет говорить ближе: {steps(e)}")

# 3. тишина
e = make()
t0 = time.time()
run(e, None, wait=30)
ok("mic_fail" in steps(e) and any("раздел «Звук и поведение»" in t for t in e.said), "тишина — подсказка про выбор микрофона: «Звук и поведение», где его выбирают (17.10)")

# 4. микрофон выключен — не ждём
e = make(muted=True)
run(e)
ok("mic_off" in steps(e) and "mic" not in steps(e), "микрофон выключен — про кнопку микрофона, без ожидания")

# 5. мозга нет и пробный разговор выключен (llm.trial: false) — в студию, на раздел «Мозг»
e = make(llm=False)
e.s.d["llm"] = {"trial": False}
run(e, ("text", "раз два три"))
br = [k for ev, k in e.events if ev == "intro" and k.get("step") == "brain"]
ok(br and br[0].get("page") == "brain" and "try" not in steps(e) and "Claude" in br[0].get("text", "") and "бесплатно" in br[0].get("text", ""), "без мозга — мягкий выбор в «Мозге», фраз не предлагает")
ok(any("я открыла" in t.lower() for t in e.said), f"женский род: {[t for t in e.said if 'открыл' in t]}")
# 5б. 0.69: мозга нет, но мозг Dewiar подключается сам (автоподключение), а пока — пробный разговор: студию не открываем,
# говорим, что можно спрашивать сразу, и предлагаем фразы
e = make(llm=False)
run(e, ("text", "раз два три"))
ba = [k for ev, k in e.events if ev == "intro" and k.get("step") == "brain_auto"]
ok(ba and "сейчас" in ba[0].get("text", "") and not ba[0].get("page") and "try" in steps(e), "без мозга (0.69) — «подключается сам, отвечать могу уже сейчас», и фразы попробовать")

# 6. «Пропустить»
e = make()
e.intro_start()
for _ in range(100):
    if e._intro_ear is not None:
        break
    time.sleep(0.05)
ok(e.intro_stop(), "«Пропустить» во время проверки микрофона")
for _ in range(100):
    if not e._intro_running:
        break
    time.sleep(0.05)
ok(not e._intro_running and "buttons" not in steps(e) and steps(e)[-1] == "done", f"замолчала, дальше не идёт: {steps(e)}")
ok(not e.intro_stop(), "повторный «Пропустить» — ничего")

# 6б. микрофона нет: уровень всё время ровно ноль — не просит говорить, а показывает клавиатуру
e = make()
def speak_zero(turn, q):
    for _ in range(12):
        e._level(0.0, "mic")
    while True:
        t = q.get()
        if t is None:
            break
        e.said.append(t)
e._speak_worker = speak_zero
run(e)
mn = [k for ev, k in e.events if ev == "intro" and k.get("step") == "mic_none"]
ok(mn and "mic" not in steps(e) and mn[0].get("buttons") == ["b-type"] and "писать" in mn[0].get("text", ""), f"микрофона нет — не требует говорить, показывает клавиатуру: {steps(e)}")
e = make()
def speak_noise(turn, q):
    for _ in range(12):
        e._level(0.01, "mic")
    while True:
        t = q.get()
        if t is None:
            break
        e.said.append(t)
e._speak_worker = speak_noise
run(e, ("text", "привет"))
ok("mic" in steps(e) and "mic_none" not in steps(e), "живой микрофон (есть шум) — проверка голосом как обычно")

e = make()
DEVICES[:] = [{"name": "out", "description": "Динамики", "kind": "sink"}]
run(e)
ok("mic_none" in steps(e) and "mic" not in steps(e), "входных устройств нет вовсе — тоже без просьбы говорить")
DEVICES[:] = [{"name": "mic", "description": "Микрофон", "kind": "source"}, {"name": "out", "description": "Динамики", "kind": "sink"}]

# 7. сам — только при первом запуске
e = make()
e.s.d["ui"]["intro"] = "done"
e.intro_auto()
ok(not e._intro_running and not e.events, "уже знакомились — само не начинается")
ok(e.intro_start() is True and e.intro_start() is False, "кнопкой — можно, второй раз поверх — нет")
e.intro_stop()

# 8. настройки: новый пользователь — "", прежний — "done"
tmp = Path(tempfile.mkdtemp())
s_new = ST.Settings(tmp / "a.json") if "path" in ST.Settings.__init__.__code__.co_varnames else None
if s_new is not None:
    ok(s_new.get("ui", "intro") == "", "новая установка — знакомство впереди")
    (tmp / "b.json").write_text(json.dumps({"ui": {"welcome": "done"}}), encoding="utf-8")
    ok(ST.Settings(tmp / "b.json").get("ui", "intro") == "done", "прежний пользователь — само не начинается")
else:
    ok(ST.DEFAULTS["ui"]["intro"] == "", "новая установка — знакомство впереди")

print("\nИТОГ:", "всё хорошо" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
