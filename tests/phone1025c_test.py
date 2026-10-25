"""Телефон, пакет здоровья 25.10:
— №254 «как удалять однажды добавленные, но неработающие мозги? В списке только „Вернуть“» — рядом корзина: первое
  нажатие спрашивает («Убрать»), второе убирает из «Прежних мозгов»; «Вернуть» и подключённый мозг — как были;
— №256: токены в журнале (JWT, ключи API, «токен: …») в отчёт уходят звёздочками;
— №257 «всё время теряет связь и долго думает» (Wi‑Fi, «Unable to resolve host dewiar.pro» вперемешку с обрывами) —
  к ошибке связи совет: мобильный интернет или «Частный DNS» → dns.google; без сбоев DNS совета нет."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
shutil.copytree(ROOT / "android/assets/www", www)
for x in ("entities.js", "rich.js", "skins.js", "skins.css", "privacy.js", "closecrypto.js", "qrcode.js", "call.js", "codes.js"):
    if (ROOT / "ui/assets" / x).exists():
        shutil.copy(ROOT / "ui/assets" / x, www / x)
shutil.copytree(ROOT / "ui/assets/live", www / "live", dirs_exist_ok=True)
shutil.copytree(ROOT / "ui/assets/arcade", www / "arcade", dirs_exist_ok=True)
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs = []
SHOTS = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.toasts = [];")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { const t = window.toast; window.toast = (m, ms) => { toasts.push(m); return t(m, ms); }; }")
    pg.evaluate("""() => { S.llm = Object.assign({}, DEF.llm, { kind: 'openai', name: 'router.example', base_url: 'https://router.example/v1', api_key: 'k', model: 'flash' });
      S.llmSaved = [{ kind: 'openai', name: 'broken.one', base_url: 'https://broken.one/v1', api_key: 'k1', model: 'm1' },
                    { kind: 'openai', name: 'broken.two', base_url: 'https://broken.two/v1', api_key: 'k2', model: 'm2' }];
      llmSeen = JSON.parse(JSON.stringify(S.llm)); saveS(); openSettings('brain'); }""")
    pg.wait_for_timeout(600)
    rows = pg.evaluate("() => [...document.querySelectorAll('#br-back .brb')].map(r => r.innerText)")
    ok(len(rows) == 2 and pg.evaluate("document.querySelectorAll('#br-back [data-forget]').length") == 2, f"у каждого прежнего мозга — «Вернуть» и корзина: {rows}")
    pg.click("#br-back [data-forget='0']"); pg.wait_for_timeout(450)
    ok(pg.evaluate("(S.llmSaved || []).length") == 2 and pg.evaluate("document.querySelector('#br-back [data-forget=\"0\"]').classList.contains('ask')")
       and pg.is_visible("#br-back [data-forget='0'] span"), "первое нажатие только спрашивает — «Убрать»")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#br-back [data-forget=\"0\"]')).backgroundColor") == "rgb(232, 80, 111)",
       "«Убрать» — красная (тема не перебивает)")
    if SHOTS:
        pg.locator("#br-back").screenshot(path=f"{SHOTS}/phone_brain_forget.png")
    pg.click("#br-back [data-forget='0']"); pg.wait_for_timeout(400)
    R = pg.evaluate("() => ({ saved: (S.llmSaved || []).map(x => x.name), cur: S.llm.name, pref: JSON.parse(D.prefGet ? (D.prefGet('settings') || '{}') : '{}').llmSaved, rows: document.querySelectorAll('#br-back .brb').length, toasts })")
    ok(R["saved"] == ["broken.two"] and R["cur"] == "router.example", f"второе — убрал «broken.one», подключённый мозг не тронут: {R['saved']}, {R['cur']}")
    ok(R["rows"] == 1 and any("убран из списка" in t for t in R["toasts"]), "в списке остался один, сказано тостом")
    pg.click("#br-back [data-forget='0']"); pg.wait_for_timeout(200); pg.click("#br-back [data-forget='0']"); pg.wait_for_timeout(400)
    ok(pg.evaluate("(S.llmSaved || []).length") == 0 and not pg.evaluate("!!document.querySelector('#br-back')"), "убрали последний — карточка «Прежние мозги» пропала")
    # совет при сбоях DNS
    pg.evaluate("() => prefSet('net_inc', '[]')")
    ok(pg.evaluate("netHint()") == "", "сбоев нет — совета нет")
    pg.evaluate("""() => prefSet('net_inc', JSON.stringify([
      { ts: Date.now() - 5000, host: 'dewiar.pro', err: 'Software caused connection abort', online: true, type: 'wifi' },
      { ts: Date.now() - 2000, host: 'dewiar.pro', err: 'Unable to resolve host "dewiar.pro": No address associated with hostname', online: true, type: 'wifi' }]))""")
    h = pg.evaluate("netHint()")
    ok("Wi‑Fi" in h and "Частный DNS" in h and "dns.google" in h, f"Wi‑Fi и сайт то находится, то нет — совет про DNS: {h[:90]!r}")
    pg.evaluate("""() => prefSet('net_inc', JSON.stringify([{ ts: Date.now() - 2000, host: '192.168.1.5:1234', err: 'Unable to resolve host', online: true, type: 'wifi' }]))""")
    ok(pg.evaluate("netHint()") == "", "домашний сервер не найден — это «вы не дома», не DNS")
    pg.evaluate("""() => prefSet('net_inc', JSON.stringify([{ ts: Date.now() - 600000, host: 'dewiar.pro', err: 'Unable to resolve host', online: true, type: 'wifi' }]))""")
    ok(pg.evaluate("netHint()") == "", "старый сбой (10 минут назад) — не считается")
    # №256: токен в журнале телефона — в отчёт уходит звёздочками
    jwt = "eyJhbGciOiJIUzI1NiJ9." + "eyJpc3MiOiJ4eXoxMjMifQ" + ".Zm9vYmFyYmF6cXV4MTIzNDU2"
    pg.evaluate("""(j) => { plog('info', '🔧 run_command $token = "' + j + '"'); plog('info', 'токен API: Zx9qw8e7r6t5y4u3i2o1p0aa');
      window.http = async (m, u, o) => { window._rep = o.body; return { status: 200, body: '{"ok":true,"id":1}' }; }; }""", jwt)
    pg.evaluate("() => reportSend('проверка', false, '').catch(e => window._repErr = e.message)"); pg.wait_for_timeout(500)
    t = pg.evaluate("() => (window._rep && window._rep.text) || window._repErr || ''")
    ok("eyJ***" in t and jwt[-10:] not in t and "Zx9qw8e7r6t5" not in t, "токены в журнале телефона — в отчёт звёздочками")
    b.close()
ok(not errs, f"без ошибок страницы: {errs[:2]}")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
