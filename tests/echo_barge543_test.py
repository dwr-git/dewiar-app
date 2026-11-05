"""№543 (пакет 04.11, Windows 10 на MacBook, 0.82.2): «он слышит сам себя в динамик… я послал его искать по поиску, он всё
нашёл, начал говорить и сам себя перебил и перестал работать». Журнал: системного эхоподавления в Windows нет, но включено
«Я в наушниках», а звук — в «Динамики (Apple Audio Device)». Через 2 с после первых слов — «⏹ Перебили (речь)»: своё эхо
прошло как речь человека, ответ (дайджест после поиска и чтения трёх страниц) пропал, а эхо «Сергей вот что.» (3 слова)
ушло как новый вопрос — узнавание эха брало фразы от 4 слов и только в 3,5 с после конца речи.
Теперь: без настоящего AEC перебить речью можно только заметно громче своего эха (barge_floor), имя в моей же фразе —
не зов; фраза, которой меня перебили, проверяется на эхо от 2 слов и в 20 с от перебивания; эхо — ответ договаривается
(готов — досказываю остаток, нет — тот же вопрос заново), а 10 минут перебить можно только именем или «стоп»."""
import collections, os, sys, tempfile, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine as E  # noqa: E402
import engine_audio as EA  # noqa: E402
from engine_base import Turn  # noqa: E402

# 1) порог перебивания речью без настоящего эхоподавления
quiet = [80.0] * 120                                       # в наушниках микрофон, пока я говорю, слышит комнату
loud = [1500.0 + (i % 7) * 30 for i in range(120)]         # колонки MacBook: своё эхо громкое
ok(EA.barge_floor(quiet) < 220, f"в наушниках порог не мешает живой речи ({EA.barge_floor(quiet):.0f})")
ok(EA.barge_floor(loud) > 2600, f"в колонках эхо (~1500) порог не проходит ({EA.barge_floor(loud):.0f})")
ok(EA.barge_floor([1500.0] * 5) == float("inf"), "первые доли секунды ответа — речью не перебить (данных нет)")
mixed = loud[:90] + [5000.0] * 30                          # человек громко заговорил последнюю секунду
ok(EA.barge_floor(mixed) < 4000, "последняя секунда (возможно, уже человек) в порог не входит")

# 2) что ещё не прозвучало
full = "Сергей, вот что. Ниши на YouTube в 2026 году: обучение, финансы и обзоры техники. Shorts растут быстрее."
ok(EA.rest_after(full, ["Сергей, вот что."]) == "Ниши на YouTube в 2026 году: обучение, финансы и обзоры техники. Shorts растут быстрее.",
   "остаток — после последней целиком сказанной фразы")
ok(EA.rest_after(full, []) == full, "ничего не сказано — весь ответ")
ok(EA.rest_after(full, ["Сергей, вот что.", "Ниши на YouTube в 2026 году: обучение, финансы и обзоры техники.", "Shorts растут быстрее."]) == "",
   "всё сказано — остатка нет")


# 3) ход: перебили речью → фраза — моё эхо → договариваю
class S:
    def __init__(self):
        self.d = {"persona": "lira", "audio": {"barge_in": "smart"}}

    def get(self, *k):
        v = self.d
        for x in k:
            v = (v or {}).get(x)
        return v


def mk():
    e = E.Engine.__new__(E.Engine)
    e.s = S()
    e._said = collections.deque(maxlen=40)
    e._echo_hits, e._echo_until, e._spoke_until = [], 0.0, 0.0
    e._barge_snap, e._barge_name_until = None, 0.0
    e._turn_lock = threading.RLock()
    e.turn, e.turn_n, e.pending_confirm, e.player, e.alarm = None, 5, None, None, None
    e.history, e.notes, e.asked, e.spoken = [], [], [], []
    e.status = {"aec": True, "aec_real": False, "headphones": True}
    e.state, e.follow_up_until, e._now_saying = "speaking", 0.0, ""
    e._intro_ear = None
    e.emit = lambda *a, **k: None
    e.note = lambda t: e.notes.append(t)
    e.set_state = lambda st: setattr(e, "state", st)
    e.ask = lambda q, **k: e.asked.append((q, k))
    e.switch_persona = lambda pid: e.s.d.__setitem__("persona", pid)

    def speak(turn, q):
        while True:
            x = q.get()
            if x is None:
                break
            e.spoken.append(x)
            turn.spoken.append(x)
    e._speak_worker = speak
    return e


