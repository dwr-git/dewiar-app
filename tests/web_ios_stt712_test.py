"""№712 (14.11): «при установке на айфоне возникла проблема по распознаванию речи, просит только писать». Веб-версия на
iPhone слушала только сервером Dewiar; без входа — «В этом устройстве нет распознавания речи… напишите текстом». Теперь
без сервера слушает распознавание Safari. И попутно: с 0.96 настройки распознавания браузера (промежуточный текст,
«держать кнопку») ушли в комментарий — снова работают. В Chrome на компьютере — как было."""
import http.server, os, shutil, subprocess, sys, tempfile, threading, functools
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp())
r = subprocess.run(["bash", str(ROOT / "tools/build_web.sh"), str(tmp / "b")], capture_output=True, text=True)
ok(r.returncode == 0, "веб-версия собирается")
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=str(tmp / "b/web")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/index.html"
FAKE = """window.__sr = [];
window.webkitSpeechRecognition = function () { const me = this; window.__sr.push(me);
  me.start = () => { setTimeout(() => { me.onstart && me.onstart();
    me.onresult && me.onresult({ results: [Object.assign([{ transcript: "какая погода" }], { isFinal: true })] });
    me.onend && me.onend(); }, 50); };
  me.stop = () => {}; me.abort = () => {}; };
window.SpeechRecognition = window.webkitSpeechRecognition;"""
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for ua, name in ((IPHONE, "iPhone"), (None, "Chrome")):
            ctx = b.new_context(user_agent=ua, locale="ru-RU", viewport={"width": 393, "height": 852}) if ua else b.new_context(locale="ru-RU", viewport={"width": 393, "height": 852})
            ctx.grant_permissions(["microphone"])
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.add_init_script(FAKE)
            pg.goto(URL); pg.wait_for_timeout(1500)
            R = pg.evaluate("""async () => { window.needPerm = async () => true; await listen(); await new Promise(r => setTimeout(r, 600));
                const r = window.__sr[0]; return { n: window.__sr.length, interim: r && r.interimResults, lang: r && r.lang,
                  bot: ($("#bot") || {}).textContent || "", you: ($("#you") || {}).textContent || "", via: sttVia, rec: D.recognizer(), any: !!(D.recognizerAny && D.recognizerAny()), st: state }; }""")
            if name == "iPhone":
                ok(R["n"] == 1 and "нет распознавания" not in R["bot"], f"iPhone без входа — слушает Safari, а не «пишите текстом»: {R}")
            else:
                ok(R["n"] == 1, f"Chrome — своё распознавание, как было: {R['n']}")
            ok(R["interim"] is True and R["lang"] == "ru-RU", f"{name}: промежуточный текст снова включён, язык ru-RU: {R['interim']}, {R['lang']}")
            ok(not errs, f"{name}: без ошибок: {errs[:2]}")
            ctx.close()
        b.close()
finally:
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
