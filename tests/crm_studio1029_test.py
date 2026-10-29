"""Студия → «Клиенты» → «CRM» (0.69): не подключено — Битрикс24 (три шага, где взять вебхук) и свой вебхук; подключено —
портал без ключа, «Новых клиентов — сразу в CRM», «Проверить связь», «Отключить». В карточке клиента — «В Битрикс24»,
после отправки — «В Битрикс24 · №42»."""
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
  window.calls = []; window.crm = { kind: "", name: "", host: "", connected: false, auto: false, last: null };
  const card = { id: "c1", name: "Иванов Пётр", company: "Ромашка", phone: "", email: "", note: "", tags: [], log: [], next: null, created: 1, updated: 1 };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "crm_get") return crm;
      if (c === "crm_connect") { if (!/rest\\/\\d+\\//.test(a.url)) throw new Error("это не ссылка входящего вебхука Битрикс24"); Object.assign(crm, { kind: a.kind, name: "Битрикс24", host: "romashka.bitrix24.ru", connected: true }); return crm; }
      if (c === "crm_auto") { crm.auto = a.on; return crm; }
      if (c === "crm_send") { card.crm = { id: "42", kind: "bitrix", host: "romashka.bitrix24.ru" }; return { id: "42", new: true, n: 0, client: card }; }
      if (c === "clients_list") return [{ id: "c1", name: card.name, company: card.company, phone: "", updated: 1, last: "", next: null, n: 0, overdue: false }];
      if (c === "client_get") return card;
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();"""

with sync_playwright() as p:
    b = p.chromium.launch(); errors = []
    st = b.new_page(viewport={"width": 1300, "height": 900}); st.on("pageerror", lambda e: errors.append(str(e)))
    st.route(re.compile(r"^https?://"), lambda r: r.abort())
    st.add_init_script(FAKE_CORE)
    st.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); st.wait_for_timeout(1500)
    st.evaluate("document.querySelector('nav button[data-p=\"clients\"]').click()"); st.wait_for_timeout(600)
    ok(st.locator("#cr-crm").count() == 0, "CRM не подключена — в карточке кнопки нет")
    st.click("#cr-tabs button[data-t='crm']"); st.wait_for_timeout(400)
    ok(st.locator("#crm-wrap").is_visible() and st.locator(".cr-main").is_hidden(), "вкладка «CRM» открывается вместо списка")
    t = st.inner_text("#crm-wrap")
    ok("Входящий вебхук" in t and "CRM" in t and "Своя CRM" in t, "два пути: Битрикс24 с шагами и свой вебхук")
    st.fill("#crm-bx-url", "https://romashka.bitrix24.ru/crm/"); st.click("#crm-bx button"); st.wait_for_timeout(300)
    ok("не ссылка входящего вебхука" in st.inner_text("#toast") and st.is_enabled("#crm-bx button"), "неверная ссылка — понятная ошибка, можно исправить")
    st.screenshot(path="/tmp/claude-0/crm_setup.png")
    st.fill("#crm-bx-url", "https://romashka.bitrix24.ru/rest/1/abc/"); st.click("#crm-bx button"); st.wait_for_timeout(400)
    t = st.inner_text("#crm-wrap")
    ok("Битрикс24 подключён" in t and "romashka.bitrix24.ru" in t and "abc" not in t, "подключено — портал виден, ключ — нет")
    st.click(".crm-tg"); st.wait_for_timeout(200)
    ok(["crm_auto", {"on": True}] in st.evaluate("calls"), "«Новых клиентов — сразу в CRM»")
    st.screenshot(path="/tmp/claude-0/crm_on.png")
    st.click("#cr-tabs button[data-t='list']"); st.wait_for_timeout(500)
    ok(st.inner_text("#cr-crm") == "В Битрикс24", "в карточке — «В Битрикс24»")
    st.click("#cr-crm"); st.wait_for_timeout(400)
    ok(["crm_send", {"id": "c1"}] in st.evaluate("calls") and st.inner_text("#cr-crm") == "В Битрикс24 · №42", "отправили — лид №42 в кнопке")
    ok(not errors, f"без ошибок: {errors[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
