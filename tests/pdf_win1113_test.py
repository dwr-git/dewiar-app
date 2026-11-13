"""Жалоба №692 (13.11, Windows 11): «Раздел „Чат“: на выходе вместо текста одно слово „готово“». В журнале — каждый PDF:
«PDF не прочитался (UnicodeEncodeError: 'charmap' codec can't encode character '\\xd7' …)». С 05.11 текст PDF разбирает
отдельный процесс (pdftext.py), а он писал ответ в трубу текстом — на Windows у трубы кодировка cp1252, и русский текст,
«×», «¢», значки шрифтов роняли разбор: модель не видела файлов. Теперь — байтами в UTF-8, мимо кодировки консоли."""
import os, stat, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import pdftext  # noqa: E402
tmp = Path(tempfile.mkdtemp())
pdf = tmp / "naolys.pdf"
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page()
        pg.set_content("<p>Флуктуационный подход: 3 × 4 мг · цена 5¢ — Наолис</p>"); pg.pdf(path=str(pdf)); b.close()
except Exception as e:  # noqa: BLE001
    print("нет браузера — PDF не собрать:", e); print("ИТОГ: всё прошло"); sys.exit(0)

# «питон Windows»: у трубы stdout — cp1252
fake = tmp / "py1252"
fake.write_text("#!/bin/sh\nexec " + sys.executable + " -I -S -c \"import sys, io; sys.argv = sys.argv[1:]; "
                "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='cp1252', errors='strict'); "
                "exec(compile(sys.argv[0], 'child', 'exec'))\" \"$4\" \"$5\" \"$6\" \"$7\" \"$8\" \"$9\"\n")
fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
real = sys.executable
sys.executable = str(fake)
try:
    pages = pdftext.pages(pdf)
    txt = " ".join(pages)
    ok("Флуктуационный" in txt and "×" in txt, f"PDF с русским и «×» читается и при cp1252 у трубы: {txt[:80]!r}")
except pdftext.PdfTextError as e:
    ok(False, f"PDF с русским и «×» читается и при cp1252 у трубы: {e}")
finally:
    sys.executable = real
ok("Флуктуационный" in " ".join(pdftext.pages(pdf)), "обычный запуск — как раньше")
# модель не смогла прочитать файлы, попробовала скриптами в «Лаборатории» и ответила одним «Готово.» — просим ответ по существу
import quality as Q  # noqa: E402
ok(Q.bare_done("на примере приложенного файла составь описание для микробиома мицелия", "Готово.", ["ocr", "lab_write", "lab_run"]),
   "«составь описание» → «Готово.» после проб в «Лаборатории» — переспросить по существу")
ok(not Q.bare_done("составь заметку про чай", "Готово.", ["save_note"]) and not Q.bare_done("включи свет", "Готово.", ["smart_home"]),
   "заметка сохранена, свет включён — «Готово» уместно")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
