"""Точечные правки документов Office без порчи (владелец 12.11: «ты работаешь с документами и не портишь их — правки
точечно, через поиск внутри; в Gemini документ переписывается и появляются новые ошибки. Лира тоже так должна: прислал
docx — замени фамилии или даты — чётко»).

Документ не пересобирается: меняется только текст внутри XML нужных абзацев, всё остальное (стили, таблицы, картинки,
колонтитулы, нумерация, поля) остаётся байт в байт. Word разбивает текст абзаца на куски (runs) как угодно — «Иванов»
бывает «Ива» + «нов» с разным оформлением; поэтому поиск идёт по тексту всего абзаца, а замена кладётся в кусок, где
найденное начиналось (его оформление и сохраняется), и вычитается из следующих кусков.

Поддерживается: .docx (тело, колонтитулы, сноски, примечания), .pptx (слайды и заметки), .xlsx (строки ячеек),
.odt / .ods / .odp (content.xml, styles.xml). Оригинал не трогаем — результат рядом: «имя (исправлено).docx».
Только стандартная библиотека (zipfile, re) — работает везде, где работает Dewiar."""

import html
import re
import zipfile
from pathlib import Path

EXTS = {".docx", ".docm", ".pptx", ".xlsx", ".odt", ".ods", ".odp"}


class DocEditError(Exception):
    """Понятная человеку ошибка."""


