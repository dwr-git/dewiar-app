"""№994 (24.11, Android 14, и в чате людей — у нескольких): «Не проверилось: unexpected end of stream on null» при проверке
обновления и «не удалось отправить отчёт» — сервер закрыл соединение, не ответив (старое «живое» соединение или обрыв по
пути). Теперь Net.request один раз повторяет запрос новым соединением — только если ответ ещё не начал приходить и запрос
не отменён."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


j = (ROOT / "android/src/pro/dewiar/app/Net.java").read_text(encoding="utf-8")
ok('m.contains("unexpected end of stream")' in j and 'c.setRequestProperty("Connection", "close")' in j, "обрыв без ответа — второй раз новым соединением")
ok("attempt == 0 && !got && RUNNING.containsKey(id)" in j, "повтор — один, до начала ответа и не после отмены")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
