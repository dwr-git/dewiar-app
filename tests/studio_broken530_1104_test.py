"""№530 (04.11, ПК 0.82.1): «Раздел „Мозг“ после обновления оказался пустым. Возможно, связано с моими экспериментами с
„Фильмами“». По журналу: человек сам вписывал свои правки в файлы программы (engine.py, engine_commands.py, settings.html,
core.js); его модуль падал ещё до обновления («cannot import name 'genres' from 'myvideo'» десятки раз в секунду), обновление
вернуло наши файлы, а студия открылась с пустыми полями и «нет связи с ядром» — хотя ядро работало: скрипт студии упал при
загрузке (страница и скрипты из разных версий), и обработчик подключения так и не встал. Ошибку видно не было.
Теперь: связь отмечается из первого файла студии; основной файл студии не дошёл до конца — вверху честная плашка «Студия
загрузилась не целиком — ошибка в файле …; переустановите поверх», ошибка — в журнал ядра (в отчёт). Ошибки в обработчиках
событий ядра тоже идут в журнал. Проверка: элемент страницы, который ждёт studio/dewiar.js, убран — как при смеси версий."""
import functools, http.server, os, re, sys, threading
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CORE = r"""
(() => { window.calls = [];
  const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    core.call = async (c, a) => { calls.push([c, a]); return {}; };
    setTimeout(() => { core.connected = true; core.emit("hello", { settings: { ui: {}, llm: { profiles: {}, active: "" }, features: {}, tts: {}, stt: {}, audio: {} },
      personas: [], persona: "lira", presets: {}, piper_voices: [], status: {} }); }, 300); };
  ready(); })();
"""
BREAK = r"""
new MutationObserver(() => { const e = document.getElementById("dw-e2e"); if (e) e.remove(); }).observe(document, { childList: true, subtree: true });
"""
# как в программе — страницы по http с 127.0.0.1 (ui/app.py ui_http_base): иначе браузер прячет имя файла с ошибкой
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(ROOT / "ui")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{srv.server_address[1]}/"
with sync_playwright() as p:
    b = p.chromium.launch()
    for broken in (False, True):
        errs = []
        pg = b.new_page(viewport={"width": 1400, "height": 900}); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
        pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };"); pg.add_init_script(CORE)
        if broken:
            pg.add_init_script(BREAK)
        pg.goto(BASE + "settings.html?port=1"); pg.wait_for_timeout(2600)
        conn = pg.inner_text("#conn")
        ban = pg.inner_text("#studio-broken") if pg.locator("#studio-broken").count() else ""
        if not broken:
            ok(conn.strip() == "ядро на связи" and not ban, f"обычная студия: «ядро на связи», плашки нет ({conn!r})")
            ok(pg.evaluate("window.__studioReady === true"), "основной файл студии дошёл до конца")
        else:
            ok(errs and "dw-e2e" not in errs[0] and pg.evaluate("!window.__studioReady"), f"смесь версий: студия падает при загрузке ({errs[:1]})")
            ok(conn.strip() == "ядро на связи", f"но ядро на связи — так и написано, а не «нет связи с ядром» ({conn!r})")
            ok("Студия загрузилась не целиком" in ban and "dewiar.js" in ban and "Переустановите Dewiar поверх" in ban and "сохранятся" in ban,
               f"плашка: какой файл и что делать: {ban[:160]!r}")
            js = [c for c in pg.evaluate("calls") if c[0] == "js_errors"]
            ok(js and "студия не загрузилась целиком" in js[0][1]["errors"][0] and any("dewiar.js" in x for x in js[0][1]["errors"]),
               "ошибка — в журнал ядра (уйдёт в отчёт)")
            if os.environ.get("DEWIAR_SHOTS"): pg.screenshot(path=str(Path(os.environ["DEWIAR_SHOTS"]) / "studio-broken530.png"))
        pg.close()
    # ошибка в обработчике события ядра — не молча
    pg = b.new_page(); pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/hud.html").as_uri() + "?port=1&mode=card"); pg.wait_for_timeout(600)
    pg.evaluate("() => { window.__jsErr = []; core.on('zzz', () => { throw new Error('бум'); }); core.emit('zzz', {}); }")
    ok(pg.evaluate("window.__jsErr.some(x => x.includes('zzz') && x.includes('бум'))"), "ошибка в обработчике события — в список ошибок страницы")
    b.close()
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
