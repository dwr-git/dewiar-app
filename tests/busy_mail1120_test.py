"""Владелец 20.11, снимок виджета: «Занят: mail_inbox — 37 с». «Почта» на «Главной» студии тянула письма целиком (с
вложениями) с медленного сервера, а виджет писал «Занят» английским именем команды. Теперь: фоновое чтение почты виджет
«занятостью» не считает (пул большой, никого не держит), имя — по-русски, а для списка писем берётся только начало письма."""
import os, re, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import bridge  # noqa: E402
b = bridge.Bridge.__new__(bridge.Bridge)
b.inflight = {object(): ("mail_inbox", time.monotonic() - 40)}
r = b.busy()
ok(r["oldest"] == 0 and r["cmd"] == "", f"долгая «Почта» на «Главной» — виджет не «Занят»: {r}")
b.inflight[object()] = ("llm_test", time.monotonic() - 30)
r = b.busy()
ok(r["cmd"] == "llm_test" and r["oldest"] >= 29, f"остальное долгое — как раньше: {r}")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('mail_inbox: "проверяет почту"' in hud, "имя команды в виджете — по-русски")
mail = (ROOT / "core/mail.py").read_text(encoding="utf-8")
ok("BODY.PEEK[]<0.{INBOX_PEEK}>" in mail and re.search(r"^INBOX_PEEK = \d+", mail, re.M), "список писем — только начало письма, не вложения целиком")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
