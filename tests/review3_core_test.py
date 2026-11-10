"""Третья рецензия выпуска 5 (05.11), ядро: проверка HTML не выносит чужие файлы в ошибках, PDF печатается без сети и
без чужих файлов, «Папка» и «Знания» не распаковывают zip-бомбы, «Открыть» не запускает то, что открывается действием
(импорт в календарь, макросы старого Office). Каждый пункт — обход рецензента (scratchpad rev5c: p_err, p_pdf, p_wsbomb)."""
import glob
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TMP = Path(tempfile.mkdtemp(prefix="dw-r3-"))
os.environ.update(DEWIAR_WORKSPACE=str(TMP / "ws"), DEWIAR_STATE_DIR=str(TMP / "st"), DEWIAR_CONFIG_DIR=str(TMP / "cfg"),
                  DEWIAR_DOWNLOADS=str(TMP / "Загрузки"))
sys.path.insert(0, str(ROOT / "core"))
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

# «чужие» файлы — рядом с папкой задачи, не в ней
SEC = TMP / "home"
SEC.mkdir()
(SEC / ".env").write_text("TOKEN_ABC = 'x'\nSuperSecretValue42\n")
(SEC / "id_rsa").write_text("-----BEGIN KEY-----\nKEYMATERIALQWERTY\n-----END KEY-----\n")
task = TMP / "task"
(task / "outputs").mkdir(parents=True)
(task / "outputs" / "ok.js").write_text("window.OKJS = 1;")
os.symlink(SEC / ".env", task / "outputs" / "env.js")                 # ссылка из папки задачи наружу — тоже чужой файл

import quality as Q  # noqa: E402
page = task / "outputs" / "index.html"
page.write_text(f"""<html><body>Страница<script src="{(SEC / '.env').as_uri()}"></script>
<script src="env.js"></script><script src="ok.js"></script>
<link rel=stylesheet href="{(SEC / 'id_rsa').as_uri()}"><iframe src="{(SEC / 'id_rsa').as_uri()}"></iframe>
<script>window.onerror = function (m) {{ document.body.append(' ERR:' + m); }}; document.body.append(' ok=' + window.OKJS);</script>
</body></html>""", encoding="utf-8")
res = Q.html_check([str(page)], roots=[str(task)])
if res is None:
    print("⚠ браузера для проверки HTML нет — часть пропущена")
else:
    r = res[str(page)]
    blob = repr(r)
    ok("SuperSecretValue42" not in blob and "TOKEN_ABC" not in blob and "KEYMATERIAL" not in blob,
       f"html_check: ни ошибки, ни текст страницы не несут содержимого файлов вне папки задачи ({r['errors']})")
    ok("ok=1" in r["text"], f"html_check: свои файлы задачи страница грузит, как раньше ({r['text'][:80]})")
    ok(any("вне папки задачи" in x for x in r.get("external") or []), f"html_check: чужие файлы — в замечаниях, без содержимого ({r.get('external')})")
    out = Q.html_check([str(SEC / ".env")], roots=[str(task)])
    ok(out and out[str(SEC / ".env")].get("unchecked"), "html_check: страницу вне папки задачи не открывает")
    long = task / "outputs" / "long.html"
    long.write_text("<html><body><script>throw new Error('x'.repeat(5000) + '\\n\\nвторая строка');</script></body></html>")
    e = Q.html_check([str(long)], roots=[str(task)])[str(long)]["errors"]
    ok(e and len(e[0]) <= 200 and "\n" not in e[0], "html_check: ошибка — одной строкой, не длиннее 200 знаков")

# PDF: без сети и без чужих файлов — и через браузер компьютера (CLI), и через Playwright
import export as X  # noqa: E402
rep = task / "outputs" / "report.html"
rep.write_text(f"""<html><head><title>r</title><meta http-equiv="refresh" content="0;url=http://127.0.0.1:{PORT}/refresh"></head>
<body>Отчёт <img src="http://127.0.0.1:{PORT}/img-leak?d=SECRET">
<script>fetch("http://127.0.0.1:{PORT}/fetch-leak", {{mode: "no-cors"}}).catch(function () {{}});</script>
<iframe src="{(SEC / 'id_rsa').as_uri()}" width=600 height=100></iframe><object data="{(SEC / 'id_rsa').as_uri()}"></object></body></html>""",
               encoding="utf-8")
