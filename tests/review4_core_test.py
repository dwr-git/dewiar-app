"""Четвёртая рецензия выпуска 5 (05.11), ядро: PDF через браузер компьютера (без Playwright) не печатает чужой файл —
ни скриптом (location = file:///…/.ssh/id_rsa), ни <meta refresh> с «>» в кавычках; <meta http-equiv> вырезается
разбором тега, как у браузера, — одинаково в Python (export.strip_meta_equiv) и в студии (core.js stripMetaEquiv);
PDF-бомба разбирается в отдельном процессе с пределами времени и памяти, обычный PDF читается как раньше.
Обходы рецензента: scratchpad rev5d — p_pdfnav, p_refresh, p_pdfbomb."""
import glob
import json
import os
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
TMP = Path(tempfile.mkdtemp(prefix="dw-r4-"))
os.environ.update(DEWIAR_WORKSPACE=str(TMP / "ws"), DEWIAR_STATE_DIR=str(TMP / "st"), DEWIAR_CONFIG_DIR=str(TMP / "cfg"),
                  DEWIAR_DOWNLOADS=str(TMP / "Загрузки"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import export as X  # noqa: E402

# 1) <meta http-equiv>: разбор тега, а не регулярка — Python и JS дают одно и то же
CASES = [
    '<meta content="0;url=http://h/gt?x=>" http-equiv="refresh">a',
    '<meta http-equiv="&#114;efresh" content="0;url=http://h/e">b',
    '<meta a"b http-equiv=refresh content=0;url=http://h/x>c',
    '<META/HTTP-EQUIV=refresh/content="0;url=http://h">d',
    '<me<meta http-equiv=x>ta http-equiv=refresh content=0;url=http://h/>e',
    '<meta content="x"http-equiv="refresh">f',
    "<script>var x='<meta a=\"';</script><meta http-equiv=refresh content=\"0;url=http://h/x\">g",
    '<meta charset=utf-8><meta name=viewport content="w">ok',
    '<meta http-equiv=refresh content="0;url=http://h/unclosed"',
    'İ<meta http-equiv="refresh" content="0;url=http://h/i">h',          # рецензия 5e: «İ».lower() — два знака
    'İİİ<META HTTP-EQUIV=refresh content=0;url=file:///etc/passwd>i',
]
py = [X.strip_meta_equiv(c) for c in CASES]
ok(not [r for r in py[:7] + py[8:] if "<meta" in r.lower() and "http-equiv" in r.lower().split("<meta", 1)[1].split(">", 1)[0]],
   f"Python: ни одного <meta http-equiv> после вырезания ({[r[:50] for r in py]})")
ok(py[7] == CASES[7], "Python: <meta charset> и viewport — на месте")
ok(py[4].startswith("<me ta"), "Python: вырезанный тег не склеивает соседние куски в новый <meta>")
if shutil.which("node"):
    core_js = (ROOT / "ui/studio/core.js").read_text(encoding="utf-8")
    fn = core_js[core_js.index("function stripMetaEquiv"):core_js.index("/* CSP — самой первой")]
    r = subprocess.run(["node", "-e", fn + "\nconsole.log(JSON.stringify(%s.map(stripMetaEquiv)))" % json.dumps(CASES)],
                       capture_output=True, text=True)
    js = json.loads(r.stdout or "[]")
    ok(js == py, f"JS (студия) и Python (печать) вырезают одинаково ({[(a, b) for a, b in zip(js, py) if a != b][:2]})")
else:
    print("⚠ node нет — сравнение с JS пропущено")

# 2) PDF браузером компьютера: страница уводит себя на чужой файл — в PDF его нет
SEC = TMP / "home" / ".ssh"
SEC.mkdir(parents=True)
(SEC / "id_rsa").write_text("-----BEGIN KEY-----\nKEYMATERIALQWERTY\n-----END KEY-----\n")
task = TMP / "task" / "outputs"
task.mkdir(parents=True)
key = (SEC / "id_rsa").as_uri()
pages = {"script.html": f'<html><body>Отчёт<script>location.href="{key}"</script></body></html>',
         "refresh.html": f'<html><head><meta content="0;url={key}?>" http-equiv="refresh"></head><body>Отчёт</body></html>',
         "frame.html": f'<html><body>Отчёт<iframe src="{key}"></iframe><img src="{key}"><object data="{key}"></object></body></html>'}
br = next(iter(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell")), None) or X.find_browser()
if not br or not shutil.which("pdftotext"):
    print("⚠ браузера или pdftotext нет — печать не проверена")
else:
    os.environ["DEWIAR_PDF_BROWSER"] = br
    for jail in ("1", "0"):
        os.environ["DEWIAR_PDF_JAIL"] = jail
        for n, h in pages.items():
            (task / n).write_text(h, encoding="utf-8")
            try:
                pdf = X.export(task / n, f"{n}-{jail}", "pdf", root=task.parent)
                txt = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
            except X.ExportError as e:
                txt = f"ERR {e}"
            ok("KEYMATERIAL" not in txt and "Отчёт" in txt,
               f"PDF без Playwright ({'в bwrap' if jail == '1' else 'без bwrap'}), {n}: чужой файл не напечатан, отчёт — на месте ({txt.strip()[:40]!r})")
    os.environ.pop("DEWIAR_PDF_JAIL", None)
    os.environ.pop("DEWIAR_PDF_BROWSER", None)
    pc = X.print_html("<script>x()</script>Отчёт", scripts=False)
    ok("script-src 'none'" in pc and "script-src 'unsafe-inline'" not in pc, "печатная копия для браузера компьютера — скрипты выключены CSP")
    try:
        import sandbox as S
        jailed = S.bwrap_ok()
    except Exception:  # noqa: BLE001
        jailed = False
    if jailed:
        argv = X._print_jail(str(task.parent), str(TMP / "Загрузки"), str(TMP / "prof"), br)
        ok(argv and "--unshare-all" in argv and str(Path.home()) not in [argv[i + 1] for i, a in enumerate(argv) if a in ("--bind", "--ro-bind")],
           "Linux с bwrap: браузер печати — без сети и без домашней папки, видна только папка задачи")

# 3) PDF-бомба: разбор — в отдельном процессе с пределами; обычный PDF — как раньше
import pdftext  # noqa: E402
import knowledge as K  # noqa: E402
bomb = TMP / "bomb.pdf"
raw = b"BT (A) Tj ET\n" * (40_000_000 // 13)
comp = zlib.compress(raw, 9)
objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(comp) + comp + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
kids = []
for i in range(300):
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] /Contents 3 0 R /Resources << /Font << /F1 4 0 R >> >> >>")
    kids.append(b"%d 0 R" % len(objs))
objs[1] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(kids), b" ".join(kids))
data, offs = bytearray(b"%PDF-1.4\n"), []
for i, o in enumerate(objs, 1):
    offs.append(len(data))
    data += b"%d 0 obj\n" % i + o + b"\nendobj\n"
x = len(data)
data += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
data += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
bomb.write_bytes(bytes(data))
del raw, comp, data
rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
pdftext.TIMEOUT = 6
t0 = time.time()
try:
    K.extract(bomb)
    ok(False, "PDF-бомба: «Знания» не разбирают её в ядре")
except pdftext.PdfTextError as e:
    ok(time.time() - t0 < 15, f"PDF-бомба: «Знания» — понятная ошибка за {time.time() - t0:.0f} с, а не минуты ({e})")
import quality as Q  # noqa: E402
t0 = time.time()
ok(Q.file_text(bomb) == "" and time.time() - t0 < 15, "PDF-бомба: проверка итога (file_text) — пусто, без зависания")
grow = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - rss0) // 1024
ok(grow < 100, f"PDF-бомба: память ядра не растёт ({grow} МБ сверх прежнего пика)")
pdftext.TIMEOUT = 25
if br:
    os.environ["DEWIAR_PDF_BROWSER"] = br
    (task / "ok.html").write_text("<html><body><h1>Обычный отчёт</h1><p>Строка два</p></body></html>", encoding="utf-8")
    good = X.export(task / "ok.html", "Обычный", "pdf", root=task.parent)
    os.environ.pop("DEWIAR_PDF_BROWSER", None)
    txt = K.extract(Path(good))
    ok("Обычный отчёт" in txt and "Строка два" in txt, f"обычный PDF — текст как раньше ({txt.strip()[:40]!r})")
    ok(Q.count_of(good, "pages") == 1 and "Обычный отчёт" in Q.file_text(good), "обычный PDF — страницы и текст для проверки итога")

shutil.rmtree(TMP, ignore_errors=True)

# рецензия 5e: «скан» PDF рисуется в процессе ядра — страница 14400×14400 pt (файл в 418 байт) давала растр 40000×40000
def _huge_pdf(path, sz=14400):
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 4 0 R >>" % (sz, sz), b"<< /Length 0 >>\nstream\n\nendstream"]
    pdf = bytearray(b"%PDF-1.4\n"); offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf)); pdf += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(pdf); pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)
    Path(path).write_bytes(bytes(pdf))


