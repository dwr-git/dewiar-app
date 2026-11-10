"""Результат задачи — в руки (скачать HTML и PDF): копия в «Загрузки», PDF из страницы
печатает браузер компьютера без окон (презентация — по слайду на страницу), PDF-файл и картинка — как есть; путь
только внутри папки задачи; браузера нет — понятный совет."""
import glob, json, os, shutil, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_WORKSPACE=str(tmp / "ws"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"),
                  DEWIAR_DOWNLOADS=str(tmp / "Загрузки"), DEWIAR_DRY_TOOLS=str(tmp / "dry.jsonl"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import export as X  # noqa: E402
br = next(iter(glob.glob("/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux*/chrome-headless-shell")
               + glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")), None) or X.find_browser()
d = tmp / "task"; (d / "outputs").mkdir(parents=True)
deck = (ROOT / "data/skills/slides/deck.html").read_text(encoding="utf-8")
(d / "outputs/slides.html").write_text(deck, encoding="utf-8")
(d / "outputs/картинка.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)
p = X.export(d / "outputs/slides.html", "Погода в Минске · 3–4 октября", "html")
ok(p.parent == tmp / "Загрузки" and p.name == "Погода в Минске · 3–4 октября.html" and p.read_text(encoding="utf-8") == deck,
   f"«Скачать HTML» — копия в «Загрузки» с понятным именем: {p.name}")
p2 = X.export(d / "outputs/slides.html", "Погода в Минске · 3–4 октября", "html")
ok(p2.name == "Погода в Минске · 3–4 октября (2).html", f"второй раз — не затирает: {p2.name}")
ok(X.export(d / "outputs/картинка.png", "Рисунок", "file").name == "Рисунок.png", "картинка — как есть")
if br:
    os.environ["DEWIAR_PDF_BROWSER"] = br
    pdf = X.export(d / "outputs/slides.html", "Погода", "pdf")
    data = pdf.read_bytes()
    pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    ok(data.startswith(b"%PDF") and pages >= 2, f"«PDF» — браузер без окна напечатал презентацию: {pdf.name}, страниц {pages}")
    (d / "outputs/своя.html").write_text("<!doctype html><html><head><style>section{display:none;position:absolute;inset:0}"
                                          "section.on{display:block}</style></head><body><section class='on'><h1>1</h1></section>"
                                          "<section><h1>2</h1></section><section><h1>3</h1></section></body></html>", encoding="utf-8")
    data = X.export(d / "outputs/своя.html", "Своя", "pdf").read_bytes()
    pages = data.count(b"/Type /Page") - data.count(b"/Type /Pages")
    ok(pages == 3 and not list((d / "outputs").glob(".печать-*")),
       f"презентация, которую модель собрала сама (слайды листаются скриптом), — каждый слайд на своей странице ({pages}), временный файл убран")
else:
    print("⚠ браузера нет — PDF не проверен")
os.environ["DEWIAR_PDF_BROWSER"] = ""
saved, saved_pw = shutil.which, X._pw_pdf
shutil.which = lambda *a, **k: None
X._pw_pdf = lambda *a, **k: None                       # и Chromium от Playwright тоже нет
try:
    try:
        X.export(d / "outputs/slides.html", "Погода", "pdf"); err = ""
    except X.ExportError as e:
        err = str(e)
finally:
    shutil.which, X._pw_pdf = saved, saved_pw
ok("Печать → Сохранить как PDF" in err or os.path.exists("/snap/bin/chromium"), f"браузера нет — честный совет: {err[:70]}")
try:
    X.export(d / "outputs/нет.html", "x", "html"); err = ""
except X.ExportError as e:
    err = str(e)
ok("файла уже нет" in err, "файла нет — понятная ошибка")

# команда ядра: только файлы внутри папки задачи
import tasks as TK  # noqa: E402
import engine as E  # noqa: E402
from types import SimpleNamespace  # noqa: E402
t = TK.Task(d, {"id": "t1", "title": "Погода", "outputs": [{"path": "outputs/slides.html", "title": "Слайды"}]})
eng = SimpleNamespace(tasks=SimpleNamespace(get=lambda i: t))
cmd = E.Engine.command
try:
    r = cmd(eng, "task_export", {"id": "t1", "path": "outputs/slides.html", "fmt": "html"})
    ok(r["name"] == "Слайды.html", f"команда task_export: {r['name']}")
    try:
        cmd(eng, "task_export", {"id": "t1", "path": "../../../etc/passwd", "fmt": "file"}); bad = False
    except ValueError:
        bad = True
    ok(bad, "чужой путь (../../etc/passwd) — отказ")
    r = cmd(eng, "task_open_result", {"id": "t1", "path": "outputs/slides.html"})
    ok(r["opened"].endswith("slides.html"), "«Посмотреть» — открывает сам результат")
    # «Папка» студии: скачать любой файл папки ассистента; у страницы имя копии — из её <title>
    from workspace import Workspace  # noqa: E402
    eng.workspace = Workspace(None)
    pg = eng.workspace.ensure() / "Задачи/старая/outputs/slides.html"; pg.parent.mkdir(parents=True)
    pg.write_text("<html><head><title>Погода &amp; ветер</title></head><body>x</body></html>", encoding="utf-8")
    r = cmd(eng, "ws_export", {"path": "Задачи/старая/outputs/slides.html", "fmt": "html"})
    ok(r["name"] == "Погода & ветер.html", f"«Папка» → «Скачать HTML»: имя из заголовка страницы ({r['name']})")
    try:
        cmd(eng, "ws_export", {"path": "../../etc/passwd"}); bad = False
    except ValueError:
        bad = True
    ok(bad, "«Папка»: путь вне папки ассистента — отказ")
except Exception as e:  # noqa: BLE001
    ok(False, f"команды ядра: {e}")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
