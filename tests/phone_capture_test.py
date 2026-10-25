"""Телефон, идеи 16.10:
— кончились талеры (сервер распознавания ответил 402 «Заряд закончился») — раньше «Не получилось услышать», теперь
  слушает распознавание самого телефона (30 минут), а сервер снова пробуем потом; своего распознавания нет — честно
  говорим, что сказал сервер, и предлагаем текст;
— значок «Записать» на рабочем столе (CaptureWidget): нажатие (intent capture) — сразу слушаем; сказанное — в «Идеи»
  без модели, «напомни завтра в 10 …» — напоминание; потом приложение уходит на рабочий стол (D.home); в настройках
  значок включается и выключается (по умолчанию включён) и добавляется на экран."""
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
(www / "personas.js").write_text(subprocess.run([sys.executable, str(ROOT / "android/tools/personas_json.py"), str(ROOT)],
                                                capture_output=True, text=True, check=True).stdout, encoding="utf-8")
errs, toasts = [], []
STUB = """(say) => { window._sys = []; window._srv = 0;
  D.recognizer = () => true;
  D.toast = (t) => toasts.push(t);
  D.listenServer = (g) => { window._srv++; setTimeout(() => N.ev(JSON.stringify({ type: 'stt_error', g, code: -2,
      msg: 'сервер распознавания ответил 402: Заряд Dewiar Облака закончился. Пополнить — в кабинете.' })), 30); };
  D.listen = (g) => { window._sys.push(g); setTimeout(() => { N.ev(JSON.stringify({ type: 'stt_start', g }));
      N.ev(JSON.stringify({ type: 'stt_result', g, text: say.shift() || '' })); }, 30); };
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.add_init_script("window.toasts = [];")
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1000)
    pg.evaluate("() => { S.stt = { engine: 'server', url: 'http://127.0.0.1:9/v1', key: 'k', model: 'gigaam' }; saveS(); }")
    pg.evaluate(STUB, ["купить батарейки для пульта и проверить старые"])
    pg.evaluate("() => { const t = window.toast; window.toast = (m, ms) => { toasts.push(m); return t(m, ms); }; }")
    # значок «Записать» → слушаем → сервер 402 → телефон → «Идеи»
    pg.evaluate("() => handleIntent({ action: 'capture' })")
    pg.wait_for_timeout(2600)
    R = pg.evaluate("""() => ({ srv: window._srv, sys: window._sys.length, toasts: toasts.slice(),
        idea: notes().filter(n => n.folder === 'Идеи').map(n => [n.title, n.text]), bot: document.querySelector('#bot').textContent, until: sttSysUntil > Date.now() })""")
    ok(R["srv"] == 1 and R["sys"] == 1 and R["until"], f"талеры кончились (402) — сразу слушает телефон: сервер {R['srv']}, телефон {R['sys']}")
    ok(any("талеры на распознавание закончились" in t and "слушает сам телефон" in t for t in R["toasts"]), f"объяснение, почему слушает телефон: {R['toasts']}")
    ok(R["idea"] == [["Купить батарейки для пульта и проверить…", "Купить батарейки для пульта и проверить старые"]] and "«Идеи»" in R["bot"],
       f"значок «Записать»: сказанное — в «Идеи» без модели: {R['idea']} / {R['bot']!r}")
    pg.wait_for_timeout(3500)
    ok(pg.evaluate("window._home || 0") == 1, "записали — приложение ушло на рабочий стол")
    # дальше сервер не дёргаем 30 минут
    pg.evaluate(STUB, ["напомни завтра в 10 позвонить в сервис"])
    pg.evaluate("() => { window._home = 0; handleIntent({ action: 'capture' }); }")
    pg.wait_for_timeout(2600)
    R2 = pg.evaluate("() => ({ srv: window._srv, sys: window._sys.length, al: JSON.parse(D.alarms()).slice(-1)[0] })")
    ok(R2["srv"] == 0 and R2["sys"] == 1, f"пока талеров нет — сразу телефон, без лишнего запроса к серверу: {R2['srv']}/{R2['sys']}")
    ok(R2["al"] and R2["al"]["title"] == "Позвонить в сервис" and __import__("datetime").datetime.fromtimestamp(R2["al"]["at"] / 1000).hour == 10,
       f"«напомни завтра в 10 …» через «Записать» — напоминание: {R2['al'] and R2['al']['title']}")
    # своего распознавания нет — честное сообщение
    pg.evaluate("() => { sttSysUntil = 0; D.recognizer = () => false; S.stt = { engine: 'server', url: 'http://127.0.0.1:9/v1', key: 'k' }; }")
    pg.evaluate("() => listen()"); pg.wait_for_timeout(400)
    bot = pg.evaluate("document.querySelector('#bot').textContent")
    ok("Заряд Dewiar Облака закончился" in bot and "напишите текстом" in bot, f"нет своего распознавания — сказано, что ответил сервер: {bot!r}")
    # другие ошибки сервера — как раньше (не уходим на телефон)
    pg.evaluate("""() => { D.recognizer = () => true; D.listenServer = (g) => setTimeout(() => N.ev(JSON.stringify({ type: 'stt_error', g, code: -2, msg: 'сервер распознавания ответил 500' })), 20); }""")
    pg.evaluate("() => listen()"); pg.wait_for_timeout(300)
    ok(pg.evaluate("sttSysUntil") == 0 and "Не получилось услышать" in pg.evaluate("document.querySelector('#bot').textContent"), "ошибка 500 — не про талеры: как раньше")
    # настройки: значок
    pg.evaluate("() => openSettings('more')"); pg.wait_for_timeout(300)
    W = pg.evaluate("() => [!!document.querySelector('#wg-on'), document.querySelector('#wg-on').checked, !!document.querySelector('#wg-pin')]")
    ok(W == [True, True, True], f"настройки: значок «Записать» включён по умолчанию, кнопка «Добавить на рабочий стол»: {W}")
    pg.click("#wg-pin"); pg.wait_for_timeout(100)
    ok("Подтвердите" in pg.evaluate("document.querySelector('#wg-res').textContent"), "«Добавить» — система спросит подтверждение")
    pg.evaluate("() => renderSettings()"); pg.wait_for_timeout(100)
    ok("На рабочем столе: 1" in pg.evaluate("document.querySelector('#sh-set').textContent"), "значок уже на экране — так и написано")
    L = pg.evaluate("() => [...document.querySelectorAll('#wg-look button')].map(b => b.dataset.l + (b.classList.contains('on') ? '*' : ''))")
    ok(L == ["glass*", "light", "dark", "theme"], f"вид значка: «Стекло» по умолчанию, ещё «Светлый», «Тёмный», «Как тема» (25.10): {L}")
    pg.click("#wg-look [data-l='light']"); pg.wait_for_timeout(100)
    ok(pg.evaluate("D.pref('widget_look')") == "light" and pg.evaluate("document.querySelector('#wg-look .on').dataset.l") == "light",
       "выбрали «Светлый» — запомнили, значок перерисуется")
    sw = pg.evaluate("() => { const s = document.querySelector('#wg-look'); return [s.scrollWidth, s.clientWidth]; }")
    ok(sw[0] <= sw[1] + 1, f"четыре варианта помещаются в ширину телефона: {sw}")
    pg.evaluate("() => { const c = document.querySelector('#wg-on'); c.checked = false; c.dispatchEvent(new Event('change')); }"); pg.wait_for_timeout(100)
    ok(pg.evaluate("JSON.parse(D.widgetState()).on") is False and not pg.evaluate("!!document.querySelector('#wg-pin')"), "выключили — значок убран из системы")
    b.close()
src = (ROOT / "android/src/pro/dewiar/app/Net.java").read_text(encoding="utf-8")
ok('getJSONObject("error").optString("message"' in src, "Android: в ошибке распознавания — и что сказал сервер")
man = (ROOT / "android/AndroidManifest.xml").read_text(encoding="utf-8")
ok(".CaptureWidget" in man and "@xml/widget_capture" in man, "Android: значок «Записать» объявлен")
ok(not errs, "без ошибок JavaScript" + (f": {errs}" if errs else ""))
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
