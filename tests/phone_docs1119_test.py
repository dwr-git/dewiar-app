"""Телефон читает документы (19.11, план улучшений, пункт 3; одна функция — одно поведение на компьютере и телефоне): раньше
на PDF и Word — «телефон пока не читает». Теперь вложение PDF (pdf.js, грузится при первом PDF), Word (.docx), Excel
(.xlsx), PowerPoint (.pptx), LibreOffice (.odt, .ods) — текстом в вопрос модели, таблицы — по листам, как core/sheets.py;
скан PDF без текста и старые .doc/.xls — понятной просьбой."""
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


tmp = Path(tempfile.mkdtemp()); www = tmp / "www"
subprocess.run(["bash", str(ROOT / "android/tools/www_assemble.sh"), str(www)], check=True, capture_output=True)
ok((www / "vendor/pdf.min.js").exists() and (www / "vendor/pdf.worker.min.js").exists(), "pdf.js — в наборе телефона и веб-версии")
D = tmp / "docs"; D.mkdir()

# --- документы ---
import openpyxl  # noqa: E402
wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Капитал"
ws.append(["Дата", "Статья", "Сумма"]); ws.append([dt.date(2026, 11, 1), "Продукты", 2350]); ws.append([dt.date(2026, 11, 3), "Аренда | офис", 1500.5])
h = wb.create_sheet("Тайный"); h["A1"] = "секрет"; h.sheet_state = "hidden"
wb.save(D / "учёт.xlsx")


