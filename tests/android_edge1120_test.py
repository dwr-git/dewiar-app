"""Телефон под Android 15 (targetSdk 35, 20.11): нужен для Google Play и чтобы Android 16–17 не считал приложение «слишком
старым». С targetSdk 35 окно всегда «от края до края»: цвет панелей не красится, клавиатура окно не сжимает. Чтобы вёрстка
осталась прежней — корень окна получает отступы = вставки системы (строка состояния, жесты, вырез, клавиатура), фон
корня = цвет панелей (тема меняет и его). На Android 14 и ниже — ничего не меняется."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
A = ROOT / "android/src/pro/dewiar/app"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


build = (ROOT / "android/tools/build_apk.sh").read_text(encoding="utf-8")
ok("--target-sdk-version 35" in build, "сборка — под Android 15 (targetSdk 35)")
comp = (A / "Compat.java").read_text(encoding="utf-8")
m = re.search(r"public static void edgeInsets\(android\.view\.View root\) \{(.*?)\n    \}", comp, re.S)
body = m.group(1) if m else ""
ok("Build.VERSION.SDK_INT < 35" in body and "return;" in body, "до Android 15 — ничего не делаем")
ok("getSystemWindowInsetTop()" in body and "getSystemWindowInsetBottom()" in body and "l + in.getSystemWindowInsetLeft()" in body,
   "отступы = вставки системы (с клавиатурой) поверх своих отступов окна")
main = (A / "MainActivity.java").read_text(encoding="utf-8")
ok("setContentView(root);" in main and "root.addView(web" in main and "Compat.edgeInsets(root);" in main and "setContentView(web);" not in main,
   "главное окно: WebView внутри корня с отступами")
br = (A / "Bridge.java").read_text(encoding="utf-8")
ok("if (a.root != null) a.root.setBackgroundColor(c);" in br, "тема оформления красит и фон под панелями")
for f in ("HtmlView.java", "AlarmActivity.java"):
    ok("Compat.edgeInsets(root);" in (A / f).read_text(encoding="utf-8"), f"{f}: тоже с отступами под панели")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
