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


_WS = "\t\n\f\r "


_ASCII_LOW = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def strip_meta_equiv(html):
    """Убрать каждый <meta> с атрибутом http-equiv (refresh, свой CSP…) — разбирая тег так, как его разберёт браузер:
    «>» в кавычках, сущности в значении и «<meta» в строке скрипта регулярку обходили (четвёртая рецензия). Тег
    заменяется пробелом (не склеится в новый), поиск — по всем вхождениям, пока что-то убирается. То же — в
    ui/studio/core.js (stripMetaEquiv)."""
    s = str(html or "")
    for _ in range(8):
        low, cut, n = s.translate(_ASCII_LOW), [], len(s)     # только A–Z, как браузер: «İ».lower() — два знака (рецензия 5e)
        j = low.find("<meta")
        while j >= 0:
            c = s[j + 5] if j + 5 < n else ""
            if c == "" or c in _WS or c in "/>":
                k, end, eq = j + 5, -1, False
                while k < n:
                    ch = s[k]
                    if ch in _WS or ch == "/":
                        k += 1
                        continue
                    if ch == ">":
                        end = k + 1
                        break
                    st = k
                    k += 1                                     # первый знак имени (и «=») — часть имени
                    while k < n and s[k] not in _WS and s[k] not in "/>=":
                        k += 1
                    if s[st:k].translate(_ASCII_LOW) == "http-equiv":
                        eq = True
                    while k < n and s[k] in _WS:
                        k += 1
                    if k < n and s[k] == "=":
                        k += 1
                        while k < n and s[k] in _WS:
                            k += 1
                        if k < n and s[k] in "\"'":
                            e = s.find(s[k], k + 1)
                            k = n if e < 0 else e + 1
                        else:
                            while k < n and s[k] not in _WS and s[k] != ">":
                                k += 1
                if end < 0:                                    # тег не закрыт до конца: браузер его отбросит — и мы
                    cut.append((j, n))
                    break
                if eq:
                    cut.append((j, end))
            j = low.find("<meta", j + 5)
        if not cut:
            return s
        out, at = [], 0
        for a, b in sorted(cut):
            if b <= at:
                continue
            out.append(s[at:max(at, a)] + " ")
            at = b
        s = "".join(out) + s[at:]
    return s


def print_html(html, scripts=True):
    """Печатная копия страницы: CSP — самой первой строкой (до всего, что есть у страницы), без <meta http-equiv>
    (strip_meta_equiv); презентация без правил печати (слайды прячутся и листаются скриптом) получает их — каждый слайд
    на странице 16:9."""
    html = re.sub(r"^\ufeff?\s*<!doctype[^>]*>", "", html, flags=re.I)
    html = strip_meta_equiv(html)
    low = html.lower()
    deck = len(re.findall(r"<section\b", low)) >= 2 or len(re.findall(r'class="[^"]*\bslide\b', low)) >= 2
    if deck and "@media print" not in low:
        html = html.replace("</head>", PRINT_DECK + "</head>", 1) if "</head>" in low else PRINT_DECK + html
    csp = PRINT_CSP if scripts else PRINT_CSP.replace("script-src 'unsafe-inline' file:", "script-src 'none'")
    return f'<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{csp}">' + html


def _printable(src, scripts=True):
    """Что печатать: копия рядом с исходной (относительные ссылки на картинки работают) — print_html.
    scripts=False — скрипты страницы выключены (CSP script-src 'none'): так печатает браузер компьютера без Playwright.
    -> (путь, временный ли). Рядом записать нельзя — копия во временной папке (картинки по относительным ссылкам
    пропадут, но страница без скриптов и чужих кадров)."""
    src = Path(src)
    ext = src.suffix.lower()
    if ext not in (".html", ".htm", ".svg"):
        return src, False                                      # .md, .txt — браузер показывает их текстом, без ресурсов
    if ext == ".svg":                                          # рисунок — картинкой: без своих скриптов и подгрузок
        import html as H
        html = f'<html><body style="margin:0"><img src="{H.escape(src.name)}" style="max-width:100%"></body></html>'
        tmp = src.with_name(f".печать-{src.stem}.html")
    else:
        try:
            html = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return src, False
        tmp = src.with_name(f".печать-{src.name}")
    try:
        tmp.write_text(print_html(html, scripts), encoding="utf-8")
    except OSError:
        tmp = Path(tempfile.mkdtemp(prefix="dewiar-print-")) / tmp.name
        tmp.write_text(print_html(html, scripts), encoding="utf-8")
    return tmp, True


