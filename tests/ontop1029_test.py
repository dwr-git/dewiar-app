"""Идея №48 (29.10): «Добавить настройку: включить/выключить окошко с Лирой всегда сверху». Студия → «Оформление» →
«Виджет поверх всех окон» (ui.on_top, по умолчанию — да); виджет при смене зовёт api.set_on_top — окно сразу становится
обычным (или снова поверх), сторож «поверх окон» на Linux его больше не поднимает; при запуске окно создаётся как выбрано."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "ui")); sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import app  # noqa: E402
import settings as ST  # noqa: E402
ok(ST.DEFAULTS["ui"]["on_top"] is True, "по умолчанию — поверх всех окон, как было")
a = app.Api.__new__(app.Api)
w1, w2 = types.SimpleNamespace(on_top=True), types.SimpleNamespace(on_top=True)
a.wins = {"card": w1, "x": w2}
ok(a.set_on_top(False) is False and not w1.on_top and not w2.on_top and app.ON_TOP[0] is False, "выключили — окно сразу обычное")
ok(a.set_on_top(True) and w1.on_top and app.ON_TOP[0], "включили — снова поверх")
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok(src.count('on_top=ON_TOP[0], hidden=True, background_color="#0b0b0e", js_api=api') == 2, "при запуске виджет создаётся как выбрано (Linux и Windows)")
ok("if not ON_TOP[0] and gw.get_title() != PAD_TITLE:" in src, "сторож «поверх окон» не поднимает виджет, если выключено")
ok(src.index('ON_TOP[0] = ui_settings().get("on_top", True) is not False') < src.index("return main_win(args, extra)"), "настройка читается до выбора системы")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("const top = ui.on_top !== false;" in hud and "a.set_on_top(top)" in hud, "виджет зовёт set_on_top при смене настройки")
ok('data-k="ui.on_top"' in (ROOT / "ui/settings.html").read_text(encoding="utf-8"), "в «Оформлении» — переключатель")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
