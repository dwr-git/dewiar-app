---
name: pdf
description: Извлечь текст/таблицы из PDF (включая СКАНЫ через OCR) и составить отчёт по большому документу.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Извлечь текст/таблицы из PDF (включая СКАНЫ через OCR) и составить отчёт по большому документу.

# Скил: работа с PDF (текст, сканы, постраничный анализ)

PyMuPDF (fitz), pytesseract и tesseract-ocr-rus УЖЕ установлены — ничего ставить не нужно.

## 1. Сначала пойми, текстовый PDF или скан
```python
import fitz
doc = fitz.open('uploads/file.pdf')
sample = ''.join(doc[i].get_text() for i in range(min(3, len(doc))))
print('страниц:', len(doc), '| символов текста в первых 3:', len(sample.strip()))
```
Текста почти нет (< 100 символов на страницу) → это СКАН → раздел 3 (OCR).

## 2. Текстовый PDF — извлекаем постранично В ФАЙЛЫ
Большой документ НИКОГДА не выводи целиком в наблюдение — сохраняй постранично:
```python
import fitz, os
os.makedirs('pages', exist_ok=True)
doc = fitz.open('uploads/file.pdf')
for i, page in enumerate(doc):
    open(f'pages/p{i+1:03d}.txt', 'w', encoding='utf-8').write(page.get_text())
print('сохранено страниц:', len(doc))
```

## 3. Скан — OCR. КРИТИЧНО: lang='rus+eng' и масштаб x3
Без lang русский текст превращается в МУСОР. Малый масштаб — тоже мусор.
```python
import fitz, pytesseract, io, os
from PIL import Image
os.makedirs('pages', exist_ok=True)
doc = fitz.open('uploads/file.pdf')
mat = fitz.Matrix(3, 3)                      # x3 ≈ 220 dpi — обычно достаточно
for i, page in enumerate(doc):
    pix = page.get_pixmap(matrix=mat)
    img = Image.open(io.BytesIO(pix.tobytes('png'))).convert('L')
    txt = pytesseract.image_to_string(img, lang='rus+eng')   # ← ОБЯЗАТЕЛЬНО
    open(f'pages/p{i+1:03d}.txt', 'w', encoding='utf-8').write(txt)
    print(i+1, len(txt.strip()))
```
Партиями: страниц > 15 — обрабатывай по 10 за запуск (range-срезы), прогресс уже в файлах.
Всё ещё мусор? Подними масштаб до Matrix(4,4) и добавь бинаризацию:
`img = img.point(lambda x: 255 if x > 150 else 0)`. Дополнительные библиотеки
(skimage, cv2) НЕ нужны — PIL хватает.

## 4. Отчёт по большому документу — ТОЛЬКО map-reduce
Не пытайся осмыслить весь документ за один шаг — он не влезет в контекст.
1) ИЗВЛЕЧЕНИЕ: страницы в pages/*.txt (разделы 2–3).
2) MAP: читай python-ом по 3–5 страниц за шаг (печатай их текст в наблюдение),
   формулируй ключевые моменты каждой и ДОПИСЫВАЙ их в notes.md:
   open('notes.md','a',encoding='utf-8').write('## стр. N\n- ...\n')
   Обновляй plan.md: какие страницы пройдены.
3) REDUCE: прочитай notes.md и собери итог в outputs/report.md ЧАСТЯМИ
   (по ~100 строк за шаг): резюме, ключевые моменты по разделам, нюансы, риски.
4) В final_answer — краткое резюме (5–10 строк) и отсылка к outputs/report.md.
   Полный отчёт в чат не вставляй — обрежется.

## 5. Таблицы и сборка PDF
Таблицы: pdfplumber (установлен): page.extract_tables(). Сборка PDF: reportlab / fpdf2 (установлены).