first = X.print_html(rep.read_text(encoding="utf-8"))
ok(first.startswith('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy"') and "frame-src 'none'" in first
   and 'http-equiv="refresh"' not in first.lower(),
   "PDF: печатная копия — CSP первой строкой (кадров нет), без <meta refresh>")
br = next(iter(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell")), None) or X.find_browser()
ways = []
if br:
    ways.append(("браузер компьютера", br))
try:
    import playwright  # noqa: F401
    ways.append(("Playwright", ""))
except ImportError:
    pass
for name, b in ways:
    os.environ["DEWIAR_PDF_BROWSER"] = b
    got.clear()
    try:
        pdf = X.export(rep, f"Отчёт {name}", "pdf", root=task)
    except X.ExportError as e:
        ok(False, f"PDF ({name}) не сделан: {e}")
        continue
    time.sleep(0.5)
    txt = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout if shutil.which("pdftotext") else ""
    ok(not got, f"PDF ({name}): ни картинки, ни fetch, ни перехода в сеть ({got[:3]})")
    ok("KEYMATERIAL" not in txt and (not shutil.which("pdftotext") or "Отчёт" in txt),
       f"PDF ({name}): ключ из ~/.ssh в PDF не попал, сам отчёт — на месте")
    ok(not list((task / "outputs").glob(".печать-*")), f"PDF ({name}): временная копия убрана")
os.environ.pop("DEWIAR_PDF_BROWSER", None)
if not ways:
    print("⚠ браузера для PDF нет — часть пропущена")

# zip-бомба через «Папку» и «Знания»: не распаковывается, память не растёт
bomb = TMP / "ws" / "bomb.docx"
bomb.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    with z.open("word/document.xml", "w", force_zip64=True) as f:
        for _ in range(300):
            f.write(b"A" * (1 << 20))
import knowledge as K  # noqa: E402
import workspace as W  # noqa: E402
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
t0 = time.time()
try:
    K.extract(bomb)
    ok(False, "«Знания»: docx-бомба отклонена")
except ValueError as e:
    ok("подозрительный" in str(e), f"«Знания»: docx-бомба — понятная ошибка, а не распаковка ({e})")
ws = W.Workspace(None)                                           # корень — DEWIAR_WORKSPACE
if ws is not None:
    r = ws.read("bomb.docx")
    ok(r.get("binary") or not r.get("text"), "«Папка»: docx-бомба показана как файл, текст не распакован")
    big = TMP / "ws" / "big.txt"
    with open(big, "wb") as f:
        f.truncate(3 << 30)                                       # 3 ГБ (разреженный файл)
    r = ws.read("big.txt")
    ok(len(r["text"]) <= 300_000 and r["truncated"], "«Папка»: огромный текст — только начало, не целиком")
    big.unlink()
grow = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - rss0) // 1024
ok(grow < 200 and time.time() - t0 < 10, f"бомба и огромный файл — без роста памяти ({grow} МБ, {time.time() - t0:.1f} с)")
big = TMP / "ws" / "big.md"
with open(big, "wb") as f:
    f.truncate(1 << 30)
ok(len(K.extract(big)) <= K.TEXT_MAX, "«Знания»: огромный .md — читается только начало")
big.unlink()

# «Открыть»: только то, что открывается просмотром
for ext in (".xml", ".ics", ".vcf", ".doc", ".xls", ".ppt", ".rtf", ".desktop", ".docm"):
    ok(not X.safe_to_open(TMP / f"a{ext}"), f"«Открыть»: {ext} — только показать в папке")
for ext in (".pdf", ".html", ".docx", ".xlsx", ".png", ".mp3", ".mp4", ".txt", ".csv"):
    ok(X.safe_to_open(TMP / f"a{ext}"), f"«Открыть»: {ext} — программой по умолчанию")

srv.shutdown()
shutil.rmtree(TMP, ignore_errors=True)
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
