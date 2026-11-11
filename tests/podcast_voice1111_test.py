"""Владелец 11.11, 23:01 («Подкасты»): «часть ответов Патрика — голосом Патрика, часть как будто другим движком — картавый,
быстрый», «"Да" в начале предложения звучит как "Тында", первые буквы съедаются».
1) Голос сервера бывал занят — реплика сразу уходила к запасному голосу (eSpeak/Piper). Теперь первый проход — только
   закреплённый голос выпуска; не вышло — реплика ждёт второго прохода тем же голосом, запасной — только потом.
2) ESpeech (F5-TTS) читает текст образца и фразу одной строкой: без «. » в конце образца первое слово фразы прилипало
   к последнему слову образца. Теперь образец всегда кончается точкой и пробелом (server/voices/app.py ref_tail)."""
import os, sys, threading
from pathlib import Path
import numpy as np
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import podcast as P  # noqa: E402
from tts import RemoteTTS  # noqa: E402


class Main(RemoteTTS):                                   # «голос сервера»: реплика 3 первые 3 раза — «занят»
    def __init__(self):
        self.name, self.cfg, self.calls, self.busy = "сервер", {}, [], {"Реплика 3.": 3}

    def synth(self, text, voice, speed=1.0):
        self.calls.append(text)
        if self.busy.get(text, 0) > 0:
            self.busy[text] -= 1
            raise RuntimeError("сервер голосов занят")
        yield 22050, (np.ones(4410, dtype=np.int16) * 3000).tobytes()


class Spare:
    name = "запасной"

    def __init__(self):
        self.calls = []

    def synth(self, text, voice, speed=1.0):
        self.calls.append(text)
        yield 22050, (np.ones(4410, dtype=np.int16) * 3000).tobytes()


main, spare = Main(), Spare()
pc = P.Podcasts.__new__(P.Podcasts)
pc.host = type("H", (), {"s": type("S", (), {"get": lambda self, a, b=None: {} if b is None else None})()})()
pc._voices = lambda m: {"a": {"_gender": "female"}, "b": {"_gender": "male"}}
pc._chain = lambda v: [main, spare]
pc._stage = lambda *a, **k: None
lines = [{"who": "a" if i % 2 == 0 else "b", "text": f"Реплика {i}."} for i in range(8)]
job = {"meta": {"hosts": {}, "usage": {"tts": 0}}, "cancel": threading.Event()}
import time  # noqa: E402
t0 = time.time()
out = pc._voice_all(job, lines)
ok(all(len(x) for x in out), "все реплики озвучены")
ok("Реплика 3." not in spare.calls and not spare.calls, f"запасной голос не понадобился — занятая реплика дождалась своего голоса: {spare.calls}")
ok(main.calls.count("Реплика 3.") == 4, f"занятую реплику повторили тем же голосом: {main.calls.count('Реплика 3.')} раза")
main.busy = {"Реплика 5.": 99}
spare.calls.clear()
out = pc._voice_all(job, lines)
ok(spare.calls == ["Реплика 5."] and all(len(x) for x in out), f"голос так и не смог — только эта реплика запасным, остальные своим: {spare.calls}")

sys.path.insert(0, str(ROOT / "server/voices"))
src = (ROOT / "server/voices/app.py").read_text(encoding="utf-8")
ns = {}
i = src.index("def ref_tail(")
exec(src[i:src.index("\ndef ", i + 10)], ns)
rt = ns["ref_tail"]
ok(rt("Привет, это Патрик") == "Привет, это Патрик. " and rt("Как дела?") == "Как дела? " and rt("Да.") == "Да. " and rt("") == "",
   "образец ESpeech кончается «. » — первое слово фразы не прилипает к образцу")
ok("ref_tail(self.accentize(e, text)" in src, "образец — через ref_tail")
if fails:
    sys.exit(1)
print("\n✅ всё в порядке")
