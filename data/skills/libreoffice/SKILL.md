---
name: libreoffice
description: Когда нужно показать или сконвертировать документ точь-в-точь как в Word: office (docx/xlsx/pptx/odt/rtf) → PDF, страницы/слайды → PNG. Только отрисовка/конвертация, не правки.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

# Навык: LibreOffice на компьютере (конвертация и отрисовка «как в Word»)

> Когда нужно показать или сконвертировать документ точь-в-точь как в Word: office (docx/xlsx/pptx/odt/rtf) → PDF, страницы/слайды → PNG. Только отрисовка/конвертация, не правки.

Если на компьютере установлен **LibreOffice headless** (`soffice`) — writer/calc/impress —
и шрифты `fonts-liberation` (метрически совместимые Times New Roman / Arial, чтобы
кириллица в приказах/договорах рисовалась правильно). Это «универсальный конвертер
верности»: `docx/xlsx/pptx/odt/rtf → pdf`, а `pdf → png` — через `pdftoppm` (poppler).

## Когда использовать LibreOffice
- Нужен **пиксель-в-пиксель** вид документа (просмотр, отправка на утверждение):
  `office → pdf`, затем при необходимости `pdf → png` постранично.
- Просмотр того, что python-docx показать не может: **таблицы** в сложной вёрстке,
  **.pptx**, **.xlsx**, конвертация **.rtf/.odt**.
- Итоговая выгрузка PDF из подготовленного .docx.

## Когда НЕ использовать (важно)
- **Правки документов идут через python-docx на уровне run'ов** (или прямой XML),
  НЕ через LibreOffice и НЕ через round-trip `docx→html→docx` — иначе слетает
  форматирование. LibreOffice — только для конвертации/отрисовки, не для
  редактирования содержимого.
- LibreOffice тяжёлый и небыстрый (запуск ~1–3 с). Для извлечения текста/данных
  предпочитай python-docx / openpyxl / PyMuPDF — они быстрее и точнее.

## Обязательная деталь: уникальный профиль на каждый запуск
LibreOffice при параллельных вызовах конфликтует на общем пользовательском профиле
и подвисает. КАЖДОМУ запуску давай отдельный `-env:UserInstallation` во временной
папке, и удаляй её после:

```python
import subprocess, tempfile, shutil, os, glob

def office_to_pdf(src, outdir):
    profile = tempfile.mkdtemp(prefix="lo_")
    try:
        subprocess.run([
            "soffice", "--headless", "--nologo", "--nofirststartwizard",
            "--norestore",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "pdf", "--outdir", outdir, src,
        ], check=True, timeout=120,
           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    base = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(outdir, base + ".pdf")
```

Постранично в PNG (poppler, стабильнее чем растеризация LibreOffice):

```python
# pdftoppm -r 150 -png document.pdf outdir/page   →  outdir/page-1.png, page-2.png …
subprocess.run(["pdftoppm", "-r", "150", "-png", pdf_path, os.path.join(outdir, "page")], check=True)
pages = sorted(glob.glob(os.path.join(outdir, "page-*.png")))
```

## Замечания
- Первый запуск в свежем контейнере чуть дольше (прогрев профиля) — это норма.
- Целевой формат задаётся строкой `--convert-to`: `pdf`, `xlsx`, `pptx`, `html`, `odt`
  и т.д. Имя выходного файла = имя входного с новым расширением, в `--outdir`.
- Если `soffice` не найден — LibreOffice на компьютере нет: скажи пользователю, что его можно поставить
  (Ubuntu: `sudo apt install libreoffice`; Windows — с libreoffice.org), а пока сделай без него.
