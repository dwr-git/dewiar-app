"""Окно напоминания — над своими окнами (25.10, владелец: «включил компьютер… звук „Пропущено напоминание“ играл и играл,
а окошко пряталось под виджетом Лиры и под текстовым редактором — я его не видел»). Пока напоминание открыто, оно
каждые 1,5 с поднимается наверх без кражи фокуса (Linux — keep_above + raise, Windows — HWND_TOPMOST и SWP_NOACTIVATE);
закрыли или пришло новое — подъёмы прекращаются."""
import os, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ws = (ROOT / "ui/winshell.py").read_text(encoding="utf-8")
ok(src.count("self._alarm_keep_top(win)") == 2, "после показа окна напоминания (Windows и Linux) — держать наверху")
ok("gw.set_keep_above(True)" in src and "gw.get_window().raise_()" in src and "present()" not in src.split("def _alarm_keep_top")[1].split("def close_alarm")[0],
   "Linux: поднимаем без present() — фокус не крадём")
ok("def raise_top(h):" in ws and "SWP_NOMOVE | SWP_NOACTIVATE" in ws and "HWND(-1)" in ws, "Windows: HWND_TOPMOST без активации")
import app  # noqa: E402
a = app.Api.__new__(app.Api)
calls = []
a._gtk = lambda fn, timeout=2: calls.append(time.time()) or True
app.WIN = False
win = object()
a._alarm = win
app.Api._alarm_keep_top(a, win)
time.sleep(3.4)
n = len(calls)
ok(n >= 2, f"пока открыто — поднимается снова и снова: {n} раз за 3,4 с")
a._alarm = None
time.sleep(1.8)
ok(len(calls) - n <= 1, f"закрыли — больше не трогаем: ещё {len(calls) - n}")
a._alarm = win
app.Api._alarm_keep_top(a, win)
time.sleep(0.3)
a._alarm = object()                                       # пришло новое напоминание — у старого цикла свой конец
m = len(calls); time.sleep(1.8)
ok(len(calls) - m <= 1, "новое напоминание заменило старое — старый цикл остановился")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
