"""Проверки качества (quality.py): готовые файлы — кодом, а не на слово. check_file / verify_outputs / quick_check —
пустые, оборванный HTML, битые JSON/CSV/Office/PDF/картинки, синтаксис Python, не UTF-8; error_hint — подсказка по
тексту ошибки скрипта; чтение файлов для сверки (file_text, count_of, zip_bomb)."""

import json
import logging
import re
import zipfile

from pathlib import Path


log = logging.getLogger("dewiar.quality")


# служебные файлы и папки верхнего уровня папки задачи (tasks.py): готовыми результатами не считаются
SERVICE = ("_run", "_out", "_src", "_snap", "_explore", "задача.json", "история.json", "история.json.tmp", "журнал.md", "план.md", "блокнот.md", "итог.md",
           "задачи.json", "критерии.json", "_undo", "код.json")   # экзамен 0.84.1: «готовые файлы — только _undo/…, код.json»


# ---------------- проверка файлов ----------------


def _html_problems(rel, txt, final=True):
    """final=False — файл ещё может дописываться частями: оборванный конец не считаем браком."""
    out = []
    low = txt.lower()
    esc = len(re.findall(r"&lt;(?:html|body|div|script|canvas|h1|p)\b", low))
    real = len(re.findall(r"<(?:html|body|div|script|canvas|h1|p)\b", low))
    if esc >= 3 and esc > real:
        out.append(f"{rel}: разметка ЭКРАНИРОВАНА (&lt;div&gt; вместо <div>) — страница покажется текстом. Перезапиши обычными тегами.")
    if final and "<html" in low and "</html>" not in low:
        out.append(f"{rel}: HTML ОБОРВАН — нет закрывающего </html>. Допиши конец файла (append=true), не переписывая целиком.")
    if low.count("<script") > low.count("</script>"):
        out.append(f"{rel}: незакрытый <script> — скрипт не выполнится. Закрой тег.")
    if low.count("<style") > low.count("</style>"):
        out.append(f"{rel}: незакрытый <style> — страница сломается. Закрой тег.")
    fm = re.search(r"""fetch\(\s*['"]([^'"]+\.(?:json|csv))['"]""", txt)
    if fm and not fm.group(1).startswith(("http://", "https://")):
        out.append(f"{rel}: fetch() локального .json/.csv не работает, когда файл открыт с диска — вшей данные прямо в страницу.")
    return out


