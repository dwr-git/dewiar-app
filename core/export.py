"""Результаты задач — человеку в руки: «Скачать HTML», «Скачать PDF», «Скачать файл» кладут копию в «Загрузки».

PDF из страницы (презентации, отчёта, дашборда) печатает браузер, который уже есть на компьютере, без окон
(headless, свой временный профиль): Edge есть в каждой Windows, на Linux — Chrome / Chromium / Edge / Brave /
Яндекс Браузер; DEWIAR_PDF_BROWSER задаёт свой. Шаблон презентаций (skills/slides/deck.html) задаёт @media print —
каждый слайд выходит отдельной страницей 16:9; презентации без таких правил их подкладывает _printable.
Браузера нет — честно говорим и предлагаем открыть страницу и «Печать → Сохранить как PDF».
"""
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("dewiar.export")
WIN = os.name == "nt"


class ExportError(Exception):
    pass


def downloads_dir():
    """Папка «Загрузки» (создаёт, если нет): Windows — известная папка, Linux — xdg-user-dir; DEWIAR_DOWNLOADS — своя."""
    d = None
    if WIN:
        try:
            import winsys
            d = Path(winsys.known_folder("Downloads"))
        except Exception:  # noqa: BLE001
            d = None
    else:
        try:
            x = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=3).stdout.strip()
            if x and x != str(Path.home()):
                d = Path(x)
        except (OSError, subprocess.SubprocessError):
            pass
    d = d or Path.home() / ("Downloads" if WIN or (Path.home() / "Downloads").exists() else "Загрузки")
    if os.environ.get("DEWIAR_DOWNLOADS"):
        d = Path(os.environ["DEWIAR_DOWNLOADS"])
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_name(title, ext):
    """Имя файла из заголовка: без знаков, запрещённых в Windows, до 90 знаков."""
    base = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", title or "Результат").strip(" .")
    base = re.sub(r"\s+", " ", base)[:90] or "Результат"
    return base + ext


def unique(path):
    """Свободное имя: «x.pdf», «x (2).pdf»… — чужие файлы в «Загрузках» не затираем."""
    p, n = Path(path), 2
    while p.exists():
        p = p.with_name(f"{Path(path).stem} ({n}){Path(path).suffix}")
        n += 1
    return p


def find_browser():
    """Путь к браузеру на движке Chromium (умеет --print-to-pdf) или None."""
    if os.environ.get("DEWIAR_PDF_BROWSER"):
        return os.environ["DEWIAR_PDF_BROWSER"]
    if WIN:
        roots = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
        rel = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
               r"Yandex\YandexBrowser\Application\browser.exe", r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        for r in roots:
            for x in rel:
                p = Path(r) / x
                if r and p.is_file():
                    return str(p)
        return None
    if sys.platform == "darwin":                      # Mac: браузеры в «Программах»
        for app, exe in (("Google Chrome", "Google Chrome"), ("Microsoft Edge", "Microsoft Edge"), ("Yandex", "Yandex"),
                         ("Brave Browser", "Brave Browser"), ("Chromium", "Chromium")):
            for root in ("/Applications", str(Path.home() / "Applications")):
                p = Path(root) / f"{app}.app" / "Contents" / "MacOS" / exe
                if p.is_file():
                    return str(p)
        return None
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "microsoft-edge-stable",
                 "brave-browser", "yandex-browser", "yandex-browser-stable"):
        p = shutil.which(name)
        if p:
            return p
    for p in ("/snap/bin/chromium", "/var/lib/flatpak/exports/bin/com.google.Chrome"):
        if Path(p).exists():
            return p
    return None


# правила печати для презентации без своих: каждый слайд (section/.slide) — страница 1280×720, служебные кнопки скрыты,
# цвета фона печатаются
PRINT_DECK = ("<style id=\"dewiar-print\">@media print{@page{size:1280px 720px;margin:0}html,body{height:auto!important;margin:0!important;padding:0!important;"
              "overflow:visible!important}.slide,section.slide,.deck>section,.slides>section,body>section,main>section{display:flex!important;"
              "flex-direction:column;position:relative!important;inset:auto!important;opacity:1!important;visibility:visible!important;"
              "transform:none!important;width:1280px!important;height:720px!important;min-height:0!important;overflow:hidden!important;"
              "box-sizing:border-box;margin:0!important;break-after:page;"
              "page-break-after:always}section:last-of-type,.slide:last-of-type{break-after:auto!important;page-break-after:auto!important}nav,.nav,.controls,.progress,.counter,.hint,button{display:none!important}"
              "*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style>")


