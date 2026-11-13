"""0.96 — английское приложение для телефона (веб-версия — тот же app.js). Новый человек с английским телефоном
получает английское приложение сам («Как в системе»), у прежних — русское, как было. Переводит тот же слой «по тексту»,
что у студии (data/i18n/text/en.json → i18n.tx.js); готовые фразы самого приложения («Фонарик включён.») — тоже,
а то, что сказал человек и что ответила модель, — нет (translate="no"). Заодно: «Что нового» в веб-версии брал выпуски
полугодовой давности — версия «0.9.38-web» сравнивалась как NaN; образец «Поручения{3}» превращал
«Поручения руководителя…» в «Assignments руководителя…»; «Сейчас {1}» — «Сейчас выключен» в «Now выключен»."""
import os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


SCAN = """() => { const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const s = n.nodeValue.trim(); const p = n.parentElement;
    if (/[А-Яа-яЁё]/.test(s) && p && p.getClientRects().length && !p.closest('textarea,[translate=no],script,style')) out.push(s); }
  for (const el of document.querySelectorAll('[title],[placeholder],[aria-label]')) { if (!el.getClientRects().length || el.closest('[translate=no]')) continue;
    for (const a of ['title', 'placeholder', 'aria-label']) { const v = el.getAttribute(a); if (v && /[А-Яа-яЁё]/.test(v)) out.push(v); } }
  return out; }"""
