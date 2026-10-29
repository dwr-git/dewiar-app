"""Студия → «Чат для сайта» (0.69): персонажи на выбор, окно чата справа меняется на лету (название, первое сообщение,
«Оставить контакт», цвет персонажа), черновик сохраняется сам, «Опубликовать» → ссылка и код для сайта со счётчиками,
«Отключить» — с вопросом. Без входа — сказано, где войти."""
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
  const base = { persona: "", title: "", greeting: "", brief: "", kb: "", folders: false, ask_contact: true, per_ip: 40, per_day: 500, on: false, kb_chars: 0, remote: null, error: "", recent: [], signed: true };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "sitechat_get" || c === "sitechat_save") return base;
      if (c === "sitechat_publish") return Object.assign({}, base, a.patch, { on: true, remote: { id: "abc123def0", link: "https://dewiar.pro/dwrapp/sitechat.php?id=abc123def0",
        embed: '<script src="https://dewiar.pro/dwrapp/sitechat.js" data-id="abc123def0" async></script>', today: 3, total: 41, leads_wait: 0 },
        recent: [{ ts: 1761800000, name: "Анна", contact: "+375 29 111-22-33", cid: "c1" }] });
      if (c === "sitechat_forget") return base;
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""

with sync_playwright() as p:
    b = p.chromium.launch(); errors = []
    st = b.new_page(viewport={"width": 1360, "height": 1000}); st.on("pageerror", lambda e: errors.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script(FAKE_CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("""() => { personas = [{ id: "lira", name: "Лира", color: "#5aa9e6", character: "тёплая", knowledge: [{ kind: "folder", path: "/home/u/Прайс", label: "Прайс" }] },
        { id: "patrik", name: "Патрик", color: "#e59a1f", character: "деловой", knowledge: [] }]; if (!S) S = {}; S.persona = "lira"; S.features = { clients: true }; featuresApply(); }""")
    ok(st.locator('nav button[data-p="sitechat"]').is_visible(), "в меню «Работа» — «Чат для сайта» (когда включены «Клиенты»)")
    st.evaluate("document.querySelector('nav button[data-p=\"sitechat\"]').click()"); st.wait_for_timeout(600)
    ok(st.locator("#sc-ps .co-m").count() == 2 and "on" in st.get_attribute("#sc-ps .co-m[data-id=lira]", "class"), "персонажи на выбор, текущий — отмечен")
    ok(st.is_enabled("#sc-fold") and "Прайс" in st.inner_text("#sc-foldtip"), "у Лиры есть папка «Прайс» — её можно добавить в знания")
    st.fill("#sc-title", "Чайный двор"); st.fill("#sc-greet", "Здравствуйте! Помогу выбрать чай."); st.wait_for_timeout(800)
    pv = st.inner_text("#sc-prev")
    ok("Чайный двор · ИИ-помощник" in pv and "Помогу выбрать чай" in pv and "Оставить контакт" in pv, f"окно чата справа — на лету: {pv[:120]!r}")
    ok(any(c == "sitechat_save" and a["patch"]["title"] == "Чайный двор" for c, a in st.evaluate("calls")), "черновик сохраняется сам")
    st.click("#sc-ps .co-m[data-id=patrik]"); st.wait_for_timeout(200)
    ok("Патрик" in st.inner_text("#sc-prev") and st.evaluate("getComputedStyle(document.querySelector('#sc-prev')).getPropertyValue('--sc').trim()") == "#956313"
       and st.is_disabled("#sc-fold"), "выбрали Патрика — его имя и цвет (темнее — чтобы белый текст читался); папок у него нет")
    st.fill("#sc-kb", "Доставка 300 ₽"); st.wait_for_timeout(100)
    ok("14 из 60 000" in st.inner_text("#sc-kbn"), "счётчик знаков знаний")
    st.click("#sc-pub"); st.wait_for_timeout(400)
    pub = [a for c, a in st.evaluate("calls") if c == "sitechat_publish"]
    ok(pub and pub[0]["patch"]["persona"] == "patrik" and pub[0]["patch"]["kb"] == "Доставка 300 ₽" and pub[0]["patch"]["folders"] is False, f"«Опубликовать»: {pub[:1]}")
    ok(st.locator("#sc-live").is_visible() and st.input_value("#sc-link").endswith("id=abc123def0") and "sitechat.js" in st.input_value("#sc-code")
       and st.inner_text("#sc-pub") == "Обновить на сайте", "после — ссылка, код для сайта, «Обновить на сайте»")
    ok("3вопросов сегодня" in st.inner_text("#sc-stats").replace("\n", "") and "Анна" in st.inner_text("#sc-leads"), "счётчики и последние заявки")
    st.locator("#p-sitechat").screenshot(path="/tmp/claude-0/sitechat_studio.png")
    st.click("#sc-off"); st.wait_for_timeout(200)
    ok(st.locator(".dwq").count() == 1, "«Отключить» — сначала вопрос")
    st.click(".dwq .yes"); st.wait_for_timeout(300)
    ok(any(c == "sitechat_forget" for c, a in st.evaluate("calls")) and st.locator("#sc-live").is_hidden(), "отключили")
    ok(not errors, f"без ошибок: {errors[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
