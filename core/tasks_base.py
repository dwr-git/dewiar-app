"""Фоновые задачи — основа (чистое ядро 1.0.10 — docs/CORE_PLAN.md): постоянные (бюджеты, шаги, опрос), одна задача (Task)
и помощники. Менеджер задач — core/tasks.py (TaskManager), его части — tasks_*.py; прежние имена tasks.X на месте.
Подменять в проверках — здесь (tasks_base.BUDGET, tasks_base.stream_events…): части читают их через основу."""
import datetime as dt
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

import quality as Q
from codework import CodeWork
from llm import stream_events

log = logging.getLogger("dewiar.tasks")

# статусы: running → waiting (ask_user) / sleeping (wait, передышка, повтор после сбоя) → done | failed | stopped;
# paused — остановлена до команды человека (или до автопродолжения после перезапуска)
ACTIVE = ("running", "waiting")
ALIVE = ("running", "waiting", "sleeping")         # задача ещё в работе: sleeping проснётся сама
STATUS_RU = {"running": "выполняется", "waiting": "ждёт ответа", "paused": "на паузе", "done": "готово",
             "failed": "не получилось", "stopped": "остановлена", "sleeping": "ждёт и вернётся"}
BUDGET = int(os.environ.get("DEWIAR_TASK_BUDGET") or 60000)     # потолок разговора задачи в памяти (символов); меньше —
                                                   # если не позволяет окно модели (_budget)
# «Большие задачи», выпуск 1 (docs/HARNESS.md): запрос задачи подстраивается под окно модели, начало запроса не меняется
WIN_DEFAULT = int(os.environ.get("DEWIAR_TASK_WINDOW") or 65536)   # окно модели, если сервер его не называет
TINY_WIN = 6144                                    # окно меньше — описания инструментов до первой фразы, набор короче
TINY_DROP = {"notes", "notify", "wait", "download", "file_glob", "set_criteria", "explore"}   # …без этих (они — через find_tool)
LIGHT_WIN = 16384                                  # окно не больше — «лёгкий режим»: короче подсказка, без уроков и частей
COMPACT_AT = float(os.environ.get("DEWIAR_TASK_COMPACT_AT") or 0.65)   # весь запрос больше этой доли окна — сжать историю
TRIM_AFTER = int(os.environ.get("DEWIAR_TASK_TRIM_AFTER") or 12)   # результаты старше стольких шагов — заглушкой
TRIM_EVERY = 6                                     # чистить пачкой раз в столько шагов: каждая чистка — промах кэша
OUT_MAX = 4000                                     # вывод инструмента длиннее (знаков) — целиком в _out/, в историю — начало
CTX_TRIES = 3                                      # «не хватило окна» подряд — столько раз сжимаем и повторяем, потом сбой
RETRY_MIN = tuple(float(x) for x in (os.environ.get("DEWIAR_TASK_RETRY") or "2,5,15,30").split(","))  # сбой модели/сети — повтор через N минут
RESUME_SEC = float(os.environ.get("DEWIAR_TASK_RESUME_SEC") or 20)   # после запуска программы — продолжить прерванные
CYCLES = int(os.environ.get("DEWIAR_TASK_CYCLES") or 0)   # кругов по max_steps шагов подряд (0 — из настроек tasks.cycles,
                                                   # по умолчанию 15: 80 × 15 = 1200 шагов), потом пауза до команды человека.
BREATHER_SEC = float(os.environ.get("DEWIAR_TASK_BREATHER_SEC") or 60)   # передышка между кругами
STALE_CYCLES = 2                                   # кругов подряд без продвижения (план, блокнот, файлы) — пауза раньше
STUCK_STEPS = int(os.environ.get("DEWIAR_TASK_STUCK_STEPS") or 40)   # шагов подряд без продвижения — пауза («буксует», №58)
ASK_DECLINES = 3                                   # отказов человека за запуск — пауза, а не новые вопросы (№54, №58)
ASK_SILENT = 2                                     # вопросов подряд без ответа (человека нет рядом) — пауза
PROGRESS_TOOLS = {"code_edit", "code_write", "code_delete", "code_undo"}   # правки рабочей копии — тоже продвижение
# ответ без действий, но с разметкой вызова (JSON с именем функции, <tool_call>, <tool_calls>/<invoke>, «DSML») — модель
# пыталась действовать, а вызов не разобрался (№448): просим вызвать правильно, а не «действуй»
CALL_MARK_RX = re.compile(r'"(?:tool_name|tool|name|function)"\s*:|<[\s｜|▁/]*(?:tool_calls?\b|function[_▁]calls|invoke\b|DSML)', re.I)
IDLE_CHANCE = ("Ты уже несколько раз подряд ответил(а) текстом, не выполнив ни одного действия. Сейчас одно из двух:\n"
               "— цель достигнута — вызови finish: в summary итог (что сделано, где результат, ссылки); отчёт пишется в "
               "finish, а не текстом ответа;\n— цель не достигнута — сделай следующий пункт плана инструментом (web_search, "
               "read_webpage, write_file, remember…), одним вызовом, без пересказа плана.\nНе пиши ответ текстом без вызова.")
