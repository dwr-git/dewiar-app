---
name: pptx
description: Создать или отредактировать презентацию PowerPoint (.pptx): слайды, текст, таблицы, картинки; правка существующих слайдов с сохранением формата. Отрисовать слайды в картинки/PDF — см. libreoffice.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

# Навык: презентации PowerPoint (.pptx) — создание и правка

> Создать или отредактировать презентацию PowerPoint (.pptx): слайды, текст, таблицы, картинки; правка существующих слайдов с сохранением формата. Отрисовать слайды в картинки/PDF — см. libreoffice.

Инструмент — **python-pptx**. Правки текста делай на уровне run'ов (как в docx),
чтобы сохранить шрифт/кегль/цвет.

## Прочитать текст
```python
from pptx import Presentation
p = Presentation('uploads/файл.pptx')
for i, slide in enumerate(p.slides, 1):
    for sh in slide.shapes:
        if sh.has_text_frame:
            for para in sh.text_frame.paragraphs:
                print(i, ''.join(r.text for r in para.runs))
```

## Править существующую С СОХРАНЕНИЕМ формата (run-level)
Меняй `run.text`, не пересоздавая фигуру и абзац:
```python
from pptx import Presentation
p = Presentation('uploads/файл.pptx')
for slide in p.slides:
    for sh in slide.shapes:
        if not sh.has_text_frame: continue
        for para in sh.text_frame.paragraphs:
            for run in para.runs:
                if run.text == 'Старый текст':
                    run.text = 'Новый текст'          # формат run'а сохраняется
p.save('outputs/готово.pptx')
```

## Создать
```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
p = Presentation()                                     # или Presentation('шаблон.pptx')
slide = p.slides.add_slide(p.slide_layouts[1])         # 0 титул, 1 заголовок+контент
slide.shapes.title.text = 'Заголовок'
body = slide.placeholders[1].text_frame
body.text = 'Первый пункт'
para = body.add_paragraph(); para.text = 'Подпункт'; para.level = 1
# отдельная надпись с форматированием
tf = slide.shapes.add_textbox(Inches(1), Inches(5), Inches(6), Inches(1)).text_frame
run = tf.paragraphs[0].add_run(); run.text = 'Итог'
run.font.size = Pt(18); run.font.bold = True; run.font.color.rgb = RGBColor(0x1B, 0x2A, 0x41)
# картинка и таблица
slide.shapes.add_picture('uploads/logo.png', Inches(8), Inches(0.3), height=Inches(0.8))
tbl = slide.shapes.add_table(2, 2, Inches(1), Inches(2), Inches(6), Inches(1.5)).table
tbl.cell(0, 0).text = 'Показатель'; tbl.cell(0, 1).text = 'Значение'
p.save('outputs/презентация.pptx')
```

## Замечания / проверка
- Диаграммы и SmartArt из шаблона правь осторожно (python-pptx их не строит) —
  меняй текст, не пересобирай.
- Чтобы задать шаблон/фирменный стиль — открывай ваш `.pptx`/`.potx` как основу
  и меняй содержимое, а не создавай с нуля.
- Итог **перечитай** и проверь тексты/структуру.
- Показать слайды картинками или выгрузить PDF — через скилл **libreoffice**
  (`soffice --convert-to pdf`, затем страницы в PNG).
