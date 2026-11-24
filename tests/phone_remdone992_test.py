"""№992 (24.11): «отметил напоминание выполненным на компьютере, а телефон всё равно напоминает — пока не откроешь Dewiar».
Фоновая проверка напоминаний с других устройств (RemWatch) — раз в 15 минут и реже, а сигнал звонит раньше. Теперь перед
самим сигналом — быстрый вопрос облаку (до 3 с): сняли на другом устройстве — не звоним; нет сети — звоним, как раньше."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


rw = (ROOT / "android/src/pro/dewiar/app/RemWatch.java").read_text(encoding="utf-8")
ar = (ROOT / "android/src/pro/dewiar/app/AlarmReceiver.java").read_text(encoding="utf-8")
ok("static boolean cancelledElsewhere(" in rw and "check(c, 2000, 2500)" in rw and "t.join(3000)" in rw,
   "перед сигналом — проверка облака не дольше 3 с")
ok("RemWatch.cancelledElsewhere(c, id)" in ar and ar.index("RemWatch.cancelledElsewhere") < ar.index("Alarms.fired(c, id)"),
   "снятое на компьютере — не звонит")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
