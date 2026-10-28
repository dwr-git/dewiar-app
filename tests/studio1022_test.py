"""Пакет здоровья 22.10 — студия:
- №184 «как закрыть панель справа — не очевидно»: у панели персонажа — крестик наверху (виден и при прокрутке), закрывается
  щелчком мимо и переходом в другой раздел (раньше оставалась поверх «Сообщить о проблеме»);
- №179 «непонятно, выполнена ли команда — страница не обновляется»: заметка, записанная голосом, сразу появляется на
  открытой странице «Заметки» и видно «Заметка «…» сохранена»;
- №167 «не могу войти, хотя код у меня перед глазами»: 6 цифр в поле логина — это код с другого устройства: подключаемся
  по нему, а не пять раз «неверный логин или пароль» до блокировки на 15 минут."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from playwright.sync_api import sync_playwright  # noqa: E402
FAKE = "window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"
CORE = r"""
(() => { window.calls = []; window.notes = [{ path: "Заметки/Старая.md", title: "Старая", mtime: 1, snippet: "x" }];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]);
      if (c === "notes_list") return notes;
      if (c === "ws_read") return { path: a.path, text: "# " + a.path + "\n\nтекст" };
      if (c === "cloud_connect") return { ok: true };
      if (c === "account_login") throw new Error("Неверный логин или пароль");
      return {}; }; };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 860}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1&skin=neusky"); pg.wait_for_timeout(1000)
    # №184
    pg.evaluate("() => { ed = { id: 'lira', name: 'Лира' }; $('#drawer').classList.add('open'); }")
    ok(pg.is_visible("#e-x"), "у панели персонажа — крестик наверху")
    pg.evaluate("$('#drawer').scrollTop = 900"); pg.wait_for_timeout(100)
    bx = pg.locator("#e-x").bounding_box()
    ok(bx and bx["y"] < 120, f"крестик виден и при прокрутке панели вниз: {bx}")
    pg.click("#e-x"); pg.wait_for_timeout(300)
    ok(not pg.evaluate("$('#drawer').classList.contains('open')"), "крестик — закрыл")
    pg.evaluate("() => { ed = { id: 'lira', name: 'Лира' }; $('#drawer').classList.add('open'); }")
    pg.click('nav button[data-p="about"]'); pg.wait_for_timeout(300)
    ok(not pg.evaluate("$('#drawer').classList.contains('open')"), "переход в другой раздел — панель закрылась (не висит поверх)")
    pg.evaluate("() => { ed = { id: 'lira', name: 'Лира' }; $('#drawer').classList.add('open'); }")
    pg.mouse.click(400, 300); pg.wait_for_timeout(300)
    ok(not pg.evaluate("$('#drawer').classList.contains('open')"), "щелчок мимо панели — закрылась")
    # №179
    pg.click('nav button[data-p="notes"]'); pg.wait_for_timeout(600)
    pg.evaluate("() => { notes.unshift({ path: 'Заметки/Купить батарейки.md', title: 'Купить батарейки', mtime: 2, snippet: 'AA' }); calls.length = 0;"
                " core.emit('note_saved', { kind: 'note', title: 'Купить батарейки', path: 'Заметки/Купить батарейки.md' }); }")
    pg.wait_for_timeout(900)
    ok("Купить батарейки" in pg.inner_text("#nt-list") and "сохранена" in pg.inner_text("#toast"),
       f"заметка голосом — сразу в списке и «сохранена»: {pg.inner_text('#toast')!r}")
    # №167
    pg.click('nav button[data-p="dw"]'); pg.wait_for_timeout(500)
    if pg.locator("#dw-login").count() and pg.is_visible("#dw-login"):
        pg.fill("#dw-login", "482 913"); pg.fill("#dw-pass", "x"); pg.click("#dw-go"); pg.wait_for_timeout(500)
        c = pg.evaluate("calls.filter(c => c[0] === 'pair_claim' || c[0] === 'cloud_connect' || c[0] === 'account_login')")
        ok(c and c[0][0] == "pair_claim" and c[0][1]["code"] == "482913", f"6 цифр в поле логина — подключение по коду (pair_claim, 0.56): {c}")
        pg.evaluate("calls.length = 0"); pg.fill("#dw-login", "masha"); pg.fill("#dw-pass", "123 456"); pg.click("#dw-go"); pg.wait_for_timeout(600)
        c = [x[0] for x in pg.evaluate("calls") if x[0] in ("cloud_connect", "account_login")]
        ok(c == ["account_login", "cloud_connect"], f"6 цифр в пароле: сначала вход, не вышло — пробуем как код: {c}")
    else:
        ok(False, "форма входа в «Dewiar.pro» не найдена")
    ok("Есть код из 6 цифр" in (ROOT / "ui/settings.html").read_text(encoding="utf-8"), "поле для кода подписано понятно")
    ok(not errs, f"без ошибок на странице: {errs[:2]}")
    b.close()
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
