"""Языки программы (0.88; владелец 11.11: «ru.json, en.json — всё в отдельных файлах; нет русского в системе — сразу
английский, в настройках переключение; без переписывания тонн кода потом»). Проверяется:
— словари data/i18n/ru.json и en.json: одни и те же ключи, формы чисел по языку, ui/assets/i18n.data.js собран из них;
— разметка: русский текст у data-i18n совпадает с ru.json (иначе студия и словарь разойдутся), все ключи есть;
— храповик: русского мимо словарей не больше, чем было (tests/i18n_baseline.json; новый текст — только ключом);
— ядро: core/i18n.py — формы чисел, язык по системе; окно с ?lang=en — меню по-английски, переключатель — без перезапуска."""
import json, os, re, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core")); sys.path.insert(0, str(ROOT / "tools"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


ru = json.loads((ROOT / "data/i18n/ru.json").read_text(encoding="utf-8"))
en = json.loads((ROOT / "data/i18n/en.json").read_text(encoding="utf-8"))
ok(set(ru) == set(en), f"ru.json и en.json — одни ключи (нет в en: {sorted(set(ru) - set(en))[:5]}, лишние: {sorted(set(en) - set(ru))[:5]})")
ok(all(not isinstance(v, dict) or {"one", "few", "many", "other"} <= set(v) for v in ru.values()), "русские формы чисел: one, few, many, other")
ok(all(not isinstance(v, dict) or {"one", "other"} <= set(v) for v in en.values()), "английские формы чисел: one, other")
ok(subprocess.run([sys.executable, str(ROOT / "tools/i18n_build.py"), "--check"], capture_output=True).returncode == 0,
   "ui/assets/i18n.data.js собран из нынешних словарей (python3 tools/i18n_build.py)")

# разметка: текст и атрибуты с ключом совпадают с ru.json
miss, diff = [], []
for page in ("ui/settings.html", "ui/hud.html"):
    html = (ROOT / page).read_text(encoding="utf-8")
    for m in re.finditer(r"<(\w+)([^>]*?)\sdata-i18n=\"([\w.]+)\"([^>]*)>([^<]*)", html):
        k, text = m.group(3), m.group(5).strip()
        if k not in ru:
            miss.append(k)
        elif text and text != ru[k]:
            diff.append((k, text, ru[k]))
    for m in re.finditer(r"<\w+([^>]*)>", html):
        attrs = m.group(1)
        for a in ("title", "placeholder", "aria-label"):
            km = re.search(rf'data-i18n-{a}="([\w.]+)"', attrs)
            vm = re.search(rf'\s{a}="([^"]*)"', attrs)
            if km:
                if km.group(1) not in ru:
                    miss.append(km.group(1))
                elif vm and vm.group(1) != ru[km.group(1)]:
                    diff.append((km.group(1), vm.group(1), ru[km.group(1)]))
ok(not miss, f"все ключи разметки — в словаре: {miss[:5]}")
ok(not diff, f"русский в разметке = ru.json: {diff[:3]}")
used = set()
for p in list((ROOT / "ui/studio").glob("*.js")) + list((ROOT / "ui/assets").glob("*.js")):
    used |= set(re.findall(r"(?<![\w.])t\(\s*\"([a-z0-9_.]+)\"", p.read_text(encoding="utf-8")))
ok(used and used <= set(ru), f"ключи t(\"…\") в коде — в словаре: {sorted(used - set(ru))[:5]}")

import i18n_ratchet as R  # noqa: E402
base = json.loads((ROOT / "tests/i18n_baseline.json").read_text(encoding="utf-8"))
now = R.current()
over = {k: (v, base.get(k, 0)) for k, v in now.items() if v > base.get(k, 0)}
ok(not over, f"русского мимо словарей не прибавилось (новый текст — ключом; tools/i18n_ratchet.py): {dict(list(over.items())[:4])}")
ok(now.get("ui/settings.html", 9999) <= 1911, f"меню студии — уже из словаря ({now.get('ui/settings.html')} строк осталось в settings.html)")

