"""Владелец 12.11: «прислал docx — замени фамилии или даты — Лира должна справляться легко и чётко, правки точечно, как
у тебя: документ не переписывается и не портится». core/docedit.py: замена по тексту абзаца, даже если Word разбил слово
на куски с разным оформлением; оформление, таблицы, колонтитулы — как были; оригинал не трогается — «(исправлено)»
рядом; чего нет — сказано. Инструменты doc_find и doc_replace."""
import os, sys, tempfile, zipfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import docedit as DE  # noqa: E402
import docx  # noqa: E402
from docx.shared import Pt  # noqa: E402

tmp = Path(tempfile.mkdtemp())
d = docx.Document()
p = d.add_paragraph()
r1 = p.add_run("Договор с Ива"); r1.bold = True
r2 = p.add_run("новым И.П. от 12.10.2026"); r2.italic = True
d.add_paragraph("Подпись: Иванов И. П.   ")
t = d.add_table(rows=1, cols=2)
t.cell(0, 0).text = "Иванов"
t.cell(0, 1).text = "12.10.2026"
d.sections[0].header.paragraphs[0].text = "ООО «Ромашка» · Иванов"
src = tmp / "договор.docx"
d.save(src)
before = src.read_bytes()

hits = DE.find(src, "Иванов")
ok(len(hits) == 4 and any(h["part"] == "верхний колонтитул" for h in hits) and any("Ива" in h["text"] and "новым" in h["text"] for h in hits),
   f"поиск находит и слово, разбитое на куски, и в таблице, и в колонтитуле: {len(hits)}")
r = DE.replace(src, [("Иванов", "Петров"), ("12.10.2026", "15.11.2026"), ("Сидоров", "Козлов")])
ok(r["counts"] == [4, 2, 0] and r["missing"] == ["Сидоров"], f"заменено и сказано, чего нет: {r['counts']} {r['missing']}")
ok(src.read_bytes() == before and r["out"].endswith("договор (исправлено).docx"), "оригинал не тронут, результат — рядом «(исправлено)»")
o = docx.Document(r["out"])
p0 = o.paragraphs[0]
ok(p0.text == "Договор с Петровым И.П. от 15.11.2026", f"текст абзаца верный: {p0.text!r}")
ok(p0.runs[0].bold and "Петров" in p0.runs[0].text and p0.runs[1].italic and p0.runs[1].text.startswith("ым"),
   f"оформление кусков сохранено (жирный, курсив): {[ (x.text, x.bold, x.italic) for x in p0.runs]}")
ok(o.paragraphs[1].text == "Подпись: Петров И. П.   ", "пробелы в конце абзаца не съедены")
ok(o.tables[0].cell(0, 0).text == "Петров" and o.tables[0].cell(0, 1).text == "15.11.2026", "таблица")
ok("Петров" in o.sections[0].header.paragraphs[0].text, "колонтитул")
zi, zo = zipfile.ZipFile(src), zipfile.ZipFile(r["out"])
same = [n for n in zi.namelist() if n != "word/document.xml" and not n.startswith("word/header") and zi.read(n) != zo.read(n)]
ok(not same and zi.namelist() == zo.namelist(), f"всё остальное в документе — байт в байт: {same[:3]}")
r2 = DE.replace(src, [("Сидоров", "Козлов")])
ok(r2["out"] == "" and r2["missing"] == ["Сидоров"], "ничего не нашлось — файл не пишем")
ok(DE.replace(src, [("ива", "X")], whole=True)["out"] == "", "«только слово целиком» — «Ива» внутри «Иванов» не трогаем")
# xlsx и pptx
import openpyxl, pptx  # noqa: E402,E401
wb = openpyxl.Workbook(); ws = wb.active; ws["A1"] = "Иванов"; ws["B1"] = 5; wb.save(tmp / "т.xlsx")
rx = DE.replace(tmp / "т.xlsx", [("Иванов", "Петров")])
ok(rx["counts"] == [1] and openpyxl.load_workbook(rx["out"]).active["A1"].value == "Петров", "xlsx")
pr = pptx.Presentation(); s = pr.slides.add_slide(pr.slide_layouts[5]); s.shapes.title.text = "Отчёт Иванова"; pr.save(tmp / "с.pptx")
rp = DE.replace(tmp / "с.pptx", [("Иванова", "Петрова")])
ok(rp["counts"] == [1] and pptx.Presentation(rp["out"]).slides[0].shapes.title.text == "Отчёт Петрова", "pptx")
try:
    DE.replace(tmp / "x.pdf", [("a", "b")])
    ok(False, "pdf — понятный отказ")