HANG_SEC = float(os.environ.get("DEWIAR_TASK_HANG_SEC") or 600)     # шаг молчит столько (модель) — «задача не отвечает»
HANG_TOOL_SEC = float(os.environ.get("DEWIAR_TASK_HANG_TOOL_SEC") or 1800)   # …а инструмент (скачивание, код) — столько
PROGRESS_FIRST = float(os.environ.get("DEWIAR_TASK_PROGRESS_FIRST") or 600)  # долгая задача: первая весточка «как идёт»
PROGRESS_EVERY = float(os.environ.get("DEWIAR_TASK_PROGRESS_EVERY") or 1800)  # …и дальше не чаще, если есть сдвиг
ASK_REMIND_SEC = float(os.environ.get("DEWIAR_TASK_ASK_REMIND_SEC") or 7200)  # вопрос без ответа — напомнить один раз
PARTS_MAX = 4                                      # частей за раз у spawn_parts (по умолчанию; настройка tasks.parts_max, 1–8)
PARTS_PARALLEL = int(os.environ.get("DEWIAR_TASK_PARALLEL") or 3)   # сколько частей работают одновременно
# «Большие задачи», выпуск 6 (docs/HARNESS.md): подзадачи с чистым контекстом — разведчик (explore), проверяющий (verify),
# части по поручению (цель, формат результата, источники, границы) с бюджетом шагов и токенов
EXPLORE_TOOLS = ("file_glob", "file_grep", "file_read", "web_search", "read_webpage")   # разведчик только читает
EXPLORE_STEPS = int(os.environ.get("DEWIAR_TASK_EXPLORE_STEPS") or 0)   # шагов разведчика (0 — tasks.explore_steps, по умолчанию 10)
EXPLORE_OUT = 1500                                 # выжимка разведчика — не больше стольких токенов (≈ ×3 знаков)
VERIFY_LOOKS = 2                                   # проверяющий может дочитать файлы и источники столько раз за проверку
PART_STEPS = 60                                    # шагов у части (tasks.part_steps): потом — итог с тем, что есть
PART_TOKENS = 800000                               # токенов у части (tasks.part_tokens; 0 — без предела)
SUBS_KEEP = 30                                     # записей о разведчиках и проверяющих в задача.json (для студии)
# выпуск 7 (начало): бюджет задачи в токенах (tasks.budget_tokens; 0 — без предела) — предупреждение на BUDGET_WARN,
# на BUDGET_STOP — «подведи итог», ещё BUDGET_GRACE шагов без итога — пауза с причиной; «продолжи» — ещё столько же
BUDGET_WARN, BUDGET_STOP, BUDGET_GRACE = 0.5, 0.8, 3
MAIL_WAKE_SEC = 300
MILESTONE_GAP = 180                                # весточки на вехах плана — не чаще раза в 3 минуты (HARNESS 7)                                # wait on_mail: почту проверяем не чаще раза в 5 минут (выпуск 8)
VOICE_AFTER = 600                                  # голосом — задача идёт дольше 10 минут (человек, скорее всего, отошёл)
VOICE_GAP = 900                                    # и не чаще раза в 15 минут: весточка, а не диктор
NOTEBOOK_HEAD = ("# Блокнот задачи\n\n## Что известно\n\n## Что решено\n\n## Чего ждём\n\n## Что дальше\n")
# «Большие задачи», выпуски 3–4 (docs/HARNESS.md): критерии готовности, проверка по существу, список дел со статусами, опрос хода
POLL_EVERY = int(os.environ.get("DEWIAR_TASK_POLL_EVERY") or 8)   # раз в столько шагов — короткий опрос хода (Magentic-One)
POLL_LOCAL = int(os.environ.get("DEWIAR_TASK_POLL_LOCAL") or POLL_EVERY * 3)   # …у своего сервера модели (кэш одного разговора)
TODO_STATUS = ("pending", "in_progress", "done", "blocked")
TODO_MARK = {"pending": "○", "in_progress": "▶", "done": "✓", "blocked": "✗"}
SRC_MAX = 8 << 20                                  # _src/результаты.txt — опора для сверки ссылок и цифр, не больше (байт)
# результаты этих инструментов пишет сама модель — опорой для сверки итога они не считаются
SELF_MADE = {"write_file", "file_edit", "update_plan", "todo_update", "set_criteria", "remember", "notes", "log", "notify", "finish",
             "show", "wait", "find_tool", "spawn_parts", "code_write", "code_edit", "code_delete", "code_undo", "code_diff",
             "explore", "verify"}                  # выжимка разведчика — пересказ модели; опора — то, что он сам прочитал


def S(props, req=()):
    """JSON-схема параметров инструмента."""
    return {"type": "object", "properties": props, "required": list(req)}


