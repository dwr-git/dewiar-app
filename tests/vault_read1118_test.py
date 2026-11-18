"""Сейф → секретная страница для чтения (18.11, владелец: «красивее отображать как страничку, а не сырые данные»; на его
снимке открытая страница показывала ключ подписи целиком). Общий ui/assets/secretpage.js — студия и телефон:
- разбор: заголовки, список, ряды «подпись: значение», блок JSON; секреты (пароль, код, ключ API, «sk» в JSON) — точками,
  а имена файлов, адреса, отпечатки и инструкции с пробелами — видны;
- студия: страница открывается для чтения — значения секретов нет на экране, пока не нажать; нажали — видно; «Скопировать»
  у ряда — через окно со стиранием из буфера; ссылка — во внешнем браузере; «Изменить» → текст, «Отмена» — назад к
  чтению без правок, «Сохранить» — снова чтение;
- телефон: «Показать» у страницы — тот же вид, секреты точками.
DEWIAR_SHOTS=<папка> — снимки vault-read.png, vault-read-dark.png, vault-read-phone.png."""
import json, os, re, subprocess, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


SK = "QW9hN2tYUzF3cGx6R0hNZ0VWYk5kU3J5c2xQWnFMa3g5UzJ1"
API = "sk-ws-H.QZtq7Pz2Wg.MEQCIVTXau-y8utkwaJUjl9YLoRJl89E8nRJZ"
TEXT = f"""# Серверы
Сервер с картой: ssh user@10.0.0.5 -p 1666
Пароль: Kx9!vQ2#mZ
Код домофона: 4711
Нужен токен: аватар → Edit profile → Access Tokens
Ключ API: {API}
Сайт: https://gitlab.example.dev/

Заметки:
- вход через VPN
- Логин: isaev

файл net-key-ABCD1234EF56AB78.json с содержимым (открытая часть ABCD-1234):
{{
    "what": "Ключ подписи сети",
    "sk": "{SK}",
    "fp": "ABCD-1234-EF56-AB78"
}}"""
SECRETS = ["Kx9!vQ2#mZ", "4711", API, SK]
SHOT = os.environ.get("DEWIAR_SHOTS")

# ---------- разбор ----------
js = f"""const SP = require({json.dumps(str(ROOT / "ui/assets/secretpage.js"))});
const r = SP.render({json.dumps(TEXT)});
const names = ["dewiar-lira-net-key-589C9457323BDF0C.json", "/var/www/dwr/abc123def456ghi789", "gitlab.ntechnology.dev", "10.0.0.5:1666",
  "Kx9vQ2mZ8pL3nR7tW1yBq", "gh" + "p_Z8xY2wV4uT6sR8qP0oN1mL3kJ5iH7gF9eD"];
console.log(JSON.stringify({{ html: r.html, secrets: r.secrets, look: names.map(SP.looksSecret) }}));"""
R = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
html = R["html"]
ok(all(s not in html for s in SECRETS), "в разметке страницы нет ни одного секрета — только точки")
ok(all(s in R["secrets"] for s in SECRETS), "секреты — отдельно, для «Показать» и «Скопировать»")
ok("<h4 class=\"sp-h\">Серверы</h4>" in html and "sp-h sub\">Заметки" in html and "<ul class=\"sp-ul\">" in html, "заголовки и список узнаются")
ok(html.count("class=\"sp-kv\"") == 7 and html.count("class=\"sp-kvs\"") == 1 and "sp-code" in html, f"ряды «подпись: значение» и блок JSON: {html.count('class=\"sp-kv\"')}")
ok("net-key-ABCD1234EF56AB78.json" in html and "ABCD-1234-EF56-AB78" in html and "аватар → Edit profile" in html and "ssh user@10.0.0.5" in html,
   "имена файлов, отпечаток, инструкции и команды — видны")
ok(R["look"] == [False, False, False, False, True, True], f"«случайная» строка — секрет, имена и адреса — нет: {R['look']}")

# ---------- студия ----------
FAKE = ("window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'clip_secret' ? ((t, s) => { (window.clips = window.clips || []).push([t, s]); return Promise.resolve(true); })"
        " : k === 'open_url' ? ((u) => { (window.opened = window.opened || []).push(u); return Promise.resolve(true); }) : (...a) => Promise.resolve(true) }) };")
