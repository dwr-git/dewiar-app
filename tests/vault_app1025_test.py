"""«Сейф паролей» и плагины на «Главной» (0.45, владелец: «иконку-кнопку „Сейф паролей“ — чтобы удобно было действительно
там сохранять пароли, и потом искать нужный пароль от нужного сервиса»; «плагины также показывать на главной»).
Ядро (vault.py): логин и сайт у записи; правка без нового пароля — пароль прежний; значения в списке нет.
Студия: свой раздел и значок на «Главной»; поиск по названию, логину, сайту, заметке; Enter — скопировать первый;
«Скопировать» — через окно (clip_secret, стирание через 30 с); «Показать» — 15 с; «Придумать» — 16 знаков всех видов;
правка, удаление; «Безопасность» ведёт в сейф. «Главная»: установленный плагин — значок, нажать — его карточка."""
import json, os, re, sys, tempfile
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
x = v.put("Почта Яндекса", "Секрет-123", login="misha@ya.ru", url="mail.yandex.ru")
ok(x["login"] == "misha@ya.ru" and x["url"] == "mail.yandex.ru" and "value" not in x, "запись: логин и сайт видны, пароля в ответе нет")
lst = v.list()
ok(lst[0]["login"] == "misha@ya.ru" and "value" not in lst[0] and lst[0]["length"] == 10, "список — без паролей, с длиной")
v.put("Почта Яндекса", "Новый-456", item_id=x["id"])
ok(v.get(x["id"])["value"] == "Новый-456" and v.get(x["id"])["login"] == "misha@ya.ru", "правка без логина — логин прежний")
src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('if a.get("id") and not val:' in src, "правка в студии без нового пароля — пароль прежний (vault_put)")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("def clip_secret(self, text, sec=30):" in app and "CanIncludeInClipboardHistory" in app and "cb.wait_for_text() == text" in app,
   "окно: пароль в буфер и стирание через 30 с, только если там всё ещё он; Windows — не в журнал буфера")

FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => k === 'clip_secret' ? ((t, s) => { (window.clips = window.clips || []).push([t, s]); return Promise.resolve(true); }) : (...a) => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.V = [
    { id: "a1", name: "Почта Яндекса", login: "misha@ya.ru", url: "mail.yandex.ru", note: "", value: "Секрет-123" },
    { id: "a2", name: "Пароль от вайфая", login: "", url: "", note: "дома, роутер в коридоре", value: "кот12345" },
    { id: "a3", name: "Домофон", login: "", url: "", note: "подъезд 2", value: "4512" }];
  const pub = () => V.map(x => { const o = Object.assign({}, x, { length: x.value.length }); delete o.value; return o; }).sort((a, b) => a.name.localeCompare(b.name));
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "vault_list") return { items: pub() };
      if (c === "vault_reveal") return { value: (V.find(x => x.id === a.id) || {}).value || "" };
      if (c === "vault_put") { let x = a.id && V.find(i => i.id === a.id);
        if (x) Object.assign(x, { name: a.name, login: a.login, url: a.url, note: a.note }, a.value ? { value: a.value } : {});
        else V.push({ id: "n" + V.length, name: a.name, login: a.login, url: a.url, note: a.note, value: a.value }); return { items: pub() }; }
      if (c === "vault_delete") { window.V = V.filter(x => x.id !== a.id); return { items: pub() }; }
      if (c === "plugins") return { plugins: [{ id: "garden", name: "Огород", tagline: "полив и посадки", icon: "🌱", color: "#2fae74", installed: true, category: "Дом", says: [], settings: [] },
                                             { id: "cars", name: "Машина", tagline: "ТО и страховка", icon: "🚗", color: "#5b8def", installed: false, category: "Дом" }], skills: [] };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
