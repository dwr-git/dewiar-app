"""Студия → «Рассылка» (0.69): кому (клиентам — с числом, по метке; сотрудникам; по списку), письмо с {имя}, справа —
как его получит первый (собирает ядро), «Отправить N письмам» — только после «Отправить?»: сначала черновик, потом
отправка; ниже — ход рассылки и «Остановить». В меню — рядом с «Клиентами»/«Поручениями» (когда они включены), в
«Клиентах» — кнопка «Рассылка». У сотрудника — «+ Почта» (team_member_set)."""
import os, re, sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE_CORE = """(() => {
  window.calls = [];
  const camp = { id: "c1", subject: "Скидки ноября", kind: "ads", source: "clients", tag: "", created: Date.now() / 1000 - 600,
    status: "sending", total: 10, sent: 4, failed: 1, errors: [{ email: "bad@x.ru", err: "550 нет такого ящика" }], skipped: {}, waiting: "", body: "…" };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mailing_get") return { sources: { clients: 3, team: 1, tags: ["vip"], mail: true, day_max: 300, boxes: ["boss@firma.ru"], stop: 1 },
        list: [camp], stop: ["no@x.ru"] };
      if (c === "mailing_preview") { const n = a.source === "list" ? (a.text.match(/@/g) || []).length : a.source === "team" ? 1 : 3;
        return { n, skipped: { dup: 0, stop: a.source === "clients" ? 1 : 0 }, names: ["Анна Петрова", "Иван", "Ольга"].slice(0, n),
          sample: n && (a.subject || a.body) ? { to: "anna@mail.ru", name: "Анна Петрова", subject: a.subject.replace("{имя}", "Анна"),
            body: a.body.replace("{имя}", "Анна") + (a.kind === "ads" ? "\\n\\n—\\nНе хотите больше — ответьте «Отписаться»." : "") } : undefined }; }
      if (c === "mailing_draft") return { id: "c2", total: 3 };
      if (c === "mailing_start") return { id: a.id, status: "sending" };
      if (c === "team_get") return { connected: true, bots: [{ ch: "app", connected: true }], members: [{ id: "m1", name: "Ольга", role: "бухгалтерия", color: "#8B8CF7", joined: true, chk: "app", ch: "Dewiar", email: "" }], tasks: [], features: {} };
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""

with sync_playwright() as p:
    b = p.chromium.launch(); errors = []
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errors.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script(FAKE_CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    nav = st.locator('nav button[data-p="mailing"]')
    ok(nav.count() == 1 and nav.inner_text().startswith("Рассылка"), "в меню «Работа» — «Рассылка»")
    st.evaluate("() => { if (!S) S = {}; S.features = { clients: true }; featuresApply(); }")
    ok(nav.is_visible(), "видно, когда включены «Клиенты»")
    st.evaluate("document.querySelector('nav button[data-p=\"mailing\"]').click()"); st.wait_for_timeout(700)
    ok(st.locator("#p-mailing").is_visible(), "раздел открывается")
    ok(st.inner_text("#mg-src button.on").startswith("Клиентам") and st.inner_text("#mg-n-clients") == "3",
       "по умолчанию — клиентам (есть с почтой), рядом число")
    ok(st.locator("#mg-tagw").is_visible() and st.locator("#mg-listw").is_hidden(), "у клиентов — выбор метки, поля списка нет")
    ok("3 получателя" in st.inner_text("#mg-who") and "отписавшихся пропущу: 1" in st.inner_text("#mg-who"),
       f"сколько получат и кого пропущу: {st.inner_text('#mg-who')!r}")
    ok(st.locator("#mg-send").is_disabled(), "без темы и текста — «Отправить» недоступна")
    st.fill("#mg-subj", "{имя}, скидки"); st.fill("#mg-body", "Здравствуйте, ")
    st.click("#mg-ins"); st.wait_for_timeout(50); st.keyboard.type("!")
    st.wait_for_timeout(500)
    ok(st.input_value("#mg-body") == "Здравствуйте, {имя}!", f"«Вставить {{имя}}» — в место курсора: {st.input_value('#mg-body')!r}")
    lt = st.inner_text("#mg-letter")
    ok("Анна Петрова <anna@mail.ru>" in lt and "Анна, скидки" in lt and "Здравствуйте, Анна!" in lt, f"письмо первому — с его именем: {lt!r}")
    ok(st.is_enabled("#mg-send") and st.inner_text("#mg-send") == "Отправить 3 письма", f"кнопка: {st.inner_text('#mg-send')!r}")
    st.click("#mg-kind button[data-k='ads']"); st.wait_for_timeout(500)
    ok("Отписаться" in st.inner_text("#mg-letter") and "согласился" in st.inner_text("#mg-kindhint"), "реклама: в письме — как отписаться, подсказка о согласии")
    st.click("#mg-src button[data-s='list']"); st.wait_for_timeout(100)
    ok(st.locator("#mg-listw").is_visible() and st.locator("#mg-tagw").is_hidden(), "«По списку» — поле адресов")
    st.fill("#mg-list", "a@x.ru\nb@x.ru"); st.wait_for_timeout(500)
    ok(st.inner_text("#mg-send") == "Отправить 2 письма", "число — по списку")
    st.click("#mg-src button[data-s='clients']"); st.wait_for_timeout(500)
    st.screenshot(path="/tmp/claude-0/mailing_studio.png", full_page=False)
    st.click("#mg-send"); st.wait_for_timeout(300)
    q = st.locator(".dwq").inner_text() if st.locator(".dwq").count() else ""
    ok("3 письма клиентам" in q and not any(c == "mailing_draft" for c, a in st.evaluate("calls")), f"сначала — «Отправить?»: {q!r}")
    st.click(".dwq .yes"); st.wait_for_timeout(500)
    cs = [(c, a) for c, a in st.evaluate("calls") if c in ("mailing_draft", "mailing_start")]
    ok(len(cs) == 2 and cs[0][0] == "mailing_draft" and cs[0][1]["source"] == "clients" and cs[0][1]["kind"] == "ads"
       and cs[0][1]["subject"] == "{имя}, скидки" and cs[1] == ("mailing_start", {"id": "c2"}), f"черновик → отправка: {cs}")
    ok(st.input_value("#mg-subj") == "", "после отправки форма чистая для следующей")
    h = st.inner_text("#mg-hist")
    ok("Скидки ноября" in h and "ушло 4 из 10, не дошло 1" in h and "идёт" in h, f"ход рассылки: {h!r}")
    ok(st.get_attribute("#mg-hist .mg-bar i", "style").replace(" ", "").rstrip(";") == "width:50%", "дорожка — сколько обработано")
    st.click("#mg-hist [data-stop]"); st.wait_for_timeout(200)
    ok(any(c == "mailing_stop" and a.get("id") == "c1" for c, a in st.evaluate("calls")), "«Остановить»")
    ok(st.input_value("#mg-stoplist") == "no@x.ru", "стоп-лист виден и правится")
    # «Клиенты» → «Рассылка»
    st.evaluate("document.querySelector('nav button[data-p=\"clients\"]').click()"); st.wait_for_timeout(300)
    st.evaluate("document.querySelector('#mg-src button[data-s=\"list\"]').click()")
    st.click("#cr-mail"); st.wait_for_timeout(500)
    ok(st.locator("#p-mailing").is_visible() and st.inner_text("#mg-src button.on").startswith("Клиентам"), "из «Клиентов» — сразу рассылка клиентам")
    # сотрудник: почта
    st.evaluate("document.querySelector('nav button[data-p=\"team\"]').click()"); st.wait_for_timeout(400)
    st.evaluate("() => { TM = { connected: true, bots: [{ ch: 'app', connected: true }], members: [{ id: 'm1', name: 'Ольга', role: 'бухгалтерия', color: '#8B8CF7', joined: true, chk: 'app', ch: 'Dewiar', email: '' }], tasks: [] }; tmPeople(); }")
    mb = st.locator("#tm-people [data-mail]")
    ok(mb.count() == 1 and mb.inner_text() == "+ Почта", "у сотрудника — «+ Почта»")
    mb.evaluate("e => e.click()"); st.wait_for_timeout(200)
    st.fill(".dwq input", "olga@firma.ru"); st.click(".dwq .yes"); st.wait_for_timeout(200)
    ok(any(c == "team_member_set" and a == {"id": "m1", "email": "olga@firma.ru"} for c, a in st.evaluate("calls")), "почта сотрудника сохраняется")
    ok(st.locator("#tm-pmail").count() == 1, "при добавлении сотрудника — поле почты (необязательно)")
    st.set_viewport_size({"width": 820, "height": 860})
    st.evaluate("document.querySelector('nav button[data-p=\"mailing\"]').click()"); st.wait_for_timeout(400)
    ow = st.evaluate("document.querySelector('#p-mailing').scrollWidth <= document.querySelector('#p-mailing').clientWidth + 1")
    st.screenshot(path="/tmp/claude-0/mailing_narrow.png", full_page=True)
    ok(ow, "на узком окне — без горизонтальной прокрутки")
    ok(not errors, f"без ошибок: {errors[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
