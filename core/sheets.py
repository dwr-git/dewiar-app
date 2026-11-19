"""Таблицы Excel и LibreOffice текстом — для разговора, «Моих файлов» и read_file (жалоба №892, 19.11: «скинула две
таблицы Excel, в диалоге вижу, что скинула, но Патрик их не видит»). Раньше .xlsx читался как обычный текст и выходило
«текста в нём нет».

Только стандартная библиотека (zipfile, re): .xlsx / .xlsm (Office Open XML) и .ods (OpenDocument), плюс .pptx — текст
слайдов. Старый двоичный .xls не читаем — понятная ошибка «сохраните как .xlsx».

Вид для модели — по листу:
    ## Лист «Расходы» · строк 120
    Дата | Категория | Сумма
    01.11.2026 | Продукты | 2350
Даты (числа со «датным» форматом ячейки) — как ДД.ММ.ГГГГ, формулы — их посчитанным значением (как видит человек)."""

import datetime as _dt
import html
import re
import zipfile
from pathlib import Path

EXTS = {".xlsx", ".xlsm", ".ods"}
SLIDES = {".pptx"}
CAP = 2 << 20                 # текст таблицы — не больше 2 МБ (огромную выгрузку дочитают кодом: run_python)
ROWS = 20000                  # строк на лист — не больше
COLS = 60                     # столбцов — не больше (дальше пустые хвосты выгрузок)
XML_MAX = 64 << 20            # распакованная часть архива — не больше


class SheetError(ValueError):
    """Понятная человеку ошибка."""


def _x(s):
    return html.unescape(s or "")


def _read(z, name):
    with z.open(name) as f:
        return f.read(XML_MAX).decode("utf-8", "replace")


def _col(ref):
    """«AB12» -> 27 (с нуля)."""
    n = 0
    for ch in re.match(r"[A-Z]*", ref or "").group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


# встроенные «датные» форматы Excel (14–22, 45–47) и свои форматы с д/м/г, но без «0.00»
_DATE_IDS = set(range(14, 23)) | {45, 46, 47}


def _date_styles(z):
    """Номера стилей ячеек (s="…"), у которых формат — дата или время."""
    try:
        st = _read(z, "xl/styles.xml")
    except KeyError:
        return set()
    custom = {}
    for m in re.finditer(r'<numFmt\b[^>]*numFmtId="(\d+)"[^>]*formatCode="([^"]*)"', st):
        code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", _x(m.group(2))).lower()
        custom[int(m.group(1))] = bool(re.search(r"[dmyдмг]", code)) and not re.search(r"0[.,]0|#", code)
    xfs = re.search(r"<cellXfs\b[^>]*>(.*?)</cellXfs>", st, re.S)
    out = set()
    for i, m in enumerate(re.finditer(r"<xf\b([^>]*)/?>", xfs.group(1) if xfs else "")):
        fid = re.search(r'numFmtId="(\d+)"', m.group(1))
        fid = int(fid.group(1)) if fid else 0
        if fid in _DATE_IDS or custom.get(fid):
            out.add(i)
    return out


def _serial_date(v, date1904=False):
    try:
        f = float(v)
    except ValueError:
        return v
    base = _dt.datetime(1904, 1, 1) if date1904 else _dt.datetime(1899, 12, 30)
    try:
        d = base + _dt.timedelta(days=f)
    except OverflowError:
        return v
    if abs(f - int(f)) < 1e-9:
        return d.strftime("%d.%m.%Y")
    if f < 1:                                          # только время
        return d.strftime("%H:%M")
    return d.strftime("%d.%m.%Y %H:%M")


def _num(v):
    """«2350.0000000001» -> «2350», «0.1» как есть: числа — коротко, как в ячейке."""
    try:
        f = float(v)
    except ValueError:
        return v
    if f == int(f) and abs(f) < 1e15:
        return str(int(f))
    return f"{f:.10g}"