TASK_TOOLS = {
    "todo_update": ("Список дел задачи со статусами — твой план. items — пункты {id, text, status, evidence}: новый пункт — "
                    "без id; изменить — по id. status: pending — ждёт, in_progress — делаю (один за раз), done — сделано: "
                    "ТОЛЬКО с evidence (путь к файлу, вывод команды или ссылка — доказательство), blocked — не сделать (в "
                    "evidence — почему). replace=true — новый план целиком (сменить подход).",
                    S({"items": {"type": "array", "items": {"type": "object", "properties": {
                        "id": {"type": "integer"}, "text": {"type": "string"},
                        "status": {"type": "string", "enum": list(TODO_STATUS)}, "evidence": {"type": "string"}}}},
                       "replace": {"type": "boolean"}}, ["items"])),
    "set_criteria": ("Критерии готовности — по ним код проверит итог перед finish. Задай в начале, сразу после плана: 2–6 "
                     "проверяемых пунктов {check, target, value}. check: file — файл есть (target — путь); contains — в файле "
                     "есть текст (value); number — в файле есть число (value); command — команда проходит; url — ссылка "
                     "открывается; page — HTML-страница без ошибок в браузере; pages / lines / rows / files — сколько страниц, "
                     "строк, строк таблицы, файлов (value — число или «3-5»); manual — остальное словами (text).",
                     S({"items": {"type": "array", "items": {"type": "object", "properties": {
                         "check": {"type": "string", "enum": list(Q.CRIT_CHECKS)}, "target": {"type": "string"},
                         "value": {"type": "string"}, "text": {"type": "string"}}, "required": ["check"]}}}, ["items"])),
    "update_plan": ("План чек-листом Markdown («- [ ] шаг», выполненные «- [x]») — старый способ; лучше todo_update.",
                    S({"plan": {"type": "string"}}, ["plan"])),
    "log": ("Короткая заметка в журнал задачи: что выяснил, что решил, что дальше.", S({"text": {"type": "string"}}, ["text"])),
    "ask_user": ("Спросить пользователя, если без его решения дальше нельзя. Ответ придёт результатом. "
                 "Спрашивай редко и по делу.", S({"question": {"type": "string"}}, ["question"])),
    "finish": ("Задача выполнена (или дальше невозможно): итог для пользователя в Markdown — что получилось (ответ, "
               "главные цифры), где результат (файл — путём), что не удалось и почему, и один следующий шаг, если он "
               "правда есть. Шаги не пересказывай — они в журнале. После этого работа заканчивается.",
               S({"summary": {"type": "string"}}, ["summary"])),
    "remember": ("Записать в блокнот задачи важный факт — сразу, как узнал: номер, код брони, сумму, адрес, ответ "
                 "человека или компании, договорённость, срок. Блокнот — твоя память: ранние шаги со временем "
                 "забываются, блокнот — нет.", S({"fact": {"type": "string"}}, ["fact"])),
    "notes": ("Переписать блокнот задачи целиком (Markdown, разделы: Что известно / Что решено / Чего ждём / Что "
              "дальше). Используй, когда картина поменялась.", S({"text": {"type": "string"}}, ["text"])),
    "notify": ("Коротко сообщить пользователю важное по ходу работы — придёт в Telegram и уведомлением: что выяснил, "
               "что изменилось, что дальше (2–5 строк, по делу, без воды). important=true — срочно.",
               S({"text": {"type": "string"}, "important": {"type": "boolean"}}, ["text"])),
    "wait": ("Подождать и вернуться к задаче позже — когда результат зависит от внешнего: ответ на письмо или "
             "обращение, смена статуса, время проверки (например, «за 2 часа до вылета проверить выход»). minutes — "
             "через сколько минут, или until — когда (YYYY-MM-DDTHH:MM, местное время); reason — чего ждёшь и что "
             "проверишь. Перед wait запиши в блокнот, чего ждёшь. Если пользователь напишет задаче раньше — продолжишь сразу. "
             "Ждёшь события — не гадай со временем: on_file — путь к файлу (вернусь, как только он появится или изменится), "
             "on_mail — от кого или о чём письмо (вернусь, как придёт новое такое письмо); minutes/until тогда — крайний срок.",
             S({"minutes": {"type": "number"}, "until": {"type": "string"}, "reason": {"type": "string"},
                "on_file": {"type": "string"}, "on_mail": {"type": "string"}}, ["reason"])),
}
# Части задачи: большую работу с независимыми кусками (собрать сведения по пяти компаниям, написать три раздела)
# задача раздаёт помощникам — они работают одновременно, каждый в своей папке; собрать — wait_parts (итоги и файлы
# частей копируются в parts/ папки задачи). Части сами частей не заводят (одна ступень).
PART_TOOLS = {
    # {pm} — tasks.parts_max (подставляет _catalog: описание одно на всю задачу — начало запроса не меняется)
    "spawn_parts": ("Раздать независимые части большой работы помощникам — они делают их одновременно (до {pm} частей; "
                    f"работают сразу по {PARTS_PARALLEL}). Каждой части — ПОРУЧЕНИЕ: title; goal — что сделать; output — "
                    "формат результата: какой файл и что в нём (например «outputs/минск.md: таблица цен, 5 строк, у каждой "
                    "цифры ссылка»); sources — где брать (адреса, файлы, «поиск»); limits — границы (чего не делать, объём); "
                    "files — файлы из твоей папки, нужные части (она получит копии в inputs/). "
                    "Без output поручение не примут. Помощник не видит твой разговор и твою папку — всё нужное пиши в поручении. Не дели "
                    "мелкое и связанное: только куски, которые можно делать порознь. Потом — wait_parts.",
                    S({"parts": {"type": "array", "items": {"type": "object", "properties": {
                        "title": {"type": "string"}, "goal": {"type": "string"}, "output": {"type": "string"},
                        "sources": {"type": "string"}, "limits": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}}},
                        "required": ["goal", "output"]}}}, ["parts"])),
    "wait_parts": ("Дождаться частей, розданных spawn_parts, и получить их короткие итоги; файлы частей и полный итог каждой "
                   "появятся в parts/<название>/ твоей папки (file_read, run_python). minutes — сколько ждать сейчас (по умолчанию 60).",
                   S({"minutes": {"type": "number"}})),
}
# Подзадачи с чистым контекстом (выпуск 6): работают синхронно, в той же папке и с теми же правами, что задача (не шире),
# со своим окном и бюджетом шагов; видны в студии («Помощники»), останавливаются вместе с задачей.
SUB_TOOLS = {
    "explore": ("Разведчик: прочитать много (длинный документ, папку, несколько страниц) ради одного вопроса — в СВОЁМ окне, "
                "не забивая твою память. question — что выяснить; paths — файлы или папки (в папке задачи или данных ей), "
                "urls — страницы. Разведчик только читает (файлы, поиск, страницы) и вернёт выжимку (до ~1,5 тыс. токенов) со "
                "ссылками, где это написано. Ответ придёт сразу результатом.",
                S({"question": {"type": "string"}, "paths": {"type": "array", "items": {"type": "string"}},
                   "urls": {"type": "array", "items": {"type": "string"}}}, ["question"])),
    "verify": ("Проверяющий с чистым контекстом — до finish: сверит сделанное с целью и критериями готовности, прочитает файлы и "
               "источники сам и вернёт замечания. what — что проверить (пути файлов или «всё»); criteria — по чему (пусто — "
               "цель и критерии задачи). Ничего не меняет.",
               S({"what": {"type": "string"}, "criteria": {"type": "string"}})),
}
EXPLORE_REPORT = {"name": "report", "description": "Сдать выжимку: summary — ответ на вопрос (цифры и факты — с тем, где "
                  "прочитано; противоречия; чего не нашёл); refs — где это написано: «путь:строки — что там» или «адрес — что там».",
                  "parameters": S({"summary": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}, ["summary"])}
