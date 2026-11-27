"""Владелец 20.11: «ложное "стой"… всегда ставит музыку на паузу» (музыка в другой программе, Лира в фоне).
Слово-стоп без имени: своё радио — пауза сразу; чужая музыка — только короткая фраза, которую подтвердила точная
модель (или, если её нет, сама короткая фраза). Слово посреди разговора и «постой, Вань» — не трогаем."""
import os, queue, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from answer_direct import DirectMixin  # noqa: E402
from ears_echo import EchoMixin  # noqa: E402
from engine_base import RATE  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


class Radio:
    def __init__(self, on): self.playing = on


class Checker:
    def __init__(self, text): self.text = text
    def transcribe(self, pcm): return self.text


class E(DirectMixin, EchoMixin):
    STOP_FORMS = {"перестаньте", "замолчите", "прекратите", "остановитесь", "помолчите", "хватит", "стоп", "stop", "стой"}
    def __init__(self, radio=False, checker=None):
        self.radio, self.checker, self.check_q, self.utt_id = Radio(radio), checker, queue.Queue(), 5
        self.paused = []
    def _stop_checker(self): return self.checker
    def _media_stop_word(self, word, force=False): self.paused.append(word); return True
    def _own_word(self, w): return False


def pcm(sec): return b"\0\0" * int(sec * RATE)


def drain(e):                                     # то, что сделал бы поток проверок (ears_name._check_worker)
    while not e.check_q.empty():
        kind, p, w = e.check_q.get()
        assert kind == "media_stop"
        e._media_stop_verify(p, w)


def settle(e):
    import time
    time.sleep(0.2)                               # пауза уходит в поток — дождаться


# своё радио — сразу, как раньше
e = E(radio=True); e._media_stop_heard("стой", 10.0, True); settle(e)
ok(e.paused == ["стой"], "своё радио: «стой» — пауза сразу")

# чужая музыка, фраза ещё звучит; кончилась длинной (разговор) — не трогаем
e = E(checker=Checker("стой")); e._media_stop_heard("стой", 10.0, True); e._media_stop_utt(pcm(3.2), 11.0); drain(e); settle(e)
ok(e.paused == [], "чужая музыка: «стой» внутри фразы 3,2 с — музыку не трогаем")

# короткая фраза, точная модель слышит другое
e = E(checker=Checker("постой ваня")); e._media_stop_heard("стой", 10.0, True); e._media_stop_utt(pcm(1.0), 10.5); drain(e); settle(e)
ok(e.paused == [], "чужая музыка: точная модель слышит «постой ваня» — не трогаем")
e = E(checker=Checker("с той стороны")); e._media_stop_heard("стой", 10.0, True); e._media_stop_utt(pcm(1.0), 10.5); drain(e); settle(e)
ok(e.paused == [], "чужая музыка: «с той стороны» — не трогаем")

# короткая фраза, точная модель подтверждает
e = E(checker=Checker("Стой.")); e._media_stop_heard("стой", 10.0, True); e._media_stop_utt(pcm(0.9), 10.5); drain(e); settle(e)
ok(e.paused == ["стой"], "чужая музыка: короткое «Стой.» подтверждено — пауза")

# Vosk дослышал позже, чем кончилась фраза
e = E(checker=Checker("пауза")); e._media_stop_utt(pcm(0.8), 10.0); e._media_stop_heard("пауза", 10.6, False); drain(e); settle(e)
ok(e.paused == ["пауза"], "фраза кончилась раньше, чем быстрый слух её дослышал — всё равно решаем по ней")

# точной модели нет — решает длина фразы
e = E(checker=None); e._media_stop_heard("стоп", 10.0, True); e._media_stop_utt(pcm(0.8), 10.5); settle(e)
ok(e.paused == ["стоп"], "без точной модели: короткое «стоп» — пауза, как раньше")
e = E(checker=None); e._media_stop_heard("стой", 10.0, True); e._media_stop_utt(pcm(2.5), 11.0); settle(e)
ok(e.paused == [], "без точной модели: «стой» во фразе 2,5 с — не трогаем")

# старая фраза не подхватывается
e = E(checker=Checker("стоп")); e._media_stop_heard("стоп", 10.0, True); e.utt_id = 6; e._media_stop_utt(pcm(0.8), 12.0); drain(e); settle(e)
ok(e.paused == [], "решение ждёт только своей фразы — следующая фраза его не запускает")

src = (ROOT / "core/ears_listen.py").read_text(encoding="utf-8")
ok("self._media_stop_heard(" in src and "self._media_stop_utt(pcm, now)" in src,
   "слух зовёт проверку, а не ставит паузу сразу")
src = (ROOT / "core/ears_name.py").read_text(encoding="utf-8")
ok('kind == "media_stop"' in src, "поток проверок знает «media_stop»")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
