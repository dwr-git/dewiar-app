"""№1128 (26.11, realme, Android 16, приложение 0.9.95): «После запуска первое сообщение голосом уходит нормально, а на втором
сразу ошибка „Распознавание речи этого устройства не отвечает“». По журналу: после ответа Лиры голосом распознаватель телефона
на следующий startListening молчит — ни «готов», ни ошибки (сторож 4 с: «нет ответа (start, system)»); после перезапуска
приложения — снова одна фраза. Распознаватель один на всё время работы (так меньше ошибок 11), и зависший так и оставался.
Теперь: прежний сеанс не дождался «готов» — Speech.java берёт новый распознаватель; приложение при таком молчании сразу,
один раз, слушает заново (человек ничего не замечает), и только второй подряд — прежний совет."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


j = (ROOT / "android/src/pro/dewiar/app/Speech.java").read_text(encoding="utf-8")
ok("if (rec != null && (renew || noReady))" in j, "прежний сеанс не дождался «готов» — новый распознаватель")
ok("noReady = true;" in j and "ready[0] = true; noReady = false;" in j, "«готов» пришёл — распознаватель жив, оставляем один на всё время")
ok(j.count("noReady = false;") >= 3, "ошибка или результат — тоже знак, что жив (ошибка 11 по-прежнему не на каждой фразе)")
for name in ("android/www-src/app/06-ears-voice.js", "android/assets/www/app.js"):
    js = (ROOT / name).read_text(encoding="utf-8")
    ok('if (!sttStartAgain) { sttStartAgain = true;' in js and "return listen(); }" in js and "sttRetry = 0; sttStartAgain = false;" in js,
       f"{name}: молчит на старте — один раз сразу заново, ожил — счётчик сброшен")
    i = js.index("if (!sttStartAgain)")
    ok(i < js.index("Распознавание речи этого устройства не отвечает", i), f"{name}: совет «войдите аккаунтом» — только после второй попытки")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
