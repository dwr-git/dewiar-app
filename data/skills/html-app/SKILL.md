---
name: html-app
description: Одностраничное HTML-приложение или игра: каркас, дизайн, сохранение, показ пользователю.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Одностраничное HTML-приложение или игра: каркас, дизайн, сохранение, показ пользователю.

# Скил: HTML-приложение / игра / страница

Результат — ВСЕГДА один самодостаточный файл `outputs/app.html` (CSS и JS внутри),
а не код в тексте ответа. После сохранения покажи его инструментом show.

## Порядок
1. `os.makedirs('outputs', exist_ok=True)` — и пиши файл через write_file.
2. БОЛЬШОЙ файл (игра, много JS) пиши ЧАСТЯМИ: сначала write_file с каркасом
   до середины, затем дописывай:
   ```python
   open('outputs/app.html','a',encoding='utf-8').write('''...продолжение...''')
   ```
3. Проверь себя: прочитай файл и убедись, что есть `</html>`, скобки/теги закрыты:
   ```python
   t = open('outputs/app.html',encoding='utf-8').read()
   print(len(t), '</html>' in t, t.count('{') - t.count('}'))
   ```
4. `{"tool":"show","args":{"path":"outputs/app.html"}}` — пользователь сразу пользуется.
5. ПОСМОТРИ НА РЕЗУЛЬТАТ СВОИМИ ГЛАЗАМИ: `{"tool":"screenshot","args":{"path":"outputs/app.html"}}`
   — увидишь скриншот страницы. Наложения, съехавшие блоки, нечитаемый текст,
   пропавшие кнопки → почини ТОЧЕЧНО (edit) и сделай screenshot снова. Только
   после визуально чистого результата — final_answer.

## Каркас (адаптивный, тёмная тема, без внешних зависимостей)
```html
<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Название</title>
<style>
  :root{--bg:#0f1320;--card:#1a2138;--tx:#e8ecff;--ac:#7aa2ff;--ok:#39d98a}
  *{box-sizing:border-box;margin:0}
  body{background:var(--bg);color:var(--tx);font:16px/1.5 system-ui,Segoe UI,Roboto,sans-serif;
       min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px}
  .card{background:var(--card);border-radius:16px;padding:24px;max-width:560px;width:100%;
        box-shadow:0 10px 40px rgba(0,0,0,.4)}
  h1{font-size:22px;margin-bottom:14px}
  button{background:var(--ac);color:#0b0f1d;border:0;border-radius:10px;padding:10px 18px;
         font-weight:600;cursor:pointer} button:hover{filter:brightness(1.1)}
  input,select{background:#10162b;color:var(--tx);border:1px solid #2a3354;border-radius:10px;padding:10px}
</style></head><body>
<div class="card"><h1>…</h1><div id="app"></div></div>
<script>
'use strict';
const $=s=>document.querySelector(s);
// состояние держи в одном объекте: const state={...}; функция render() перерисовывает.
</script></body></html>
```

## Частые требования
- Игры на Canvas: requestAnimationFrame-цикл, состояние в объекте, рестарт кнопкой/клавишей.
- Управление: клавиатура (keydown) + кнопки на экране (для мобильных).
- Счёт/рекорд: переменные в памяти (localStorage может быть недоступен в предпросмотре —
  оборачивай в try/catch).
- Графики без интернета: рисуй сам на Canvas; Chart.js используй только если задача
  явно его просит (CDN может быть закрыт у пользователя).
