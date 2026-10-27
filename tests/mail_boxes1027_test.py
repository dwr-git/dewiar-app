"""Почта: несколько ящиков в студии (пакет 27.10: «как настроить на несколько ящиков? а то только один»). Ящики —
кнопками над формой, первый — «главный»; «+ Ещё ящик» — пустая форма, «Подключить» уходит с номером нового ящика;
«Отключить» убирает выбранный ящик."""
import os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = [];
  const box = (a) => ({ address: a, has_password: true, configured: true, smtp_host: "smtp.x", imap_host: "imap.x" });
  window.MB = [box("anna@yandex.ru"), box("work@corp.ru")];
  const pub = () => Object.assign({}, MB[0] || {}, { boxes: MB.map((b, n) => Object.assign({ n }, b)) });
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "mail_save") { const i = a.box; MB[i] = Object.assign(MB[i] || {}, box(a.patch.address)); return pub(); }
      if (c === "mail_test") return { smtp: "ok", imap: "ok" };
      if (c === "mail_forget") { MB.splice(a.box, 1); return pub(); }
      return {}; };
    setTimeout(() => mlFill(pub()), 300); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    chips = pg.evaluate("[...document.querySelectorAll('#ml-boxes .chip')].map(c => c.textContent)")
    ok(chips == ["anna@yandex.ru · главный", "work@corp.ru", "+ Ещё ящик"], f"ящики кнопками, первый — главный: {chips}")
    ok(pg.input_value("#ml-addr") == "anna@yandex.ru", "форма — главного ящика")
    pg.evaluate("document.querySelectorAll('#ml-boxes .chip')[2].click()"); pg.wait_for_timeout(100)
    ok(pg.input_value("#ml-addr") == "", "«+ Ещё ящик» — пустая форма")
    pg.evaluate("document.querySelector('#ml-addr').value = 'home@mail.ru'; document.querySelector('#ml-pass').value = 'app-pass'"); pg.evaluate("document.querySelector('#ml-save').click()"); pg.wait_for_timeout(400)
    sv = [c for c in pg.evaluate("calls") if c[0] == "mail_save"][-1][1]
    ok(sv["box"] == 2 and sv["patch"]["address"] == "home@mail.ru", f"новый ящик сохраняется третьим: {sv['box']}")
    ok(len(pg.evaluate("document.querySelectorAll('#ml-boxes .chip')")) == 4 and "Готово" in pg.inner_text("#ml-res"), "три ящика и «Готово»")
    pg.evaluate("document.querySelectorAll('#ml-boxes .chip')[1].click()"); pg.wait_for_timeout(100)
    pg.evaluate("document.querySelector('#ml-off').click()"); pg.wait_for_timeout(300)
    chips = pg.evaluate("[...document.querySelectorAll('#ml-boxes .chip')].map(c => c.textContent)")
    ok([c for c in pg.evaluate("calls") if c[0] == "mail_forget"][-1][1] == {"box": 1} and "work@corp.ru" not in " ".join(chips) and "отключён" in pg.inner_text("#ml-res"),
       f"«Отключить» — только выбранный ящик: {chips}")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
raise SystemExit(1 if fails else 0)
