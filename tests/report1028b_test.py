"""Пакет 28.10, 12:06:
- №377: «можно, чтобы Лира и все персонажи читали вслух полностью и до конца весь ответ? Сейчас — „Дальше не читаю вслух —
  всё на экране“». Студия → «Голос» → «Читать длинные ответы вслух целиком» (tts.read_all); «прочитай целиком / полностью /
  до конца» — тоже целиком; в первый раз фраза об обрыве подсказывает, где включить.
- владелец: «на Windows виджет с прямыми углами, нет скруглений» — форма окна (регион) проверяется раз в 3 с и ставится
  заново, если слетела (winshell.has_shape), с записью в ui.log."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from settings import DEFAULTS  # noqa: E402
ok(DEFAULTS["tts"]["read_all"] is False, "по умолчанию — около минуты вслух, как раньше")
src = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
m = re.search(r'voice_cap = 10 \*\* 9 if \(self\.s\.get\("tts", "read_all"\) or re\.search\(r"([^"]+)"', src)
ok(bool(m), "предел снимается настройкой tts.read_all")
rx = re.compile(m.group(1)) if m else re.compile("$^")
ok(all(rx.search(t) for t in ("прочитай целиком", "расскажи полностью", "дочитай до конца")) and not rx.search("какая погода"),
   "«целиком», «полностью», «до конца» — читается до конца")
ok("Читать целиком — студия, «Голос»." in src and "self._cap_said = True" in src, "первый обрыв — подсказка, где включить")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('data-k="tts.read_all"' in html and "Читать длинные ответы вслух целиком" in html, "студия → «Голос»: переключатель")
ws = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("def has_shape(h):" in ws and "GetWindowRgn" in ws, "Windows: есть ли у окна форма")
ok("self._win_shape_keeper()" in app and "not winshell.has_shape(h)" in app and "форма окна слетела" in app,
   "виджет: форма проверяется и ставится заново, в ui.log — запись")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
