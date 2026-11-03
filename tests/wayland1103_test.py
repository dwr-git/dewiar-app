"""№442 (31.10, Ubuntu 24.04, монитор 4K): «шрифт нечёткий, пиксели размазаны». Виджет и студия ради «поверх всех» и
своего места работают через XWayland (ui.force_x11), а GNOME с дробным масштабом (scale-monitor-framebuffer) рисует
такие окна в масштабе 1 и растягивает картинкой. Теперь: Dewiar узнаёт этот случай (xwayland_blurry: настройки mutter
+ масштаб мониторов), один раз подсказывает, а студия → «Оформление» → «Чёткий текст на Wayland» (ui.wayland_sharp)
запускает окна прямо на Wayland — в масштабе экрана; перетаскивает тогда композитор (drag1103)."""
import os, sys
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

FEAT = "['scale-monitor-framebuffer']"
ok(app.blurry_from(FEAT, ["1.5"]) == 1.5, "дробный масштаб 150 % — окна XWayland растянуты (размыто)")
ok(app.blurry_from("['scale-monitor-framebuffer', 'xwayland-native-scaling']", ["1.5"]) == 0, "GNOME 47+ с родным масштабом XWayland — чётко")
ok(app.blurry_from("@as []", ["2"]) == 0, "без дробного масштаба (целый 200 %) GTK сам рисует ×2 — чётко")
ok(app.blurry_from(FEAT, ["1", "1.0"]) == 0, "масштаб 100 % — чётко")
ok(app.blurry_from(FEAT, ["1", "2"]) == 2, "второй монитор 200 % при дробном режиме — растянуто")
ok(app.blurry_from(FEAT, []) == 0, "масштаб не узнали — не тревожим")
GDBUS = ("(uint32 12, [(('DP-1', 'GSM', 'LG HDR 4K', '0x0001'), [('3840x2160@60.000', 3840, 2160, 60.0, 1.5, [1.0, 1.25, 1.5], "
         "{'is-current': <true>})], {})], [(0, 0, 1.5, uint32 0, true, [('DP-1', 'GSM', 'LG HDR 4K', '0x0001')], {})], {'layout-mode': <uint32 1>})")
ok(app.MUTTER_SCALE_RX.findall(GDBUS) == ["1.5"], f"масштаб логического монитора из ответа mutter: {app.MUTTER_SCALE_RX.findall(GDBUS)}")
ok(ST.DEFAULTS["ui"]["wayland_sharp"] is False and ST.DEFAULTS["ui"]["force_x11"] is True, "по умолчанию — как было: XWayland («поверх всех», место окна)")
os.environ.pop("WAYLAND_DISPLAY", None)
ok(app.xwayland_blurry() == 0, "не Wayland — проверка молчит")
src = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('uis.get("force_x11", True) and not uis.get("wayland_sharp")' in src, "«Чёткий текст на Wayland» — окна прямо на Wayland (без GDK_BACKEND=x11)")
ok("wayland_blur_hint(blur)" in src and "wayland-blur-told" in src, "размыто — один раз подсказываем, где включить чёткий текст")
st = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('data-k="ui.wayland_sharp"' in st and "Чёткий текст на Wayland" in st, "в «Оформлении» — переключатель с объяснением, чем платим")
ok('$("#lk-sharp").style.display = "none"' in (ROOT / "ui/studio/look.js").read_text(encoding="utf-8"), "на Windows переключателя нет")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
