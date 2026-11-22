"""Сейф на телефоне — отпечатком, лицом или PIN телефона (идея №224, 15 голосов: «мастер-пароль из 15 символов на каждом
входе на телефоне вводить невозможно»). Мастер-пароль — один раз; дальше сейф открывает экран блокировки телефона: ключ сейфа
(не пароль) хранит Android под защитой (SafeKey.java, AndroidKeyStore, 30 с после подтверждения). Предложение — после входа
паролем, отказ запоминается; выключить — строкой внизу. Ключ не подошёл (мастер-пароль сменили) или сменились отпечатки —
снова паролем, с понятной строкой. Пока на экране системное «подтвердите, что это вы», сейф не закрывается."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
STUB = """() => { window._bio = { state: "off", ct: null, opens: 0 };
  const ev = (o) => setTimeout(() => N.ev(JSON.stringify(Object.assign({ type: "safebio" }, o))), 0);
  D.safeBioState = () => _bio.state;
  D.safeBioSave = (k) => { _bio.ct = k; _bio.state = "on"; ev({ op: "save", ok: true }); };
  D.safeBioOpen = () => { _bio.opens++; ev(_bio.next || { op: "open", ok: true, key: _bio.ct }); _bio.next = null; };
  D.safeBioForget = () => { _bio.state = "off"; _bio.ct = null; }; }"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 393, "height": 852}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { delete D.safeBioState; }")
    pg.evaluate("openSafe()"); pg.wait_for_timeout(300)
    pg.fill("#sf-pw", "Длинный-мастер-15!"); pg.fill("#sf-pw2", "Длинный-мастер-15!"); pg.click("#sf-open")
    pg.wait_for_selector("#sf-q", timeout=20000)
    ok(not pg.is_visible(".sf-offer"), "веб-версия и старое приложение (моста нет) — предложения нет")
    pg.evaluate(STUB); pg.evaluate("safeRender()")
    ok(pg.is_visible(".sf-offer") and "Открывать отпечатком?" in pg.inner_text(".sf-offer"), "после входа паролем — «Открывать отпечатком?»")
    pg.click("#sf-bio-on"); pg.wait_for_timeout(200)
    ok(pg.evaluate("_bio.state") == "on" and pg.evaluate("_bio.ct === DC().b64e(SF.k)"), "«Включить» — телефону уходит ключ сейфа, не мастер-пароль")
    ok(not pg.is_visible(".sf-offer") and pg.is_visible("#sf-bio-off"), "включено — предложения нет, внизу «выключить»")
    pg.evaluate("safeLock()"); pg.wait_for_timeout(100)
    pg.evaluate("openSafe()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("_bio.opens") == 1 and pg.evaluate("safeOpen()") and pg.is_visible("#sf-q"), "сейф открывается сам — системным подтверждением, без мастер-пароля")
    pg.evaluate("safeLock()"); pg.evaluate("_bio.next = { op: 'open', ok: false, error: 'cancel' }; openSafe()"); pg.wait_for_timeout(300)
    ok(not pg.evaluate("safeOpen()") and pg.is_visible("#sf-bio") and pg.is_visible("#sf-pw") and not pg.is_visible("#sf-gate ~ .res.bad, .sf-gate > .res.bad"),
       "отменил подтверждение — кнопка «Открыть отпечатком» и поле пароля, без ошибки")
    pg.click("#sf-bio"); pg.wait_for_timeout(300)
    ok(pg.evaluate("safeOpen()"), "кнопка «Открыть отпечатком» — открывает")
    pg.evaluate("SF.bio = true; Object.defineProperty(document, 'hidden', { configurable: true, get: () => true }); document.dispatchEvent(new Event('visibilitychange'))")
    ok(pg.evaluate("safeOpen()"), "системное «подтвердите, что это вы» поверх приложения — сейф не закрывается")
    pg.evaluate("SF.bio = false; document.dispatchEvent(new Event('visibilitychange'))")
    ok(not pg.evaluate("safeOpen()"), "а настоящее сворачивание — закрывает, как раньше")
    pg.evaluate("Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })")
    pg.evaluate("_bio.ct = DC().b64e(DC().randomBytes(32)); openSafe()"); pg.wait_for_timeout(300)
    ok(not pg.evaluate("safeOpen()") and pg.evaluate("_bio.state") == "off" and "Мастер-пароль сейфа сменился" in pg.inner_text("#safe-body"),
       "ключ не подошёл (мастер-пароль сменили) — снова паролем, вход отпечатком сброшен, сказано почему")
    pg.evaluate("SF.bioMsg = ''; _bio.state = 'on'; _bio.ct = 'x'; _bio.next = { op: 'open', ok: false, error: 'changed' }; safeLock(); openSafe()"); pg.wait_for_timeout(300)
    ok("Отпечатки или блокировка экрана сменились" in pg.inner_text("#safe-body"), "сменились отпечатки или блокировка — понятная строка")
    pg.evaluate("SF.bioMsg = ''; _bio.state = 'off'; safeRender()")
    pg.fill("#sf-pw", "Длинный-мастер-15!"); pg.click("#sf-open"); pg.wait_for_selector("#sf-q", timeout=20000)
    pg.click("#sf-bio-no"); pg.wait_for_timeout(100)
    ok(not pg.is_visible(".sf-offer") and pg.evaluate("prefGet('safe_bio_no')") == "1", "«Не сейчас» — предложение больше не показывается")
    if os.environ.get("SAFE_SHOTS"):
        pg.evaluate("prefSet('safe_bio_no', ''); safeRender()"); pg.screenshot(path=os.environ["SAFE_SHOTS"] + "/safebio-offer.png")
        pg.evaluate("_bio.state = 'on'; safeLock(); _bio.next = { op: 'open', ok: false, error: 'cancel' }; openSafe()"); pg.wait_for_timeout(300)
        pg.screenshot(path=os.environ["SAFE_SHOTS"] + "/safebio-gate.png")
    ok(not errs, f"без ошибок JavaScript {errs[:3]}")
    b.close()
shutil.rmtree(tmp, ignore_errors=True)
J = (ROOT / "android/src/pro/dewiar/app/SafeKey.java").read_text(encoding="utf-8")
ok("setUserAuthenticationRequired(true)" in J and "AndroidKeyStore" in J and "createConfirmDeviceCredentialIntent" in J and "KeyPermanentlyInvalidatedException" in J,
   "Android: ключ в хранилище ключей, только после подтверждения себя; сменились отпечатки — ключ негоден")
M = (ROOT / "android/src/pro/dewiar/app/MainActivity.java").read_text(encoding="utf-8")
Br = (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8")
ok("SafeKey.onResult(this, res == RESULT_OK)" in M and all(f"public {t} {n}(" in Br for t, n in (("String", "safeBioState"), ("void", "safeBioSave"), ("void", "safeBioOpen"), ("void", "safeBioForget"))),
   "мост: состояние, включить, открыть, забыть; ответ системного экрана — в SafeKey")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