# (часть архива — регулярное выражение имени, абзац, кусок текста)
_OOXML_W = (re.compile(r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"), "w:p", "w:t")
_OOXML_P = (re.compile(r"^ppt/(slides/slide\d+|notesSlides/notesSlide\d+)\.xml$"), "a:p", "a:t")
_OOXML_X = (re.compile(r"^xl/sharedStrings\.xml$"), "si", "t")
_OOXML_XS = (re.compile(r"^xl/worksheets/sheet\d+\.xml$"), "is", "t")           # строки прямо в ячейке (inlineStr)
_ODF = (re.compile(r"^(content|styles)\.xml$"), None, None)


def _parts(ext):
    if ext in (".docx", ".docm"):
        return [_OOXML_W]
    if ext == ".pptx":
        return [_OOXML_P]
    if ext == ".xlsx":
        return [_OOXML_X, _OOXML_XS]
    return [_ODF]


def _xml_text(s):
    return html.unescape(s)


def _xml_esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _compile(find, whole, case):
    pat = re.escape(find)
    pat = re.sub(r"(?:\\ )+", r"\\s+", pat)          # пробел в искомом — любой пробел (в документах бывают неразрывные)
    if whole:
        pat = r"(?<![\w])" + pat + r"(?![\w])"
    return re.compile(pat, 0 if case else re.I)


def _edit_para(xml_para, tag_t, rules, counts):
    """Абзац XML: куски <tag_t …>текст</tag_t> -> тот же абзац с заменами. counts[i] += найдено по правилу i."""
    rx = re.compile(r"(<%s(?:\s[^>]*)?>)(.*?)(</%s>)" % (re.escape(tag_t), re.escape(tag_t)), re.S)
    pieces = list(rx.finditer(xml_para))
    if not pieces:
        return xml_para
    texts = [_xml_text(m.group(2)) for m in pieces]
    for i, (prx, new) in enumerate(rules):
        full = "".join(texts)
        hits = list(prx.finditer(full))
        if not hits:
            continue
        counts[i] += len(hits)
        for h in reversed(hits):                       # с конца — смещения начала не сдвигаются
            a, b = h.start(), h.end()
            rep = h.expand(new) if "\\" in new else new
            pos = 0
            first = True
            for k, t in enumerate(texts):
                s, e = pos, pos + len(t)
                pos = e
                if e <= a or s >= b:
                    continue
                lo, hi = max(a, s) - s, min(b, e) - s
                if first:                              # кусок, где найденное начинается, — несёт замену и своё оформление
                    texts[k] = t[:lo] + rep + t[hi:]
                    first = False
                else:
                    texts[k] = t[:lo] + t[hi:]
            # длина первого изменённого куска поменялась — следующие совпадения считаем заново (идём с конца, это ок)
    out, last = [], 0
    for m, t in zip(pieces, texts):
        open_tag = m.group(1)
        if (t != t.strip() or "  " in t) and "xml:space" not in open_tag and tag_t in ("w:t", "t"):
            open_tag = open_tag[:-1] + ' xml:space="preserve">'       # пробелы по краям Word иначе съест
        out.append(xml_para[last:m.start()] + open_tag + _xml_esc(t) + m.group(3))
        last = m.end()
    out.append(xml_para[last:])
    return "".join(out)


def _edit_ooxml(xml, tag_p, tag_t, rules, counts):
    prx = re.compile(r"<%s(?:\s[^>]*)?>.*?</%s>" % (re.escape(tag_p), re.escape(tag_p)), re.S)
    return prx.sub(lambda m: _edit_para(m.group(0), tag_t, rules, counts), xml)


def _edit_odf(xml, rules, counts):
    """ODF: абзацы <text:p>/<text:h>, текст между тегами (span — внутри). Правим текстовые узлы абзаца как куски."""
    prx = re.compile(r"<text:(p|h)(?:\s[^>]*)?>.*?</text:\1>", re.S)

    def para(m):
        x = m.group(0)
        parts = re.split(r"(<[^>]+>)", x)
        idx = [i for i, s in enumerate(parts) if s and not s.startswith("<")]
        texts = [_xml_text(parts[i]) for i in idx]
        joined = "".join(texts)
        changed = False
        for ri, (rx, new) in enumerate(rules):
            hits = list(rx.finditer("".join(texts)))
            if not hits:
                continue
            counts[ri] += len(hits)
            changed = True
            for h in reversed(hits):
                a, b = h.start(), h.end()
                rep = h.expand(new) if "\\" in new else new
                pos, first = 0, True
                for k, t in enumerate(texts):
                    s, e = pos, pos + len(t)
                    pos = e
                    if e <= a or s >= b:
                        continue
                    lo, hi = max(a, s) - s, min(b, e) - s
                    texts[k] = (t[:lo] + rep + t[hi:]) if first else (t[:lo] + t[hi:])
                    first = False
        if not changed or "".join(texts) == joined:
            return x
        for i, t in zip(idx, texts):
            parts[i] = _xml_esc(t)
        return "".join(parts)
    return prx.sub(para, xml)


def paragraphs(path):
    """Текст документа по абзацам (для поиска и показа модели) -> [(часть, номер, текст)]."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in EXTS:
        raise DocEditError(f"«{p.name}»: правлю только {', '.join(sorted(EXTS))}")
    out = []
    with zipfile.ZipFile(p) as z:
        for name in z.namelist():
            for rxn, tag_p, tag_t in _parts(ext):
                if not rxn.match(name):
                    continue
                xml = z.read(name).decode("utf-8", errors="replace")
                if tag_p is None:
                    paras = [re.sub(r"<[^>]+>", "", m.group(0)) for m in re.finditer(r"<text:(p|h)(?:\s[^>]*)?>.*?</text:\1>", xml, re.S)]
                else:
                    trx = re.compile(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (re.escape(tag_t), re.escape(tag_t)), re.S)
                    paras = ["".join(trx.findall(m.group(0))) for m in
                             re.finditer(r"<%s(?:\s[^>]*)?>.*?</%s>" % (re.escape(tag_p), re.escape(tag_p)), xml, re.S)]
                for i, t in enumerate(paras):
                    t = _xml_text(t)
                    if t.strip():
                        out.append((name, i + 1, t))
    return out


def find(path, query, whole=False, case=False, limit=40):
    """Где в документе встречается query -> [{где, текст вокруг}] (как grep: чтобы правка была точной)."""
    rx = _compile(query, whole, case)
    hits = []
    for part, n, t in paragraphs(path):
        for m in rx.finditer(t):
            a, b = max(0, m.start() - 60), min(len(t), m.end() + 60)
            hits.append({"part": _part_ru(part), "para": n, "text": ("…" if a else "") + t[a:b] + ("…" if b < len(t) else "")})
            if len(hits) >= limit:
                return hits
    return hits


def _part_ru(name):
    m = re.match(r"word/(header|footer)", name)
    if m:
        return "верхний колонтитул" if m.group(1) == "header" else "нижний колонтитул"
    if "footnotes" in name or "endnotes" in name:
        return "сноски"
    if "comments" in name:
        return "примечания"
    m = re.search(r"slide(\d+)", name)
    if m:
        return ("заметки к слайду " if "notes" in name else "слайд ") + m.group(1)
    if name.startswith("xl/"):
        return "таблица"
    return "текст"


def replace(path, pairs, out=None, whole=False, case=False):
    """Заменить в документе: pairs — [(что, на что)]. Оригинал не трогаем: результат — out или «имя (исправлено).ext»
    рядом. -> {"out": путь, "counts": [найдено по каждой паре], "missing": [чего нет]}. Ничего не найдено — файл не пишем."""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in EXTS:
        raise DocEditError(f"«{p.name}»: правлю только {', '.join(sorted(EXTS))} (PDF — сначала в Word)")
    if not p.is_file():
        raise DocEditError(f"файла «{p}» нет")
    pairs = [(str(a), str(b)) for a, b in pairs if str(a or "").strip()]
    if not pairs:
        raise DocEditError("что на что заменить?")
    rules = [(_compile(a, whole, case), b.replace("\\", "\\\\")) for a, b in pairs]
    counts = [0] * len(rules)
    try:
        zin = zipfile.ZipFile(p)
    except zipfile.BadZipFile as e:
        raise DocEditError(f"«{p.name}» не открылся как документ Office (повреждён или это не {ext})") from e
    dst = Path(out) if out else p.with_name(f"{p.stem} (исправлено){p.suffix}")
    files = {}
    with zin:
        for info in zin.infolist():
            data = zin.read(info.filename)
            for rxn, tag_p, tag_t in _parts(ext):
                if rxn.match(info.filename):
                    xml = data.decode("utf-8")
                    new = _edit_odf(xml, rules, counts) if tag_p is None else _edit_ooxml(xml, tag_p, tag_t, rules, counts)
                    if new != xml:
                        data = new.encode("utf-8")
                    break
            files[info.filename] = (info, data)
    missing = [a for (a, _), c in zip(pairs, counts) if not c]
    if not any(counts):
        return {"out": "", "counts": counts, "missing": missing}
    tmp = dst.with_name(dst.name + ".tmp")
    with zipfile.ZipFile(tmp, "w") as zout:
        for name, (info, data) in files.items():
            zi = zipfile.ZipInfo(name, date_time=info.date_time)   # тот же порядок, сжатие и права, что у оригинала
            zi.compress_type, zi.external_attr = info.compress_type, info.external_attr
            zout.writestr(zi, data)
    tmp.replace(dst)
    return {"out": str(dst), "counts": counts, "missing": missing}


# ---------- архивы (владелец 12.11: «принимать архивы и смотреть, что в них») ----------
ARC_MAX_FILES, ARC_MAX_BYTES = 3000, 800 * 1024 * 1024


def unpack(path, dest=None):
    """.zip -> папка рядом («имя (распаковано)»): безопасно — без путей «../» и абсолютных, без ссылок, не больше
    ARC_MAX_FILES файлов и ARC_MAX_BYTES в распакованном виде (защита от «архивных бомб»). Имена из Windows-архивов
    (cp866) — по-русски. -> {"dir", "files": [(путь, размер)], "skipped": [...]}."""
    p = Path(path)
    if p.suffix.lower() != ".zip":
        raise DocEditError(f"«{p.name}»: открываю .zip; .rar и .7z — пересохраните в .zip (правой кнопкой → «Сжать в ZIP»)")
    try:
        z = zipfile.ZipFile(p)
    except zipfile.BadZipFile as e:
        raise DocEditError(f"«{p.name}» не открылся как архив (повреждён?)") from e
    dst = Path(dest) if dest else p.with_name(f"{p.stem} (распаковано)")
    root = dst.resolve()
    files, skipped, total = [], [], 0
    with z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if len(infos) > ARC_MAX_FILES:
            raise DocEditError(f"в архиве {len(infos)} файлов — больше {ARC_MAX_FILES}, не распаковываю")
        if sum(i.file_size for i in infos) > ARC_MAX_BYTES:
            raise DocEditError("архив в распакованном виде больше 800 МБ — не распаковываю")
        for i in infos:
            name = i.filename
            if not (i.flag_bits & 0x800):                  # не UTF-8 — имя, скорее всего, в cp866 (архиватор Windows)
                try:
                    name = name.encode("cp437").decode("cp866")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            if (i.external_attr >> 16) & 0o170000 == 0o120000:      # символическая ссылка
                skipped.append(name)
                continue
            tgt = (dst / name).resolve()
            if tgt == root or not str(tgt).startswith(str(root) + "/") and not str(tgt).startswith(str(root) + "\\"):
                skipped.append(name)
                continue
            tgt.parent.mkdir(parents=True, exist_ok=True)
            with z.open(i) as src, open(tgt, "wb") as out:
                n = 0
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    n += len(b)
                    total += len(b)
                    if total > ARC_MAX_BYTES:
                        raise DocEditError("архив распаковывается больше чем в 800 МБ — остановилась")
                    out.write(b)
            files.append((tgt.relative_to(root).as_posix(), n))
    return {"dir": str(dst), "files": files, "skipped": skipped}