except DE.DocEditError as e:
    ok("PDF" in str(e), "pdf — понятный отказ")
# инструменты модели
import tools  # noqa: E402
opened = []
ctx = {"show_file": opened.append}
r = tools.t_doc_find({"path": str(src), "text": "Иванов"}, ctx)
ok("найдено 4" in r and "колонтитул" in r, f"doc_find: где и в каком окружении: {r[:80]}")
(tmp / "договор (исправлено).docx").unlink()
r = tools.t_doc_replace({"path": str(src), "replacements": [{"find": "Иванов", "replace": "Петров"}, {"find": "Сидоров", "replace": "Х"}]}, ctx)
ok(r.startswith("Готово") and "«Иванов» → «Петров»: 4" in r and "Не нашлось: «Сидоров»" in r and opened, f"doc_replace: что заменено, чего нет, файл открыт: {r[:120]}")
r = tools.t_doc_replace({"path": str(src), "replacements": [{"find": "Сидоров", "replace": "Х"}]}, ctx)
ok("ничего из этого не нашлось" in r and "doc_find" in r, "ничего не нашлось — подсказка проверить написание, файл не менялся")
ok("doc_replace" in tools.TOOLS and "doc_find" in tools.TOOLS and "НЕ переписывай" in tools.TOOLS["doc_replace"][0], "инструменты есть; модели сказано не переписывать документ заново")
# «сделай такой же план на этот год» — образец остаётся, новый файл под своим именем
r = tools.t_doc_replace({"path": str(src), "save_as": "План 2026-2027", "replacements": [{"find": "12.10.2026", "replace": "12.10.2027"}]}, ctx)
ok((tmp / "План 2026-2027.docx").is_file() and src.read_bytes() == before and "План 2026-2027.docx" in r, "save_as: новый документ по образцу, образец цел")
try:
    tools.t_doc_replace({"path": str(src), "save_as": "договор", "replacements": [{"find": "Иванов", "replace": "П"}]}, ctx)
    ok(False, "save_as с именем образца — отказ")
except tools.ToolError:
    ok(True, "save_as с именем образца — отказ (образец не перезаписываем)")
# архивы
import zipfile as _z  # noqa: E402
arc = tmp / "документы.zip"
with _z.ZipFile(arc, "w") as z:
    z.writestr("план/план 7 класс.docx", src.read_bytes())
    z.writestr("заметка.txt", "привет")
    z.writestr("../../злое.txt", "x")
r = tools.t_archive_open({"path": str(arc)}, ctx)
dd = tmp / "документы (распаковано)"
ok((dd / "план" / "план 7 класс.docx").is_file() and (dd / "заметка.txt").read_text(encoding="utf-8") == "привет" and "2 файлов" in r,
   f"архив распакован рядом, сказано, что внутри: {r[:90]}")
ok(not (tmp.parent / "злое.txt").exists() and "пропущено небезопасных 1" in r, "путь «../» из архива — пропущен")
ok(tools.t_doc_find({"path": str(dd / "план" / "план 7 класс.docx"), "text": "Иванов"}, ctx).startswith("«план 7 класс.docx»: найдено"),
   "документ из архива — сразу можно искать и править")
try:
    tools.t_archive_open({"path": str(tmp / "x.rar")}, ctx)
except tools.ToolError as e:
    ok("не нашла" in str(e) or "zip" in str(e).lower(), "rar — понятный ответ")

if fails:
    sys.exit(1)
sk = {n: (ROOT / f"data/skills/{n}/SKILL.md").read_text(encoding="utf-8") for n in ("docx", "pptx", "archive")}
ok("doc_replace" in sk["docx"] and "doc_replace" in sk["pptx"] and "archive_open" in sk["archive"],
   "навыки docx, pptx, archive сначала ведут к точечной правке и archive_open (в задаче — через find_tool)")
print("\n✅ всё в порядке")
