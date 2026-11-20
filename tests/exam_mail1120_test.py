"""Экзамен 20.11, Б12: «Подготовь поздравление… отправь — Сергею Петрову, почта sp@…»: почта не подключена, модель писала
через «Близкие», получала «не нашла» — и не давала даже текста. Теперь ответ инструмента подсказывает: письмом (если
почта есть) или одной фразой «почта не подключена» и готовый текст целиком."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from close import CloseError  # noqa: E402
from tools_base import ToolError  # noqa: E402
import tools_people as TP  # noqa: E402

bad = 0
def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


class Close:
    def send(self, to, text, files):
        raise CloseError(f"Не нашла «{to}» среди близких (сейчас: пока никого). Добавить — студия → «Близкие» → «Пригласить».")


class Mail:
    def __init__(self, on): self.on = on
    def configured(self): return self.on


def err(ctx):
    try:
        TP.t_close_send({"to": "Сергей Петров", "text": "С юбилеем!"}, ctx)
    except ToolError as e:
        return str(e)
    return ""

e = err({"close": Close(), "mail": Mail(False)})
ok("Почта не подключена" in e and "готовый текст целиком" in e, "почты нет — сказать и отдать текст целиком")
e = err({"close": Close(), "mail": Mail(True)})
ok("send_email" in e and "не подключена" not in e, "почта есть — отправить письмом")
e = err({"close": Close()})
ok("готовый текст" in e, "почты нет вовсе — то же")
print("ALL OK" if not bad else f"FAILED {bad}")
sys.exit(1 if bad else 0)
