"""Сейф паролей (29.10, владелец): «1. при сохранении вместо „Сохранить“ случайно нажимаю „Добавить“, и всё заполненное
в форме очищается; 2. хочется страничку с множеством паролей или секретной информацией — не по одному, а всё в кучу,
как на обычной странице, но чтобы тоже безопасно лежало и шифровалось».
Набранное не теряется: пока форма открыта, «Добавить» спрятана; «Отмена», Esc, другая запись — только через вопрос.
Секретная страница: вид «Страница» в той же форме, текст до 50 000 знаков, то же шифрование ключом компьютера; в списке —
название и число строк, текст — только по «Открыть» (vault_reveal); открытая без дела — прячется сама, уход из раздела —
закрывает; голосом страница не зачитывается и не выводится в ответ — «откройте в студии»."""
import os, re, sys, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


# ---------- ядро ----------
from vault import Vault  # noqa: E402
d = Path(tempfile.mkdtemp())
v = Vault(d / "v.bin", d / "k.key")
TEXT = "Сервер 1: root / Пароль-1\nСервер 2: admin / Пароль-2\n\nКлюч API: sk-тест\n" * 40
pw = v.put("Серверы", "один-пароль")
pgx = v.put("Серверы", TEXT, kind="page")
ok(pgx["id"] != pw["id"] and pgx["kind"] == "page" and "value" not in pgx, "страница с тем же названием, что у пароля, — отдельная запись, без текста в ответе")
ok(v.get(pw["id"])["value"] == "один-пароль", "пароль с тем же названием не затёрт")
lst = {x["id"]: x for x in v.list()}
ok(lst[pgx["id"]]["lines"] == 120 and "value" not in lst[pgx["id"]] and "lines" not in lst[pw["id"]], f"в списке — число строк, текста нет: {lst[pgx['id']].get('lines')}")
blob = (d / "v.bin").read_bytes()
ok("Пароль-1".encode() not in blob and "sk-тест".encode() not in blob, "на диске страница зашифрована")
v2 = Vault(d / "v.bin", d / "k.key")
ok(v2.get(pgx["id"])["value"] == TEXT, "открывается тем же ключом — текст целиком")
try:
    v.put("Огромная", "x" * 50001, kind="page"); ok(False, "больше 50 000 знаков принято")
except ValueError as e:
    ok("50000" in str(e), f"страница — до 50 000 знаков: «{e}»")
try:
    v.put("Пустая", "  \n ", kind="page"); ok(False, "пустая страница принята")
except ValueError as e:
    ok("пуст" in str(e), f"пустую страницу не сохраняет: «{e}»")
v.put("Серверы", "Сервер 3\n", item_id=pgx["id"], kind="page")
ok(v.get(pgx["id"])["value"] == "Сервер 3\n" and v.get(pgx["id"])["kind"] == "page", "правка страницы — по id, вид остаётся")
ex = v.export_plain(); v3 = Vault(d / "v3.bin", d / "k.key"); v3.import_plain(ex)
ok(any(x.get("kind") == "page" for x in v3.list()), "закрытая копия (слепок) переносит и страницы")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('kind=a.get("kind")' in src and 'a.get("kind") != "page"' in src, "vault_put: вид передаётся; пустой текст страницы не подменяется прежним")
mus = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok('x.get("kind") == "page"' in mus and "откройте её в студии" in mus, "голосом страница не выводится в ответ — «откройте в студии»")

