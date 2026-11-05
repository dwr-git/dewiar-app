"""Таблица Excel (.xlsx) без сторонних библиотек (№541, 04.11: «подготовь Excel с содержимым почтового ящика» — у программы
не было чем записать .xlsx: openpyxl в комплект не входит, а слабая модель вместо файла выдала скрипт на Python).

xlsx — zip с XML: книга, листы, стили. Здесь — минимум, который открывают Excel, LibreOffice, Google Таблицы и openpyxl:
строки — встроенным текстом (inlineStr), числа — числами, первая строка листа — жирная, закреплена и с фильтром,
ширина колонок — по содержимому."""
import re
import zipfile
from xml.sax.saxutils import escape

_BAD = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, v, bold=False):
    st = ' s="1"' if bold else ""
    if v is None or v == "":
        return ""                                  # пустая клетка — без записи
    if isinstance(v, bool):
        v = "да" if v else "нет"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f'<c r="{ref}"{st}><v>{v}</v></c>'
    t = escape(_BAD.sub("", str("" if v is None else v)))[:32000]
    return f'<c r="{ref}" t="inlineStr"{st}><is><t xml:space="preserve">{t}</t></is></c>'


def _sheet(rows):
    widths = {}
    for r in rows:
        for j, v in enumerate(r):
            widths[j] = min(60, max(widths.get(j, 6), len(str(v if v is not None else "")) + 2))
    cols = "".join(f'<col min="{j + 1}" max="{j + 1}" width="{w}" customWidth="1"/>' for j, w in sorted(widths.items()))
    body = []
    for i, r in enumerate(rows):
        body.append(f'<row r="{i + 1}">' + "".join(_cell(f"{_col(j)}{i + 1}", v, bold=i == 0) for j, v in enumerate(r)) + "</row>")
    last = f"{_col(max(0, len(rows[0]) - 1))}{max(1, len(rows))}" if rows and rows[0] else "A1"
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
            + (f"<cols>{cols}</cols>" if cols else "") + "<sheetData>" + "".join(body) + "</sheetData>"
            + (f'<autoFilter ref="A1:{last}"/>' if len(rows) > 1 else "") + "</worksheet>")


def write(path, sheets):
    """sheets — [(название листа, [[заголовки], [значения], …]), …] -> path."""
    names = []
    for k, (name, _) in enumerate(sheets):
        n = re.sub(r"[\[\]:*?/\\]", " ", str(name or f"Лист{k + 1}")).strip()[:31] or f"Лист{k + 1}"
        while n in names:
            n = (n[:28] + f" {k + 1}")[:31]
        names.append(n)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for i in range(len(sheets))) + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          + "".join(f'<sheet name="{escape(n, {chr(34): "&quot;"})}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(names))
          + "</sheets>"
          + "".join(f'<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
                    f"'{escape(n)}'!$A$1:${_col(max(0, len(rows[0]) - 1))}${len(rows)}</definedName></definedNames>"
                    for i, (n, (_, rows)) in enumerate(zip(names, sheets)) if len(rows) > 1 and i == 0)
          + "</workbook>")
    wrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             + "".join(f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                       for i in range(len(sheets)))
             + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             "</Relationships>")
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
              "</styleSheet>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wrels)
        z.writestr("xl/styles.xml", styles)
        for i, (_, rows) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", _sheet(rows))
    return path