def _printable(src):
    """Презентация, собранная моделью без правил печати (слайды прячутся и листаются скриптом), напечаталась бы одним
    слайдом. Тогда печатаем копию с правилами: каждый слайд — страница 16:9. -> путь к тому, что печатать (и временный ли)."""
    try:
        html = Path(src).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return src, False
    low = html.lower()
    deck = len(re.findall(r"<section\b", low)) >= 2 or len(re.findall(r'class="[^"]*\bslide\b', low)) >= 2
    if not deck or "@media print" in low:
        return src, False
    tmp = Path(src).with_name(f".печать-{Path(src).name}")     # рядом с исходной: относительные ссылки на картинки работают
    html = html.replace("</head>", PRINT_DECK + "</head>", 1) if "</head>" in low else PRINT_DECK + html
    tmp.write_text(html, encoding="utf-8")
    return tmp, True


def html_to_pdf(src, dst, timeout=90):
    """Страница → PDF браузером без окна. -> путь к PDF."""
    src, temp = _printable(src)
    try:
        return _html_to_pdf(src, dst, timeout)
    finally:
        if temp:
            Path(src).unlink(missing_ok=True)


def _html_to_pdf(src, dst, timeout=90):
    br = find_browser()
    if not br:
        raise ExportError("для PDF нужен браузер Chrome, Chromium или Edge — его нет. Откройте страницу и выберите "
                          "«Печать → Сохранить как PDF»")
    src, dst = Path(src).resolve(), Path(dst)
    prof = tempfile.mkdtemp(prefix="dewiar-pdf-")              # свой профиль: не мешаем открытому браузеру человека
    cmd = [br, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
           f"--user-data-dir={prof}", "--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=4000",
           f"--print-to-pdf={dst}", src.as_uri()]
    if not WIN and hasattr(os, "geteuid") and os.geteuid() == 0:
        cmd.insert(1, "--no-sandbox")                          # от root браузер иначе не запускается
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=0x08000000 if WIN else 0)      # CREATE_NO_WINDOW
        if not dst.is_file() or dst.stat().st_size < 500:      # старый Chrome не знает --headless=new
            cmd[cmd.index("--headless=new")] = "--headless"
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=0x08000000 if WIN else 0)
    except subprocess.TimeoutExpired as e:
        raise ExportError("браузер не успел сделать PDF за полторы минуты") from e
    except OSError as e:
        raise ExportError(f"браузер для PDF не запустился: {e}") from e
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    if not dst.is_file() or dst.stat().st_size < 500:
        raise ExportError("браузер не сохранил PDF" + (f": {(r.stderr or '').strip()[-200:]}" if r.stderr else ""))
    log.info("PDF: %s (%d КБ, %s)", dst, dst.stat().st_size // 1024, Path(br).name)
    return dst


def page_title(src):
    """Имя для копии: у страницы — её <title> («slides.html» → «Погода в Минске»), иначе имя файла."""
    src = Path(src)
    if src.suffix.lower() in (".html", ".htm"):
        try:
            head = src.read_text(encoding="utf-8", errors="replace")[:20000]
            m = re.search(r"<title[^>]*>(.*?)</title>", head, re.I | re.S)
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""
            if t:
                import html as H
                return H.unescape(t)
        except OSError:
            pass
    return src.stem


def export(src, title, fmt="file"):
    """Копия результата в «Загрузки» под именем title. fmt: file и html — копия как есть, pdf — страница в PDF
    (уже PDF — просто копия). -> путь."""
    src = Path(src)
    if not src.is_file():
        raise ExportError("файла уже нет — возможно, задачу удалили")
    out = downloads_dir()
    if fmt == "pdf":
        if src.suffix.lower() == ".pdf":
            fmt = "file"
        elif src.suffix.lower() not in (".html", ".htm", ".svg", ".md", ".txt"):
            raise ExportError("в PDF превращаются страницы (HTML) — этот файл скачайте как есть")
        else:
            return html_to_pdf(src, unique(out / safe_name(title, ".pdf")))
    dst = unique(out / safe_name(title, src.suffix.lower()))
    shutil.copy2(src, dst)
    log.info("Скачано: %s", dst)
    return dst


def reveal(path):
    """Показать файл в папке (Windows — выделенным в Проводнике)."""
    p = Path(path)
    try:
        if WIN:
            subprocess.Popen(["explorer", "/select,", str(p)], creationflags=0x08000000)
        elif sys.platform == "darwin":                       # Finder с выделенным файлом
            subprocess.Popen(["open", "-R", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(p.parent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        log.info("папку не открыть: %s", e)


def open_file(path):
    """Открыть файл программой по умолчанию."""
    p = Path(path)
    try:
        if WIN:
            os.startfile(str(p))  # noqa: S606
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        raise ExportError(f"не открылось: {e}") from e