import ocr  # noqa: E402
hp = Path(tempfile.mkdtemp()) / "huge.pdf"
_huge_pdf(hp)
ok(ocr._safe_dpi(14400, 14400, 200) < 40 and ocr._safe_dpi(595, 842, 200) == 200, "огромная страница рисуется мельче, обычная A4 — как была")
try:
    im = ocr.page_image(hp, 0)
    ok(im is None or im.size[0] * im.size[1] <= ocr.PAGE_MAX_PX * 1.01, f"растр огромной страницы — не больше {ocr.PAGE_MAX_PX // 1000000} Мп ({im and im.size})")
except MemoryError:
    ok(False, "растр огромной страницы съел память")


# рецензия 5e, п. 3: печать браузером компьютера без bwrap (Windows, Mac) — CSP без file:, свои картинки внутри копии
import base64  # noqa: E402
_d = Path(tempfile.mkdtemp()); (_d / "img").mkdir()
(_d / "img/a.png").write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))
(_d / "s.css").write_text("body{background:url(img/a.png)}", encoding="utf-8")
_out = X.inline_local('<link rel="stylesheet" href="s.css"><img src="img/a.png"><img src="../../etc/passwd">'
                      '<img src="file:///etc/hostname"><img srcset="file:///etc/hostname 2x" src="x">', str(_d), str(_d))
ok(_out.count("data:image/png") == 2 and "/etc/" not in _out, "печать без скриптов: свои картинки и стили — внутри копии, чужие файлы — пустая ссылка")
_pc = X.print_html("<p>Отчёт</p>", scripts=False)
ok("file:" not in _pc.split("Content-Security-Policy", 1)[1].split(">", 1)[0], "CSP печати браузером компьютера — без file:")

print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
