"""24.10, владелец: «быстрая кнопка на экране удобная, но может в нашем новом светлом стиле её сделать — Лира оформлена
красиво в белом». Значок «Записать» берёт тему приложения: светлая (pref look_body содержит « light ») — светлый
неоморфизм с чернильным мозгом; тёмная — прежний матово-чёрный. Сменили тему в приложении — значок обновляется сразу."""
import os, re
from pathlib import Path
from PIL import Image
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
A = ROOT / "android"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


dark = (A / "res/layout/widget_capture.xml").read_text(encoding="utf-8")
light = (A / "res/layout/widget_capture_light.xml").read_text(encoding="utf-8")
ids = lambda s: sorted(re.findall(r'android:id="@\+id/(\w+)"', s))
ok(ids(dark) == ids(light) == ["w_root", "w_sub"], f"у светлого значка те же w_root и w_sub (нажатие и подпись): {ids(light)}")
ok("@drawable/w_bg_light" in light and "@drawable/w_brain_ink" in light and "#FF24324A" in light, "светлый фон, чернильный мозг и текст")
ok("@drawable/w_bg\"" in dark and "@drawable/w_brain\"" in dark, "тёмный значок — как был")
bg = (A / "res/drawable/w_bg_light.xml").read_text(encoding="utf-8")
ok("layer-list" in bg and "#99B8C5D6" in bg and "#F2F7FBFF" in bg, "фон — неоморфизм «Небесного»: тень и блик слоями")
im = Image.open(A / "res/drawable-nodpi/w_brain_ink.png").convert("RGBA")
px = [p for p in (im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()) if p[3] > 0]
ok(im.size == (192, 192) and px and all(p[:3] == (0x24, 0x32, 0x4a) for p in px), "мозг перекрашен в чернила #24324a, форма из w_brain.png")
cw = (A / "src/pro/dewiar/app/CaptureWidget.java").read_text(encoding="utf-8")
ok('if ("theme".equals(w)) return light(c) ? "light" : "dark";' in cw and '"look_body"' in cw and '" light "' in cw,
   "вид «Как тема» — по теме приложения (светлый или тёмный)")
br = (A / "src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
ok(re.search(r'"look_body"\.equals\(key\) \|\| "widget_look"\.equals\(key\)\)\s*CaptureWidget\.refresh', br) is not None,
   "сменили тему или вид значка — значок обновился")

# 25.10, владелец: «светлая терпимо, но не круто… может стекло матовое… стильно и красиво» — «Стекло» по умолчанию
glass = (A / "res/layout/widget_capture_glass.xml").read_text(encoding="utf-8")
ok(ids(glass) == ["w_root", "w_sub"] and "@drawable/w_bg_glass" in glass and "@drawable/w_brain\"" in glass,
   "«Стекло»: те же w_root и w_sub, стеклянный фон, белый мозг")
ok(glass.count("android:shadowColor") == 2, "у белого текста — мягкая тень (читается и на светлых обоях)")
gb = (A / "res/drawable/w_bg_glass.xml").read_text(encoding="utf-8")
ok("layer-list" in gb and "#38101820" in gb and "<gradient" in gb and "<stroke" in gb and "#66FFFFFF" in gb,
   "стекло слоями: вуаль, белый градиент, светлая кромка")
ok('"light".equals(look) ? R.layout.widget_capture_light' in cw and ': R.layout.widget_capture_glass' in cw and '"widget_look"' in cw,
   "по умолчанию — «Стекло»; «Светлый» и «Тёмный» — по выбору (pref widget_look)")
ok('.put("look", look(c))' in cw, "приложение знает выбранный вид")
app = (A / "assets/www/app.js").read_text(encoding="utf-8")
ok('D.setPref("look_body", v)' in app and '(sk.light ? " light" : "")' in app, "app.js пишет тему в look_body")

if fails:
    raise SystemExit(1)
