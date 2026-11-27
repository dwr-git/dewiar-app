"""№1056 (25.11, телефон): «Лира не правильно ориентируется в днях недели: говорит, что началась среда, и тут же — что
сегодня четверг». В сводке дня было «Сегодня 25.11.2026, среда», а в памяти — «викторины по четвергам»; какой день
завтра, модель считала сама и сбилась. Теперь завтрашний день недели называем в подсказке прямо — и на телефоне, и на компьютере."""
import os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
src = app[app.index("function welcomePrompt(p)"):]
src = src[:src.index("\n}\n") + 3]
js = src + """
const pad = (n) => String(n).padStart(2, "0");
const RealDate = Date;
globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [2026, 10, 25, 9, 26])); } };
console.log(welcomePrompt({ kind: "day", facts: ["Напоминание: викторина по четвергам"], gone: "12 ч" }).split("\\n")[0]);
const D2 = globalThis.Date; globalThis.Date = class extends RealDate { constructor(...a) { super(...(a.length ? a : [2026, 10, 28, 9, 0])); } };
console.log(welcomePrompt({ kind: "day", facts: [], gone: "9 ч" }).split("\\n")[0]);
"""
out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=30)
lines = out.stdout.strip().splitlines()
ok(len(lines) == 2 and "среда (завтра — четверг)" in lines[0], f"телефон, среда: {lines[:1]} {out.stderr[-300:]}")
ok(len(lines) == 2 and "суббота (завтра — воскресенье)" in lines[1], f"телефон, суббота → воскресенье: {lines[1:]}")
pc = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok("(завтра — {morning.WD[(now.weekday() + 1) % 7]})" in pc, "компьютер: утренняя сводка тоже называет завтра")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