TABS = "about assist brain bug devices features hands lite look menu perms privacy smart sound telegram voice widget".split()
www = Path(tempfile.mkdtemp()) / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
ok((www / "i18n.tx.js").exists(), "словарь перевода по тексту едет в приложение")
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(locale="en-US", viewport={"width": 412, "height": 900})
    ctx.add_init_script("window.DW_SYS_LANG = 'en-US'")              # язык телефона (без моста — так; см. phoneSysLang)
    pg = ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(2500)
    ok(pg.evaluate("dwLang()") == "en", "новый человек, телефон по-английски — приложение по-английски само")
    pg.wait_for_function("!!window.DW_TX", timeout=8000)
    left = {}
    for t in TABS:
        pg.evaluate(f"openSettings('{t}')"); pg.wait_for_timeout(450)
        left[t] = sorted(set(pg.evaluate(SCAN)))
    total = sum(len(v) for v in left.values())
    ok(total <= 12, f"настройки (17 вкладок) по-английски — русских строк почти нет ({total}): {[x for v in left.values() for x in v][:12]}")
    for t in ("look", "sound", "brain", "voice", "menu"):
        ok(not left[t], f"вкладка «{t}» — без русского: {left[t][:5]}")
    pg.evaluate("closeSheets()")
    for f in ("openApps", "openDone", "openTricks"):
        pg.evaluate(f"{f}()"); pg.wait_for_timeout(500)
        got = sorted(set(pg.evaluate(SCAN)))
        ok(len(got) <= 3, f"{f}: по-английски ({len(got)}): {got[:5]}")
        pg.evaluate("closeSheets()")
    # готовые фразы приложения — на языке приложения, и на экране, и голосом
    said = pg.evaluate("(() => { const out = []; const o = window.say; window.say = (t) => out.push(trL(t)); answerLocal({ say: 'Фонарик включён.' }); window.say = o; return [document.querySelector('#bot').textContent, out[0]]; })()")
    ok(said[0] == "Flashlight on." and said[1] == "Flashlight on.", f"«Фонарик включён.» без модели — «Flashlight on.»: {said}")
    ok(pg.get_attribute("#bot", "translate") == "no" and pg.get_attribute("#you", "translate") == "no", "сказанное человеком и ответ модели слой не трогает")
    ok(pg.evaluate("trL('Here is the answer in English.')") == "Here is the answer in English.", "английский ответ модели — как есть")
    # правила слоя
    tx = lambda s: pg.evaluate("(s) => dwTx(s)", s)
    ok(tx("Пятница, 13 ноября") == "Friday, November 13", f"дата, собранная по-русски: {tx('Пятница, 13 ноября')!r}")
    ok(tx("1 марта 2026") == "March 1, 2026", f"дата с годом: {tx('1 марта 2026')!r}")
    ok(tx("Тёмные · Сдержанная").startswith("Dark · "), f"«группа · имя» через точку: {tx('Тёмные · Сдержанная')!r}")
    v = tx("Сейчас что-то непонятное")
    ok(not re.search(r"[A-Za-z]", v), f"короткий образец не клеит английское к русскому: {v!r}")
    v = tx("Поручения руководителя отдельно от личного")
    ok(not v.startswith("Assignments"), f"образец с приклеенной разметкой («Поручения{{3}}») не берёт текст: {v!r}")
    ok(tx("Играет «Ретро FM».") == "Playing “Retro FM”." or "«Ретро FM»" in tx("Играет «Ретро FM».") or "Ретро FM" in tx("Играет «Ретро FM»."), "имя в кавычках подставляется как есть")
    # «Что нового» в веб-версии — по номеру версии, а не NaN
    ok(pg.evaluate("verCmp('0.9.38-web', '0.9.37') > 0 && verCmp('0.9.38-web', '0.9.38') === 0"), "версия «0.9.38-web» сравнивается как 0.9.38")
    # распознавание: приложение по-английски — телефон слушает английский, английская фраза — не «чужой язык»
    ok(not pg.evaluate("sttNotRu('turn on the light please')"), "английская фраза при английском приложении — не повод звать сервер")
    pg.evaluate("openSettings('voice')"); pg.wait_for_timeout(400)
    ok("Also understand Russian speech" in pg.text_content("#sh-set"), "второй язык при английском приложении — русский")
    ok(pg.evaluate("(() => { const a = D.ttsReady, b = D.ttsReadyLang; D.ttsReady = () => false; D.ttsReadyLang = (l) => l === 'en'; const r = ttsOk(); D.ttsReady = a; D.ttsReadyLang = b; return r; })()"),
       "телефон без русского голоса, но с английским — при английском приложении голос есть")
    pg.evaluate("showYou('Remind me at 9')")
    ok(pg.text_content("#you") == "“Remind me at 9”", f"сказанное — в английских кавычках: {pg.text_content('#you')!r}")
    ok(not errs, f"без ошибок JavaScript: {errs[:3]}")
    ctx.close()
    # прежний человек с русским — всё как было, словарь не грузится
    ctx = b.new_context(locale="ru-RU", viewport={"width": 412, "height": 900})
    ctx.add_init_script("window.DW_SYS_LANG = 'ru-RU'")
    pg = ctx.new_page(); pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(2000)
    ok(pg.evaluate("dwLang()") == "ru" and not pg.evaluate("!!window.DW_TX"), "русский телефон — русское приложение, словарь перевода не грузится")
    ctx.close()
    ctx = b.new_context(locale="en-US", viewport={"width": 412, "height": 900})          # проверки без языка телефона — как раньше
    pg = ctx.new_page(); pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1500)
    ok(pg.evaluate("dwLang()") == "ru", "без моста и без DW_SYS_LANG (прежние проверки телефона) — русский, хотя Chromium en-US")
    ctx.close()
    ctx = b.new_context(locale="ru-RU", viewport={"width": 412, "height": 900})
    ctx.add_init_script("window.DW_SYS_LANG = 'ru-RU'")
    pg = ctx.new_page(); pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(1500)
    ok(pg.evaluate("trL('Фонарик включён.')") == "Фонарик включён.", "по-русски готовые фразы — как есть")
    ok(pg.evaluate("sttNotRu('turn on the light please') && !sttNotRu('включи свет')"), "по-русски английская фраза — как раньше, «не по-русски» (№253)")
    ok(not pg.evaluate("(() => { const a = D.ttsReady, b = D.ttsReadyLang; D.ttsReady = () => false; D.ttsReadyLang = (l) => l === 'en'; const r = ttsOk(); D.ttsReady = a; D.ttsReadyLang = b; return r; })()"),
       "по-русски без русского голоса — голоса нет, как раньше")
    b.close()
sp = (ROOT / "android/src/pro/dewiar/app/Speech.java").read_text(encoding="utf-8")
ok('"en".equals(lang1) ? "en-US" : "ru-RU"' in sp and "EXTRA_LANGUAGE, main" in sp and "EXTRA_LANGUAGE_PREFERENCE, main" in sp,
   "Speech.java: язык распознавания — язык приложения")
tj = (ROOT / "android/src/pro/dewiar/app/Tts.java").read_text(encoding="utf-8")
ok("readyEn = tts.isLanguageAvailable(Locale.US)" in tj and "!(ready || readyEn)" in tj, "Tts.java: английский голос — и без русского")
ok("sttLang1(String l)" in (ROOT / "android/src/pro/dewiar/app/Bridge.java").read_text(encoding="utf-8"), "мост: sttLang1")
ok('dwLang() === "en" ? "en-US" : "ru-RU"' in (ROOT / "android/web/webbridge.js").read_text(encoding="utf-8"), "веб-версия: браузер слушает по-английски")
print("ИТОГ:", "всё прошло" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
