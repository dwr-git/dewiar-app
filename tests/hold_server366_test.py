"""№366 (20.11): голосовое удержанием кнопки на телефоне (слушает сервер) обрывалось на 15-й секунде и пропадало целиком:
сторож «нет событий 15 с» не считал событиями уровень громкости своей записи (частичного текста у неё нет) — отменял запись
посреди удержания. Теперь уровень своей записи заводит сторожа заново: держите сколько нужно (до 2 минут), отпустили — ушло."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


www = Path(tempfile.mkdtemp()) / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for f in ("entities.js", "skins.css", "skins.js", "privacy.js"):
    shutil.copy(ROOT / "ui/assets" / f, www / f)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 393, "height": 820}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("https://**", lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    pg.evaluate("""() => { window._asked = []; ask = (t, o) => { _asked.push([t, !!(o && o.voice)]); setState('idle'); };
      window._cancel = 0; window._rec = 0; D.recognizer = () => false; needPerm = async () => true;
      D.listenServerHold = () => { _rec++; }; D.listenServer = () => { _rec++; }; D.cancelListen = () => { _cancel++; };
      S.stt = { engine: 'server', url: 'http://x/v1', key: '' }; }""")
    pg.evaluate("async () => { holdTalk = true; await listen(); N.ev({ type: 'stt_start', g: sttGen }); "
                "window._lv = setInterval(() => N.ev({ type: 'stt_level', g: sttGen, v: 0.3 }), 400); }")
    pg.wait_for_timeout(17500)                           # дольше сторожа (15 с): держат кнопку и говорят
    r = pg.evaluate("[_cancel, _rec, sttActive]")
    ok(r == [0, 1, True], f"17 с удержания: запись не отменена и не перезапущена ({r})")
    pg.evaluate("() => { clearInterval(_lv); holdTalk = false; N.ev({ type: 'stt_end', g: sttGen }); "
                "N.ev({ type: 'stt_result', g: sttGen, text: 'длинное голосовое на семнадцать секунд', cut: false }); }")
    pg.wait_for_timeout(300)
    a = pg.evaluate("_asked.slice()")
    ok(a == [["длинное голосовое на семнадцать секунд", True]], f"отпустили — ушло целиком, голосом: {a}")
    # своя запись замолчала совсем (ни уровня, ни конца) — сторож по-прежнему не даёт кнопке залипнуть
    pg.evaluate("async () => { _cancel = 0; holdTalk = false; await listen(); N.ev({ type: 'stt_start', g: sttGen }); }")
    pg.wait_for_timeout(15800)
    ok(pg.evaluate("[_cancel, sttActive]") == [1, False], "запись замолчала совсем — через 15 с сами заканчиваем, как раньше")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
