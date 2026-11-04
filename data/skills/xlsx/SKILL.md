---
name: xlsx
description: Создать или ТОЧНО отредактировать таблицу Excel (.xlsx): значения, формулы, стили, числовые форматы, ширины, закрепление строк. Для анализа данных и отчётов — см. data-report.
---
_Навык мастерской: выполняй его в фоновой задаче (если ты в разговоре — запусти start_task с целью пользователя). Инструменты задачи: write_file (файл в папке задачи, результаты — в outputs/), read_file, list_files, run_python (там, где ниже «python», «выполни код» или команды shell — пиши код Python; внешние программы — через subprocess), show (показать результат пользователю), transcribe (расшифровка аудио/видео своим слухом), download (скачать файл), web_search и read_webpage (вместо browser / web_fetch), use_skill / read_skill_file. Инструментов screenshot, export_pdf, see_image, rag_search здесь нет: проверяй результат, перечитывая файл (read_file) или кодом; PDF — предложи пользователю открыть HTML и «Печать → Сохранить как PDF»; по базе знаний — search_documents. Вместо requests — httpx (тот же API: httpx.get(url, follow_redirects=True)); BeautifulSoup может не быть — проверь import, иначе разбирай re или html.parser. ffmpeg — по пути из os.environ["FFMPEG"] (subprocess.run([os.environ["FFMPEG"], ...])). Программ вроде soffice, git, faster-whisper может не быть — проверь (shutil.which / import) и честно скажи, если нет._

# Навык: таблицы Excel (.xlsx) — точное создание и правка

> Создать или ТОЧНО отредактировать таблицу Excel (.xlsx): значения, формулы, стили, числовые форматы, ширины, закрепление строк. Для анализа данных и отчётов — см. data-report.

Инструмент — **openpyxl** (стили сохраняются). Для тяжёлого анализа больших
таблиц бери pandas, но для правки С СОХРАНЕНИЕМ ОФОРМЛЕНИЯ — только openpyxl.

## Прочитать
```python
import openpyxl
wb = openpyxl.load_workbook('uploads/файл.xlsx')      # со стилями
ws = wb.active                                         # или wb['Лист1']
for row in ws.iter_rows(values_only=True):
    print(row)
```
Нужны ВЫЧИСЛЕННЫЕ значения формул? `load_workbook(path, data_only=True)` —
но кэш есть, только если файл сохраняла настоящая программа (Excel/LibreOffice).
openpyxl формулы САМ НЕ СЧИТАЕТ: `data_only` по свежесозданной формуле вернёт None.
Если значение нужно в пайплайне — посчитай в Python и запиши число, либо
прогони файл через LibreOffice (`soffice --convert-to xlsx`, он пересчитает).

## Править С СОХРАНЕНИЕМ формата
Меняй ЗНАЧЕНИЕ ячейки — её стиль остаётся. Не пересобирай лист заново.
```python
ws['B2'] = 3000            # стиль, шрифт, формат B2 сохраняются
wb.save('outputs/готово.xlsx')
```

## Создать с оформлением
```python
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Отчёт'
ws['A1'] = 'Показатель'; ws['B1'] = 'Значение'
ws['A1'].font = Font(bold=True, size=12)
ws['A1'].fill = PatternFill('solid', fgColor='DDDDDD')
ws['A1'].alignment = Alignment(horizontal='center')
ws['B2'] = 2500; ws['B2'].number_format = '#,##0.00'   # 2 500,00
ws['B4'] = '=B2-B3'                                     # формула-строкой
ws.column_dimensions['A'].width = 24
ws.freeze_panes = 'A2'                                  # шапка закреплена
ws.auto_filter.ref = 'A1:B4'
wb.save('outputs/отчёт.xlsx')
```
Полезное: `Border(left=Side(style='thin'))`; объединение `ws.merge_cells('A1:C1')`;
несколько листов `wb.create_sheet('Имя')`; для .xlsm — `load_workbook(path, keep_vba=True)`.

## Ограничения / проверка
- Диаграммы, картинки и сводные таблицы при round-trip могут не сохраниться —
  если они важны, правь минимально и проверь результат.
- Итог всегда **перечитай** (`load_workbook` заново) и убедись, что значения,
  формулы и ключевые стили на месте.
- Показать таблицу «как на экране» / выгрузить PDF — через скилл **libreoffice**.