# ---------- студия ----------
FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'clip_secret' ? ((t, s) => { (window.clips = window.clips || []).push([t, s]); return Promise.resolve(true); }) : (...a) => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.V = [
    { id: "a1", name: "Почта", login: "m@ya.ru", url: "", note: "", value: "Секрет-123" },
    { id: "p1", name: "Серверы", kind: "page", value: "dev: root / Пароль-dev\nprod: admin / Пароль-prod\n" }];
  const pub = () => V.map(x => { const o = Object.assign({}, x, { length: x.value.length }); if (x.kind === "page") o.lines = x.value.split("\n").filter(l => l.trim()).length; delete o.value; return o; }).sort((a, b) => a.name.localeCompare(b.name));
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "vault_list") return { items: pub() };
      if (c === "vault_reveal") return { value: (V.find(x => x.id === a.id) || {}).value || "" };
      if (c === "vault_put") { let x = a.id && V.find(i => i.id === a.id);
        if (x) Object.assign(x, a); else { x = Object.assign({ id: "n" + V.length }, a); V.push(x); }
        const o = Object.assign({}, x); delete o.value; return { item: o, items: pub() }; }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={"width": 1400, "height": 950}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"vault\"]').click()"); pg.wait_for_timeout(500)
    # 1. «Добавить» не стирает набранное
    pg.click("#vl-add"); pg.wait_for_timeout(150)
    pg.fill("#vl-name", "Банк"); pg.fill("#vl-login", "ivan"); pg.fill("#vl-value", "Очень-секретно-1")
    ok(pg.is_hidden("#vl-add"), "пока форма открыта — «Добавить» спрятана, по ней не промахнуться")
    pg.evaluate("document.querySelector('#vl-add').click()"); pg.wait_for_timeout(150)
    ok(pg.input_value("#vl-name") == "Банк" and pg.input_value("#vl-value") == "Очень-секретно-1", "даже если нажать «Добавить» — набранное на месте")
    pg.click("#vl-cancel"); pg.wait_for_timeout(200)
    ok(pg.locator(".dwq button.yes").count() == 1 and pg.input_value("#vl-name") == "Банк", "«Отмена» с набранным — сначала вопрос")
    pg.click(".dwq button:not(.yes)"); pg.wait_for_timeout(200)
    ok(pg.is_visible("#vl-form") and pg.input_value("#vl-login") == "ivan", "«нет» — форма и данные остаются")
    pg.click(".vl-item[data-id='a1'] [data-v='edit']"); pg.wait_for_timeout(200)
    ok(pg.locator(".dwq button.yes").count() == 1, "«Изменить» другую запись при набранном — тоже вопрос")
    pg.click(".dwq button:not(.yes)"); pg.wait_for_timeout(200)
    pg.click("#vl-save"); pg.wait_for_timeout(300)
    ok(pg.evaluate("V.some(x => x.name === 'Банк' && x.value === 'Очень-секретно-1')") and pg.is_hidden("#vl-form") and pg.is_visible("#vl-add"),
       "«Сохранить» — запись в сейфе, «Добавить» снова видна")
    pg.click("#vl-add"); pg.wait_for_timeout(100); pg.press("#vl-name", "Escape"); pg.wait_for_timeout(150)
    ok(pg.is_hidden("#vl-form") and pg.locator(".dwq button.yes").count() == 0, "пустую форму Esc закрывает без вопросов")
    # 2. секретная страница
    ok(pg.evaluate("document.querySelector('.vl-item[data-id=\"p1\"]').classList.contains('vl-page')") and "2 строки" in pg.text_content(".vl-item[data-id='p1']"),
       "в списке страница — значком страницы и числом строк")
    ok("Пароль-dev" not in pg.content(), "текст страницы в разметке не лежит, пока её не открыли")
    pg.click(".vl-item[data-id='p1'] .vl-name"); pg.wait_for_timeout(300)
    ok(pg.input_value("#vl-ptext").startswith("dev: root") and pg.is_visible("#vl-pg") and pg.is_hidden("#vl-grid") and pg.is_hidden("#vl-kind")
       and pg.text_content("#vl-form-h") == "Секретная страница", "нажали на страницу — открыта для чтения и правки")
    ok(["vault_reveal", {"id": "p1"}] in pg.evaluate("calls"), "текст — только по vault_reveal")
    pg.fill("#vl-ptext", "dev: root / Пароль-dev\nprod: admin / Пароль-prod\nstage: x / y\n"); pg.dispatch_event("#vl-ptext", "input")
    pg.press("#vl-ptext", "Control+Enter"); pg.wait_for_timeout(300)
    put = pg.evaluate("calls.filter(c => c[0] === 'vault_put').pop()[1]")
    ok(put == {"name": "Серверы", "value": "dev: root / Пароль-dev\nprod: admin / Пароль-prod\nstage: x / y\n", "kind": "page", "id": "p1"} and pg.is_visible("#vl-form"),
       f"Ctrl+Enter — сохранить, страница остаётся открытой: {put}")
    pg.click("#vl-pcopy"); pg.wait_for_timeout(150)
    ok(pg.evaluate("window.clips && window.clips.pop()[0]").startswith("dev: root"), "«Скопировать всё» — через окно, со стиранием из буфера")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "vault-page.png"))
    pg.evaluate("document.querySelector('nav button[data-p=\"home\"]').click()"); pg.wait_for_timeout(200)
    ok(pg.is_hidden("#vl-form") and pg.input_value("#vl-ptext") == "", "ушли из сейфа — страница закрыта, текст из поля убран")
    pg.evaluate("document.querySelector('nav button[data-p=\"vault\"]').click()"); pg.wait_for_timeout(300)
    # новая страница
    pg.click("#vl-add"); pg.wait_for_timeout(100); pg.fill("#vl-name", "Ключи API")
    pg.click("#vl-kind [data-k='page']"); pg.wait_for_timeout(100)
    ok(pg.input_value("#vl-pname") == "Ключи API" and pg.evaluate("document.activeElement.id") == "vl-ptext" and pg.text_content("#vl-form-h") == "Новая страница",
       "«Страница» — название переходит, курсор в тексте")
    pg.click("#vl-save"); pg.wait_for_timeout(200)
    ok("пустая" in pg.text_content("#vl-res"), "пустую страницу не сохраняет — подсказка")
    pg.fill("#vl-ptext", "openai: sk-1\n"); pg.click("#vl-save"); pg.wait_for_timeout(300)
    ok(pg.evaluate("V.some(x => x.name === 'Ключи API' && x.kind === 'page')"), "новая страница — в сейфе")
    if SHOT: pg.screenshot(path=str(Path(SHOT) / "vault-page-list.png"))
    # сама прячется
    pg.evaluate("vlFormClose(); VL_IDLE_TEST = 1"); pg.click(".vl-item[data-id='p1'] .vl-name"); pg.wait_for_timeout(300)
    pg.evaluate("clearTimeout(VL.idle); VL.idle = setTimeout(() => {}, 0)")
    js = (ROOT / "ui/studio/vault.js").read_text(encoding="utf-8")
    ok("VL_PAGE_IDLE = 3 * 60000" in js and "if (!vlDirty()) { vlFormClose();" in js, "открытая страница без правок прячется сама через 3 минуты")
    # 29.10 вечер, владелец: «хотел восстановить из слепка — и не вижу»: кнопка прямо в сейфе и ссылка в пустом сейфе
    pg.evaluate("() => { window._sr = 0; window.snRestore = () => { _sr++; }; }")
    pg.click("#vl-keep-back"); pg.wait_for_timeout(100)
    pg.evaluate("window.V = []; loadVaultPage()"); pg.wait_for_timeout(300)
    pg.click("#vl-empty-back"); pg.wait_for_timeout(100)
    ok(pg.evaluate("_sr") == 2, "«Восстановить из слепка» — в карточке сейфа и в пустом сейфе: тот же выбор слепка, что на «Главной»")
    pg.set_viewport_size({"width": 720, "height": 900}); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
