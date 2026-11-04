"""Идея №128 (04.11): «как мне редактировать контакт без имени в разделе „Близкие“». Имя близкого приходит с его
устройства — не вписал, и у вас он «Без имени». Теперь в переписке — «Переименовать»: своё имя (только на этом компьютере);
пустое — снова как он сам себя назвал. У группы кнопки нет (у неё своё название в «Участниках»). Имена — выдуманные."""
import os, re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


FAKE = "window.pywebview = { api: new Proxy({}, { get: (_, k) => (...a) => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = [];
  window.ST = { me: { name: "Миша" }, offers: [], groups: [], people: [
    { pid: "p1", name: "Без имени", devs: [{ dev: "d1" }], unread: 0, marks: [0, 0], last: null },
    { pid: "p2", name: "Андрей", devs: [{ dev: "d2" }], unread: 0, marks: [0, 0], last: null }] };
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "close_state") return JSON.parse(JSON.stringify(ST));
      if (c === "close_history") return [];
      if (c === "close_rename") { const p = ST.people.find(x => x.pid === a.pid);
        if (a.name) { p.orig = p.orig || p.name; p.name = a.name; } else { p.name = p.orig || p.name; delete p.orig; }
        return JSON.parse(JSON.stringify(ST)); }
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"close\"]').click()"); pg.wait_for_timeout(500)
    pg.evaluate("clOpen('p1')"); pg.wait_for_timeout(300)
    ok(pg.is_visible("#cl-ren") and pg.text_content("#cl-ren") == "Переименовать", "в переписке — кнопка «Переименовать»")
    pg.evaluate("window.DEWIAR_AUTO_ASK = 'Мама'"); pg.click("#cl-ren"); pg.wait_for_timeout(300)
    ok(pg.evaluate("calls.filter(c => c[0] === 'close_rename').pop()[1]") == {"pid": "p1", "name": "Мама"}, "имя ушло ядру")
    ok(pg.text_content("#cl-who") == "Мама" and "Без имени" in (pg.get_attribute("#cl-who", "title") or ""),
       f"в шапке — новое имя, в подсказке — как он себя назвал: {pg.text_content('#cl-who')!r}")
    ok("Мама" in pg.evaluate("[...document.querySelectorAll('#cl-list b, .cl-p b')].map(e => e.textContent).join(' ')"), "и в списке близких")
    pg.evaluate("window.DEWIAR_AUTO_ASK = ' '"); pg.click("#cl-ren"); pg.wait_for_timeout(300)
    ok(pg.text_content("#cl-who") == "Без имени", "пустое имя — снова как он сам себя назвал")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
raise SystemExit(1 if fails else 0)
