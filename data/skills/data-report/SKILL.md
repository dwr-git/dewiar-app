---
name: data-report
description: Анализ табличных данных (CSV/Excel): порядок исследования, графики, итоговый отчёт.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

> Анализ табличных данных (CSV/Excel): порядок исследования, графики, итоговый отчёт.

# Скил: анализ данных и отчёт

## 1. Загрузка (не угадывай формат — проверь)
```python
import pandas as pd
# кодировка/разделитель часто нестандартные:
for enc in ['utf-8','cp1251','latin-1']:
    try:
        df = pd.read_csv('uploads/data.csv', encoding=enc, sep=None, engine='python')
        print('encoding:', enc); break
    except Exception as e: print(enc, 'failed')
# Excel: df = pd.read_excel('uploads/data.xlsx')  (sheet_name=None — все листы)
print(df.shape); print(df.dtypes); print(df.head(5).to_string())
```

## 2. Обзор перед выводами (ОБЯЗАТЕЛЬНО, не выдумывай статистику)
```python
print(df.describe(include='all').to_string())
print('пропуски:\n', df.isna().sum())
print('дубли:', df.duplicated().sum())
```

## 3. Чистка (если нужна)
- дубли: `df = df.drop_duplicates()`
- пропуски чисел: медианой `df[c] = df[c].fillna(df[c].median())`
- даты: `df[c] = pd.to_datetime(df[c], errors='coerce')`
- выбросы: правило 1.5·IQR — пометь, не удаляй молча.

## 4. Графики — сохраняй файлами (matplotlib, бэкенд уже Agg)
```python
import matplotlib.pyplot as plt
import os; os.makedirs('outputs', exist_ok=True)
fig, ax = plt.subplots(figsize=(9,5), dpi=120)
df.groupby('категория')['значение'].sum().sort_values().plot.barh(ax=ax)
ax.set_title('…'); fig.tight_layout(); fig.savefig('outputs/chart1.png'); plt.close(fig)
```
2–4 графика достаточно: распределение, динамика, топ-N, корреляции (heatmap).

## 5. Итоговый отчёт
Собери `outputs/report.html`: заголовок, 3–6 ключевых цифр, картинки графиков
(`<img src="chart1.png">` — файлы лежат рядом), таблица топ-строк, выводы списком.
Либо Markdown `outputs/report.md`, если просили текст. Числа в выводах бери ТОЛЬКО
из посчитанного (print → проверил → вписал). Покажи отчёт через show.

## 6. Если просили Excel на выходе
```python
with pd.ExcelWriter('outputs/result.xlsx') as w:
    df.to_excel(w, sheet_name='data', index=False)
    summary.to_excel(w, sheet_name='summary')
```
