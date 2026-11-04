---
name: media-transcribe
description: Транскрибация речи из аудио/видео (инструмент transcribe — GigaAM-v3), протоколы и выжимки встреч, субтитры SRT, извлечение аудио, нарезка фрагментов, кадры из видео.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Транскрибация речи из аудио/видео (инструмент transcribe — GigaAM-v3), протоколы и выжимки встреч, субтитры SRT, извлечение аудио, нарезка фрагментов, кадры из видео.

# Скил: аудио и видео — транскрибация и обработка

## 0. ГЛАВНОЕ: распознавание речи — инструмент `transcribe`
```
transcribe {"path":"uploads/встреча.mp4"}
```
- Сервис GigaAM-v3 (лучшее качество для русского, с пунктуацией). Модель уже
  загружена — час записи распознаётся за минуты, диктовка — за секунды.
- Принимает ЛЮБОЙ аудио или видеофайл (mp4, mkv, mov, mp3, m4a, wav, ogg, webm…):
  извлекать звук ffmpeg-ом заранее НЕ нужно. Длинные записи он режет по паузам сам.
- Кладёт результат в `outputs/<имя>.txt` (абзацы по паузам) и `outputs/<имя>.srt`.
  Это готовый результат: не распознавай заново whisper-ом «для проверки».
- Дальше — по задаче: протокол/выжимка/задачи → read_file по .txt (большой — кусками
  через offset) и пиши `outputs/протокол.md`. Покажи пользователю через show.
- Нужно распознать только фрагмент — сначала вырежи его ffmpeg-ом (раздел 1), потом transcribe.
- Язык не русский или transcribe ответил ошибкой («сервис недоступен») → раздел 2
  (faster-whisper на компьютере). GigaAM-v3 — только русский.
- Кто говорит (разметка спикеров) сервис НЕ определяет — не придумывай «Спикер 1/2».

ffmpeg УЖЕ установлен на компьютере. Файл без расширения? Определи тип по заголовку:
```python
h = open('uploads/файл','rb').read(16).hex()
# 'ftyp' в hex (66747970) → MP4-видео; 'ID3'/'fffb' → MP3; 'RIFF' → WAV
print(h)
```

## 1. Извлечь аудио (весь файл или фрагмент)
СНАЧАЛА создай outputs/: `os.makedirs('outputs', exist_ok=True)` — иначе ffmpeg упадёт «No such file or directory».
```python
import os, subprocess
os.makedirs('outputs', exist_ok=True)
# фрагмент с 17 по 80 сек, моно 16кГц WAV (идеально для распознавания):
r = subprocess.run(['ffmpeg','-y','-i','uploads/video.mp4','-ss','17','-to','80',
                    '-vn','-acodec','pcm_s16le','-ar','16000','-ac','1','audio.wav'],
                   capture_output=True, text=True)
print(r.returncode, r.stderr[-300:] if r.returncode else os.path.getsize('audio.wav'))
```
(Без `-ss`/`-to` — конвертируется весь файл. MP3 на выдачу: `-acodec libmp3lame -q:a 4 out.mp3`.)

## 2. Запасной способ — faster-whisper (другие языки или сервис недоступен)
ВАЖНО: НЕ ставь пакет `openai-whisper` — его установка тянет torch и НЕ УКЛАДЫВАЕТСЯ
в таймаут (проверено: 900с не хватает). Ставь `faster-whisper` — лёгкий и быстрый:
```python
# шаг A: install {"manager":"pip","packages":"faster-whisper"}  (если ещё не стоит)
# шаг B:
from faster_whisper import WhisperModel
model = WhisperModel('small', device='cpu', compute_type='int8')  # 'base' — быстрее, 'small' — точнее
segments, info = model.transcribe('audio.wav', language='ru')      # language=None → автоопределение
parts = [(s.start, s.end, s.text.strip()) for s in segments]
text = ' '.join(p[2] for p in parts)
open('outputs/transcription.txt','w',encoding='utf-8').write(text)
print(text[:1000])
```
Первый запуск скачает модель (~100–500 МБ) — это нормально, дождись. Длинное видео
(>20 мин) транскрибируй кусками по 10 минут, дописывая результат в файл.

## 3. Запасной способ для КОРОТКИХ клипов (<60 сек, нужен интернет)
```python
# install: {"manager":"pip","packages":"SpeechRecognition pydub"}
import speech_recognition as sr
r = sr.Recognizer()
with sr.AudioFile('audio.wav') as src: audio = r.record(src)
print(r.recognize_google(audio, language='ru-RU'))
```

## 4. Субтитры SRT (из faster-whisper, есть таймкоды в parts)
```python
def ts(t): h=int(t//3600); m=int(t%3600//60); s=t%60; return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.',',')
srt = '\n'.join(f"{i+1}\n{ts(a)} --> {ts(b)}\n{tx}\n" for i,(a,b,tx) in enumerate(parts))
open('outputs/subtitles.srt','w',encoding='utf-8').write(srt)
```

## 5. Кадры из видео
```python
subprocess.run(['ffmpeg','-y','-i','uploads/video.mp4','-vf','fps=1/10','frame_%03d.png'])  # кадр каждые 10с
```

Итог всегда клади в outputs/ (текст — .txt или .md, субтитры — .srt) и покажи через show.