def html_to_pdf(src, dst, timeout=90, root=None):
    """Страница → PDF браузером без окна. root — откуда странице можно брать файлы (папка задачи; по умолчанию — папка
    самой страницы). -> путь к PDF."""
    root = os.path.realpath(root or Path(src).parent)
    if not os.environ.get("DEWIAR_PDF_BROWSER"):
        p, temp = _printable(src, scripts=True)               # Playwright: скрипты есть, файлы — только из папки задачи
        try:
            got = _pw_pdf(p, dst, root, timeout)
        finally:
            if temp:
                Path(p).unlink(missing_ok=True)
        if got:
            return got
    p, temp = _printable(src, scripts=False)                  # браузер компьютера: без скриптов (и в bwrap, где он есть)
    try:
        return _html_to_pdf(p, dst, timeout, root=root)
    finally:
        if temp:
            Path(p).unlink(missing_ok=True)


# Печать — без сети и без чужих файлов (третья рецензия выпуска 5): страница задачи печаталась в Chrome с сетью
# (<img src="http://…?данные">), а <iframe src="file:///home/…/.ssh/id_rsa"> попадал в PDF. Теперь: ключи браузера —
# как у проверки HTML (quality.NO_NET_ARGS), CSP — первой строкой печатной копии (кадров нет совсем, сети нет), а в
# Playwright (если он есть) файлы странице — только из папки задачи. Внешние картинки в PDF больше не попадают.
PRINT_CSP = ("default-src 'none'; script-src 'unsafe-inline' file:; style-src 'unsafe-inline' file:; img-src file: data: blob:; "
             "font-src file: data:; media-src file: data: blob:; frame-src 'none'; child-src 'none'; object-src 'none'; "
             "connect-src 'none'; form-action 'none'; base-uri 'none'")
