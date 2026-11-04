---
name: vision
description: Посмотреть на изображение: понять, что на нём, или прочитать текст.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Посмотреть на изображение: понять, что на нём, или прочитать текст.

# Скил: зрение

У тебя есть НАСТОЯЩЕЕ зрение через мультимодальную модель. Чтобы разглядеть
картинку — используй инструмент see_image, он покажет изображение тебе и вернёт
описание:

use_skill не нужен для самого взгляда — просто вызови:
{"thought":"посмотрю на картинку","tool":"see_image","args":{"path":"uploads/photo.png","question":"Что изображено? Если есть текст — приведи его."}}

Когда что использовать:
- ПОНЯТЬ смысл, описать сцену, узнать объекты, прочитать вывеску/текст «по смыслу»
  → see_image (твои глаза). Это основной способ.
- Нужен ТОЧНЫЙ машинный текст со скана/документа (например, чтобы потом обработать
  программно) → OCR: pytesseract (lang='rus+eng') — см. ниже.
- Точные размеры/цвета/пиксельный анализ → PIL/numpy.

OCR (точный текст):
```python
import pytesseract
from PIL import Image
print(pytesseract.image_to_string(Image.open('uploads/scan.png'), lang='rus+eng'))
```

Свойства изображения:
```python
from PIL import Image
im = Image.open('uploads/photo.png'); print(im.size, im.mode)
```

Если задача — «повтори/перерисуй изображение» (например в SVG):
1. Сначала see_image — понять, что на картинке.
2. При необходимости измерь размеры/цвета кодом (PIL/numpy), найди фигуры.
3. Сгенерируй результат и сохрани его в outputs/ (только итог увидит пользователь).
