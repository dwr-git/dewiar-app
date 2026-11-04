---
name: web-download
description: Скачать документы/файлы с сайта (в т.ч. динамического, JS) и сохранить их для пользователя.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Скачать документы/файлы с сайта (в т.ч. динамического, JS) и сохранить их для пользователя.

# Скил: скачивание файлов с сайта

Когда пользователь просит «скачай с сайта …» — действуй так:

1. **Открой страницу в браузере** инструментом `browser` (не web_fetch — многие
   сайты, например pravo.by, рендерятся через JavaScript, и web_fetch вернёт пусто).
   `browser` вернёт ТЕКСТ страницы и СПИСОК ССЫЛОК (текст → url).

2. **Найди нужный пункт в списке ссылок** по словам из запроса пользователя
   (например «о стандартах проведения расчётов»). Возьми его url.

3. **Перейди по этой ссылке** снова через `browser` — попадёшь на страницу
   документа. Там найди прямую ссылку на файл (PDF/DOC) или на версию для печати.
   Часто это ссылка с `/document/?guid=...`, кнопка «скачать», «версия для печати»
   или ссылка, заканчивающаяся на `.pdf`/`.doc`/`.docx`.

4. **Скачай файл кодом** через `python` (на компьютере есть интернет):
   ```python
   import requests, os
   os.makedirs('downloads', exist_ok=True)
   url = 'ПРЯМАЯ_ССЫЛКА_НА_ФАЙЛ'
   r = requests.get(url, timeout=120, headers={'User-Agent':'Mozilla/5.0'})
   r.raise_for_status()
   # имя файла из URL или Content-Disposition
   name = url.split('/')[-1].split('?')[0] or 'document'
   if 'pdf' in r.headers.get('Content-Type','') and not name.endswith('.pdf'): name += '.pdf'
   open('downloads/'+name,'wb').write(r.content)
   print('saved', name, len(r.content), 'bytes')
   ```

5. **Если файлов много** — собери все ссылки, сохрани список в файл, качай партиями
   (по 20–50 за запуск), помечая в файле уже скачанное, чтобы продолжить на след. шаге.

6. В `final_answer` укажи, какие файлы готовы (они в папке — пользователь скачает).

Подсказки:
- Если прямой ссылки на файл нет, но есть «версия для печати» — открой её `browser`,
  и сохрани её текст/HTML как файл (.html или .txt).
- Если сайт отдаёт 403 — добавь заголовок User-Agent (см. пример выше).
- Проверяй размер скачанного (>0 байт) и тип контента.
