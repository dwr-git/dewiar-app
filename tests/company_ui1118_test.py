"""«Компания» в студии (пилот 18.11; ui/studio/company.js): раздела в меню нет.
- «Мозг» → «ИИ-баланс»: руководитель — котёл и «Места и приглашения»; сотрудник — «за ответы платит компания», свой лимит,
  «Пополнить» спрятано; без компании — «Код от компании», войти по коду (неверный формат — подсказка здесь же);
- «Поручения» (руководитель): котёл, места с расходом за месяц и «на связи», «Пригласить сотрудника» → код на 14 дней,
  лимит человеку, «Убрать» — через вопрос; разговоров нет;
- впервые увидели свою компанию — набор «Для работы»: рабочее на виду и первым на «Главной», личное скрыто (раз и молча).
DEWIAR_SHOTS=<папка> — снимки company-team.png, company-brain.png."""
import copy, json, os, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from settings import DEFAULTS  # noqa: E402
SS = copy.deepcopy(DEFAULTS); SS["ui"]["preset"] = "done"; SS["ui"]["welcome"] = "done"
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


now = int(time.time())
OWNER = {"connected": True, "tail": "ab12", "active": True, "percent": 80, "balance": 41.5, "turns": 9000, "per_taler": 220,
         "label": "Электро Плюс", "service": "Компания «Электро Плюс»", "pay": [], "topup": "",
         "company": {"id": 3, "name": "Электро Плюс", "role": "owner", "left": 41.5, "month_left": 21.5, "bought": 20, "seat_amt": 15,
                     "seats_n": 3, "lim": 0, "lim_default": 5, "spent_month": 1.2,
                     "seats": [{"key": 11, "name": "Руководитель", "role": "owner", "lim": 0, "seen": now - 60, "spent_month": 1.2},
                               {"key": 12, "name": "Иван, монтажник", "role": "member", "lim": 0, "seen": now - 7200, "spent_month": 4.6},
                               {"key": 13, "name": "Олег", "role": "member", "lim": 8, "seen": 0, "spent_month": 0.3}],
                     "invites": [{"code": "ABCD-EFGH", "name": "Пётр", "until": now + 86400 * 10}]}}
MEMBER = dict(OWNER, company=dict(OWNER["company"], role="member", lim=5, spent_month=4.6, seats=None, invites=None))
NONE = {"connected": True, "tail": "zz99", "active": True, "percent": 60, "balance": 3, "turns": 600, "per_taler": 200, "label": "Мой ключ",
        "service": "Dewiar Облако", "pay": [], "topup": ""}
