"""№892 (19.11): «Скинула две таблицы Excel через виджет, в диалоге вижу, что скинула, но Патрик их не видит»; и в «Моих
файлах» таблицы Excel не добавлялись. .xlsx читался как обычный текст — «текста в нём нет», read_file — «не текстовый
файл», doc_find с пустым поиском — «найдено 40: Дата, Дата…». Теперь таблицы (.xlsx, .xlsm, .ods) и слайды (.pptx) —
текстом по листам; даты — датами; .xls — понятная просьба пересохранить. Плюс из того же журнала: пути Windows с одиночной
косой в аргументах (delete_files «не указано, что удалить») и «loadChat is not defined» в студии."""
import datetime as dt
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import openpyxl  # noqa: E402
import sheets  # noqa: E402
from knowledge import extract, EXTS  # noqa: E402

tmp = Path(tempfile.mkdtemp())

# --- xlsx: строки, числа, даты, формулы, скрытый лист, пустые строки ---
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Капитал"
ws.append(["Дата", "Категория", "Сумма"])
ws.append([dt.date(2026, 11, 1), "Продукты", 2350])
ws.append([dt.date(2026, 11, 3), "Донат | школа", 1500.5])
ws.append([])
ws.append(["Итого", None, "=SUM(C2:C3)"])
h = wb.create_sheet("Скрытый")
h["A1"] = "секрет"
h.sheet_state = "hidden"
d = wb.create_sheet("Донаты")
d["A1"] = "Месяц"
d["B1"] = "Сколько"
d["A2"] = "Октябрь"
d["B2"] = 7
wb.save(tmp / "ЛИЧНЫЙ КАПИТАЛ.xlsx")
t = extract(tmp / "ЛИЧНЫЙ КАПИТАЛ.xlsx")
print(t)
ok("## Лист «Капитал» · строк 4" in t, "лист с именем и числом строк")
ok("Дата | Категория | Сумма" in t, "заголовок таблицы")
ok("01.11.2026 | Продукты | 2350" in t, "дата — датой, число — без .0")
ok("Донат / школа | 1500.5" in t, "палка в ячейке не ломает столбцы")
ok("## Лист «Донаты»" in t and "Октябрь | 7" in t, "второй лист")
ok("секрет" not in t, "скрытый лист не показывается")
ok(".xlsx" in EXTS and ".ods" in EXTS and ".pptx" in EXTS, "«Мои файлы» ищут и в таблицах, и в слайдах")

# --- inlineStr и логические — руками, как пишут выгрузки из сервисов ---
x = tmp / "выгрузка.xlsx"
with zipfile.ZipFile(x, "w") as z:
    z.writestr("[Content_Types].xml", "<Types/>")
    z.writestr("xl/workbook.xml", '<workbook xmlns:r="r"><sheets><sheet name="Notion" sheetId="1" r:id="rId1"/></sheets></workbook>')
    z.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
    z.writestr("xl/worksheets/sheet1.xml", '<worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Имя</t></is></c>'
               '<c r="C1" t="b"><v>1</v></c></row></sheetData></worksheet>')
t2 = extract(x)
ok("Имя |  | да" in t2, f"inlineStr, пропуск столбца, логическое: {t2!r}")

# --- ods ---
ods = tmp / "учёт.ods"
with zipfile.ZipFile(ods, "w") as z:
    z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
    z.writestr("content.xml", '<office:document-content><office:body><office:spreadsheet><table:table table:name="Бюджет">'
               '<table:table-row><table:table-cell office:value-type="string"><text:p>Месяц</text:p></table:table-cell>'
               '<table:table-cell office:value-type="string"><text:p>Сумма</text:p></table:table-cell></table:table-row>'
               '<table:table-row><table:table-cell office:value-type="date" office:date-value="2026-11-05"><text:p>05/11/26</text:p></table:table-cell>'
               '<table:table-cell office:value-type="float" office:value="12.5"><text:p>12,5</text:p></table:table-cell>'
               '<table:table-cell table:number-columns-repeated="16000"/></table:table-row>'
               '<table:table-row table:number-rows-repeated="1048000"><table:table-cell table:number-columns-repeated="1024"/></table:table-row>'
               '</table:table></office:spreadsheet></office:body></office:document-content>')
t3 = extract(ods)
ok("## Лист «Бюджет» · строк 2" in t3 and "05.11.2026 | 12,5" in t3, f"ods: {t3!r}")
ok(len(t3) < 300, "миллион пустых повторов ods не раздувает текст")

# --- pptx ---
pp = tmp / "доклад.pptx"
with zipfile.ZipFile(pp, "w") as z:
    for i, s in ((1, "Привет"), (2, "План на год"), (10, "Конец")):
        z.writestr(f"ppt/slides/slide{i}.xml", f"<p:sld><a:p><a:r><a:t>{s}</a:t></a:r></a:p></p:sld>")
t4 = extract(pp)
ok(t4.index("Привет") < t4.index("План на год") < t4.index("Конец") and "## Слайд 3" in t4, "слайды по порядку (10 после 2)")

