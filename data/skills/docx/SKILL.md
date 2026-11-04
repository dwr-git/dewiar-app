---
name: docx
description: Прочитать или создать документ Word (.docx).
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Прочитать или создать документ Word (.docx).

# Скил: работа с .docx

python-docx УЖЕ установлен — install не нужен.

Прочитать:
```python
import docx
d = docx.Document('uploads/file.docx')
text = "\n".join(p.text for p in d.paragraphs)
# таблицы тоже несут текст:
for t in d.tables:
    for row in t.rows:
        print(' | '.join(c.text for c in row.cells))
print(text[:1500])
```

Создать (итог — в outputs/):
```python
import docx, os
os.makedirs('outputs', exist_ok=True)
d = docx.Document()
d.add_heading('Заголовок', 0)
d.add_paragraph('Текст абзаца.')
t = d.add_table(rows=2, cols=3); t.style = 'Table Grid'
t.cell(0, 0).text = 'Ячейка'
d.save('outputs/result.docx')
print('saved outputs/result.docx')
```
Стили: add_heading(level=1..4); жирный/курсив — через runs:
`p = d.add_paragraph(); r = p.add_run('важно'); r.bold = True`.
Конвертация в PDF не средствами docx — собери PDF reportlab/fpdf2 или сохрани HTML.