def _xlsx(p):
    with zipfile.ZipFile(p) as z:
        from quality import zip_bomb
        why = zip_bomb(z)
        if why:
            raise SheetError(f"архив таблицы подозрительный ({why}) — не читаю")
        names = set(z.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in re.finditer(r"<si\b[^>]*>(.*?)</si>", _read(z, "xl/sharedStrings.xml"), re.S):
                body = re.sub(r"<rPh\b.*?</rPh>", "", si.group(1), flags=re.S)        # фонетика (японские подсказки) — не текст
                shared.append(_x("".join(re.findall(r"<t\b[^>]*>(.*?)</t>", body, re.S))))
        wb = _read(z, "xl/workbook.xml")
        d1904 = bool(re.search(r'date1904="(1|true)"', wb))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            for m in re.finditer(r"<Relationship\b([^>]*)/?>", _read(z, "xl/_rels/workbook.xml.rels")):
                a = m.group(1)
                rid, tgt = re.search(r'Id="([^"]+)"', a), re.search(r'Target="([^"]+)"', a)
                if rid and tgt:
                    t = tgt.group(1).lstrip("/")
                    rels[rid.group(1)] = t if t.startswith("xl/") else "xl/" + t
        sheets = []
        for m in re.finditer(r"<sheet\b([^>]*)/?>", wb):
            a = m.group(1)
            nm = re.search(r'name="([^"]*)"', a)
            rid = re.search(r'r:id="([^"]+)"', a) or re.search(r'\bid="([^"]+)"', a)
            if re.search(r'state="(hidden|veryHidden)"', a):
                continue
            path = rels.get(rid.group(1)) if rid else None
            if path and path in names:
                sheets.append((_x(nm.group(1)) if nm else path, path))
        if not sheets:                                  # без workbook-связей — по порядку файлов
            sheets = [(Path(n).stem, n) for n in sorted(names) if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
        dates = _date_styles(z)
        out = []
        for title, path in sheets:
            rows = []
            for rm in re.finditer(r"<row\b[^>]*>(.*?)</row>|<row\b[^>]*/>", _read(z, path), re.S):
                if len(rows) >= ROWS:
                    break
                cells = {}
                for cm in re.finditer(r"<c\b([^>]*?)(?:/>|>(.*?)</c>)", rm.group(1) or "", re.S):
                    a, body = cm.group(1), cm.group(2) or ""
                    ref = re.search(r'\br="([A-Z]+)\d+"', a)
                    ci = _col(ref.group(1)) if ref else len(cells)
                    if ci >= COLS:
                        continue
                    t = re.search(r'\bt="(\w+)"', a)
                    t = t.group(1) if t else "n"
                    v = re.search(r"<v\b[^>]*>(.*?)</v>", body, re.S)
                    v = _x(v.group(1)) if v else ""
                    if t == "s":
                        v = shared[int(v)] if v.isdigit() and int(v) < len(shared) else ""
                    elif t == "inlineStr":
                        v = _x("".join(re.findall(r"<t\b[^>]*>(.*?)</t>", body, re.S)))
                    elif t == "b":
                        v = "да" if v == "1" else ("нет" if v == "0" else v)
                    elif t == "n" and v:
                        s = re.search(r'\bs="(\d+)"', a)
                        v = _serial_date(v, d1904) if s and int(s.group(1)) in dates else _num(v)
                    v = v.replace("\r", "").replace("\n", " ").replace("|", "/").strip()
                    if v:
                        cells[ci] = v
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
            out.append((title, rows))
        return out


def _ods(p):
    with zipfile.ZipFile(p) as z:
        from quality import zip_bomb
        why = zip_bomb(z)
        if why:
            raise SheetError(f"архив таблицы подозрительный ({why}) — не читаю")
        x = _read(z, "content.xml")
    out = []
    for tm in re.finditer(r'<table:table\b([^>]*)>(.*?)</table:table>', x, re.S):
        nm = re.search(r'table:name="([^"]*)"', tm.group(1))
        rows = []
        for rm in re.finditer(r"<table:table-row\b([^>]*?)(?:/>|>(.*?)</table:table-row>)", tm.group(2), re.S):
            rep_r = re.search(r'table:number-rows-repeated="(\d+)"', rm.group(1))
            cells = []
            for cm in re.finditer(r"<table:(?:covered-)?table-cell\b([^>]*?)(?:/>|>(.*?)</table:(?:covered-)?table-cell>)",
                                  rm.group(2) or "", re.S):
                a, body = cm.group(1), cm.group(2) or ""
                rep = re.search(r'table:number-columns-repeated="(\d+)"', a)
                vt = re.search(r'office:value-type="(\w+)"', a)
                v = ""
                if vt and vt.group(1) == "date":
                    d = re.search(r'office:date-value="([^"]+)"', a)
                    if d:
                        try:
                            dd = _dt.datetime.fromisoformat(d.group(1))
                            v = dd.strftime("%d.%m.%Y" if (dd.hour, dd.minute) == (0, 0) else "%d.%m.%Y %H:%M")
                        except ValueError:
                            v = d.group(1)
                if not v:
                    paras = re.findall(r"<text:p\b[^>]*>(.*?)</text:p>", body, re.S)
                    v = " ".join(_x(re.sub(r"<[^>]+>", "", s)) for s in paras)
                    if not v and vt and vt.group(1) in ("float", "currency", "percentage"):
                        n = re.search(r'office:value="([^"]+)"', a)
                        v = _num(n.group(1)) if n else ""
                v = v.replace("\n", " ").replace("|", "/").strip()
                k = min(int(rep.group(1)) if rep else 1, COLS)
                cells.extend([v] * k)
                if len(cells) >= COLS:
                    cells = cells[:COLS]
                    break
            while cells and not cells[-1]:
                cells.pop()
            k = int(rep_r.group(1)) if rep_r else 1
            rows.extend([cells] * (min(k, 50) if cells else min(k, 1)))   # пустые повторы (миллион строк) — одной
            if len(rows) >= ROWS:
                break
        out.append((_x(nm.group(1)) if nm else f"Лист {len(out) + 1}", rows))
    return out


def _render(sheets, cap):
    parts, used = [], 0
    for title, rows in sheets:
        while rows and not any(rows[-1]):
            rows.pop()
        filled = [r for r in rows if any(r)]
        if not filled:
            continue
        lines = [f"## Лист «{title}» · строк {len(filled)}"]
        gap = False
        for r in rows:
            if not any(r):
                gap = bool(lines[-1:] and not lines[-1].startswith("## "))
                continue
            if gap:
                lines.append("")
                gap = False
            lines.append(" | ".join(r))
        block = "\n".join(lines)
        if used + len(block) > cap:
            block = block[:max(0, cap - used)].rsplit("\n", 1)[0] + "\n…(таблица обрезана — целиком её разберёт код: run_python)"
            parts.append(block)
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts)


def _pptx(p, cap):
    with zipfile.ZipFile(p) as z:
        from quality import zip_bomb
        why = zip_bomb(z)
        if why:
            raise SheetError(f"архив презентации подозрительный ({why}) — не читаю")
        slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                        key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        out, used = [], 0
        for i, n in enumerate(slides, 1):
            paras = []
            for pm in re.finditer(r"<a:p\b[^>]*>(.*?)</a:p>", _read(z, n), re.S):
                t = "".join(_x(s) for s in re.findall(r"<a:t\b[^>]*>(.*?)</a:t>", pm.group(1), re.S)).strip()
                if t:
                    paras.append(t)
            note = n.replace("slides/slide", "notesSlides/notesSlide")
            notes = []
            if note in z.namelist():
                notes = [t for t in (_x(s).strip() for s in re.findall(r"<a:t\b[^>]*>(.*?)</a:t>", _read(z, note), re.S))
                         if t and not t.isdigit()]
            block = f"## Слайд {i}\n" + "\n".join(paras) + (("\nЗаметки: " + " ".join(notes)) if notes else "")
            if used + len(block) > cap:
                out.append("…(дальше обрезано)")
                break
            out.append(block)
            used += len(block)
        return "\n\n".join(out)


def text(p, cap=CAP) -> str:
    """Таблица или презентация -> текст для модели и поиска. Нечитаемый файл — SheetError с понятным текстом."""
    p = Path(p)
    ext = p.suffix.lower()
    if ext == ".xls":
        raise SheetError(f"«{p.name}» — старый формат Excel (.xls): откройте его и сохраните как .xlsx")
    try:
        if ext in (".xlsx", ".xlsm"):
            return _render(_xlsx(p), cap)
        if ext == ".ods":
            return _render(_ods(p), cap)
        if ext in SLIDES:
            return _pptx(p, cap)
    except (zipfile.BadZipFile, KeyError) as e:
        raise SheetError(f"«{p.name}» не открылся как {ext[1:].upper()} — файл повреждён или это другой формат ({e})")
    return ""
