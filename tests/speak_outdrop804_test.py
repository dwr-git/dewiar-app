"""Пакет 17.11, №804 (Windows): «за всё время пару раз дочитала до конца — обрывает в каком-то месте; „дочитывать до
конца“ включено». В журнале — ни одного перебивания: программа считала, что договорила. Так бывает, когда вывод звука
падает посреди фразы (сменилось устройство, драйвер, другая программа заняла звук): Player.write → False, и все
следующие фразы молча «проговаривались» в никуда. Теперь — запись в журнал, и следующая фраза открывает вывод заново."""
import logging, os, queue, sys, threading, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import engine as E  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


class TTS:
    name = "t"

    def synth(self, text, voice, speed=1.0):
        yield 16000, text.encode("utf-8").ljust(64, b"\x00")


class FlakyPlayer:
    """Вывод падает на второй фразе (как отключившееся устройство): write → False, пока вывод не открыли заново."""
    rate = 16000

    def __init__(self):
        self.starts, self.heard, self.dead, self.n = 0, [], False, 0

    def start(self, r):
        self.rate, self.starts, self.dead = r, self.starts + 1, False

    def write(self, b):
        self.n += 1
        if self.n == 2:
            self.dead = True
        if self.dead:
            return False
        self.heard.append(b.rstrip(b"\x00").decode("utf-8"))
        return True

    def finish(self):
        pass


class Grab(logging.Handler):
    def __init__(self):
        super().__init__(); self.lines = []

    def emit(self, r):
        self.lines.append(r.getMessage())


g = Grab(); logging.getLogger("dewiar").addHandler(g); logging.getLogger("dewiar").setLevel(logging.INFO)
pl = FlakyPlayer()
me = types.SimpleNamespace(s=types.SimpleNamespace(get=lambda *k: {"speed": 1.0}.get(k[-1])), _voice_cfg=lambda: {}, _output_muted=lambda: False,
                           _fx_name=lambda v: "off", player=pl, set_state=lambda s: None, _engines_for_speech=lambda v, *a: [TTS()],
                           _synth_mixed=lambda eng, text, voice, sp: eng.synth(text, voice, sp), _wait_vosk_tts=lambda v: None,
                           last_speak_end=0, vosk_tts=None, _said=[], null_player=True)
turn = types.SimpleNamespace(cancel=threading.Event(), spoken=[])
q = queue.Queue()
for s in ["Разбейте яйца.", "Посолите белок.", "Жарьте три минуты.", "Приятного аппетита!"]:
    q.put(s)
q.put(None)
E.Engine._speak_worker(me, turn, q)
ok(pl.heard[-2:] == ["Жарьте три минуты.", "Приятного аппетита!"], f"после сбоя вывода — дочитывает до конца: {pl.heard}")
ok(pl.starts == 2, f"вывод открыт заново один раз: {pl.starts}")
ok(any("Звук оборвался посреди фразы" in x for x in g.lines), "сбой вывода — в журнале (для отчёта)")

# перебили по-настоящему — заново не открываем и дальше не читаем
pl2 = FlakyPlayer(); me.player = pl2
turn2 = types.SimpleNamespace(cancel=threading.Event(), spoken=[])
q2 = queue.Queue()
for s in ["Раз.", "Два.", "Три."]:
    q2.put(s)
q2.put(None)
orig = pl2.write
def write_and_cancel(b):
    r = orig(b)
    if pl2.n == 2:
        turn2.cancel.set()
    return r
pl2.write = write_and_cancel
E.Engine._speak_worker(me, turn2, q2)
ok(pl2.starts == 1 and pl2.heard == ["Раз."], f"перебили — вывод не открывается заново: {pl2.heard}, открытий {pl2.starts}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
