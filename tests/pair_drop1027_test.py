"""Отчёт №364 (27.10): «ввёл код для подключения компьютера, нажал „Подключить“ — „не получилось, нет связи с ядром“».
Связь студии с ядром оборвалась посреди подключения, а само подключение могло пройти. Теперь студия ждёт ядро и
спрашивает, чем кончилось: подключилось — «Подключено»; нет — понятно, что делать (нажать ещё раз или взять новый код)."""
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
(() => { window.calls = []; window.MODE = "ok"; window.statusN = 0;
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push(c);
      if (c === "cloud_connect") throw new Error("нет связи с ядром");
      if (c === "cloud_status") { statusN++; if (statusN < 3) throw new Error("нет связи с ядром");
        return MODE === "ok" ? { connected: true, active: true, label: "Аня", tail: "ab12", percent: 90 } : { connected: false }; }
      if (c === "settings_get") return {};
      return {}; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();
"""
with sync_playwright() as p:
    b = p.chromium.launch(); errs = []
    pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://"), lambda r: r.abort())
    pg.add_init_script(FAKE); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1"); pg.wait_for_timeout(1200)
    pg.evaluate("document.querySelector('#dk-key').value = '123 456'; document.querySelector('#dk-go').click()")
    pg.wait_for_function("() => /Подключено|прервалась, подключение/.test(document.querySelector('#dk-res').textContent)", timeout=15000)
    t = pg.inner_text("#dk-res")
    ok(t.startswith("Подключено") and "Аня" in t, f"связь оборвалась, но подключение прошло — «Подключено», а не «нет связи с ядром»: {t!r}")
    pg.evaluate("MODE = 'no'; statusN = 0; document.querySelector('#dk-key').value = '123 456'; document.querySelector('#dk-go').click()")
    pg.wait_for_function("() => /Подключено|прервалась, подключение/.test(document.querySelector('#dk-res').textContent) && !document.querySelector('#dk-go').disabled", timeout=15000)
    t = pg.inner_text("#dk-res")
    ok("ещё раз" in t and "Подключить ещё устройство" in t, f"не прошло — понятно, что делать (новый путь — «Устройства», 0.56): {t!r}")
    ok(not errs, f"без ошибок: {errs[:2]}")
    b.close()
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
raise SystemExit(1 if fails else 0)
