"""Английская студия и виджет целиком (0.95; план владельца 12.11: «0.95 — английская студия и виджет целиком»).
Перевод по тексту: data/i18n/text/en.json {"Русская строка": "English"} -> window.DW_TX, ui/assets/i18n.js переводит
всё, что на странице, — разметку и дорисованное кодом. Проверяется:
— словарь покрывает интерфейс компьютера (tools/i18n_texts.py en — почти пусто), подстановки {1} в переводе те же;
— окна с ?lang=en: все разделы студии, виджет, суфлёр, блокнот, будильник, «Закинуть идею», «Вырезать» — без русского;
— образцы («Найдено: 5», «3 дела», «Утро с Лирой», «Хранятся у вас.») и склейки предложений;
— своё у людей не трогаем (textarea, translate="no"), имя языка — на нём самом; вернулись к русскому — всё как было."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "tools"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


en = json.loads((ROOT / "data/i18n/text/en.json").read_text(encoding="utf-8"))
ok(len(en) > 8000, f"словарь по тексту: {len(en)} строк")
bad = [k for k, v in en.items() if sorted(re.findall(r"\{\d\}", k)) != sorted(re.findall(r"\{\d\}", v))]
ok(not bad, f"подстановки {{1}}… в переводе — те же, что в строке: {bad[:3]}")
cyr = [v for v in en.values() if re.search(r"[А-Яа-яЁё]{3}", re.sub(r"\{[^{}]*\}", "", v))]   # {что} — поле плагина, его имя остаётся
ok(not cyr, f"в английских строках нет русского текста: {cyr[:3]}")
import i18n_texts as T  # noqa: E402
left = set()
for rel, miss in T.todo("en").items():
    left |= set(miss)
ok(len(left) <= 90, f"не переведено в интерфейсах компьютера: {len(left)} строк (в основном подсказки модели и куски кода)")
data_left = sum(len(v) for v in T.todo("en", data=True).values())
ok(data_left <= 5, f"руководство, «Что я умею» и плагины Dewiar — переведены (осталось {data_left})")
tx = (ROOT / "ui/assets/i18n.tx.js").read_text(encoding="utf-8")
ok("window.DW_TX" in tx and "DW_TX" not in (ROOT / "ui/assets/i18n.data.js").read_text(encoding="utf-8"),
   "перевод по тексту — отдельным файлом i18n.tx.js: русским окнам грузить его не нужно")
r = subprocess.run([sys.executable, str(ROOT / "tools/i18n_texts.py"), "en", "--merge", "/nonexistent.json"], capture_output=True, text=True)
ok(r.returncode != 0, "--merge без файла — ошибка, а не порча словаря")

from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); if (c === "month_get") throw new Error("нет"); return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
SCAN = """(root) => { const out = []; const w = document.createTreeWalker(root || document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) { const s = n.nodeValue.trim();
    if (/[А-Яа-яЁё]/.test(s) && !/undefined/.test(s) && n.parentElement.offsetParent !== null && !n.parentElement.closest('textarea,[contenteditable=true],[translate=no]')) out.push(s.slice(0, 60)); }
  for (const el of (root || document.body).querySelectorAll('[title],[placeholder],[aria-label]')) {
    if (el.offsetParent === null) continue;
    for (const a of ['title', 'placeholder', 'aria-label']) { const v = el.getAttribute(a); if (v && /[А-Яа-яЁё]/.test(v)) out.push('@' + a + ': ' + v.slice(0, 50)); } }
  return out; }"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900})
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&lang=en"); st.wait_for_timeout(1500)
    st.evaluate("() => { if (!S) S = { ui: {} }; if (!Array.isArray(personas)) personas = []; const w = document.querySelector('#wlc'); if (w) w.remove(); }")
    pages = st.evaluate("[...document.querySelectorAll('nav button[data-p]')].map(b => b.dataset.p)")
    seen, worst = 0, {}
    for pg in pages:
        st.evaluate(f"() => document.querySelector('nav button[data-p=\"{pg}\"]').click()"); st.wait_for_timeout(200)
        c = st.evaluate("(f) => (new Function('return ' + f))()(document.querySelector('main section.cur'))", SCAN)
        seen += len(c)
        if c:
            worst[pg] = c[:2]
    ok(len(pages) > 40 and seen <= 12, f"все {len(pages)} разделов студии по-английски: русских строк на виду {seen} {dict(list(worst.items())[:4])}")
    nav = st.evaluate("[...document.querySelectorAll('nav button[data-p]')].map(b => b.textContent.trim()).filter(t => /[А-Яа-яЁё]/.test(t))")
    ok(not nav, f"меню целиком: {nav[:3]}")
    # образцы и склейки
    got = st.evaluate("""async () => { const d = document.createElement('div'); d.id = 'tx-t';
      d.innerHTML = '<p>Найдено: 5</p><p>3 дела</p><p>Хранятся у вас.</p><p>Утро с Лирой</p><p>Все вкладки (4)</p>'
        + '<p>Пароли и ключи. Близкие.</p><textarea>Сохранить</textarea><p translate="no">Сохранить</p><input placeholder="Ваш город">';
      document.querySelector('main section.cur').appendChild(d); await new Promise(r => setTimeout(r, 50));
      return [...d.querySelectorAll('p')].map(p => p.textContent).concat([d.querySelector('textarea').value, d.querySelector('input').placeholder]); }""")
    ok(got[:5] == ["Found: 5", "3 to-dos", "Stored with you.", "Morning with Lira", "All tabs (4)"], f"образцы: «Найдено: 5», «3 дела», точка, имя в подстановке, «(4)»: {got[:5]}")
    ok(got[5] == "Passwords and keys. My people.", f"склейка предложений: {got[5]}")
    ok(got[6] == "Сохранить" and got[7] == "Сохранить", "содержимое поля ввода и translate=\"no\" — как есть")
    ok(got[8] == "Your city", f"подписи полей (placeholder) — переводятся: {got[8]}")
    st.evaluate("() => { const p = document.querySelector('#tx-t p'); p.textContent = 'Найдено: 7'; }"); st.wait_for_timeout(60)
    ok(st.evaluate("document.querySelector('#tx-t p').textContent") == "Found: 7", "текст, поменянный кодом позже, — тоже")
    ok(st.evaluate("dwTx('Сохранено')") == "Saved" and st.evaluate("dwTx('Нет такого текста')") == "Нет такого текста", "dwTx() для кода: перевод или как есть")
    ok(st.evaluate("[...document.querySelectorAll('#lang-seg [data-v]')].map(b => b.textContent)")[1] == "Русский", "имя языка — на нём самом («Русский», не «Russian»)")
    st.evaluate("() => document.querySelector('nav button[data-p=\"look\"]').click()"); st.wait_for_timeout(200)
    st.click("#lang-seg [data-v=ru]"); st.wait_for_timeout(300)
    ru = st.evaluate("[document.querySelector('#tx-t p').textContent, document.querySelector('#tx-t input').placeholder, document.querySelector('nav button[data-p=\"brain\"]').textContent.trim()]")
    ok(ru[0] == "Найдено: 7" and ru[1] == "Ваш город" and ru[2].startswith("Мозг"), f"выбрали русский — оригиналы на месте: {ru}")
    st.click("#lang-seg [data-v=en]"); st.wait_for_timeout(300)
    ok(st.evaluate("document.querySelector('#tx-t p').textContent") == "Found: 7", "и снова английский")
    # окна
    for f in ("hud.html", "prompter.html", "pad.html", "alarm.html", "capture.html", "snip.html"):
        w = b.new_page(viewport={"width": 900, "height": 700}); w.on("pageerror", lambda e: errs.append(str(e)[:120]))
        w.route(re.compile(r"^https?://"), lambda r: r.abort())
        w.goto((ROOT / "ui" / f).as_uri() + "?port=1&lang=en"); w.wait_for_timeout(900)
        c = w.evaluate("(f) => (new Function('return ' + f))()(document.body)", SCAN)
        ok(not c, f"{f} с ?lang=en — без русского: {c[:3]}")
        w.close()
    w = b.new_page(); w.route(re.compile(r"^https?://"), lambda r: r.abort())
    w.goto((ROOT / "ui/hud.html").as_uri() + "?port=1"); w.wait_for_timeout(700)
    ok(w.evaluate("document.querySelector('#askin') ? document.querySelector('#askin').placeholder : 'Спросите'").startswith("Спросите"), "без ?lang (русский) — слой спит, всё по-русски")
    ok(w.evaluate("window.DW_TX === undefined"), "русскому окну словарь перевода по тексту не грузится")
ok(not errs, f"окна без ошибок JavaScript: {errs[:2]}")
for f in ("prompter", "pad", "alarm", "capture", "snip", "call"):
    ok("assets/i18n.js" in (ROOT / f"ui/{f}.html").read_text(encoding="utf-8"), f"ui/{f}.html подключает словари")
js = (ROOT / "ui/studio/chat.js").read_text(encoding="utf-8")
ok('class="tx md" translate="no"' in js and 'id="bot" translate="no"' in (ROOT / "ui/hud.html").read_text(encoding="utf-8"),
   "ответы Лиры и ваши сообщения (чат, виджет) не переводятся")
print(f"\nИТОГ: {'провалов ' + str(len(fails)) if fails else 'всё прошло'}")
sys.exit(1 if fails else 0)
