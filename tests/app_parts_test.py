"""Телефон по частям (чистое ядро, 1.0.18): исходник интерфейса — android/www-src/app/NN-имя.js, android/assets/www/app.js
собран из них склейкой (tools/app_join.py) — тем же одним файлом, поэтому у людей ничего не меняется. Проверка следит,
чтобы app.js не правили мимо частей, у каждой части была шапка «что в ней», части резались по разделам «/* ---------- …»,
а сами части не попадали в приложение и веб-версию (там нужен только собранный app.js)."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


sys.path.insert(0, str(ROOT / "tools"))
import app_join  # noqa: E402
parts = app_join.parts()
ok(len(parts) >= 10 and [p.name[:2] for p in parts] == [f"{i:02d}" for i in range(1, len(parts) + 1)],
   f"части по порядку 01…{len(parts):02d}")
app = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok(app == app_join.joined(), "app.js = склейка частей (правка мимо частей — python3 tools/app_join.py)")
ok(app.startswith(app_join.HEAD), "в начале app.js — пометка «собран из частей»")
for p in parts:
    t = p.read_text(encoding="utf-8")
    ok(t.startswith("//@ Телефон и веб-версия, часть " + p.name[:2] + ":"), f"{p.name}: шапка — что в части")
    b = app_join.body(t)
    if p.name[:2] != "01":
        ok(b.startswith("/* ---------- "), f"{p.name}: начинается с раздела «/* ---------- …»")
    ok(b.endswith("\n") and "//@" not in b.splitlines()[0], f"{p.name}: шапка не попадает в app.js")
ok(re.search(r'<script src="app\.js"></script>', (ROOT / "android/assets/www/index.html").read_text(encoding="utf-8")) is not None,
   "index.html подключает один app.js, как раньше")
w = Path(tempfile.mkdtemp())
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(w)], check=True, capture_output=True)
ok((w / "app.js").read_text(encoding="utf-8") == app and not any(w.rglob("[0-9][0-9]-*.js")),
   "в приложение и веб-версию — собранный app.js, частей там нет")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