def zipf(path, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, t in files.items():
            z.writestr(n, t)


zipf(D / "договор.docx", {"[Content_Types].xml": "<Types/>", "word/document.xml":
     '<w:document><w:body><w:p><w:r><w:t>Договор № 7</w:t></w:r></w:p><w:p><w:r><w:t xml:space="preserve">Срок </w:t></w:r>'
     '<w:r><w:t>оплаты — 14 дней &amp; без пени</w:t></w:r></w:p></w:body></w:document>'})
zipf(D / "доклад.pptx", {f"ppt/slides/slide{i}.xml": f"<p:sld><a:p><a:r><a:t>{t}</a:t></a:r></a:p></p:sld>"
                        for i, t in ((1, "Привет"), (2, "План"), (10, "Конец"))})
zipf(D / "письмо.odt", {"content.xml": '<office:document-content><office:body><office:text><text:h>Заголовок</text:h>'
                        '<text:p>Первая <text:span>строка</text:span></text:p></office:text></office:body></office:document-content>'})
zipf(D / "бюджет.ods", {"content.xml": '<office:document-content><office:body><office:spreadsheet><table:table table:name="Бюджет">'
                        '<table:table-row><table:table-cell office:value-type="string"><text:p>Месяц</text:p></table:table-cell>'
                        '<table:table-cell office:value-type="string"><text:p>Сумма</text:p></table:table-cell></table:table-row>'
                        '<table:table-row><table:table-cell office:value-type="date" office:date-value="2026-11-05"><text:p>05.11</text:p></table:table-cell>'
                        '<table:table-cell office:value-type="float" office:value="12.5"><text:p>12,5</text:p></table:table-cell>'
                        '<table:table-cell table:number-columns-repeated="16000"/></table:table-row>'
                        '<table:table-row table:number-rows-repeated="1048000"><table:table-cell table:number-columns-repeated="1024"/></table:table-row>'
                        '</table:table></office:spreadsheet></office:body></office:document-content>'})
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.ttfonts import TTFont  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402
pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
c = canvas.Canvas(str(D / "инструкция.pdf")); c.setFont("DV", 14)
c.drawString(72, 760, "Возврат товара — в течение 14 дней."); c.showPage()
c.setFont("DV", 14); c.drawString(72, 760, "Гарантия — 2 года."); c.save()
c = canvas.Canvas(str(D / "скан.pdf")); c.rect(50, 50, 400, 400, fill=1); c.save()
(D / "старый.doc").write_bytes(b"\xd0\xcf\x11\xe0old")

files = {p.name: list(p.read_bytes()) for p in D.iterdir()}
seen, errs = [], []


def llm(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers={"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "*"})
    seen.append(json.loads(req.post_data or "{}").get("messages") or [])
    d = {"choices": [{"delta": {"content": "Прочитала документ."}}]}
    route.fulfill(status=200, body=f"data: {json.dumps(d, ensure_ascii=False)}\n\ndata: [DONE]\n\n",
                  headers={"Access-Control-Allow-Origin": "*", "Content-Type": "text/event-stream"})


MIME = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".doc": "application/msword"}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 400, "height": 820})
    pg.on("pageerror", lambda x: errs.append(str(x)))
    pg.route("http://127.0.0.1:9/**", llm)
    pg.goto((www / "index.html").as_uri()); pg.wait_for_timeout(900)
    acc = pg.get_attribute("#att-file", "accept")
    ok("application/pdf" in acc and "spreadsheetml.sheet" in acc and "wordprocessingml" in acc, "выбор файла предлагает PDF, Word, Excel")
    R = pg.evaluate("""async (files) => { const out = {};
      for (const [name, bytes] of Object.entries(files)) {
        const f = new File([new Uint8Array(bytes)], name);
        try { out[name] = await docText(f); } catch (e) { out[name] = "ERR: " + e.message; } }
      return out; }""", {k: v for k, v in files.items() if not k.endswith(".doc")})
    x = R["учёт.xlsx"]
    ok("## Лист «Капитал» · строк 3" in x and "01.11.2026 | Продукты | 2350" in x and "Аренда / офис | 1500.5" in x and "секрет" not in x,
       f"Excel: листы, даты, числа, скрытый лист не виден: {x!r}")
    ok(R["договор.docx"] == "Договор № 7\nСрок оплаты — 14 дней & без пени", f"Word: абзацы и куски текста: {R['договор.docx']!r}")
    ok(R["доклад.pptx"].index("Привет") < R["доклад.pptx"].index("План") < R["доклад.pptx"].index("Конец"), "PowerPoint: слайды по порядку")
    ok(R["письмо.odt"] == "Заголовок\nПервая строка", f"ODT: {R['письмо.odt']!r}")
    ok(R["бюджет.ods"] == "## Лист «Бюджет» · строк 2\nМесяц | Сумма\n05.11.2026 | 12,5", f"ODS (миллион пустых повторов — не раздувает): {R['бюджет.ods'][:120]!r}")
    pdf = R["инструкция.pdf"]
    ok("Возврат товара — в течение 14 дней." in pdf and "— стр. 2 —" in pdf and "Гарантия — 2 года." in pdf, f"PDF с кириллицей — текстом по страницам: {pdf!r}")
    ok(R["скан.pdf"].startswith("ERR: в PDF нет текста — похоже, это скан"), f"скан — просьба прислать фото: {R['скан.pdf']!r}")
    # вложение целиком: в вопросе модели — текст документа
    pg.evaluate("() => { Object.assign(S.llm, { kind: 'openai', base_url: 'http://127.0.0.1:9/v1', model: 'm', name: 'тест', cloud: false }); saveS(); }")
    toasts = pg.evaluate("""async (args) => { const [bytes, name, type] = args; const t = []; const real = window.toast; window.toast = (m) => t.push(m);
      await addAttach(new File([new Uint8Array(bytes)], name, { type })); window.toast = real; return t; }""",
                         [files["инструкция.pdf"], "инструкция.pdf", MIME[".pdf"]])
    pg.evaluate("async () => { const att = attached; attached = []; await ask('Сколько дней на возврат?', { attach: att }); }")
    pg.wait_for_timeout(800)
    u = [m for m in seen[-1] if m.get("role") == "user"][-1]["content"] if seen else ""
    u = u if isinstance(u, str) else " ".join(x.get("text", "") for x in u if isinstance(x, dict))
    ok("Возврат товара — в течение 14 дней." in u and "инструкция.pdf" in u, "PDF вложением — текст уходит модели с вопросом")
    old = pg.evaluate("""async (args) => { const [bytes, name, type] = args; const t = []; const real = window.toast; window.toast = (m) => t.push(m);
      await addAttach(new File([new Uint8Array(bytes)], name, { type })); window.toast = real; return [t, attached.length]; }""",
                      [files["старый.doc"], "старый.doc", MIME[".doc"]])
    ok(old[1] == 0 and "сохраните как .docx" in " ".join(old[0]), f"старый .doc — понятная просьба пересохранить: {old}")
    ok(not errs, f"без ошибок JavaScript: {errs[:2]}")
    b.close()
shutil.rmtree(tmp, ignore_errors=True)
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