CORE = r"""
(() => { window.calls = []; window.V = [{ id: "p1", name: "Серверы", kind: "page", value: %s }];
  const pub = () => V.map(x => { const o = Object.assign({}, x); o.lines = x.value.split("\n").filter(l => l.trim()).length; delete o.value; return o; });
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "vault_list") return { items: pub() };
      if (c === "vault_reveal") return { value: (V.find(x => x.id === a.id) || {}).value || "" };
      if (c === "vault_put") { const x = V.find(i => i.id === a.id); Object.assign(x, a); const o = Object.assign({}, x); delete o.value; return { item: o, items: pub() }; }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
""" % json.dumps(TEXT)
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 1100}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"vault\"]').click()"); pg.wait_for_timeout(500)
    pg.click(".vl-item[data-id='p1'] .vl-name"); pg.wait_for_timeout(300)
    seen = pg.inner_text("#vl-view")
    ok(pg.is_visible("#vl-view") and pg.is_hidden("#vl-ptext") and all(s not in seen for s in SECRETS), "открыта для чтения — секретов на экране нет")
    ok(pg.text_content("#vl-form-h").startswith("Серверы") and "Секретная страница · 16 строк" in pg.text_content("#vl-form-h"), f"заголовок — имя страницы: {pg.text_content('#vl-form-h')}")
    if SHOT:
        Path(SHOT).mkdir(parents=True, exist_ok=True); pg.locator("#vl-form").screenshot(path=str(Path(SHOT) / "vault-read.png"))
    dots = pg.locator("#vl-view .sp-kv:has-text('Ключ API') .sp-dots")
    dots.click(); pg.wait_for_timeout(100)
    ok(API in pg.inner_text("#vl-view") and SK not in pg.inner_text("#vl-view"), "нажали на точки — виден только этот секрет")
    dots.click(); pg.wait_for_timeout(100)
    ok(API not in pg.inner_text("#vl-view"), "ещё раз — снова точки")
    pg.hover("#vl-view .sp-kv:has-text('Пароль')"); pg.click("#vl-view .sp-kv:has-text('Пароль') .sp-ib"); pg.wait_for_timeout(150)
    ok(pg.evaluate("window.clips && window.clips.pop()") == ["Kx9!vQ2#mZ", 30], "«Скопировать» у пароля — через окно, со стиранием через 30 с")
    pg.click("#vl-view .sp-code .sp-ib"); pg.wait_for_timeout(150)
    ok(SK in pg.evaluate("window.clips.pop()[0]"), "блок JSON копируется целиком")
    pg.click("#vl-view .sp-a"); pg.wait_for_timeout(100)
    ok((pg.evaluate("window.opened") or [None])[-1] == "https://gitlab.example.dev/", f"ссылка — во внешнем браузере: {pg.evaluate('window.opened')}")
    pg.click("#vl-pedit"); pg.wait_for_timeout(150)
    ok(pg.is_visible("#vl-ptext") and pg.input_value("#vl-ptext") == TEXT and pg.text_content("#vl-cancel") == "Отмена", "«Изменить» — текст страницы")
    pg.fill("#vl-ptext", TEXT + "\nлишнее"); pg.dispatch_event("#vl-ptext", "input"); pg.click("#vl-cancel"); pg.wait_for_timeout(200)
    ok(pg.locator(".dwq button.yes").count() == 1, "«Отмена» с правками — сначала вопрос")
    pg.click(".dwq button.yes"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#vl-view") and "лишнее" not in pg.inner_text("#vl-view") and pg.input_value("#vl-ptext") == TEXT and pg.is_visible("#vl-form"),
       "«Отмена» — назад к чтению, правки отброшены, страница открыта")
    pg.click("#vl-pedit"); pg.fill("#vl-ptext", TEXT + "\nНовая строка: тут"); pg.dispatch_event("#vl-ptext", "input"); pg.click("#vl-save"); pg.wait_for_timeout(300)
    ok(pg.is_visible("#vl-view") and "Новая строка" in pg.inner_text("#vl-view") and pg.evaluate("V[0].value").endswith("тут"), "«Сохранить» — снова чтение, с правкой")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    ok(pg.is_hidden("#vl-form") and pg.input_value("#vl-ptext") == "", "Esc при чтении — страница закрыта, текста в поле нет")
    pg.evaluate("() => studioSkin('brand')"); pg.wait_for_timeout(150)
    pg.click(".vl-item[data-id='p1'] .vl-name"); pg.wait_for_timeout(300)
    if SHOT:
        pg.locator("#vl-form").screenshot(path=str(Path(SHOT) / "vault-read-dark.png"))
    pg.set_viewport_size({"width": 720, "height": 900}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")

    # ---------- телефон ----------
    www = Path(tempfile.mkdtemp()) / "www"
    subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
    ph = b.new_page(viewport={"width": 393, "height": 852}); ph.on("pageerror", lambda e: errs.append(str(e)))
    ph.goto((www / "index.html").as_uri()); ph.wait_for_timeout(1000)
    ph.evaluate("""(t) => { SF.list = [{ id: "p1", name: "Серверы", kind: "page", value: t }]; SF.cur = "p1"; openSafe(); SF.k = {}; SF.view = "card";
        sfCard(document.getElementById("safe-body")); }""", TEXT); ph.wait_for_timeout(200)
    ok("Скрыт" in ph.inner_text("#sf-pv"), "телефон: страница скрыта, пока не «Показать»")
    ph.click("#sf-show"); ph.wait_for_timeout(150)
    t = ph.inner_text("#sf-pv")
    ok(ph.locator("#sf-pv .sp-kv").count() == 7 and "Серверы" in t and all(s not in t for s in SECRETS), "телефон: «Показать» — страница как документ, секреты точками")
    ph.evaluate("window._copies = []; Dewiar.copy = (x) => { window._copies.push(x); return true; }; 0")
    ph.click("#sf-pv .sp-kv:has-text('Код домофона') .sp-ib"); ph.wait_for_timeout(100)
    ok(ph.evaluate("window._copies[0]") == "4711", "телефон: «Скопировать» у ряда")
    ok(ph.evaluate("document.documentElement.scrollWidth <= innerWidth"), "телефон: без прокрутки вбок")
    if SHOT:
        ph.screenshot(path=str(Path(SHOT) / "vault-read-phone.png"), full_page=True)
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