def check_file(path, rel=None, final=True):
    """Дефекты одного файла -> [строки «что не так и что сделать»] — тексты для модели.
    Ошибка самой проверки — не дефект (иначе модель чинит то, что не сломано)."""
    p = Path(path)
    rel = rel or p.name
    try:
        if not p.exists():
            return [f"{rel}: файл обещан, но НЕ существует — создай его."]
        if p.is_dir():
            return []
        size = p.stat().st_size
        if size == 0:
            return [f"{rel}: файл ПУСТОЙ (0 байт) — перезапиши с содержимым."]
        ext = p.suffix.lower()
        head = p.read_bytes()[:8192] if size < 50 << 20 else open(p, "rb").read(8192)
        if ext in (".html", ".htm"):
            return _html_problems(rel, p.read_text(encoding="utf-8", errors="replace"), final)
        if ext == ".json":
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                return [f"{rel}: НЕВАЛИДНЫЙ JSON ({str(e)[:120]}) — исправь синтаксис."]
        elif ext in (".csv", ".tsv"):
            import csv
            sep = "\t" if ext == ".tsv" else None
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            lines = text.splitlines()[:500]
            if not [x for x in lines if x.strip()]:
                return [f"{rel}: таблица пустая — запиши данные."]
            if sep is None:
                try:
                    sep = csv.Sniffer().sniff(text[:4096], delimiters=",;\t").delimiter
                except csv.Error:
                    sep = ","
            rows = [r for r in csv.reader(lines, delimiter=sep) if r]
            # брак — только если не совпадает заметная доля строк: одиночные кривые строки бывают и в нормальных таблицах
            cols = len(rows[0])
            bad = sum(len(r) != cols for r in rows[1:])
            if bad > max(2, len(rows) // 10):
                return [f"{rel}: у {bad} строк из {len(rows)} число колонок не совпадает с заголовком ({cols}) — файл битый, "
                        "пересохрани через csv.writer или pandas."]
        elif ext in (".docx", ".xlsx", ".pptx", ".zip", ".odt", ".ods", ".odp", ".epub"):
            if not head.startswith(b"PK"):
                return [f"{rel}: это не настоящий {ext[1:]} (внутри не архив Office/ZIP) — собери файл библиотекой (python-docx, openpyxl, python-pptx)."]
            try:
                with zipfile.ZipFile(p) as z:
                    bomb = zip_bomb(z)
                    if bomb:
                        return [f"{rel}: архив подозрительный ({bomb}) — так Office-файлы не выглядят, пересобери."]
                    if z.testzip() is not None:
                        return [f"{rel}: архив повреждён — пересобери файл."]
            except zipfile.BadZipFile:
                return [f"{rel}: файл повреждён (архив не открывается) — пересобери."]
        elif ext == ".pdf":
            if not head.startswith(b"%PDF-"):
                return [f"{rel}: это не PDF (нет заголовка %PDF-) — собери настоящий PDF."]
            with open(p, "rb") as f:
                f.seek(max(0, size - 2048))
                if b"%%EOF" not in f.read():
                    return [f"{rel}: PDF оборван (нет %%EOF в конце) — пересобери."]
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ok = (head.startswith(b"\x89PNG") if ext == ".png" else head.startswith(b"\xff\xd8") if ext in (".jpg", ".jpeg")
                  else head.startswith(b"GIF8") if ext == ".gif" else head[8:12] == b"WEBP")
            if not ok:
                return [f"{rel}: внутри не картинка {ext[1:]} — сохрани изображение заново (Pillow / matplotlib savefig)."]
        elif ext == ".py":
            try:
                compile(p.read_text(encoding="utf-8"), str(p), "exec")
            except SyntaxError as e:
                return [f"{rel}: СИНТАКСИЧЕСКАЯ ошибка Python в строке {e.lineno}: {e.msg} — почини."]
            except UnicodeDecodeError:
                return [f"{rel}: файл не в UTF-8 — пересохрани в UTF-8."]
        elif ext in (".md", ".txt", ".srt", ".css", ".js", ".svg", ".xml"):
            try:
                (p.read_bytes()[:32768]).decode("utf-8")
            except UnicodeDecodeError as e:
                if e.start < 32760:                 # ошибка у самого края — это обрезанная на 32 КБ буква, не брак
                    return [f"{rel}: текст не в UTF-8 — пересохрани в UTF-8 (encoding='utf-8')."]
    except Exception as e:  # noqa: BLE001
        log.debug("проверка %s: %s", rel, e)
    return []


def verify_outputs(task_dir, shown=()):
    """Готовые файлы задачи: outputs/ (не больше 200) и показанные пользователю (shown, пути от папки задачи).
    -> список дефектов; файл, показанный, но не созданный, — тоже дефект."""
    d = Path(task_dir)
    rels = []
    out = d / "outputs"
    if out.is_dir():
        rels += [p.relative_to(d).as_posix() for p in sorted(out.rglob("*")) if p.is_file()][:200]
    for r in shown:
        if r and r not in rels:
            rels.append(r)
    problems = []
    for r in rels:
        problems += check_file(d / r, r)
    return problems


def summarize(problems, limit=8):
    """Дефекты -> сообщение модели, после которого она должна починить файлы и снова вызвать finish."""
    lines = problems[:limit] + ([f"…и ещё {len(problems) - limit}"] if len(problems) > limit else [])
    return ("МАШИННАЯ ПРОВЕРКА ФАЙЛОВ НАШЛА БРАК:\n- " + "\n- ".join(lines) +
            "\nЭто ОБЪЕКТИВНЫЕ дефекты (найдены кодом, не мнением). Почини КАЖДЫЙ пункт точечно, проверь и только потом снова вызови finish.")


def quick_check(path, rel=None):
    """Сразу после записи файла: только .py/.json/.html, чтобы не запускать сломанное. -> предупреждение или ""."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in (".py", ".json", ".html", ".htm"):
        return ""
    if ext in (".html", ".htm"):
        txt = p.read_text(encoding="utf-8", errors="replace")
        if "</html>" not in txt.lower():
            return ""                                         # пишется частями — проверим, когда допишет
    probs = check_file(p, rel)
    return ("⚠ ПРОВЕРКА: " + " ".join(probs)) if probs else ""


# ---------------- подсказки по ошибкам ----------------


# имя модуля в import -> имя пакета для pip, когда они различаются
PIP_NAMES = {"cv2": "opencv-python-headless", "PIL": "Pillow", "docx": "python-docx", "pptx": "python-pptx", "yaml": "pyyaml",
             "sklearn": "scikit-learn", "bs4": "beautifulsoup4", "fitz": "pymupdf", "dateutil": "python-dateutil"}


# (шаблон в выводе скрипта, подсказка); срабатывает первый подошедший — порядок важен
HINTS = [
    (r"ModuleNotFoundError: No module named '([\w.]+)'", lambda m: (
        f"Модуля {m.group(1)} нет. Обойдись стандартной библиотекой или тем, что есть (numpy, Pillow, httpx, pypdf), либо "
        f"скажи пользователю, что нужен пакет {PIP_NAMES.get(m.group(1).split('.')[0], m.group(1).split('.')[0])}.")),
    (r"FileNotFoundError|No such file or directory", lambda m: (
        "Файла нет: сначала посмотри list_files; папки создавай os.makedirs(..., exist_ok=True); пути — относительно папки задачи.")),
    (r"\b40[13]\b.*(?:Forbidden|Unauthorized)|status(?:_code)?\W+40[13]", lambda m: (
        "Сайт не пускает (401/403): добавь заголовок User-Agent браузера; не помогло — другой источник (web_search).")),
    (r"Остановлено по времени|TimeoutExpired|timed out", lambda m: (
        "Долго: делай работу порциями — прогресс в файл после каждой порции, повторный запуск продолжает с места.")),
    (r"UnicodeDecodeError", lambda m: "Кодировка: открывай файлы с encoding='utf-8' (errors='replace'), для Windows-файлов — cp1251."),
    (r"JSONDecodeError", lambda m: "Пришёл не JSON: сначала напечатай начало ответа (print(r.text[:500])) и посмотри, что там."),
    (r"SyntaxError|IndentationError", lambda m: (
        "Синтаксис: перепиши код проще; HTML/JS не клади в f-строки — пиши файл через write_file или вставляй данные через .replace().")),
    (r"MemoryError|Killed|exit(?:ed)? (?:code )?137", lambda m: "Не хватило памяти: обрабатывай данными частями (chunks), не читай всё сразу."),
    (r"SSLError|CERTIFICATE_VERIFY_FAILED", lambda m: "Ошибка сертификата сайта: попробуй другой адрес (https/http) или источник."),
    (r"PermissionError", lambda m: "Нет прав на запись: пиши только в папку задачи (outputs/)."),
]


def error_hint(output):
    for rx, fn in HINTS:
        m = re.search(rx, output or "")
        if m:
            return "Подсказка: " + fn(m)
    return ""


# ---------------- чтение файлов для сверки ----------------


def _nums(s):
    """Числа строки: «1 234,56» -> 1234.56, «3,2» -> 3.2 (запятая — дробная часть)."""
    out = []
    for m in re.finditer(r"(?<![\d.,])-?\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|(?<![\d.,])-?\d+(?:[.,]\d+)?", str(s or "")):
        try:
            out.append(float(re.sub(r"[   ]", "", m.group(0)).replace(",", ".")))
        except ValueError:
            pass
    return out


TEXT_FILE_MAX = 64 << 20           # файл для проверок — не больше (pdf, docx, xlsx); текст читается только начало


ZIP_MAX = 256 << 20                 # архив Office: распакованное целиком — не больше


ZIP_RATIO = 400                     # …и не «бомба» (сжатие в сотни раз)


def zip_bomb(z):
    """ZipFile -> причина «это бомба» или "" (вторая рецензия: docx на 1,5 ГБ текста съедал память проверки)."""
    total = 0
    for i in z.infolist():
        total += i.file_size
        if total > ZIP_MAX:
            return f"внутри больше {ZIP_MAX >> 20} МБ"
        if i.compress_size and i.file_size > 1 << 20 and i.file_size / i.compress_size > ZIP_RATIO:
            return f"«{i.filename}» сжат в {i.file_size // max(1, i.compress_size)} раз"
    return ""


def _zread(z, name, cap):
    """Член архива — не больше cap байт (поток, без чтения целиком)."""
    with z.open(name) as f:
        return f.read(cap)


def file_text(p, limit=2_000_000):
    """Текст файла для проверок: обычный текст (UTF-8 / cp1251), ячейки .xlsx, текст .docx и .pptx, страницы .pdf (pypdf).
    Не вышло — ""."""
    p = Path(p)
    if p.is_symlink() or not p.is_file():    # ссылку или FIFO мог оставить код задачи (выпуск 5) — не идём по ним
        return ""
    try:
        ext = p.suffix.lower()
        if ext in (".xlsx", ".docx", ".pptx", ".odt", ".pdf") and p.stat().st_size > TEXT_FILE_MAX:
            return ""
        if ext in (".xlsx", ".docx", ".pptx", ".odt"):
            with zipfile.ZipFile(p) as z:
                if zip_bomb(z):
                    return ""
        if ext == ".xlsx":
            import openpyxl
            wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
            rows, n = [], 0
            for ws in wb.worksheets:
                for r in ws.iter_rows(values_only=True):
                    n += 1
                    if n > 20000:
                        break
                    rows.append("\t".join("" if v is None else str(v) for v in r))
            wb.close()
            return "\n".join(rows)[:limit]
        if ext in (".docx", ".pptx", ".odt"):
            with zipfile.ZipFile(p) as z:
                xml = " ".join(_zread(z, n, limit * 4).decode("utf-8", "replace") for n in z.namelist()
                               if re.match(r"(word/document|ppt/slides/slide\d+|content)\.xml$", n))
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))[:limit]
        if ext == ".pdf":                                       # pypdf — в отдельном процессе с пределами (PDF-бомба)
            import pdftext
            return "\n".join(pdftext.pages(p, limit=400, cap=limit))[:limit]
        with open(p, "rb") as f:
            data = f.read(limit)
        if b"\0" in data[:4096]:
            return ""
        try:
            return data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            # 0.86: предел обрезал UTF-8 посреди буквы — это всё ещё UTF-8, а не cp1251 (было: выдержка русского отчёта для
            # проверяющего приходила «РћС‚С‡С‘С‚» примерно в половине случаев)
            if len(data) >= limit and e.start >= len(data) - 3:
                return data[:e.start].decode("utf-8-sig", "replace")
            return data.decode("cp1251", "replace")
    except Exception as e:  # noqa: BLE001 — битый файл: проверка «не прочитался», а не сбой задачи
        log.debug("текст %s: %s", p, e)
        return ""


def count_of(p, unit):
    """Сколько страниц / строк / строк таблицы / файлов в p -> число или None (так не посчитать)."""
    p = Path(p)
    if unit == "files":
        return sum(1 for x in p.rglob("*") if x.is_file()) if p.is_dir() else (1 if p.is_file() else 0)
    if unit == "pages":
        if p.is_dir():                                          # сайт: страницы .html в папке
            return sum(1 for x in p.rglob("*.htm*") if x.is_file())
        ext = p.suffix.lower()
        if ext == ".pdf":
            try:
                import pdftext
                return pdftext.count(p)
            except Exception:  # noqa: BLE001
                with open(p, "rb") as f:
                    return len(re.findall(rb"/Type\s*/Page(?!s)", f.read(TEXT_FILE_MAX)))
        if ext == ".pptx":
            try:
                with zipfile.ZipFile(p) as z:
                    return sum(1 for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
            except zipfile.BadZipFile:
                return 0
        if ext in (".html", ".htm"):
            return 1
        return None
    if not p.is_file():
        return 0
    if unit == "lines":
        return sum(1 for ln in file_text(p).splitlines() if ln.strip())
    if unit == "rows":
        if p.suffix.lower() in (".xlsx",):
            return max(0, sum(1 for ln in file_text(p).splitlines() if ln.strip("\t ")) - 1)
        rows = [ln for ln in file_text(p).splitlines() if ln.strip()]
        return max(0, len(rows) - 1)
    return None


def _range(v):
    m = re.match(r"^\s*(\d+)\s*(?:[-–—]\s*(\d+))?\s*$", str(v))
    return (int(m.group(1)), int(m.group(2)) if m.group(2) else None) if m else (0, None)
