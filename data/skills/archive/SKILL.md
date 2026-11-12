---
name: archive
description: Когда на вход дан .zip (или нужно отдать пачку файлов одним архивом): безопасно распаковать, обработать каждый файл, собрать результат в новый .zip.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

# Навык: архивы (.zip) — распаковать, обработать пачку, собрать обратно

**Просто посмотреть, что в архиве, — инструмент `archive_open`** (в задаче: find_tool «archive_open»): распакует .zip рядом безопасно (без выхода из папки, с пределами размера, русские имена из Windows) и перечислит файлы. Документы Office внутри править точечно — `doc_find` / `doc_replace`. Код ниже — когда файлов много и их надо обработать и собрать обратно.

> Когда на вход дан .zip (или нужно отдать пачку файлов одним архивом): безопасно распаковать, обработать каждый файл, собрать результат в новый .zip.

Инструмент — стандартный `zipfile`. Для .rar/.7z на компьютере обычно нужен
отдельный пакет — если он есть, используй, иначе попроси .zip.

## Безопасная распаковка (защита от путей «../»)
```python
import zipfile, os
def safe_extract(zip_path, dest):
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        root = os.path.realpath(dest)
        for m in z.namelist():
            tgt = os.path.realpath(os.path.join(dest, m))
            if tgt != root and not tgt.startswith(root + os.sep):
                raise ValueError('небезопасный путь в архиве: ' + m)
        z.extractall(dest)
safe_extract('uploads/входной.zip', 'work')
```

## Обойти файлы и обработать
```python
import os
for base, _dirs, files in os.walk('work'):
    for name in files:
        p = os.path.join(base, name)
        # ... обработать p по типу (docx/pdf/...): см. соответствующие скилы
```

## Собрать результат в архив
```python
import zipfile, os
with zipfile.ZipFile('outputs/результат.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for base, _dirs, files in os.walk('out'):
        for name in files:
            full = os.path.join(base, name)
            z.write(full, os.path.relpath(full, 'out'))   # относительные пути внутри
```

## Правила
- Имена внутри архива могут быть в кириллице — `zipfile` пишет UTF-8, это нормально.
- Не распаковывай архив целиком в память для больших файлов — работай по файлам.
- Всегда сохраняй итог в `outputs/` и покажи пользователю (`show`).
