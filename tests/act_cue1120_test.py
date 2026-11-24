"""Голос во время долгого действия (владелец 20.11: «Если действие идёт дольше ~3 секунд, а Лира ещё ничего не сказала,
она один раз коротко говорит, что именно делает… это ОЧЕНЬ КРУТО! Сделай»)."""
import os, queue, sys, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import act_cue  # noqa: E402
from engine_base import Turn  # noqa: E402
from engine_answer import AnswerMixin  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)

act_cue.ACT_CUE_S = 0.15


class S:
    def __init__(self, text_only=False): self.t = text_only
    def get(self, a, b=None): return self.t if (a, b) == ("tts", "text_only") else None


class E(AnswerMixin):
    def __init__(self, text_only=False): self.s, self.turn = S(text_only), None


def run(name="web_search", setup=None, text_only=False, wait=0.4, second=None):
    e, t, q = E(text_only), Turn(1), queue.Queue()
    e.turn = t
    if setup:
        setup(t, e)
    e._act_cue_arm(t, name, q)
    if second:
        e._act_cue_arm(t, second, q)
    time.sleep(wait)
    out = []
    while not q.empty():
        out.append(q.get())
    return out

ok(run() == ["Ищу в интернете…"], "поиск идёт дольше порога, Лира молчит — «Ищу в интернете…»")
ok(run("read_emails") == ["Смотрю почту…"], "почта — «Смотрю почту…»")
ok(run(second="read_webpage") == ["Ищу в интернете…"], "за ход — не больше одного раза")
ok(run(setup=lambda t, e: setattr(t, "full", "Сейчас посмотрю. ")) == [], "модель уже сказала «сейчас посмотрю» — молчим")
ok(run(setup=lambda t, e: setattr(t, "ended", True)) == [], "ход кончился раньше — молчим")
ok(run(setup=lambda t, e: t.cancel.set()) == [], "ход перебили — молчим")
ok(run(setup=lambda t, e: setattr(t, "via", {"done": print})) == [], "вопрос из мессенджера — молчим")
ok(run(text_only=True) == [], "«Отвечать текстом» — молчим")
ok(run("set_reminder") == [] and run("start_task") == [] and run("call_persona") == [], "быстрые и говорящие сами — без фразы")
ok(run("run_command") == [] and run("manage_email") == [], "действия с «Выполнить?» — без фразы (не поверх вопроса)")
ok(all("…" in v and not v.lower().startswith(("секунд", "минут")) for v in act_cue.ACT_CUE.values()), "фразы говорят, что именно делаю")
ok(all(v.split()[0].rstrip("…").endswith(("ю", "у")) for v in act_cue.ACT_CUE.values()), "фразы в настоящем времени, без рода — для любого персонажа")

# голос: фраза-подсказка синтезируется один раз и дальше звучит мгновенно
src = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok("text in CUE_TEXTS" in src and "_cue_audio" in src, "синтез фраз-подсказок запоминается (второй раз — мгновенно)")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok(src.index("self._act_cue_arm(turn, c.get(\"name\"), sentences)") < src.index("r_ = self._use_tool(turn, c, sentences)"),
   "таймер ставится до действия")
from engine_remote import RemoteMixin  # noqa: E402


class Eng:
    name, n = "fake", 0
    def synth(self, t, v, sp):
        Eng.n += 1
        yield 22050, b"xx"


class P:
    def has(self, v): return True


o = RemoteMixin.__new__(RemoteMixin); o.piper, o.s = P(), S()
for txt in ("Ищу в интернете…", "Ищу в интернете…", "Привет.", "Привет."):
    list(o._synth_mixed(Eng(), txt, {"_gender": "female"}, 1.0))
ok(Eng.n == 3, f"фраза-подсказка синтезирована один раз, обычные фразы — как всегда: синтезов {Eng.n} из 4")
import json, re  # noqa: E402
en = json.loads((ROOT / "data/i18n/text/en.json").read_text(encoding="utf-8"))
ok(all(v in en for v in act_cue.ACT_CUE.values()), "по-английски — свои фразы (словарь перевода)")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("function actCueArm(" in app and "actCueArm(c.name, ctl, sink)" in app and "sink.text().trim()" in app,
   "телефон: то же — один раз за ход, если ещё ничего не сказано")
ph = dict(re.findall(r'(\w+): "([^"]+…)"', app[app.index("const ACT_CUE = {"):app.index("function actCueArm(")]))
ok(ph and all(v in en for v in ph.values()) and "send_sms" not in ph and "call" not in ph, f"телефон: фраз {len(ph)}, все переведены, без звонков и SMS")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