NO_NET_ARGS = ["--proxy-server=socks5://127.0.0.1:9", "--proxy-bypass-list=<-loopback>",
               "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]


def _inside(path, root):
    rp = os.path.realpath(path)
    return rp == root or rp.startswith(root.rstrip(os.sep) + os.sep)


def _pw_pdf(src, dst, root, timeout=90):
    """PDF через Playwright (если он и его Chromium есть): без сети, файлы — только из root. -> путь или None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    from urllib.parse import unquote, urlparse
    dst = Path(dst)

    def route(r, *_):
        u = r.request.url
        if u.startswith(("data:", "blob:", "about:")) or (u.startswith("file:") and _inside(unquote(urlparse(u).path), root)):
            return r.continue_()
        return r.abort()
    try:
        with sync_playwright() as pw:
            try:
                br = pw.chromium.launch(args=NO_NET_ARGS)
            except Exception:  # noqa: BLE001 — Chromium Playwright не скачан: печатает браузер компьютера
                return None
            try:
                ctx = br.new_context(offline=True, service_workers="block")
                pg = ctx.new_page()
                pg.route("**/*", route)
                pg.goto(Path(src).resolve().as_uri(), wait_until="load", timeout=min(timeout, 60) * 1000)
                pg.wait_for_timeout(1500)                       # скрипты страницы дорисовали (как --virtual-time-budget)
                pg.pdf(path=str(dst), print_background=True, prefer_css_page_size=True, format="A4",
                       margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"})
            finally:
                br.close()
    except Exception as e:  # noqa: BLE001
        log.info("PDF через Playwright не вышел (%s) — печатает браузер компьютера", e)
        return None
    if dst.is_file() and dst.stat().st_size >= 500:
        log.info("PDF: %s (%d КБ, Playwright)", dst, dst.stat().st_size // 1024)
        return dst
    return None


def _print_jail(root, out_dir, prof, br):
    """Linux с работающим bwrap: браузер печати видит только систему (/usr, /etc без ключей сетей, /opt, шрифты), папку
    задачи (чтение), папку для PDF и свой временный профиль; сети нет совсем (--unshare-all). Четвёртая рецензия:
    страница без Playwright уводила себя на file:///…/.ssh/id_rsa — и он печатался в PDF. -> префикс команды или []."""
    if WIN or sys.platform == "darwin" or os.environ.get("DEWIAR_PDF_JAIL") == "0":
        return []
    try:
        import sandbox as S
        if not S.bwrap_ok():
            return []
        a = [S._bwrap_bin(), "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL"]
        for d in S.SYS_DIRS:
            if os.path.islink(d):
                a += ["--symlink", os.readlink(d), d]
            elif os.path.isdir(d):
                a += ["--ro-bind", d, d]
        a += ["--ro-bind", "/etc", "/etc"]
        for f in S.ETC_HIDE:
            a += S._hide_args(f)
        for d in ("/opt", "/sys", "/var/cache/fontconfig", "/var/lib/fontconfig"):
            a += ["--ro-bind-try", d, d]
        bdir = os.path.dirname(os.path.realpath(br))
        if not bdir.startswith(("/usr/", "/opt/")):
            a += ["--ro-bind-try", bdir, bdir]                 # браузер не из системы (~/.cache/ms-playwright…) — только он
        a += ["--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "--tmpfs", "/run", "--bind", prof, prof,
              "--ro-bind", str(root), str(root), "--bind", str(out_dir), str(out_dir), "--setenv", "HOME", prof, "--"]
        return a
    except Exception as e:  # noqa: BLE001
        log.info("PDF: без bwrap (%s)", e)
        return []


def _html_to_pdf(src, dst, timeout=90, root=None):
    br = find_browser()
    if not br:
        raise ExportError("для PDF нужен браузер Chrome, Chromium или Edge — его нет. Откройте страницу и выберите "
                          "«Печать → Сохранить как PDF»")
    src, dst = Path(src).resolve(), Path(dst)
    root = os.path.realpath(root or src.parent)
    prof = tempfile.mkdtemp(prefix="dewiar-pdf-")              # свой профиль: не мешаем открытому браузеру человека
    # скрипты страницы выключены CSP печатной копии (_printable scripts=False; четвёртая рецензия: location =
    # file:///…/.ssh/id_rsa печатал чужой файл). --blink-settings=scriptEnabled=false headless-печать не переносит: PDF нет.
    cmd = [br, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--hide-scrollbars",
           f"--user-data-dir={prof}", "--no-pdf-header-footer", "--print-to-pdf-no-header", "--virtual-time-budget=4000",
           *NO_NET_ARGS, f"--print-to-pdf={dst}", src.as_uri()]
    jail = _print_jail(root, dst.parent, prof, br)
    if jail or (not WIN and hasattr(os, "geteuid") and os.geteuid() == 0):
        cmd.insert(1, "--no-sandbox")                          # от root иначе не запускается; в bwrap песочница — он сам
    try:
        r = None
        if jail:
            r = subprocess.run(jail + cmd, capture_output=True, text=True, timeout=timeout)
            if not dst.is_file() or dst.stat().st_size < 500:
                log.info("PDF в bwrap не вышел (%s) — печатаю без него", (r.stderr or "").strip()[-200:])
        if not dst.is_file() or dst.stat().st_size < 500:
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


def export(src, title, fmt="file", root=None):
    """Копия результата в «Загрузки» под именем title. fmt: file и html — копия как есть, pdf — страница в PDF
    (уже PDF — просто копия; root — откуда странице можно брать файлы, html_to_pdf). -> путь."""
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
            return html_to_pdf(src, unique(out / safe_name(title, ".pdf")), root=root)
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


# что можно открыть «своей программой» (документы, картинки, звук, видео, страницы); остальное (.desktop, .sh, .jar, .exe,
# документы с макросами…) — только показать в папке: результат задачи мог написать код задачи (вторая рецензия выпуска 5)
# Без старых .doc/.xls/.ppt и .rtf (макросы и встроенные объекты без «m» в имени), .xml (Windows отдаёт Word-XML 2003
# самому Word), .ics и .vcf (открыть = сразу импорт в календарь и контакты) — их только показываем в папке (третья рецензия).
OPEN_OK = {".html", ".htm", ".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".svg", ".png", ".jpg", ".jpeg", ".gif",
           ".webp", ".bmp", ".ico", ".tif", ".tiff", ".heic", ".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".opus", ".aac",
           ".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".docx", ".xlsx", ".pptx", ".odt", ".ods",
           ".odp", ".epub", ".srt", ".vtt", ".zip", ".log", ".gpx", ".kml"}


def safe_to_open(path):
    """Папку и «безопасный» файл (OPEN_OK) можно открыть программой по умолчанию."""
    p = Path(path)
    return p.is_dir() or (p.suffix.lower() in OPEN_OK and not p.is_symlink())


def open_file(path):
    """Открыть файл программой по умолчанию; файл не из OPEN_OK — показать в папке (не запускать)."""
    p = Path(path)
    if not safe_to_open(p):
        reveal(p)
        return
    try:
        if WIN:
            os.startfile(str(p))  # noqa: S606
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        raise ExportError(f"не открылось: {e}") from e