# --- .xls и битый файл — понятные ошибки ---
(tmp / "старый.xls").write_bytes(b"\xd0\xcf\x11\xe0junk")
try:
    sheets.text(tmp / "старый.xls")
    ok(False, ".xls — ошибка")
except sheets.SheetError as e:
    ok("сохраните как .xlsx" in str(e), ".xls — просьба пересохранить")
(tmp / "битый.xlsx").write_bytes(b"not a zip")
try:
    sheets.text(tmp / "битый.xlsx")
    ok(False, "битый — ошибка")
except sheets.SheetError as e:
    ok("повреждён" in str(e), "битый .xlsx — понятная ошибка")

# --- вложение в разговоре: текст таблицы — в вопросе модели ---
import base64  # noqa: E402
from answer_direct import DirectMixin  # noqa: E402


class WS:
    root = tmp / "ws"

    def ensure(self):
        self.root.mkdir(exist_ok=True)
        return self.root


class E(DirectMixin):
    workspace = WS()


raw = (tmp / "ЛИЧНЫЙ КАПИТАЛ.xlsx").read_bytes()
q = E()._attach_files("Проанализируй", [{"name": "ЛИЧНЫЙ КАПИТАЛ.xlsx", "b64": base64.b64encode(raw).decode()},
                                        {"name": "старый.xls", "b64": base64.b64encode(b"\xd0\xcf\x11\xe0").decode()}], [])
ok("01.11.2026 | Продукты | 2350" in q and "текста в нём нет" not in q.split("старый.xls")[0], "вложение .xlsx — текст в вопросе")
ok("старый.xls" in q and "сохраните как .xlsx" in q, "вложение .xls — просьба пересохранить")

# --- read_file по таблице во «Входящих» ---
import workspace as W  # noqa: E402
import types  # noqa: E402
w = types.SimpleNamespace(root=WS.root, safe=lambda rel: WS.root / rel, _vault_path=None)
r = W.Workspace.read(w, "Входящие/ЛИЧНЫЙ КАПИТАЛ.xlsx")
ok(not r.get("binary") and "Продукты" in r.get("text", ""), "read_file читает таблицу")

# --- doc_find с пустым поиском — подсказка read_file, а не «Дата, Дата…» ---
import tools_docs as TD  # noqa: E402
from tools_base import ToolError  # noqa: E402
TD._doc_path = lambda a, ctx, exts=None: WS.root / "Входящие" / "ЛИЧНЫЙ КАПИТАЛ.xlsx"
TD._ws = lambda ctx: w
try:
    TD.t_doc_find({"path": "ЛИЧНЫЙ КАПИТАЛ.xlsx", "text": ""}, None)
    ok(False, "пустой doc_find — ошибка")
except ToolError as e:
    ok("read_file" in str(e) and "Входящие/ЛИЧНЫЙ КАПИТАЛ.xlsx" in str(e), f"пустой doc_find → read_file: {e}")

# --- пути Windows с одиночной косой в аргументах ---
from llm_text import loads_args  # noqa: E402
a = loads_args(r'{"paths": ["C:\Users\Lenovo\Documents\Adobe\Premiere Pro\13.0\Auto-Save"]}')
ok(a == {"paths": [r"C:\Users\Lenovo\Documents\Adobe\Premiere Pro\13.0\Auto-Save"]}, "одиночные косые в пути — читаются")
ok(loads_args(r'{"p": "C:\\Users\\x", "n": "a\nb"}') == {"p": "C:\\Users\\x", "n": "a\nb"}, "правильный JSON — как был")
try:
    loads_args('{"p": ')
    ok(False, "оборванный — ValueError")
except ValueError:
    ok(True, "оборванный JSON — ValueError (дальше repair_json)")

src = (ROOT / "core/llm_sse.py").read_text(encoding="utf-8")
ok("loads_args(c[\"args\"])" in src, "поток модели читает аргументы так же")

# --- студия: «Чат» до загрузки chat.js ---
cj = (ROOT / "ui/studio/core.js").read_text(encoding="utf-8")
ok('typeof loadChat === "function"' in cj, "нажатие «Чата» раньше chat.js не роняет страницу")
html = (ROOT / "ui/settings.html").read_text(encoding="utf-8")
ok('id="kn-file" multiple accept=".pdf,.docx,.odt,.xlsx' in html, "«Мои файлы» → «Добавить файлы…» принимает Excel")

# №1153 (28.11): копейки в больших суммах не теряются; хвосты float — убираются, как в Excel
import sheets as _SH  # noqa: E402
ok(_SH._num("1234567890.12") == "1234567890.12" and _SH._num("123456789.12") == "123456789.12", "большие суммы — с копейками")
ok(_SH._num("2350.0000000000005") == "2350" and _SH._num("0.30000000000000004") == "0.3" and _SH._num("1.23456") == "1.23456",
   "хвосты float — нет, обычные дроби — как есть")

print("\nИтог:", "всё хорошо" if not fails else f"ошибок {len(fails)}")
sys.exit(1 if fails else 0)