# «Мастерская»: задача сама делает файлы-результаты (страница, дашборд, презентация, таблица, расшифровка) и показывает
# их пользователю (студия → «Задачи» → «Результаты»). Пути — только внутри папки задачи (_path).
# Одноимённые инструменты чата (read_file…) в задаче заменяются этими — см. _specs.
WORK_TOOLS = {
    "write_file": ("Создать файл в папке задачи (HTML-страница, дашборд, презентация, .md, .csv, .json, .py…). path — "
                   "относительный, результаты — в outputs/ (например outputs/app.html). Большой файл пиши частями: "
                   "append=true дописывает в конец. HTML/CSS/JS пиши обычным текстом здесь, а не строкой внутри Python.",
                   S({"path": {"type": "string"}, "content": {"type": "string"}, "append": {"type": "boolean"}}, ["path", "content"])),
    "file_read": ("Прочитать файл с номерами строк: из папки задачи (путь относительный) или из папок, которые "
                  "человек дал задаче (полный путь). Кусками до ~4000 знаков; start/end — диапазон строк. PDF, Word, Excel "
                  "и PowerPoint — их текстом (в PDF перед каждой страницей строка «=== стр. N ===»); длинный документ — "
                  "сначала найди нужное file_grep, потом читай рядом.",
                  S({"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"])),
    "file_edit": ("Правка файла куском: old — точный кусок из файла (лучше с соседней строкой, чтобы был единственным), new — "
                  "чем заменить; replace_all=true — заменить все вхождения. Не нужно переписывать файл целиком. После правки "
                  ".py, .json, .html проверяются: сломанный синтаксис не сохраняется.",
                  S({"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "replace_all": {"type": "boolean"}},
                    ["path", "old", "new"])),
    "file_grep": ("Поиск по содержимому файлов (регулярное выражение, без учёта регистра): в папке задачи или в данной ей "
                  "папке (path — полный путь или подпапка); glob — какие файлы (*.csv, **/*.py). Ответ — файл:строка: текст. Ищет и "
                  "внутри PDF, Word, Excel (строка — как в file_read этого файла).",
                  S({"pattern": {"type": "string"}, "path": {"type": "string"}, "glob": {"type": "string"}}, ["pattern"])),
    "file_glob": ("Список файлов по шаблону (**/*.pdf, отчёты/*.md, *) с размерами: в папке задачи или в данной ей папке "
                  "(path). Вместо обхода папок по одной.",
                  S({"pattern": {"type": "string"}, "path": {"type": "string"}})),
    "read_file": ("То же, что file_read (старое имя).",
                  S({"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"])),
    "list_files": ("Файлы в папке задачи (что уже сделано, что скачано).", S({})),
    "run_python": ("Выполнить код Python в папке задачи (текущая папка = папка задачи): расчёты, обработка данных, "
                   "сборка файлов (есть numpy, Pillow, httpx, pypdf; openpyxl, python-docx, python-pptx — если "
                   "установлены, проверь import). Печатай print — увидишь вывод. До 3 минут (timeout — до 600 с). Код "
                   "работает в песочнице: пишет только в папку задачи, личные папки человека не видит, сеть — если задаче её дали.",
                   S({"code": {"type": "string"}, "timeout": {"type": "integer"}}, ["code"])),
    "run_shell": ("Выполнить команду в папке задачи (" + ("PowerShell" if os.name == "nt" else "bash") + "): утилиты — ffmpeg, "
                  "pandoc, unzip, git, sort… В песочнице: пишет только в папку задачи, сеть — если задаче её дали. "
                  "timeout — секунд (до 600).",
                  S({"command": {"type": "string"}, "timeout": {"type": "integer"}}, ["command"])),
    "rewind": ("Откатить outputs/ к виду перед шагом step (номер шага — из журнала или списка снимков): испорченные файлы "
               "вернутся, лишние уйдут. Без step — список снимков. Текущий вид перед откатом тоже сохраняется.",
               S({"step": {"type": "integer"}})),
    "show": ("Показать файл пользователю как готовый результат: страница, дашборд, презентация, картинка, PDF, документ, "
             "таблица. Он появится в студии во вкладке «Результаты» с просмотром. Вызывай для каждого главного файла.",
             S({"path": {"type": "string"}, "title": {"type": "string"}}, ["path"])),
    "transcribe": ("Расшифровать речь из аудио или видео в текст с метками времени [мм:сс] (своим распознаванием). "
                   "path — файл в папке задачи, в папке ассистента или полный путь. Сохраняет .txt и .srt в outputs/.",
                   S({"path": {"type": "string"}}, ["path"])),
    "download": ("Скачать файл по ссылке в папку задачи (downloads/). Вернёт путь.",
                 S({"url": {"type": "string"}, "name": {"type": "string"}}, ["url"])),
}
# режим «Код» (только у задачи с проектом): работа в рабочей копии codework.CodeWork
CODE_TOOLS = {
    "code_list": ("Файлы проекта (можно фильтр: *.py, src/, имя).", S({"pattern": {"type": "string"}})),
    "code_read": ("Прочитать файл проекта с номерами строк (по 400 строк; start/end — диапазон).",
                  S({"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"])),
    "code_search": ("Поиск по коду (регулярное выражение), glob — фильтр файлов.",
                    S({"pattern": {"type": "string"}, "glob": {"type": "string"}}, ["pattern"])),
    "code_edit": ("Точечная правка: заменить фрагмент old (точно как в файле, единственный) на new.",
                  S({"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, ["path", "old", "new"])),
    "code_write": ("Создать файл или переписать целиком.", S({"path": {"type": "string"}, "content": {"type": "string"}},
                                                             ["path", "content"])),
    "code_delete": ("Удалить файл или папку проекта.", S({"path": {"type": "string"}}, ["path"])),
    "code_run": ("Выполнить команду в папке проекта (" + ("PowerShell" if os.name == "nt" else "bash") + "): тесты, сборка, линтер, git status… timeout — секунд. "
                 "Долгая программа, которая не завершается сама (сервер разработки, наблюдатель), — background=true: запустится "
                 "в фоне, а ты проверишь её (например, curl к серверу) и прочитаешь вывод через code_process.",
                 S({"command": {"type": "string"}, "timeout": {"type": "integer"}, "background": {"type": "boolean"}}, ["command"])),
    "code_process": ("Фоновые процессы задачи: action status — список, output — вывод (id), stop — остановить (id или all). "
                     "В конце задачи они останавливаются сами.",
                     S({"action": {"type": "string", "enum": ["status", "output", "stop"]}, "id": {"type": "string"}}, ["action"])),
    "code_undo": ("Отменить свои последние правки (steps — сколько, по умолчанию 1), если правка всё сломала: файлы вернутся как были.",
                  S({"steps": {"type": "integer"}})),
    "code_diff": ("Посмотреть свои изменения (diff) — перед finish проверь, что всё как задумано.", S({})),
}
# что показать в карточке задачи, пока идёт вызов (если модель не написала своих слов)
ACT_RU = {"write_file": "пишу файл", "read_file": "читаю файл", "file_read": "читаю файл", "file_edit": "правлю файл",
          "file_grep": "ищу в файлах", "file_glob": "смотрю файлы", "list_files": "смотрю файлы", "run_python": "запускаю Python",
          "show": "показываю результат", "run_shell": "выполняю команду", "rewind": "откатываю результаты", "transcribe": "расшифровываю запись", "download": "скачиваю файл",
          "web_search": "ищу в интернете", "read_webpage": "читаю страницу", "update_plan": "обновляю план", "log": "пишу журнал",
          "finish": "подвожу итог", "code_run": "запускаю в проекте", "code_edit": "правлю код", "code_read": "читаю код",
          "remember": "записываю в блокнот", "notes": "обновляю блокнот", "notify": "сообщаю вам", "wait": "жду и вернусь"}
# инструменты чата, которые не нужны внутри задачи
SKIP_IN_TASK = {"start_task", "task_status", "stop_task", "remove_task", "resume_task", "tell_task", "call_persona", "write_diary"}
# Профиль задачи (выпуск 1): постоянный узкий набор — файлы, веб, run_python, план и блокнот, ask/notify/wait/finish, части,
# навыки. Всё остальное (музыка, деньги, напоминания…) — через find_tool: подключается до конца задачи и встаёт В КОНЕЦ
# списка, чтобы начало запроса (подсказка и инструменты) не менялось и сервер брал его из кэша.
PROFILE_TASK = ("todo_update", "set_criteria", "ask_user", "finish", "remember", "notes", "notify", "wait")   # update_plan, log,
                                                   # list_files, read_file — по имени (совместимость)
BY_NAME = ("update_plan", "log", "list_files", "read_file")   # не в профиле, но вызов по имени (и текстом) — выполняется
PROFILE_WORK = ("write_file", "file_read", "file_edit", "file_grep", "file_glob", "run_python", "show", "download")
PROFILE_CHAT = ("web_search", "read_webpage", "use_skill")      # read_skill_file — подключается сам, когда навык его назовёт
RETRY_SAFE = {"web_search", "read_webpage", "download", "file_read", "read_file", "file_grep", "file_glob", "use_skill", "read_skill_file"}
RETRY_SEC = float(os.environ.get("DEWIAR_TASK_TOOL_RETRY_SEC") or 3)    # безопасный инструмент упал на сбое сети — пауза и ещё раз
LIST_MAX = 200                                     # строк в ответе поиска и списка файлов — дальше «сузь: …»
FIND_TOOL = {"find_tool": ("Найти инструмент, которого нет в списке (напоминания, погода, расчёты, почта, расшифровка записи, "
                           "музыка…): query — что нужно сделать, своими словами. Вернёт подходящие с описанием; connect — имя "
                           "инструмента, чтобы подключить его до конца задачи (или просто вызови его).",
                           S({"query": {"type": "string"}, "connect": {"type": "string"}}))}
NO_TRIM = {"ask_user", "wait_parts", "finish", "spawn_parts", "update_plan", "todo_update", "set_criteria", "remember", "notes", "notify",
           "wait", "log", "show"}
ACT_RU.update(todo_update="обновляю список дел", set_criteria="записываю критерии готовности", find_tool="ищу нужный инструмент", spawn_parts="раздаю части помощникам", wait_parts="жду части", code_process="смотрю фоновый процесс",
              explore="разведчик читает", verify="проверяющий сверяет сделанное",
              code_undo="откатываю правку", code_search="ищу в коде", code_diff="проверяю изменения")


def _now():
    return dt.datetime.now().isoformat(timespec="seconds")


# «Отказано в доступе», Permission denied, WinError 5 — задаче нужны права, которых нет: ночной обход не перезапускает её
# каждую ночь, а один раз объясняет человеку (отложенное 22.10)
ACCESS_RX = re.compile(r"Permission denied|PermissionError|Отказано в доступе|Access is denied|WinError 5\b|"
                       r"Operation not permitted|EACCES|EPERM|нет доступа|нет прав", re.I)


def _clean(name):
    """Название задачи -> допустимое имя папки (Windows запрещает \\/:*?"<>|), не длиннее 60 символов, без пробелов и точек
    по краям: Windows их срезает, и путь к «план.md» не совпадал с папкой (пакет 22.10: FileNotFoundError в синхронизации)."""
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", " ", name or "").strip()
    return re.sub(r"\s+", " ", name)[:60].strip(" .") or "задача"


_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


def _regular(p):
    """Обычный файл (не ссылка, не FIFO, не устройство) — по lstat."""
    import stat
    try:
        return stat.S_ISREG(os.lstat(p).st_mode)
    except OSError:
        return False


def _rd(p, default=""):
    """Прочитать служебный файл задачи: только обычный файл — FIFO, оставленный кодом, повесил бы карточку (вторая рецензия)."""
    if not _regular(p):
        return default
    try:
        fd = os.open(p, os.O_RDONLY | _NOFOLLOW | _NONBLOCK | getattr(os, "O_BINARY", 0))
    except OSError:
        return default
    with os.fdopen(fd, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def _wr(p, data, append=False, root=None):
    """Запись Dewiar в папку задачи (B2, выпуск 5): код задачи мог оставить там ссылку (журнал.md → ~/.bashrc) — по ссылкам
    не пишем: ссылка на месте файла удаляется, файл открывается без перехода по ссылке (O_NOFOLLOW), а папка, куда пишем
    (root задан), должна быть внутри root по настоящему пути."""
    p = Path(p)
    if isinstance(data, str):
        data = data.encode("utf-8")
    if root is not None:
        par, r = os.path.realpath(p.parent), os.path.realpath(root)
        if not (par == r or par.startswith(r.rstrip(os.sep) + os.sep)):
            raise OSError(f"«{p.name}»: папка ведёт за пределы папки задачи (ссылка) — не пишу")
    if p.is_symlink() or (os.path.lexists(p) and not os.path.isdir(p) and not _regular(p)):
        p.unlink()                                     # ссылка или FIFO/сокет на месте файла
    fl = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC) | _NOFOLLOW | _NONBLOCK | getattr(os, "O_BINARY", 0)
    fd = os.open(p, fl, 0o644)
    with os.fdopen(fd, "ab" if append else "wb") as f:
        f.write(data)


def _file_names(v):
    """Отчёт 656 (0.87.2): задача, поставленная до 0.86, хранила в «files» записи {"name", "b64"} — продолжение после
    паузы падало «sequence item 0: expected str instance, dict found». Список файлов или папок -> строки (у записи — имя)."""
    out = []
    for x in (v if isinstance(v, (list, tuple)) else [v] if v else []):
        if isinstance(x, dict):
            x = x.get("path") or x.get("name") or ""
        x = str(x or "").strip()
        if x:
            out.append(x)
    return out


class Task:
    """Одна задача: папка и состояние data (задача.json). Поля data читаются как атрибуты: t.status, t.title…
    События cancel/answer_ev связывают поток задачи с командами человека (стоп, ответ на вопрос)."""
    def __init__(self, d: Path, data: dict):
        self.dir = d
        self.data = data
        self.cancel = threading.Event()
        self.answer_ev = threading.Event()
        self.answer = None
        self.thread = None
        self.beat = 0.0           # monotonic последнего признака жизни шага (кусок ответа модели, начало и конец инструмента)
        self.beat_tool = ""       # какой инструмент сейчас работает ("" — ждём модель)
        self.run_t0 = 0.0         # monotonic запуска потока — для весточек долгой задачи
        self._save_lock = threading.Lock()

    def __getattr__(self, k):
        try:
            return self.__dict__["data"][k]
        except KeyError as e:
            raise AttributeError(k) from e

    def save(self):
        """задача.json — через временный файл и замену (как история.json): прежде запись шла поверх, и второй менеджер
        (перезапуск программы) читал файл посреди записи — задача пропадала из списка (tasks_test, раз из четырёх)."""
        self.data["updated"] = _now()
        body = json.dumps(self.data, ensure_ascii=False, indent=1)
        with self.__dict__.setdefault("_save_lock", threading.Lock()):
            tmp = self.dir / "задача.json.tmp"
            _wr(tmp, body)
            for i in range(5):                          # Windows: читающий в этот миг держит файл — замена ждёт
                try:
                    os.replace(tmp, self.dir / "задача.json")
                    break
                except PermissionError:
                    if i == 4:
                        _wr(self.dir / "задача.json", body)
                        tmp.unlink(missing_ok=True)
                    else:
                        time.sleep(0.02 * (i + 1))

    def journal(self, text):
        _wr(self.dir / "журнал.md", f"\n**{dt.datetime.now():%H:%M:%S}** · {text}\n", append=True)

    def plan(self):
        return _rd(self.dir / "план.md")

    def notebook(self):
        return _rd(self.dir / "блокнот.md")

    def set_notebook(self, text):
        """Перезаписать блокнот (не больше 30 000 символов; в «Состояние задачи» каждого шага он идёт с ограничением по окну)."""
        text = (text or "").strip()
        if not text.startswith("#"):
            text = "# Блокнот задачи\n\n" + text
        # «Ответы человека» (рецензия 0.83): модель переписывает блокнот целиком (notes, сжатие) — его слова не теряются
        head = "## Ответы человека"
        old = self.notebook()
        if head in old:
            sec = old.split(head, 1)[1].split("\n## ", 1)[0]
            lost = [ln for ln in sec.splitlines() if ln.startswith("- ") and re.sub(r"\s*_\(.*?\)_$", "", ln[2:]).strip()[:120] not in text]
            if lost:
                if head in text:
                    text = text.replace(head + "\n", head + "\n" + "\n".join(lost) + "\n", 1) if head + "\n" in text else text + "\n" + "\n".join(lost)
                else:
                    m = re.search(r"^# .*\n+", text)
                    at = m.end() if m else 0
                    text = text[:at] + head + "\n" + "\n".join(lost) + "\n\n" + text[at:]
        _wr(self.dir / "блокнот.md", text[:30000] + "\n")

    def _json(self, name, default):
        try:
            d = json.loads(_rd(self.dir / name) or "null")
        except (OSError, ValueError):
            return default
        return d if isinstance(d, type(default)) else default

    def todos(self):
        """Список дел (задачи.json, выпуск 4): [{id, text, status, evidence, at}]."""
        return [x for x in self._json("задачи.json", {}).get("items") or [] if isinstance(x, dict) and x.get("text")]

    def criteria(self):
        """Критерии готовности (критерии.json, выпуск 3): {items, results, checked}."""
        return self._json("критерии.json", {})

    def put_json(self, name, d):
        tmp = self.dir / (name + ".tmp")
        _wr(tmp, json.dumps(d, ensure_ascii=False, indent=1))
        os.replace(tmp, self.dir / name)

    def code(self):
        """CodeWork для задачи с проектом, иначе None. Рабочая копия создаётся лениво — при первом code_* (prepare)."""
        return CodeWork(self.data["project"], self.dir / "рабочая копия") if self.data.get("project") else None

    def public(self):
        """Состояние для студии и виджета: data + папка + статус по-русски («вернётся в 14:30»)."""
        d = dict(self.data)
        d["dir"] = str(self.dir)
        d["status_ru"] = STATUS_RU.get(d.get("status"), d.get("status"))
        d["metrics"] = usage_text((d.get("quality") or {}).get("usage"), (d.get("quality") or {}).get("subs"))
        b = d.get("budget") or {}
        if b.get("tokens"):                                # выпуск 7: сколько бюджета потрачено (%)
            d["budget_pct"] = round(100 * task_spent(d) / max(1, int(b["tokens"])))
        if d.get("status") == "sleeping" and d.get("wake_at"):
            try:
                w = dt.datetime.fromisoformat(d["wake_at"])
                d["status_ru"] = "вернётся " + (f"в {w:%H:%M}" if w.date() == dt.date.today() else f"{w:%d.%m} в {w:%H:%M}")
            except ValueError:
                pass
        return d

def tasks_brief(items, today=None):
    """HARNESS 7: «что с задачами?» — одной фразой: что в работе (с ходом плана), что ждёт человека, что готово сегодня,
    что не получилось. items — TaskManager.list(). -> «Коротко: …» или ""."""
    today = today or dt.date.today().isoformat()
    run = [x for x in items if x.get("status") == "running"]
    ask = [x for x in items if x.get("status") == "waiting"]
    zzz = [x for x in items if x.get("status") in ("sleeping", "paused")]
    day = lambda x: str(x.get("updated") or x.get("created") or "")[:10] == today   # noqa: E731
    done = [x for x in items if x.get("status") == "done" and day(x)]
    bad = [x for x in items if x.get("status") in ("failed", "stopped") and day(x)]

    def names(xs, plan=False):
        out = []
        for x in xs[:2]:
            p = x.get("progress") or [0, 0]
            out.append(f"«{str(x.get('title') or '')[:40]}»" + (f" — {p[0]} из {p[1]} по плану" if plan and p[1] else ""))
        return ", ".join(out) + (f" и ещё {len(xs) - 2}" if len(xs) > 2 else "")
    parts = []
    if run:
        parts.append(f"в работе {names(run, True)}")
    if ask:
        parts.append(f"ждёт вашего ответа {names(ask)}")
    if zzz:
        parts.append(f"на паузе или ждёт события {names(zzz)}")
    if done:
        parts.append(f"сегодня готово {len(done)}" + (f" ({names(done)})" if len(done) <= 2 else ""))
    if bad:
        parts.append(f"не получилось {names(bad)}")
    return ("Коротко: " + "; ".join(parts) + ".") if parts else ""


def usage_text(u, subs=None):
    """Метрики задачи для карточки в студии одной строкой: «токены: 140 тыс. на вход, 6 тыс. на выход · из кэша 78%»
    (+ «· из них помощники 30 тыс.» — разведчики и проверяющие, выпуск 6)."""
    if not u or not u.get("req"):
        return ""
    def k(x):
        x = int(x or 0)
        return f"{x / 1e6:.1f} млн" if x >= 1e6 else (f"{round(x / 1000)} тыс." if x >= 1000 else str(x))
    out = f"токены: {k(u.get('in'))} на вход, {k(u.get('out'))} на выход" + (" (оценка)" if u.get("est") == u.get("req") else "")
    if u.get("ck") and u.get("in"):
        out += f" · из кэша {round(100 * u.get('cached', 0) / max(1, u['in']))}%"
    subs = subs or {}
    sub = sum(int(x.get("in") or 0) + int(x.get("out") or 0) for n, x in subs.items() if isinstance(x, dict) and n != "part")
    if sub:                                            # выпуск 6: помощники дорогие — их доля видна (входит в общий счёт)
        out += f" · из них помощники {k(sub)}"
    p = subs.get("part") or {}
    if p.get("n"):                                     # части — свои задачи: их токены сверх счёта задачи
        out += f" · части ({p['n']}) — ещё {k(int(p.get('in') or 0) + int(p.get('out') or 0))}"
    return out



TASK_KINDS = (("code", r"\bкод|программ|скрипт|репозитор|\bбаг|тест[ыа]?\b|python|функци[юя]|рефактор"),
              ("doc", r"презентац|документ|доклад|отч[её]т|таблиц|word|excel|pptx|docx|xlsx|pdf|письм[оа]"),
              ("research", r"исследова|найди|сравни|изучи|обзор|конкурент|рын[оке]|собери|подбер|проанализ"),
              ("wait", r"дожд|проследи|добей|верни|вернуть|статус|ответ[а-я]* от"))
EST_MIN_SAMPLES = 2                                # оценка — по стольким завершённым задачам того же вида, не меньше
EST_ASK_MIN, EST_ASK_TOKENS = 20, 1_500_000        # дольше или дороже — «план, срок, цена — начинаю?» до запуска


def task_kind(goal):
    """Вид задачи по цели (для оценки до старта): code, doc, research, wait или other."""
    g = str(goal or "").lower()
    for k, rx in TASK_KINDS:
        if re.search(rx, g):
            return k
    return "other"


keep_facts = Q.keep_facts                         # выпуск 8, п.2 (живёт в quality: им пользуется и разговор)


def task_spent(d):
    """Сколько токенов потратила задача (вход + выход, с разведчиком и проверяющим) и её части — для бюджета (выпуск 7)."""
    q = d.get("quality") or {}
    u = q.get("usage") or {}
    p = (q.get("subs") or {}).get("part") or {}
    return int(u.get("in") or 0) + int(u.get("out") or 0) + int(p.get("in") or 0) + int(p.get("out") or 0)


def _write_hist(path, msgs):
    """история.json — через временный файл и замену: прерванная запись (падение, выключение) оставляет прежнюю историю
    целой, а читающий одновременно не видит пустой файл (GitHub, task_parts_test: JSONDecodeError на «готовой» задаче)."""
    tmp = path.with_name(path.name + ".tmp")
    _wr(tmp, json.dumps(msgs, ensure_ascii=False))
    os.replace(tmp, path)
