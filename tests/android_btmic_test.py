"""Телефон: микрофон Bluetooth-наушников (отчёт №51, 14.10: «Лиру слышу в наушниках, а она меня — нет; отошёл на 4 шага —
совсем не слышит»). Android по умолчанию пишет встроенным микрофоном телефона; BtMic.java включает голосовой канал
гарнитуры (SCO) на время слушания:
— Speech.java: и системное распознавание, и запись для сервера сначала включают микрофон наушников (btUp), после —
  выключают с задержкой (stopSoon); запись для сервера при наушниках — источник «связь» (VOICE_COMMUNICATION);
— Tts.java: перед ответом голосом канал гарнитуры выключается — ответ звучит в обычном качестве;
— Android 12+ — setCommunicationDevice через отражение (собираемся против API 23), раньше — startBluetoothSco;
— интерфейс: настройка «Микрофон Bluetooth-наушников» (по умолчанию включена) передаётся в Speech (D.btMic);
  «Сейчас подключены» — если гарнитура есть; не включился — в журнал и одна подсказка."""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


J = ROOT / "android/src/pro/dewiar/app"
sp, bt, tts, br = ((J / f).read_text(encoding="utf-8") for f in ("Speech.java", "BtMic.java", "Tts.java", "Bridge.java"))
ok(sp.count("btUp(g)") >= 3 and "VOICE_COMMUNICATION" in sp and sp.count("BtMic.stopSoon()") >= 4,
   "Speech: оба пути слушания включают микрофон наушников и выключают его после")
ok("setCommunicationDevice" in bt and "startBluetoothSco" in bt and "TYPE_BLUETOOTH_SCO" in bt and "getMethod(" in bt,
   "BtMic: Android 12+ — setCommunicationDevice (отражением), раньше — startBluetoothSco")
ok(tts.count("BtMic.offNow(ctx)") == 3, "Tts: перед ответом голосом — канал гарнитуры выключается (все пути: голос устройства, фраза на другом языке, голос сервера)")
ok("public void btMic(boolean on)" in br and "btMicAvailable" in br, "Bridge: настройка и проверка наушников")
ok('android.permission.BLUETOOTH" android:maxSdkVersion="30"' in (ROOT / "android/AndroidManifest.xml").read_text(), "манифест: BLUETOOTH для старых Android")

tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
shutil.copy(ROOT / "ui/assets/entities.js", www / "entities.js")
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(800)
    R = pg.evaluate("""() => { window.__bt = []; D.btMic = (on) => window.__bt.push(on); D.btMicAvailable = () => true;
        btMicSync(); openSettings('voice');
        const box = document.getElementById('bt-mic'), row = box.closest('.sw').textContent;
        const r = { first: window.__bt.slice(), checked: box.checked, row };
        box.checked = false; box.onchange();
        r.after = window.__bt.slice(); r.saved = S.btMic;
        N.ev({ type: 'stt_bt', on: false }); N.ev({ type: 'stt_bt', on: false });
        r.toasts = [...document.querySelectorAll('.toast, #toast')].map(x => x.textContent).join(' | ');
        return r; }""")
    pg.wait_for_timeout(300)
    b.close()
ok(R["first"] == [True] and R["checked"], f"по умолчанию — слушать наушниками: {R['first']}")
ok("Микрофон Bluetooth-наушников" in R["row"] and "Сейчас подключены" in R["row"], f"настройка в «Слух и голос» и что наушники подключены: {R['row'][:120]}")
ok(R["after"][-1] is False and R["saved"] is False, "выключили — передано в Speech и сохранено")
ok("Микрофон наушников не включился" in R["toasts"], f"не включился — подсказка: {R['toasts'][:120]}")
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
