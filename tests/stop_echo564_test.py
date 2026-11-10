"""№564, идея №143 (Gray, 05.11, Windows, ноутбук, без эхоподавления): «обрывает разговор на середине, какое-то время
висит и потом уходит в трей». В журнале — «✋ «перестань» — замолкаю (без эхоподавления)» три раза за три минуты,
хотя человек молчал: быстрый слух (Vosk с грамматикой стоп-слов) принимал голос Лиры из колонок за «перестань» /
«достаточно» — ответ обрывался, Лира засыпала («💤 сплю до имени»), а виджет, показавшийся из трея на имя, через 9 с
прятался обратно (hud: backLater). Теперь в полудуплексе слово-стоп перепроверяет точная модель по последним ~2 с
микрофона (голос на это время приглушён): эхо — договариваем, настоящее «стоп» — замолкаем, как раньше."""
import collections, os, queue, sys, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_audio  # noqa: E402


class Checker:
    name = "GigaAM"
    ready = True

    def __init__(self, text=None, boom=False):
        self.text, self.boom, self.got = text, boom, []

    def transcribe(self, pcm):
        self.got.append(len(pcm))
        if self.boom:
            raise RuntimeError("сбой")
        return self.text


class Eng(engine_audio.AudioMixin):
    def __init__(self, checker, cfg=None):
        self.cfg = cfg or {}
        self.s = types.SimpleNamespace(get=lambda a, b=None: self.cfg.get(b))
        self.checker = checker
        self.player = types.SimpleNamespace(gain=1.0)
        self.check_q = queue.Queue()
        self.state = "speaking"
        self._now_saying = "Наши взаимоотношения с помощниками стали теплее, мы работаем вместе."
        self._said = collections.deque()
        self.stopped = []
        self.stop_utt, self._stop_sleep = False, False
        self.stopping = threading.Event()

    @property
    def gigaam(self):
        return self.checker

    def interrupt(self, reason, follow=True):
        self.stopped.append(reason)
        self.state = "idle"


pcm = b"\x00\x01" * 16000
# 1. эхо: точная модель слышит мой же ответ — договариваем
e = Eng(Checker("наши взаимоотношения с помощниками стали теплее"))
ok(e._stop_verify("перестань", pcm, time.monotonic()) is True and e.player.gain < 1.0 and e.check_q.qsize() == 1,
   "«перестань» от быстрого слуха — на проверку точной моделью, голос пока тише")
ok(e._stop_verify("перестань", pcm, time.monotonic()) is True and e.check_q.qsize() == 1, "второе «стоп» той же фразы ждёт ту же проверку")
kind, p, info = e.check_q.get()
e._stop_check(p, info)
ok(not e.stopped and e.player.gain == 1.0 and e.state == "speaking", "эхо моего голоса — ответ договаривается, голос снова в полную силу")
ok(not e.stop_utt and not e._stop_sleep, "и не засыпаю (виджет не уходит в трей)")
# 2. настоящее «стоп»
for said in ("перестань", "Стоп!", "хватит уже", "перестаньте, пожалуйста"):
    e = Eng(Checker(said))
    e._stop_verify("перестань", pcm, time.monotonic())
    e._stop_check(*e.check_q.get()[1:])
    ok(e.stopped == ["перестань"] and e.stop_utt and e._stop_sleep, f"человек сказал «{said}» — замолкаю, как раньше")
# 3. слово-стоп есть, но оно — в моей же фразе
e = Eng(Checker("хватит на всех"))
e._now_saying = "Пирогов хватит на всех."
e._stop_verify("хватит", pcm, time.monotonic())
e._stop_check(*e.check_q.get()[1:])
ok(not e.stopped and e.player.gain == 1.0, "«хватит» — из моей же фразы — не останавливаюсь")
# 4. проверять нечем / выключено — как раньше, сразу
ok(Eng(None)._stop_verify("стоп", pcm, 0) is False, "нет своего GigaAM — решает быстрый слух, как раньше")
nr = Checker("x"); nr.ready = False
ok(Eng(nr)._stop_verify("стоп", pcm, 0) is False, "GigaAM ещё грузится — как раньше")
ok(Eng(Checker("x"), cfg={"stop_check": False})._stop_verify("стоп", pcm, 0) is False, "audio.stop_check = false — как раньше")
# 5. точная модель упала — верим быстрому слуху
e = Eng(Checker(boom=True))
e._stop_verify("стоп", pcm, 0)
e._stop_check(*e.check_q.get()[1:])
ok(e.stopped == ["стоп"], "точная модель не ответила — останавливаюсь, как раньше")
# 6. ответ закончился, пока проверяли — ничего не делаем
e = Eng(Checker("стоп"))
e._stop_verify("стоп", pcm, 0)
e.state = "idle"
e._stop_check(*e.check_q.get()[1:])
ok(not e.stopped and e.player.gain == 1.0, "ответ уже кончился — не трогаем")
# 7. поток name-check принимает «stop»
e = Eng(Checker("наши взаимоотношения"))
e._check_voiceprint = lambda *a: False
e.wake_checker = lambda: e.checker
th = threading.Thread(target=e._check_worker, daemon=True); th.start()
e._stop_verify("достаточно", pcm, 0)
end = time.monotonic() + 2
while time.monotonic() < end and (e.check_q.qsize() or getattr(e, "_stop_checking", False)):
    time.sleep(0.01)
ok(e.checker.got and not e.stopped and not e._stop_checking, "поток проверки имени разбирает и проверку «стоп»")
e.stopping.set(); e.check_q.put(("stop", b"", ("x", 0)))
src = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok("self._stop_verify(w, b\"\".join(half_pcm), now)" in src, "полудуплекс: слово-стоп идёт через проверку")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