CORE = r"""
(() => { window.calls = []; window.__CS = %s; window.SS = %s;
  const merge = (a, b) => { for (const k in b) { if (b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) && a[k] && typeof a[k] === "object") merge(a[k], b[k]); else a[k] = b[k]; } return a; };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "cloud_status") return window.__CS;
      if (c === "sitechat_get") return { kb_chars: 640, remote: { id: "abc", link: "https://dewiar.pro/dwrapp/sitechat.php?id=abc", tg: "" } };
      if (c === "team_set") return { members: [{ id: "m1", name: "Сергей" }, { id: "m2", name: "Олег" }], leads_to: a.leads_to || "" };
      if (c === "team_hire") return a.name ? { members: [], hired: { id: "m9", name: a.name, link: "https://dewiar.pro/dwrapp/download.php?work=Tok123456789", expires: Date.now() / 1000 + 14 * 86400 } } : Promise.reject(new Error("впишите имя"));
      if (c === "cloud_company") {
        if (a.op === "invite") return { ok: true, code: "QWER-TY23", until: Date.now() / 1000 + 14 * 86400, how: "Сотрудник вводит код в Лире: «Мозг» → «Баланс» → «Ввести код компании»." };
        if (a.op === "create") return { ok: true, moved: 3, message: `Компания «${a.name}» создана, ваш баланс — в её котле. Дальше — «Поручения»: там «Запуск компании».`, company: {} };
        if (a.op === "join") { if (a.code.replace("-", "").length !== 8) throw new Error("Код компании не подошёл или устарел — попросите у руководителя новый."); return { ok: true, message: "Вы в компании «Электро Плюс»: ответы Лиры теперь оплачивает компания. Ваш собственный баланс сохранится.", company: {} }; }
        if (a.op === "seat") { const co = JSON.parse(JSON.stringify(window.__CS.company)); co.seats.find(s => s.key === a.key).lim = +a.lim; return { ok: true, company: co }; }
        return { ok: true, company: window.__CS.company }; }
      if (c === "settings_save") { merge(SS, a.patch || {}); return JSON.parse(JSON.stringify(SS)); }
      if (c === "settings") return SS;
      return {}; };
    setTimeout(() => core.emit("hello", { settings: JSON.parse(JSON.stringify(SS)), personas: [], persona: "lira", presets: {}, piper_voices: [], voice_fx: [] }), 200); };
  ready(); })();
"""
SHOT = os.environ.get("DEWIAR_SHOTS")
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []

    def page(cs):
        pg = b.new_page(viewport={"width": 1320, "height": 980}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://"), lambda r: r.abort())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(true) }) };")
        pg.add_init_script(CORE % (json.dumps(cs, ensure_ascii=False), json.dumps(SS, ensure_ascii=False)))
        pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
        pg.evaluate("document.querySelector('nav button[data-p=\"brain\"]').click()"); pg.wait_for_timeout(300)
        pg.evaluate("(c) => cloudFill(c)", cs); pg.wait_for_timeout(300)
        return pg

    # ---------- руководитель ----------
    pg = page(OWNER)
    t = pg.inner_text("#cloud-card")
    ok("Компания «Электро Плюс»" in t and "Вы — руководитель" in t and "Места и приглашения" in t and pg.is_hidden("#cc-join"), "«Мозг»: руководитель видит котёл компании и путь к местам")
    if SHOT:
        Path(SHOT).mkdir(parents=True, exist_ok=True); pg.locator("#cloud-card").screenshot(path=str(Path(SHOT) / "company-brain.png"))
    ui = pg.evaluate("S.ui")
    ok(ui.get("co_seen") == 3 and "team" not in (ui.get("nav_hide") or []) and "music" not in (ui.get("home_apps") or []) and "family" not in (ui.get("home_apps") or [])
       and (ui.get("home_apps") or [])[:3] == ["team", "clients", "insight"], f"впервые своя компания — набор «Для работы»: {(ui.get('home_apps') or [])[:4]}, скрыто {len(ui.get('nav_hide') or [])}")
    feats = pg.evaluate("S.features")
    ok(feats.get("team") is True and feats.get("clients") is True, "«Для работы» включает «Поручения» и «Клиентов»")
    pg.evaluate("document.getElementById('cc-co-go').click()"); pg.wait_for_timeout(400)
    ok(pg.evaluate("document.getElementById('p-team').classList.contains('cur')") and pg.is_visible("#tm-co"), "«Места и приглашения» — «Поручения», карточка компании сверху")
    tc = pg.inner_text("#tm-co")
    ok("41,5" in tc and "Иван, монтажник" in tc and "4,6 из 5 тал. за месяц" in tc and "0,3 из 8" in tc and "ещё не был" in tc and "ABCD-EFGH" in tc,
       "котёл, места: расход за месяц из лимита, «на связи», ждущие коды")
    ok("привет" not in tc.lower(), "разговоров нет — только расход")
    ok(not re.search(r"котёл|котле|котла|доля месяца|начислено", tc.lower()) and "тал. на балансе" in tc and "потратил 4,6 из 5 тал. за месяц" in tc,
       f"18.11 (партнёр: «вообще непонятно, о чём речь»): без «котла» и «доли месяца» — баланс компании и «потратил» у каждого")
    pg.click("#co-inv"); pg.fill("#co-nm", "Пётр, электрик"); pg.click("#co-mk"); pg.wait_for_timeout(300)
    nw = pg.inner_text("#co-new")
    ok("download.php?work=Tok123456789" in nw and ["team_hire", {"name": "Пётр", "role": "электрик"}] in pg.evaluate("calls")
       and "оплатит компания" in nw and "14 дн." in nw,
       "«Пригласить сотрудника» — одна ссылка: «Поручения» в приложении и место в компании («Пётр, электрик» → имя и чем занят)")
    if SHOT:
        pg.locator("#co-new").screenshot(path=str(Path(SHOT) / "company-invite.png"))
    pg.click("#co-pc"); pg.wait_for_timeout(300)
    ok("QWER-TY23" in pg.inner_text("#co-new") and any(c == "cloud_company" and a.get("op") == "invite" and a.get("name") == "Пётр" for c, a in pg.evaluate("calls")),
       "«Работает только на компьютере?» — код компании для «Мозга»")
    pg.click("#co-done"); pg.wait_for_timeout(200)
    pg.evaluate("""() => { TM = Object.assign({}, TM || {}, { members: [{ id: "m1", name: "Сергей" }, { id: "m2", name: "Олег" }], leads_to: "" }); core.emit("team", TM); }"""); pg.wait_for_timeout(200)
    opts = pg.evaluate("[...document.querySelectorAll('#co-leads option')].map(o => o.textContent)")
    ok(opts == ["никому, только в «Клиенты»", "Сергей", "Олег"], f"«Заявки клиентов — поручать»: никому или сотрудник: {opts}")
    pg.select_option("#co-leads", "m1"); pg.wait_for_timeout(300)
    ok(["team_set", {"leads_to": "m1"}] in pg.evaluate("calls") and pg.evaluate("TM.leads_to") == "m1", "выбрали Сергея — заявки ему поручением")
    pg.wait_for_timeout(200)
    st = pg.inner_text("#tm-co .cz-steps")
    ok("Запуск компании" in st and "4 из 5" in st and pg.locator("#tm-co .cz-steps li:not(.on)").count() == 1 and "Telegram-бота" in st,
       f"«Запуск компании»: 4 из 5 по настоящим данным, остался Telegram-бот: {st[:160]!r}")
    if SHOT:
        pg.locator("#tm-co .cz-steps").screenshot(path=str(Path(SHOT) / "company-steps.png"))
    pg.evaluate("""() => core.emit("sitechat", { site: "", kb_chars: 640, remote: { id: "abc", link: "x", tg: "@elektro_help_bot" } })"""); pg.wait_for_timeout(300)
    ok(pg.locator("#tm-co .cz-steps").count() == 0 and "Компания запущена" in pg.inner_text("#tm-co"), "подключили бота — все пять шагов: «Компания запущена» одной строкой")
    pg.evaluate("""() => core.emit("sitechat", { site: "", kb_chars: 640, remote: { id: "abc", link: "x", tg: "" } })"""); pg.wait_for_timeout(300)
    pg.click('#tm-co [data-go="chat"]'); pg.wait_for_timeout(300)
    ok(pg.evaluate("document.getElementById('p-sitechat').classList.contains('cur')"), "«Открыть» у шага — «Чат для сайта»")
    pg.evaluate("document.querySelector('nav button[data-p=\"team\"]').click()"); pg.wait_for_timeout(300)
    pg.click('#tm-co [data-lim="12"]'); pg.fill("#tm-co .co-limin", "7,5"); pg.click("#tm-co .co-act .btn.primary"); pg.wait_for_timeout(300)
    ok(["cloud_company", {"op": "seat", "key": 12, "lim": "7.5"}] in pg.evaluate("calls") and "Лимит 7,5" in pg.inner_text("#tm-co"),
       f"лимит человеку — 7,5 тал. в месяц: {pg.evaluate('[...document.querySelectorAll(\'.toast, #toast\')].map(t => t.textContent).join(\' | \')')}")
    pg.click('#tm-co [data-rm="13"]'); pg.wait_for_timeout(200)
    ok(pg.locator(".dwq button.yes").count() == 1 and "Убрать «Олег»" in pg.inner_text(".dwq"), "«Убрать» — сначала вопрос")
    pg.click(".dwq button:not(.yes)"); pg.wait_for_timeout(500)
    if SHOT:
        pg.locator("#tm-co").screenshot(path=str(Path(SHOT) / "company-team.png"))
    pg.set_viewport_size({"width": 700, "height": 900}); pg.wait_for_timeout(150)
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "узкое окно — без прокрутки вбок")
    pg.close()
    # ---------- сотрудник ----------
    pg = page(MEMBER)
    t = pg.inner_text("#cloud-card")
    ok("За ответы Лиры платит компания «Электро Плюс»" in t and "лимит — 5 тал. в месяц, потрачено 4,6" in t and "Выйти из компании" in t, "сотрудник: платит компания, свой лимит и потрачено")
    ok(pg.is_hidden("#cc-top") and pg.is_hidden("#tm-co"), "сотруднику «Пополнить» не нужно — пополняет руководитель; котла с местами не видит")
    pg.close()
    # ---------- без компании ----------
    pg = page(NONE)
    ok(pg.is_visible("#cc-join") and pg.is_hidden("#cc-co"), "без компании — «Код от компании»")
    pg.click("#cc-join > summary"); pg.fill("#cc-join-code", "12"); pg.click("#cc-join-go"); pg.wait_for_timeout(100)
    ok("8 знаков" in pg.inner_text("#cc-join-res"), "неверный формат — подсказка здесь же, без запроса")
    pg.fill("#cc-join-code", "qwer-ty23"); pg.click("#cc-join-go"); pg.wait_for_timeout(300)
    ok(["cloud_company", {"op": "join", "code": "qwer-ty23"}] in pg.evaluate("calls") and "Вы в компании «Электро Плюс»" in pg.inner_text("#cc-join-res"), "войти по коду — словами")
    ok(pg.is_visible("#cc-new-go") and pg.is_visible("#cc-new-mv"), "«Вы руководитель? Создайте компанию» — тут же; баланс есть — галочка «Перенести мой баланс»")
    pg.click("#cc-new-go"); pg.wait_for_timeout(100)
    ok("название" in pg.inner_text("#cc-new-res"), "без названия — подсказка, без запроса")
    pg.fill("#cc-new-name", "Свет и Ток"); pg.click("#cc-new-go"); pg.wait_for_timeout(200)
    ok(pg.locator(".dwq").count() == 1 and "баланса компании" in pg.inner_text(".dwq") and "перейдёт" in pg.inner_text(".dwq"), "сначала вопрос: что изменится с деньгами")
    pg.click(".dwq .yes"); pg.wait_for_timeout(300)
    ok(["cloud_company", {"op": "create", "name": "Свет и Ток", "move": True}] in pg.evaluate("calls") and "создана" in pg.inner_text("#cc-new-res"),
       "«Создать компанию» — сам, без администратора")
    if SHOT:
        pg.locator("#cc-join").screenshot(path=str(Path(SHOT) / "company-create.png"))
    pg.close()
    # ---------- телефон ----------
    import subprocess, tempfile
    www = Path(tempfile.mkdtemp()) / "www"
    subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
    ph = b.new_page(viewport={"width": 393, "height": 852}); ph.on("pageerror", lambda e: errs.append(str(e)))
    ph.route(re.compile(r"^https?://"), lambda r: r.abort())
    ph.goto((www / "index.html").as_uri()); ph.wait_for_timeout(900)
    ph.evaluate("""() => { S.llm = Object.assign({}, S.llm, { kind: "openai", cloud: true, api_key: "dw-test-key-1234", base_url: "https://x.invalid/cloud.php?p=", model: "chat" }); saveS(); }""")
    ph.evaluate("openSettings ? openSettings('brain') : 0"); ph.wait_for_timeout(500)
    if ph.locator("#cl-card").count():
        ph.evaluate("(c) => cloudFill(c)", MEMBER); ph.wait_for_timeout(150)
        t = ph.inner_text("#cl-card")
        ok("За ответы Лиры платит компания «Электро Плюс»" in t and "Выйти из компании" in t and ph.is_hidden("#cl-how") and ph.is_hidden("#cl-join"),
           "телефон: сотрудник — платит компания, «Пополнить» спрятано, «Выйти»")
        ph.evaluate("(c) => cloudFill(c)", NONE); ph.wait_for_timeout(150)
        ok(ph.locator("#cl-join").count() == 1 and not ph.evaluate("document.getElementById('cl-join').hidden"), "телефон: без компании — «Код от компании»")
    else:
        ok(False, "телефон: карточка «Баланс» не открылась")
    b.close()
ok(not errs, f"без ошибок на странице: {errs[:3]}")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
