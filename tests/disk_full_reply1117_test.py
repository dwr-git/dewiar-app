"""Отчёт №844 (17.11, Windows): на диске 56 МБ — виджет показал «Ошибка в виджете: [Errno 28] No space left on device» и
кнопку «Отправить отчёт разработчику». Теперь ответ ядра на команду, упавшую от заполненного диска, — понятная фраза
(«Диск заполнен… освободите хотя бы 1 ГБ»), и виджет не предлагает слать отчёт: место освобождает сам человек.
Ошибка Windows «os error 112» (диск полон) тоже узнаётся. Настоящий core/bridge.py (_reply) и engine_base."""
import asyncio, json, os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import bridge as B  # noqa: E402
import engine_base as EB  # noqa: E402

ok(EB.disk_full(OSError(28, "No space left on device")), "ENOSPC — диск полон")
ok(EB.disk_full(RuntimeError("I/O error: IO Error: Недостаточно места на диске. (os error 112)")), "Windows «os error 112» — тоже")
ok(not EB.disk_full(RuntimeError("нет связи")), "прочие ошибки — нет")
br = B.Bridge.__new__(B.Bridge)


async def boom(cmd, args):
    raise OSError(28, "No space left on device")


class WS:
    sent = []

    async def send(self, t):
        self.sent.append(json.loads(t))


br._call = boom
ws = WS()
asyncio.run(br._reply(ws, {"id": 7, "cmd": "say", "args": {}}))
r = ws.sent[-1]
ok(r["ok"] is False and r["error"].startswith("Диск заполнен") and "1 ГБ" in r["error"] and "Errno" not in r["error"],
   f"ответ на команду — понятная фраза: {r['error'][:90]}")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("if (/^Диск заполнен/.test(msg)) return;" in hud, "виджет при заполненном диске не зовёт слать отчёт разработчику")
print("\nИТОГ: " + ("всё прошло" if not fails else f"не прошло {len(fails)}"))
sys.exit(1 if fails else 0)