SHOT = os.environ.get("SHOT_DIR")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    nav = pg.evaluate("[...document.querySelectorAll('nav button[data-p]')].map(b => b.dataset.p)")
    ok("vault" in nav and nav.index("vault") == nav.index("pay") + 1, "«Сейф паролей» — в меню, после «Платежей»")
    pg.evaluate("document.querySelector('nav button[data-p=\"vault\"]').click()"); pg.wait_for_timeout(500)
    ok(pg.evaluate("document.activeElement.id") == "vl-q", "открыли сейф — курсор сразу в поиске")
    rows = pg.evaluate("[...document.querySelectorAll('#vl-list .vl-item .vl-name')].map(e => e.textContent)")
    ok(rows == ["Домофон", "Пароль от вайфая", "Почта Яндекса"], f"все записи по алфавиту: {rows}")
    ok("Секрет-123" not in pg.content() and "кот12345" not in pg.content(), "в разметке страницы паролей нет")
    ok(pg.evaluate("document.querySelector('.vl-item[data-id=\"a2\"] .vl-mono').textContent") == "Wi", "у вайфая — значок «Wi»")
    pg.fill("#vl-q", "wifi"); pg.wait_for_timeout(100)
    ok(pg.evaluate("[...document.querySelectorAll('#vl-list .vl-item')].map(e => e.dataset.id)") == ["a2"], "поиск «wifi» находит «Пароль от вайфая»")
    pg.fill("#vl-q", "коридор"); pg.wait_for_timeout(100)
    ok(pg.evaluate("[...document.querySelectorAll('#vl-list .vl-item')].map(e => e.dataset.id)") == ["a2"], "поиск — и по заметке")
    pg.fill("#vl-q", "yandex"); pg.wait_for_timeout(100)
    ok(pg.evaluate("[...document.querySelectorAll('#vl-list .vl-item')].map(e => e.dataset.id)") == ["a1"] and pg.locator("#vl-list mark").count() >= 1,
       "поиск — по сайту, найденное подсвечено")
    pg.press("#vl-q", "Enter"); pg.wait_for_timeout(200)
    ok(pg.evaluate("window.clips") == [["Секрет-123", 30]], f"Enter — пароль первой записи в буфер через окно, стереть через 30 с: {pg.evaluate('window.clips')}")
    ok("сотрётся" in pg.text_content("#toast") if pg.locator("#toast").count() else True, "сказано, что сотрётся из буфера")
    pg.press("#vl-q", "Escape"); pg.wait_for_timeout(100)
    ok(pg.locator("#vl-list .vl-item").count() == 3, "Esc — поиск сброшен")
    pg.click(".vl-item[data-id='a3'] [data-v='show']"); pg.wait_for_timeout(150)
    ok(pg.text_content(".vl-item[data-id='a3'] .vl-val") == "4512", "«Показать» — пароль на экране")
    pg.click(".vl-item[data-id='a3'] [data-v='show']"); pg.wait_for_timeout(100)
    ok("4512" not in pg.text_content(".vl-item[data-id='a3'] .vl-val"), "ещё раз — снова скрыт (и сам скроется через 15 с)")
    # добавить
    pg.click("#vl-add"); pg.wait_for_timeout(150)
    ok(pg.is_visible("#vl-form") and pg.evaluate("document.activeElement.id") == "vl-name", "«Добавить» — форма, курсор в названии")
    pg.fill("#vl-name", "Госуслуги"); pg.fill("#vl-login", "+375 29 000-00-00"); pg.fill("#vl-url", "gosuslugi.ru")
    pg.click("#vl-gen"); pg.wait_for_timeout(100)
    gen = pg.input_value("#vl-value")
    ok(len(gen) == 16 and re.search(r"[a-z]", gen) and re.search(r"[A-Z]", gen) and re.search(r"\d", gen) and re.search(r"[^\w]", gen) and not re.search(r"[0O1lI]", gen),
       f"«Придумать» — 16 знаков: строчные, заглавные, цифры, знаки, без похожих: {gen}")
    ok("надёжный" in pg.text_content("#vl-str"), "подпись — «надёжный»")
    pg.fill("#vl-value", "12345"); pg.dispatch_event("#vl-value", "input")
    ok("пин-код" in pg.text_content("#vl-str"), "цифры — «пин-код или код»")
    pg.fill("#vl-value", "qwerty"); pg.dispatch_event("#vl-value", "input")
    ok("слабый" in pg.text_content("#vl-str"), "qwerty — «слабый»")
    pg.fill("#vl-value", gen); pg.click("#vl-save"); pg.wait_for_timeout(300)
    ok(pg.locator("#vl-list .vl-item").count() == 4 and pg.is_hidden("#vl-form") and pg.input_value("#vl-value") == "", "сохранили — запись в списке, форма закрыта, поле пароля очищено")
    put = pg.evaluate("calls.filter(c => c[0] === 'vault_put').pop()[1]")
    ok(put["login"] == "+375 29 000-00-00" and put["url"] == "gosuslugi.ru" and put["value"] == gen, "в ядро ушли название, логин, сайт, пароль")
    # правка без нового пароля
    pg.click(".vl-item[data-id='a1'] [data-v='edit']"); pg.wait_for_timeout(150)
    ok(pg.input_value("#vl-name") == "Почта Яндекса" and pg.input_value("#vl-value") == "" and "не изменится" in pg.get_attribute("#vl-value", "placeholder"),
       "«Изменить» — поля заполнены, пароль пустой: «не изменится»")
    pg.fill("#vl-login", "mikhail@ya.ru"); pg.click("#vl-save"); pg.wait_for_timeout(300)
    ok(pg.evaluate("V.find(x => x.id === 'a1').value") == "Секрет-123" and pg.evaluate("V.find(x => x.id === 'a1').login") == "mikhail@ya.ru",
       "правка логина — пароль прежний")
    if SHOT:
        pg.click(".vl-item[data-id='a3'] [data-v='show']"); pg.fill("#vl-q", ""); pg.dispatch_event("#vl-q", "input")
        pg.click(".vl-item[data-id='a3'] [data-v='show']"); pg.wait_for_timeout(100)
        pg.screenshot(path=f"{SHOT}/vault.png")
        pg.click("#vl-add"); pg.fill("#vl-name", "Банк"); pg.click("#vl-gen"); pg.wait_for_timeout(100); pg.screenshot(path=f"{SHOT}/vault_form.png"); pg.click("#vl-cancel")
    # удалить
    pg.click(".vl-item[data-id='a3'] [data-v='edit']"); pg.wait_for_timeout(100)
    pg.click("#vl-del"); pg.wait_for_timeout(200)
    ok(pg.locator(".dwq button.yes").count() == 1, "удаление — только после вопроса")
    pg.click(".dwq button.yes"); pg.wait_for_timeout(300)
    ok(pg.locator(".vl-item[data-id='a3']").count() == 0, "«Удалить» (после вопроса) — записи нет")
    # пусто — подсказка
    pg.evaluate("window.V = []; loadVaultPage()"); pg.wait_for_timeout(200)
    ok("запомни пароль от вайфая" in pg.text_content("#vl-list"), "пусто — подсказка, как добавить голосом")
    # «Безопасность» → сейф
    pg.evaluate("window.V = [{ id: 'z', name: 'X', value: 'y' }]")
    pg.evaluate("loadVault()"); pg.wait_for_timeout(150)
    ok(pg.text_content("#v-count") == "в сейфе: 1", "«Безопасность»: сколько в сейфе")
    pg.evaluate("document.querySelector('#v-open').click()"); pg.wait_for_timeout(200)
    ok(pg.evaluate("document.querySelector('#p-vault').classList.contains('cur')"), "«Открыть «Сейф паролей»» — в сейф")
    # «Главная»: значок сейфа и плагин
    pg.evaluate("S = S || {}; S.ui = {}; document.querySelector('nav button[data-p=\"home\"]').click(); loadHome()"); pg.wait_for_timeout(600)
    apps = pg.evaluate("[...document.querySelectorAll('#hm-apps .hm-app')].map(a => a.dataset.app)")
    ok("vault" in apps and apps.index("vault") == apps.index("pay") + 1, f"на «Главной» — «Сейф» рядом с «Платежами»: {apps}")
    ok("plg:garden" in apps and "plg:cars" not in apps, "установленный плагин — значком на «Главной», не установленный — нет")
    ok(pg.text_content(".hm-app[data-app='plg:garden'] .hm-plg") == "🌱", "у плагина — его эмодзи")
    pg.evaluate("S.ui = { home_apps: ['chat', 'notes'], home_known: HM_APPS.map(x => x.id) }; hmRender()")
    ok(pg.evaluate("hmApps()") == ["chat", "notes", "plg:garden"], f"настроили главную раньше — новый плагин появился сам, в конце: {pg.evaluate('hmApps()')}")
    pg.evaluate("S.ui = { home_apps: ['chat', 'notes'], home_known: HM_APPS.map(x => x.id).concat(['plg:garden']) }; hmRender()")
    ok(pg.evaluate("hmApps()") == ["chat", "notes"], "скрыли плагин с главной — не возвращается")
    pg.evaluate("S.ui = {}; hmRender()")
    if SHOT:
        pg.screenshot(path=f"{SHOT}/home_plg.png")
    pg.evaluate("window.plgDrawerCalls = []; const o = plgDrawer; plgDrawer = (id) => { plgDrawerCalls.push(id); }")
    pg.click(".hm-app[data-app='plg:garden'] .hm-ic"); pg.wait_for_timeout(300)
    ok(pg.evaluate("plgOpen") == "garden" and pg.evaluate("document.querySelector('#p-skills').classList.contains('cur')"), "нажали плагин — «Плагины», открывается его карточка")
    noicon = pg.evaluate("[...document.querySelectorAll('nav button[data-p]')].filter(b => !b.querySelector('svg')).map(b => b.dataset.p)")
    ok(not noicon, f"у каждого пункта меню — значок: {noicon}")
    ok(not errs, "без ошибок на странице" + (f": {errs}" if errs else ""))
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
raise SystemExit(1 if fails else 0)
