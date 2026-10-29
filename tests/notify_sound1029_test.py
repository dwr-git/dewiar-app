"""Свой звук и знак в уведомлениях телефона (владелец 29.10: «синий значок Dewiar — сделать в стиле лого»; «у Viber свой
звук — можем и мы свой: пришла новость, пуш»). Сообщения, новости и близкие — канал dw_note с фирменным звуком
res/raw/dewiar_note.ogg (короткий, до 1,5 с), прежний канал info удаляется (звук канала Android меняет только новым id);
до Android 8 — звук у самого уведомления. Новости и «Dewiar на связи» — с крупным знаком Dewiar (маленький значок система
красит сама), цвет знака — почти чёрный (Compat.BRAND)."""
import os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ogg = ROOT / "android/res/raw/dewiar_note.ogg"
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(ogg)], capture_output=True, text=True).stdout or 0)
ok(ogg.exists() and 0.4 < dur < 1.5, f"фирменный звук есть и короткий: {dur:.2f} с")
cp = (ROOT / "android/src/pro/dewiar/app/Compat.java").read_text(encoding="utf-8")
ok('CH_INFO = "dw_note"' in cp and 'invoke(b, note(c), aa)' in cp and "CH_OLD_INFO" in cp and "deleteNotificationChannel" in cp,
   "канал dw_note со своим звуком, старый info удаляется")
ok('"/raw/dewiar_note"' in cp and "USAGE_NOTIFICATION" in cp, "звук — по имени ресурса, как уведомление (не будильник)")
ok("b.setSound(note(c))" in cp and "0xFF111111" in cp, "до Android 8 — звук у уведомления; знак — почти чёрный")
cl = (ROOT / "android/src/pro/dewiar/app/CloseLive.java").read_text(encoding="utf-8")
ok(cl.count("Compat.logo(this)") >= 2, "новости и «Dewiar на связи» — с крупным знаком Dewiar")
gen = (ROOT / "tools/sounds/notify_sound.py").read_text(encoding="utf-8") + (ROOT / "tools/sounds/signature.py").read_text(encoding="utf-8")
ok('"kalimba"' in gen and "1568.0" in gen and "2349.3" in gen, "звук — «Калимба» (выбор владельца), собирается из исходника (tools/sounds)")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