def turn_with(e, done):
    t = Turn(5)
    t.q, t.images = "Что нового про YouTube: рейтинги, популярный контент, выбор ниши?", []
    t.full = full
    t.spoken = ["Сергей, вот что."]
    t.gen_done = done
    e.turn = t
    e._said.append((time.monotonic(), "Сергей, вот что."))
    return t


e = mk()
turn_with(e, True)
e.interrupt("речь")
ok(e._barge_snap is not None and e.turn is None, "перебили речью во время ответа — ход запомнен")
ok(any("(меня перебили)" in (m.get("content") or "") for m in e.history), "в истории пока — «меня перебили»")
e.handle_text("Сергей вот что.", True, False)
for _ in range(50):
    if e.history and "(меня перебили)" not in str(e.history) and e.turn is None and e.spoken:
        break
    time.sleep(0.05)
ok(e.spoken and e.spoken[0].startswith("Ниши на YouTube"), f"эхо «Сергей вот что.» (3 слова) — договариваю остаток: {e.spoken[:1]}")
ok("(меня перебили)" not in str(e.history) and e.history[-1]["content"] == full and e.history[-2]["role"] == "user",
   "в истории — вопрос и весь ответ, без «меня перебили»")
ok(e._barge_name_until > time.monotonic() + 500, "эхо прорвалось — 10 минут перебить речью нельзя, только именем или «стоп»")
ok(any("Я в наушниках" in n for n in e.notes), "человеку понятно: звук в колонках, хотя включено «Я в наушниках»")
ok(not e.asked, "готовый ответ не спрашиваю у модели заново")

# ответ ещё не сложился (модель читала страницы) — тот же вопрос заново
e = mk()
turn_with(e, False)
e.interrupt("речь")
e.handle_text("Сергей, вот что.", True, False)
ok(e.asked and e.asked[0][0].startswith("Что нового про YouTube") and e.asked[0][1].get("quiet"),
   f"ответ не сложился — задаю тот же вопрос заново: {e.asked[:1]}")

# настоящий новый вопрос поверх ответа — не эхо, прежний не договариваем
e = mk()
turn_with(e, True)
e.interrupt("речь")
ok(not e._is_self_echo("Стоп, расскажи лучше какая завтра погода в Минске", barge=True), "живой вопрос поверх ответа — не эхо")
# имя в моём же ответе — не зов (быстрый слух и точная модель)
e = mk()
e._said.append((time.monotonic(), "Джарвис расскажет подробнее про нишу YouTube."))
e._now_saying = "Джарвис расскажет подробнее про нишу YouTube."
ok(e._own_word("джарвис"), "имя есть в том, что я сейчас говорю")
ok(e._is_self_echo("Джарвис расскажет подробнее", barge=True), "точная модель услышала «Джарвис расскажет…» — это моя фраза")
src = (ROOT / "core" / "engine_audio.py").read_text(encoding="utf-8")
ok("имя в моей же речи (эхо), не перебиваю" in src and "barge_floor(list(spk_all))" in src and "now >= self._barge_name_until" in src,
   "в слухе: имя из своей речи не перебивает; порог речи без AEC; после эха — только по имени")
ok('self.status["aec_real"] = bool(use_aec)' in src, "наушники — не настоящий AEC (status.aec_real)")

# старое поведение: длинная своя фраза — эхо, короткое «да, давай» — нет
e = mk()
e._said.append((time.monotonic(), "Миша, посмотрела. Увы, трек всё ещё на паузе."))
ok(not e._is_self_echo("да давай"), "«да, давай» без перебивания — не эхо")

print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