import i18n  # noqa: E402
forms = {n: i18n.plural_form("ru", n) for n in (1, 2, 5, 11, 21, 22, 25, 111, 1.5)}
ok(forms == {1: "one", 2: "few", 5: "many", 11: "many", 21: "one", 22: "few", 25: "many", 111: "many", 1.5: "other"}, f"русские формы чисел: {forms}")
ok([i18n.plural_form("en", n) for n in (1, 2, 0)] == ["one", "other", "other"], "английские формы")
ok([i18n.plural_form("ar", n) for n in (0, 1, 2, 3, 11, 100)] == ["zero", "one", "two", "few", "many", "other"], "арабские формы — на будущее")
ok(i18n.t("nav.home", "en") == "Home" and i18n.t("nav.home", "ru") == "Главная" and i18n.t("нет.такого", "en") == "нет.такого", "t(): язык, запасной русский, ключ")
for k in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "DEWIAR_SYS_LANG"):   # DEWIAR_SYS_LANG — его задают проверкам run_quick
    os.environ.pop(k, None)
os.environ["LANG"] = "de_DE.UTF-8"
ok(i18n.resolve("auto") == "en" and i18n.resolve("ru") == "ru", "система не на русском — английский; выбор человека — главнее")
os.environ["LANG"] = "ru_RU.UTF-8"
ok(i18n.resolve("auto") == "ru" and i18n.resolve("xx") == "ru", "система на русском — русский")
os.environ["LANG"] = "uk_UA.UTF-8"
ok(i18n.resolve("auto") == "ru", "украинская система — русский (скорее всего читает)")
import tempfile  # noqa: E402
# любой язык — новым файлом (владелец 11.11, 21:10: «иврит, немецкий, французский, китайский»)
tl = Path(tempfile.mkdtemp())
for l, d in (("ru", ru), ("en", en), ("de", {"lang.name": "Deutsch", "nav.home": "Startseite"}), ("he", {"lang.name": "עברית"})):
    (tl / f"{l}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
i18n.DIR, i18n._cache = tl, {}
ok(i18n.langs() == ("ru", "de", "en", "he"), f"новый язык — новый файл, код не трогаем: {i18n.langs()}")
ok(i18n.t("nav.home", "de") == "Startseite" and i18n.t("nav.chat", "de") == "Chat", "нет немецкой строки — английская (её поймут скорее русской)")
os.environ["LANG"] = "de_DE.UTF-8"
ok(i18n.resolve("auto") == "de", "немецкая система и есть немецкий словарь — немецкий")
os.environ["LANG"] = "ja_JP.UTF-8"
ok(i18n.resolve("auto") == "en", "японская система, японского словаря нет — английский")
ok([i18n.plural_form("he", n) for n in (1, 2, 5)] == ["one", "two", "other"] and i18n.plural_form("zh", 1) == "other"
   and [i18n.plural_form("pl", n) for n in (1, 3, 5, 22)] == ["one", "few", "many", "few"] and i18n.plural_form("fr", 0) == "one",
   "формы чисел: иврит, китайский, польский, французский")
i18n.DIR, i18n._cache = ROOT / "data" / "i18n", {}
js = (ROOT / "ui/assets/i18n.js").read_text(encoding="utf-8")
ok('RTL = ["ar", "he", "fa", "ur"]' in js and "Object.keys(window.DW_I18N || {})" in js and "for (const x of [lang, FB, SRC])" in js,
   "окна: языки — из словарей, справа налево — иврит и арабский, запасной — английский, затем русский")
from settings import Settings  # noqa: E402
td = Path(tempfile.mkdtemp())
(td / "old.json").write_text(json.dumps({"ui": {"skin": "neusky"}}), encoding="utf-8")
ok(Settings(td / "old.json").get("ui", "lang") == "ru", "кто пользовался до 0.88 — остаётся по-русски (даже на английской Windows)")
ok(Settings(td / "new.json").get("ui", "lang") == "auto", "новая установка — «как в системе»")
ok("_win_ru_keyboard()" in (ROOT / "core/i18n.py").read_text(encoding="utf-8"), "Windows: русская раскладка — значит, русский")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("&lang={lang}{extra}" in app and "i18n.resolve(ui_settings().get(\"lang\"))" in app, "окна открываются сразу на языке программы")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok("Язык программы у человека — английский: отвечай по-английски" in ea, "программа на английском — Лира отвечает по-английски")

os.environ["LANG"] = "en_US.UTF-8"                 # браузер берёт язык системы для «как в системе»
from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = """(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); if (c === "month_get") throw new Error("нет"); return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""
errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errs.append(str(e) + " @ " + (e.stack or "")[:300]))
    st.route(re.compile(r"^https?://"), lambda r: r.abort()); st.add_init_script(FAKE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&lang=en"); st.wait_for_timeout(1500)
    nav = lambda k: st.evaluate(f"[...document.querySelector('nav button[data-p=\"{k}\"]').childNodes].filter(n => n.nodeType === 3 && n.nodeValue.trim()).map(n => n.nodeValue.trim())[0]")   # noqa: E731
    ok(nav("home") == "Home" and nav("reminders") == "To-dos & reminders", f"?lang=en — меню по-английски: {nav('home')}, {nav('reminders')}")
    ok(st.get_attribute('nav button[data-p="node"]', "title").startswith("Lira Node:"), "подсказки меню — тоже")
    ok(st.evaluate("document.querySelector('nav button[data-p=\"dw\"] .ndot') !== null"), "значки-точки в пунктах меню на месте")
    ok(st.evaluate("document.documentElement.lang") == "en", "<html lang='en'>")
    ok(st.evaluate("[...document.querySelectorAll('nav .ng')].map(g => g.textContent.trim())").count("Settings") == 1, "заголовки групп меню — по-английски")
    st.evaluate("() => { if (!S) S = { ui: {} }; if (!Array.isArray(personas)) personas = []; const w = document.querySelector('#wlc'); if (w) w.remove(); document.querySelector('nav button[data-p=\"home\"]').click(); loadHome(); }")
    st.wait_for_timeout(500)
    g = st.inner_text("#hm-greet")
    ok(g.startswith("Good"), f"приветствие на «Главной» — по-английски: {g}")
    st.evaluate("document.querySelector('nav button[data-p=\"look\"]').click()"); st.wait_for_timeout(300)
    ok(st.inner_text("#lang-row b") == "Language" and st.evaluate("[...document.querySelectorAll('#lang-seg [data-v]')].map(b => b.textContent)") == ["System language", "Русский", "English"],
       "«Оформление» → «Language»: как в системе + все языки из словарей, каждый своим именем")
    st.click("#lang-seg [data-v=ru]"); st.wait_for_timeout(300)
    ok(nav("home") == "Главная" and st.evaluate("document.documentElement.lang") == "ru", "выбрали «Русский» — меню сразу по-русски, без перезапуска")
    ok(any(c == "settings_save" and a["patch"] == {"ui": {"lang": "ru"}} for c, a in st.evaluate("calls")), "выбор сохраняется в настройках (ui.lang)")
    st.click("#lang-seg [data-v=en]"); st.wait_for_timeout(300)
    ok(nav("home") == "Home", "и обратно на английский")
    g0 = st.evaluate("document.querySelector('nav .ng').dataset.foldK")
    ok(g0 == "Для себя", "свёрнутость групп помнится под прежними русскими именами (data-fold-k) — при смене языка не теряется")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
# 0.89: виджет — главные строки состояния из словаря; телефон — те же словари («Клиенты», планшет)
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok(all(f'window.t("{k}")' in hud for k in ("hud.st.listen", "hud.st.think", "hud.mic_off", "hud.st.sleep", "hud.upd.go")) and en.get("hud.st.listen") == "I'm listening",
   "виджет: «Слушаю», «Думаю», микрофон, сон, обновление — по-английски из en.json")
www = (ROOT / "android/assets/www/index.html").read_text(encoding="utf-8")
ok("i18n.data.js" in www and "i18n.js" in www and 'cp "$ROOT/ui/assets/i18n.data.js"' in (ROOT / "android/tools/www_assemble.sh").read_text(encoding="utf-8"),
   "телефон берёт те же словари")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
