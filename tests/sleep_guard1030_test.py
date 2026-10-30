"""Компьютер не засыпает из-за Dewiar (идея №70, 29.10: «Windows 11 не уходит в сон — powercfg /requests: сон держит
аудиопоток микрофона, открытый pythonw.exe»). Теперь в Windows микрофон отпускается, когда компьютер и так вот-вот уснёт
(мышь и клавиатура не трогались почти столько, сколько стоит «Сон», голоса не было, ассистент не занят), и снова
открывается, как только тронут мышь. «Сон: никогда» — ничего не меняется."""
import os, sys, types, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import sleepguard as SG  # noqa: E402

EN = """Power Setting GUID: 29f6c1db-86da-48c5-9fdb-f2b67b1f44da  (Sleep after)
    Minimum Possible Setting: 0x00000000
    Maximum Possible Setting: 0xffffffff
    Possible Settings increment: 0x00000001
    Possible Settings units: Seconds
  Current AC Power Setting Index: 0x00000708
  Current DC Power Setting Index: 0x00000384
"""
RU = """GUID параметра питания: 29f6c1db-86da-48c5-9fdb-f2b67b1f44da  (Переход в спящий режим через)
    Минимальное значение параметра: 0x00000000
    Максимальное значение параметра: 0xffffffff
  Текущий индекс параметра питания от сети: 0x00000000
  Текущий индекс параметра питания от батареи: 0x00000258
"""
ok(SG.parse_standby(EN, True) == 1800 and SG.parse_standby(EN, False) == 900, "английский powercfg: от сети 30 мин, от батареи 15")
ok(SG.parse_standby(RU, True) == 0 and SG.parse_standby(RU, False) == 600, "русский powercfg: от сети «никогда», от батареи 10 мин")
ok(SG.parse_standby("", True) == 0, "не прочитали — считаем «никогда» (микрофон не трогаем)")
ok(SG.release_due(1750, 1800, 1800, False), "до сна меньше минуты, голоса не было — отпустить")
ok(not SG.release_due(1000, 1800, 1800, False), "до сна ещё далеко — держать")
ok(not SG.release_due(1750, 1800, 30, False), "только что говорили с Лирой — держать")
ok(not SG.release_due(1750, 1800, 1800, True), "ассистент занят (разговор, будильник, радио) — держать")
ok(not SG.release_due(99999, 0, 99999, False), "«Сон: никогда» — держать всегда")
ok(not SG.release_due(None, 1800, 1800, False), "не Windows — ничего не меняется")

from engine_audio import AudioMixin  # noqa: E402

SG.idle_seconds, SG.standby_seconds = (lambda: 1790.0), (lambda: 1800)
S = types.SimpleNamespace(get=lambda *k: None)
eng = types.SimpleNamespace(s=S, turn=None, state="idle", alarm=None, hold=None, radio=types.SimpleNamespace(playing=False),
                            prompter=types.SimpleNamespace(on=False), meeting=None, mic_voice_t=time.monotonic() - 3600)
ok(AudioMixin._sleep_due(eng), "ядро: тихо и пора — микрофон отпускается")
eng.radio.playing = True
ok(not AudioMixin._sleep_due(eng), "ядро: играет радио — не отпускать")
eng.radio.playing = False
eng.s = types.SimpleNamespace(get=lambda *k: False if k == ("audio", "let_sleep") else None)
ok(not AudioMixin._sleep_due(eng), "ядро: настройка выключена — не отпускать")
src = (ROOT / "core/engine_audio.py").read_text()
ok("self._mic_asleep = True" in src and "idle_seconds()" in src and "Снова слушаю микрофон" in src, "аудиопоток: отпустил — ждёт мышь и открывает снова")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
