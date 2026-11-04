---
name: etalon
description: Поиск и анализ документов белорусского законодательства через информационно-поисковую систему ЭТАЛОН-ONLINE (etalonline.by).
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Поиск и анализ документов белорусского законодательства через информационно-поисковую систему ЭТАЛОН-ONLINE (etalonline.by).

# Скил: работа с законодательством РБ (ЭТАЛОН-ONLINE)

У тебя есть доступ к публичной информационной системе «ЭТАЛОН-ONLINE» — основному источнику правовой информации Республики Беларусь. Через обычные HTTP-запросы (requests + BeautifulSoup) можно искать документы по ключевым словам и получать их полные тексты.

## 1. ПОИСК ДОКУМЕНТОВ

**URL поиска:**
```
https://etalonline.by/search/?search_str=ЗАПРОС&ps=100&PAGEN_1={страница}
```

Параметры:
- `search_str` — поисковый запрос (кириллица, URL-кодирование не требуется, requests сам закодирует)
- `ps=100` — количество результатов на странице (максимум)
- `PAGEN_1` — номер страницы (начиная с 1)

**Пример кода:**
```python
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def search_documents(query, max_pages=5):
    """Поиск документов на etalonline.by."""
    results = []
    for page in range(1, max_pages + 1):
        url = f'https://etalonline.by/search/?search_str={query}&ps=100&PAGEN_1={page}'
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.encoding = 'utf-8'
        soup = BeautifulSoup(r.text, 'html.parser')
        
        rows = soup.find_all('div', class_='ui-table-row')
        if not rows:
            break  # больше нет результатов
        
        for row in rows:
            num_div = row.find('div', class_='left-num')
            if not num_div:
                continue
            num_link = num_div.find('a', class_='docResNum')
            if not num_link:
                continue
            
            regnum = num_link.get('data-regnum', '')
            if not regnum:
                href = num_link.get('href', '')
                m = re.search(r'regnum=([^&]+)', href)
                if m:
                    regnum = m.group(1)
            if not regnum:
                continue
            
            title_link = row.find('a', class_='docLink')
            title = title_link.get_text(strip=True) if title_link else ''
            
            results.append({
                'regnum': regnum,
                'title': title,
                'url': f'https://etalonline.by/document/?regnum={regnum}'
            })
    return results

# Пример использования:
docs = search_documents('трудовой кодекс', max_pages=3)
for d in docs[:5]:
    print(f"{d['regnum']}: {d['title'][:80]}")
```

## 2. ПОЛУЧЕНИЕ ТЕКСТА ДОКУМЕНТА

**URL документа:**
```
https://etalonline.by/document/?regnum=REGNUM
```

Текст документа находится в `<div class="document-wrap">`. Извлекай через `get_text(separator='\n', strip=True)`.

**Важно:** Некоторые документы требуют авторизации для полного просмотра. Конституция и кодексы доступны в открытом виде. Если текст пустой или содержит только фильтры — документ закрыт.

**Пример кода:**
```python
def get_document_text(regnum):
    """Получить полный текст документа по regnum."""
    url = f'https://etalonline.by/document/?regnum={regnum}'
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.encoding = 'utf-8'
    soup = BeautifulSoup(r.text, 'html.parser')
    
    doc_div = soup.find('div', class_='document-wrap')
    if doc_div:
        text = doc_div.get_text(separator='\n', strip=True)
        return text
    return None  # документ недоступен без авторизации

# Пример:
text = get_document_text('v19402875')  # Конституция РБ
if text:
    print(f"Длина: {len(text)} символов")
    print(text[:500])
```

## 3. АЛЬТЕРНАТИВНЫЕ ИСТОЧНИКИ

Если документ недоступен на etalonline.by (требуется авторизация), попробуй:

- **president.gov.by** — официальные тексты законов и указов Президента
  - `https://president.gov.by/ru/normative-acts/search?search_str=ЗАПРОС`
- **pravo.by** — Национальный правовой Интернет-портал РБ
  - `https://pravo.by/search/?search_str=ЗАПРОС`
- **law.by** — англоязычная версия Эталона

## 4. ТИПОВЫЙ РАБОЧИЙ ПРОЦЕСС

1. **Поиск:** `search_documents("ключевые слова", max_pages=N)` → список документов с regnum
2. **Выбор:** отфильтруй по названию, дате, типу акта
3. **Получение текста:** `get_document_text(regnum)` → полный текст
4. **Анализ:** ищи нужные статьи, разделы, изменения через regex или строковый поиск
5. **Сохранение:** сохрани текст в файл `outputs/doc_NAME.txt` для дальнейшей работы

## 5. ОСОБЕННОСТИ

- **Паузы:** делай паузу 2-3 секунды между запросами (`time.sleep(2)`), чтобы не нагружать сервер
- **Кодировка:** всегда устанавливай `r.encoding = 'utf-8'` после запроса
- **regnum:** уникальный идентификатор документа, формат обычно `vXXXXXXX` или `hkXXXXXXX` (для кодексов)
- **Большие документы:** текст может быть очень длинным (Конституция ~88К символов). Сохраняй в файл, а не держи в памяти
- **Изменения:** в тексте документа обычно указаны все изменения и дополнения с датами

## 6. ПРИМЕР: НАЙТИ И ПРОАНАЛИЗИРОВАТЬ ДОКУМЕНТ

```python
import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Шаг 1: Поиск
docs = search_documents('минимальная заработная плата', max_pages=2)
print(f"Найдено {len(docs)} документов")

# Шаг 2: Выбор самого свежего
for d in docs[:3]:
    print(f"{d['regnum']}: {d['title'][:100]}")

# Шаг 3: Получение текста первого документа
regnum = docs[0]['regnum']
text = get_document_text(regnum)

# Шаг 4: Анализ — найти конкретную статью
articles = re.findall(r'Статья\s+\d+[\.\s](.+?)(?=Статья\s+\d+|$)', text, re.DOTALL)
for i, art in enumerate(articles[:3]):
    print(f"\n--- Статья {i+1} ---")
    print(art[:300])
```
