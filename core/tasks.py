"""Долгие задачи: ассистент работает в фоне (поток на задачу) по плану, ведёт журнал и блокнот, может ждать часами
(wait), спрашивать пользователя и продолжать после перезапуска программы. TaskManager — управление и цикл модели,
host — Engine (модель, инструменты, подтверждения, уведомления). Проверки качества — quality.py, код — codework.py.
Задача — папка «Задачи/‹дата название›/» в папке ассистента:
    задача.json — состояние; история.json — разговор с моделью; план.md, журнал.md, блокнот.md (память задачи), итог.md;
    outputs/ — результаты для пользователя, downloads/ — скачанное; _run/, _out/ — скрипты шагов и длинные выводы
    (удаляются по готовности); рабочая копия/ — для задач по коду. Имена служебных файлов перечислены и в quality.SERVICE.
"""

import datetime as dt
import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path

import quality as Q
from codework import CodeError, CodeWork
from llm import LLMError, ctx_full, est_tokens, prompt_tools_mode, stream_chat, stream_events, take_usage, tool_turn_messages

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
TINY_DROP = {"notes", "notify", "wait", "download", "file_glob"}   # …без этих (они — через find_tool)
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
PARTS_MAX = 4                                      # частей за раз у spawn_parts
PARTS_PARALLEL = int(os.environ.get("DEWIAR_TASK_PARALLEL") or 3)   # сколько частей работают одновременно
NOTEBOOK_HEAD = ("# Блокнот задачи\n\n## Что известно\n\n## Что решено\n\n## Чего ждём\n\n## Что дальше\n")


def S(props, req=()):
    """JSON-схема параметров инструмента."""
    return {"type": "object", "properties": props, "required": list(req)}


TASK_TOOLS = {
    "update_plan": ("Записать или обновить план задачи — чек-лист Markdown («- [ ] шаг», выполненные «- [x]»). "
                    "Первым делом составь план, потом отмечай сделанное.", S({"plan": {"type": "string"}}, ["plan"])),
    "log": ("Короткая заметка в журнал задачи: что выяснил, что решил, что дальше.", S({"text": {"type": "string"}}, ["text"])),
    "ask_user": ("Спросить пользователя, если без его решения дальше нельзя. Ответ придёт результатом. "
                 "Спрашивай редко и по делу.", S({"question": {"type": "string"}}, ["question"])),
    "finish": ("Задача выполнена (или дальше невозможно): итог для пользователя в Markdown — что сделано, где "
               "результат, что проверить. После этого работа заканчивается.", S({"summary": {"type": "string"}}, ["summary"])),
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
             "проверишь. Перед wait запиши в блокнот, чего ждёшь. Если пользователь напишет задаче раньше — продолжишь сразу.",
             S({"minutes": {"type": "number"}, "until": {"type": "string"}, "reason": {"type": "string"}}, ["reason"])),
}
# Части задачи: большую работу с независимыми кусками (собрать сведения по пяти компаниям, написать три раздела)
# задача раздаёт помощникам — они работают одновременно, каждый в своей папке; собрать — wait_parts (итоги и файлы
# частей копируются в parts/ папки задачи). Части сами частей не заводят (одна ступень).
PART_TOOLS = {
    "spawn_parts": ("Раздать независимые части большой работы помощникам — они делают их одновременно (до "
                    f"{PARTS_MAX} частей; работают сразу по {PARTS_PARALLEL}). Каждой части — title и goal: что именно сделать "
                    "и какой нужен результат (файл в outputs/ или итог текстом), со всеми нужными сведениями — помощник не "
                    "видит твой разговор. Не дели мелкое и связанное: только куски, которые можно делать порознь. Потом — wait_parts.",
                    S({"parts": {"type": "array", "items": {"type": "object", "properties": {"title": {"type": "string"},
                                                                                            "goal": {"type": "string"}},
                                                           "required": ["goal"]}}}, ["parts"])),
    "wait_parts": ("Дождаться частей, розданных spawn_parts, и получить их итоги; файлы частей появятся в parts/<название>/ "
                   "твоей папки (file_read, run_python). minutes — сколько ждать сейчас (по умолчанию 60).",
                   S({"minutes": {"type": "number"}})),
}
# «Мастерская»: задача сама делает файлы-результаты (страница, дашборд, презентация, таблица, расшифровка) и показывает
# их пользователю (студия → «Задачи» → «Результаты»). Пути — только внутри папки задачи (_path).
# Одноимённые инструменты чата (read_file…) в задаче заменяются этими — см. _specs.
WORK_TOOLS = {
    "write_file": ("Создать файл в папке задачи (HTML-страница, дашборд, презентация, .md, .csv, .json, .py…). path — "
                   "относительный, результаты — в outputs/ (например outputs/app.html). Большой файл пиши частями: "
                   "append=true дописывает в конец. HTML/CSS/JS пиши обычным текстом здесь, а не строкой внутри Python.",
                   S({"path": {"type": "string"}, "content": {"type": "string"}, "append": {"type": "boolean"}}, ["path", "content"])),
    "file_read": ("Прочитать текстовый файл с номерами строк: из папки задачи (путь относительный) или из папок, которые "
                  "человек дал задаче (полный путь). Кусками до ~4000 знаков; start/end — диапазон строк.",
                  S({"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"])),
    "file_edit": ("Правка файла куском: old — точный кусок из файла (лучше с соседней строкой, чтобы был единственным), new — "
                  "чем заменить; replace_all=true — заменить все вхождения. Не нужно переписывать файл целиком. После правки "
                  ".py, .json, .html проверяются: сломанный синтаксис не сохраняется.",
                  S({"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "replace_all": {"type": "boolean"}},
                    ["path", "old", "new"])),
    "file_grep": ("Поиск по содержимому файлов (регулярное выражение, без учёта регистра): в папке задачи или в данной ей "
                  "папке (path — полный путь или подпапка); glob — какие файлы (*.csv, **/*.py). Ответ — файл:строка: текст.",
                  S({"pattern": {"type": "string"}, "path": {"type": "string"}, "glob": {"type": "string"}}, ["pattern"])),
    "file_glob": ("Список файлов по шаблону (**/*.pdf, отчёты/*.md, *) с размерами: в папке задачи или в данной ей папке "
                  "(path). Вместо обхода папок по одной.",
                  S({"pattern": {"type": "string"}, "path": {"type": "string"}})),
    "read_file": ("То же, что file_read (старое имя).",
                  S({"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"])),
    "list_files": ("Файлы в папке задачи (что уже сделано, что скачано).", S({})),
    "run_python": ("Выполнить код Python в папке задачи (текущая папка = папка задачи): расчёты, обработка данных, "
                   "сборка файлов (есть numpy, Pillow, httpx, pypdf; openpyxl, python-docx, python-pptx — если "
                   "установлены, проверь import). Печатай print — увидишь вывод. До 3 минут.",
                   S({"code": {"type": "string"}, "timeout": {"type": "integer"}}, ["code"])),
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
          "show": "показываю результат", "transcribe": "расшифровываю запись", "download": "скачиваю файл",
          "web_search": "ищу в интернете", "read_webpage": "читаю страницу", "update_plan": "обновляю план", "log": "пишу журнал",
          "finish": "подвожу итог", "code_run": "запускаю в проекте", "code_edit": "правлю код", "code_read": "читаю код",
          "remember": "записываю в блокнот", "notes": "обновляю блокнот", "notify": "сообщаю вам", "wait": "жду и вернусь"}
# инструменты чата, которые не нужны внутри задачи
SKIP_IN_TASK = {"start_task", "task_status", "stop_task", "remove_task", "resume_task", "tell_task", "call_persona", "write_diary"}
# Профиль задачи (выпуск 1): постоянный узкий набор — файлы, веб, run_python, план и блокнот, ask/notify/wait/finish, части,
# навыки. Всё остальное (музыка, деньги, напоминания…) — через find_tool: подключается до конца задачи и встаёт В КОНЕЦ
# списка, чтобы начало запроса (подсказка и инструменты) не менялось и сервер брал его из кэша.
PROFILE_TASK = ("update_plan", "ask_user", "finish", "remember", "notes", "notify", "wait")   # log, list_files, read_file — по имени
PROFILE_WORK = ("write_file", "file_read", "file_edit", "file_grep", "file_glob", "run_python", "show", "download")
PROFILE_CHAT = ("web_search", "read_webpage", "use_skill")      # read_skill_file — подключается сам, когда навык его назовёт
RETRY_SAFE = {"web_search", "read_webpage", "download", "file_read", "read_file", "file_grep", "file_glob", "use_skill", "read_skill_file"}
RETRY_SEC = float(os.environ.get("DEWIAR_TASK_TOOL_RETRY_SEC") or 3)    # безопасный инструмент упал на сбое сети — пауза и ещё раз
LIST_MAX = 200                                     # строк в ответе поиска и списка файлов — дальше «сузь: …»
FIND_TOOL = {"find_tool": ("Найти инструмент, которого нет в списке (напоминания, погода, расчёты, почта, расшифровка записи, "
                           "музыка…): query — что нужно сделать, своими словами. Вернёт подходящие с описанием; connect — имя "
                           "инструмента, чтобы подключить его до конца задачи (или просто вызови его).",
                           S({"query": {"type": "string"}, "connect": {"type": "string"}}))}
NO_TRIM = {"ask_user", "wait_parts", "finish", "spawn_parts", "update_plan", "remember", "notes", "notify", "wait", "log", "show"}
ACT_RU.update(find_tool="ищу нужный инструмент", spawn_parts="раздаю части помощникам", wait_parts="жду части", code_process="смотрю фоновый процесс",
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

    def __getattr__(self, k):
        try:
            return self.__dict__["data"][k]
        except KeyError as e:
            raise AttributeError(k) from e

    def save(self):
        self.data["updated"] = _now()
        (self.dir / "задача.json").write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")

    def journal(self, text):
        with open(self.dir / "журнал.md", "a", encoding="utf-8") as f:
            f.write(f"\n**{dt.datetime.now():%H:%M:%S}** · {text}\n")

    def plan(self):
        try:
            return (self.dir / "план.md").read_text(encoding="utf-8")
        except OSError:
            return ""

    def notebook(self):
        try:
            return (self.dir / "блокнот.md").read_text(encoding="utf-8")
        except OSError:
            return ""

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
        (self.dir / "блокнот.md").write_text(text[:30000] + "\n", encoding="utf-8")

    def code(self):
        """CodeWork для задачи с проектом, иначе None. Рабочая копия создаётся лениво — при первом code_* (prepare)."""
        return CodeWork(self.data["project"], self.dir / "рабочая копия") if self.data.get("project") else None

    def public(self):
        """Состояние для студии и виджета: data + папка + статус по-русски («вернётся в 14:30»)."""
        d = dict(self.data)
        d["dir"] = str(self.dir)
        d["status_ru"] = STATUS_RU.get(d.get("status"), d.get("status"))
        d["metrics"] = usage_text((d.get("quality") or {}).get("usage"))
        if d.get("status") == "sleeping" and d.get("wake_at"):
            try:
                w = dt.datetime.fromisoformat(d["wake_at"])
                d["status_ru"] = "вернётся " + (f"в {w:%H:%M}" if w.date() == dt.date.today() else f"{w:%d.%m} в {w:%H:%M}")
            except ValueError:
                pass
        return d

def usage_text(u):
    """Метрики задачи для карточки в студии одной строкой: «токены: 140 тыс. на вход, 6 тыс. на выход · из кэша 78%»."""
    if not u or not u.get("req"):
        return ""
    def k(x):
        x = int(x or 0)
        return f"{x / 1e6:.1f} млн" if x >= 1e6 else (f"{round(x / 1000)} тыс." if x >= 1000 else str(x))
    out = f"токены: {k(u.get('in'))} на вход, {k(u.get('out'))} на выход" + (" (оценка)" if u.get("est") == u.get("req") else "")
    if u.get("ck") and u.get("in"):
        out += f" · из кэша {round(100 * u.get('cached', 0) / max(1, u['in']))}%"
    return out


def _write_hist(path, msgs):
    """история.json — через временный файл и замену: прерванная запись (падение, выключение) оставляет прежнюю историю
    целой, а читающий одновременно не видит пустой файл (GitHub, task_parts_test: JSONDecodeError на «готовой» задаче)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(msgs, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class TaskManager:
    """Все задачи ассистента. Запускает фоновый поток-будильник (_scheduler) и по потоку на каждую работающую задачу."""
    def __init__(self, host):
        self.host = host
        self.tasks = {}
        self._lock = threading.Lock()
        self._started_at = dt.datetime.now()
        self.load()
        threading.Thread(target=self._scheduler, name="tasks-clock", daemon=True).start()

    def _scheduler(self):
        """Поток-будильник (раз в 2 с): будит спящие задачи к сроку или по новому сообщению; через RESUME_SEC после
        запуска программы продолжает задачи, прерванные выключением (auto_resume)."""
        import time as _t
        stop = getattr(self.host, "stopping", None)
        while not (stop is not None and stop.is_set()):
            _t.sleep(2)
            now = dt.datetime.now()
            for t in list(self.tasks.values()):
                try:
                    alive = t.thread is not None and t.thread.is_alive()
                    if t.status == "sleeping" and t.data.get("inbox") and not alive:
                        self.start(t.id)                     # написали, пока поток засыпал, — не ждём срока
                    elif t.status == "sleeping" and t.data.get("wake_at") and dt.datetime.fromisoformat(t.data["wake_at"]) <= now:
                        self.start(t.id, wake=t.data.get("wait_reason") or "время пришло")
                    elif t.data.get("auto_resume") and t.status == "paused" and (now - self._started_at).total_seconds() > RESUME_SEC:
                        t.data.pop("auto_resume", None)
                        t.journal("▶ Компьютер включили — продолжаю, где остановился.")
                        self.start(t.id)
                    elif t.status == "running" and alive:
                        self._watch(t)
                    elif t.status == "waiting":
                        self._ask_remind(t)
                except Exception:  # noqa: BLE001
                    log.exception("будильник задачи %s", t.id)

    def _watch(self, t):
        """Работающая задача (раз в 2 с из _scheduler): завис ли шаг; пора ли весточкой сказать, как идёт."""
        import time as _t
        now = _t.monotonic()
        limit = HANG_TOOL_SEC if t.beat_tool else HANG_SEC
        if t.beat and now - t.beat > limit and not t.data.get("hung_told"):
            what = f"инструмент «{t.beat_tool}»" if t.beat_tool else "модель"
            mins = round((now - t.beat) / 60)
            t.data["hung_told"] = True
            t.journal(f"⏳ Шаг не отвечает {mins} мин ({what}). Жду ещё; если не оживёт — остановите задачу и запустите снова.")
            self._problem(f"Задача: шаг завис — {what} молчит {mins} мин")
            self._push(f"⏳ Задача не отвечает: {t.title}", f"{what.capitalize()} молчит {mins} мин. Если не оживёт — остановите и "
                       "запустите снова.", critical=True)
            self._emit(t)
        if t.data.get("parent") or not t.run_t0:
            return
        last = float(t.data.get("progress_told_at") or 0)
        due = PROGRESS_FIRST if not last else PROGRESS_EVERY
        if now - (last or t.run_t0) < due:
            return
        sig = self._progress_sig(t)
        if last and sig == t.data.get("progress_told_sig"):
            t.data["progress_told_at"] = now                  # сдвига нет — молчим до следующего срока
            return
        t.data.update(progress_told_at=now, progress_told_sig=sig)
        done, total = (t.data.get("progress") or [0, 0])[:2]
        mins = round((now - t.run_t0) / 60)
        where = f"сделано {done} из {total} по плану" if total else f"шагов: {t.data.get('steps', 0)}"
        act = (t.data.get("activity") or "").strip()
        self._push(f"⏱ Работаю над «{t.title}»", f"{mins} мин, {where}." + (f" Сейчас: {act[:120]}" if act else ""))
        t.journal(f"⏱ Весточка: {mins} мин, {where}.")

    def _ask_remind(self, t):
        """Задача спросила и ждёт ответа дольше ASK_REMIND_SEC — напомнить один раз (вопрос мог потеряться)."""
        if t.data.get("ask_reminded") or not t.data.get("asked_at"):
            return
        try:
            asked = dt.datetime.fromisoformat(t.data["asked_at"])
        except ValueError:
            return
        if (dt.datetime.now() - asked).total_seconds() >= ASK_REMIND_SEC:
            t.data["ask_reminded"] = True
            t.save()
            self._push(f"❓ Задача ждёт ответа: {t.title}", (t.data.get("question") or "")[:200] or "Ответьте в карточке задачи.",
                       critical=True)
            t.journal("❓ Напомнил о вопросе — ответа пока нет.")

    def _problem(self, text):
        """Сбой задачи — в пульс «Здоровья» и журнал сбоев для ночного разбора (host.health_problem, health.py)."""
        fn = getattr(self.host, "health_problem", None)
        if fn:
            try:
                fn(text, kind="task")
            except Exception:  # noqa: BLE001
                pass

    @property
    def root(self):
        return self.host.workspace.ensure() / "Задачи"

    def load(self):
        """Прочитать задачи с диска при запуске. Поток задачи не переживает перезапуск: running -> paused + auto_resume."""
        try:
            root = self.root
        except OSError:
            return
        if not root.is_dir():
            return
        for d in sorted(root.iterdir()):
            f = d / "задача.json"
            if f.exists():
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                t = Task(d, data)
                if data.get("status") == "running":
                    t.data.update(status="paused", auto_resume=True)
                    t.save()
                self.tasks[data["id"]] = t                    # sleeping проснётся по сроку, waiting ждёт ответа (см. answer)

    def list(self):
        return sorted((t.public() for t in self.tasks.values()), key=lambda x: x.get("created", ""), reverse=True)

    def get(self, tid):
        """Задача по id или части названия; пустой tid — первая живая, иначе последняя изменённая. Нет — KeyError."""
        if not tid:
            act = [t for t in self.tasks.values() if t.status in ALIVE] or sorted(
                self.tasks.values(), key=lambda t: t.data.get("updated", ""), reverse=True)
            if not act:
                raise KeyError("задач нет")
            return act[0]
        if tid in self.tasks:
            return self.tasks[tid]
        for t in self.tasks.values():                         # по названию
            if tid.lower() in t.title.lower():
                return t
        raise KeyError(f"нет задачи «{tid}»")

    # ---------- управление ----------

    def create(self, title, goal, project="", start=True, persona="", parent="", folders=()):
        """Создать папку задачи и начальные файлы; project — папка проекта для режима «Код»; folders — папки человека, которые
        задача может читать без вопросов (менять — с разрешения; выпуск 2). Нет папки — ValueError."""
        fl = []
        for f in folders or ():
            fp = Path(str(f)).expanduser()
            if not fp.is_dir():
                raise ValueError(f"папки нет: {f}")
            if fp.resolve() == Path(fp.resolve().anchor):     # весь диск — никогда (откуда бы ни пришла просьба)
                raise ValueError(f"«{fp.resolve()}» — это весь диск; задаче можно дать только конкретную папку")
            fl.append(str(fp.resolve()))
        title = _clean(title or goal[:50])
        tid = uuid.uuid4().hex[:8]
        if project:
            p = Path(project).expanduser()
            if not p.is_dir():
                raise ValueError(f"папки проекта нет: {project}")
            project = str(p.resolve())
        # GitHub #12 (24.10): две задачи с одним названием в одну минуту делили папку — вторая затирала задача.json
        # первой, а удаление одной стирало обе. Занята — берём «(2)», «(3)»…; mkdir без exist_ok не отдаст чужую.
        base = f"{dt.datetime.now():%Y-%m-%d %H%M} {title}"
        self.root.mkdir(parents=True, exist_ok=True)
        for n in range(1, 1000):
            d = self.root / (base if n == 1 else f"{base} ({n})")
            try:
                d.mkdir()
                break
            except FileExistsError:
                continue
        else:
            d = self.root / f"{base} {tid}"
            d.mkdir()
        data = {"id": tid, "title": title, "goal": goal.strip(), "project": project or "", "status": "paused",
                "created": _now(), "updated": _now(), "steps": 0, "persona": persona or self.host.persona_name(),
                "question": "", "result": "", "error": "", "activity": ""}
        if parent:
            data["parent"] = parent
        if fl:
            data["folders"] = fl
        (d / "план.md").write_text(f"# {title}\n\n**Цель:** {goal.strip()}\n\n_План появится, когда ассистент начнёт._\n", encoding="utf-8")
        (d / "журнал.md").write_text(f"# Журнал: {title}\n", encoding="utf-8")
        (d / "блокнот.md").write_text(NOTEBOOK_HEAD, encoding="utf-8")
        t = Task(d, data)
        t.save()
        self.tasks[tid] = t
        if start:
            self.start(tid)
        return t

    def start(self, tid, wake=""):
        """Запустить или продолжить задачу в отдельном потоке (уже идёт — ничего не делает).
        wake — причина пробуждения (wait_reason): по ней _run решает, что сказать модели. Без wake (запустил человек
        или пришло сообщение) счёт кругов CYCLES начинается заново."""
        t = self.get(tid)
        if t.thread and t.thread.is_alive():
            return t
        t.cancel.clear()
        if wake:
            t.data["wake_note"] = wake
        else:
            t.data["cycles"] = 0
        t.data.pop("auto_resume", None)
        if t.data.get("finished"):
            # №448, №460 (ПК 0.76): «второй раз прошу — не выполняет». Задачу, остановленную «не выполнено» (и готовую),
            # запускали снова — а метка finished оставалась, и цикл выходил после первого же действия с тем же итогом.
            # Новый запуск — новая попытка: итог и проверки перед ним — заново.
            t.data.update(finished=False, finish_checked=False, force_finish=False, force_why="", verified=False, critic_done=False,
                          refusal_nudged=False, tests_gate=0, gate_rejects=0, unfinished="")
        t.data.update(status="running", error="", wake_at="", sleep_now=False)
        for k in ("hung_told", "progress_told_at", "progress_told_sig"):
            t.data.pop(k, None)
        import time as _t
        t.beat, t.beat_tool, t.run_t0 = _t.monotonic(), "", _t.monotonic()
        t.save()
        t.thread = threading.Thread(target=self._run, args=(t,), name=f"task-{t.id}", daemon=True)
        t.thread.start()
        self._emit(t)
        return t

    def tell(self, tid, text):
        """Сообщение пользователя задаче (новые сведения, просьба, ответ). Ждёт ответа на вопрос — это ответ; иначе
        сообщение кладётся во входящие (inbox), и задача сразу продолжает работу — даже если уже готова."""
        text = (text or "").strip()
        if not text:
            raise ValueError("пустое сообщение")
        t = self.get(tid)
        if t.status == "waiting" and t.thread and t.thread.is_alive():
            return self.answer(t.id, text)
        t.data.setdefault("inbox", []).append({"time": _now(), "text": text})
        t.journal(f"💬 Пользователь: {text}")
        t.save()
        if not (t.thread and t.thread.is_alive()):
            if t.status == "done":
                t.data.update(finished=False, finish_checked=False, force_finish=False, verified=False, critic_done=False, refusal_nudged=False, tests_gate=0,
                              gate_rejects=0, unfinished="")
                t.journal("↺ Новое сообщение после итога — продолжаю работу.")
            self.start(t.id)
        self._emit(t)
        return t

    def stop(self, tid):
        """Остановить: поток выйдет на ближайшей проверке cancel (ожидание ответа тоже прерывается)."""
        t = self.get(tid)
        t.cancel.set()
        t.answer_ev.set()
        for c in self.tasks.values():                     # остановили задачу — и её части
            if c.data.get("parent") == t.id and (c.status in ALIVE or c.status == "paused"):
                self.stop(c.id)
        if t.status in ALIVE or t.status == "paused":
            t.data.update(status="stopped", wake_at="", auto_resume=False)
            t.save()
        self._emit(t)
        return t

    def answer(self, tid, text):
        """Ответ на вопрос задачи (ask_user): будит ждущий поток."""
        t = self.get(tid)
        if t.status != "waiting":
            raise ValueError("задача сейчас ни о чём не спрашивает")
        if not (t.thread and t.thread.is_alive()):                # спросила до перезапуска программы — потока нет,
                                                                  # ответ уходит обычным сообщением и перезапускает задачу
            t.data.update(status="paused", question="")
            q = t.data.get("question_was") or ""
            return self.tell(t.id, (f"Ответ на твой вопрос «{q}»: " if q else "Ответ пользователя: ") + text)
        t.answer = text
        t.answer_ev.set()
        return t

    def waiting(self):
        return next((t for t in self.tasks.values() if t.status == "waiting"), None)

    def delete(self, tid):
        """Остановить и удалить задачу вместе с папкой и рабочей копией (git worktree тоже убирается)."""
        t = self.get(tid)
        self.stop(t.id)
        c = t.code()
        if c:
            c.discard()
        import shutil
        shutil.rmtree(t.dir, ignore_errors=True)
        self.tasks.pop(t.id, None)
        self.host.emit("tasks", tasks=self.list())

    def accept(self, tid):
        """Перенести изменения кода из рабочей копии в проект (CodeWork.accept) -> текст для человека."""
        t = self.get(tid)
        c = t.code()
        if not c:
            raise ValueError("у задачи нет проекта")
        msg = c.accept()
        t.data["code_state"] = "accepted"
        t.journal("✅ Пользователь принял изменения. " + msg)
        t.save()
        self._emit(t)
        return msg

    def discard(self, tid):
        t = self.get(tid)
        c = t.code()
        if c:
            c.discard()
        t.data["code_state"] = "discarded"
        t.journal("↩ Пользователь отклонил изменения — рабочая копия удалена.")
        t.save()
        self._emit(t)
        return "Изменения отклонены."

    def detail(self, tid):
        """Всё для карточки задачи в студии: план, журнал (последние 60 000 символов), итог, блокнот, изменения кода."""
        t = self.get(tid)
        read = lambda n: (t.dir / n).read_text(encoding="utf-8") if (t.dir / n).exists() else ""  # noqa: E731
        d = t.public()
        d.update(plan=read("план.md"), journal=read("журнал.md")[-60000:], summary=read("итог.md"), notebook=read("блокнот.md"))
        c = t.code()
        if c and c.work.exists():
            try:
                d["changes"] = c.changes()
                d["diff"] = c.diff()
            except CodeError as e:
                d["changes"], d["diff"] = [], f"(не получилось: {e})"
        return d

    def _emit(self, t):
        self.host.emit("task", task=t.public())

    def _push(self, title, text, critical=False, file=None):
        """Всплывающее уведомление через host.push (если есть): пользователь мог отойти или свернуть виджет.
        Ошибка показа не должна мешать задаче."""
        push = getattr(self.host, "push", None)
        if push:
            try:
                push(title, text, critical=critical, **({"file": file} if file else {}))
            except Exception as e:  # noqa: BLE001
                log.info("Уведомление не показано: %s", e)

    # ---------- работа ----------

    def _russian(self, text):
        """Итог — по-русски: если в тексте больше 60% латиницы, просим ту же модель перевести (не вышло — как есть).
        Некоторые модели после долгой работы с англоязычными страницами и кодом пишут итог по-английски."""
        letters = re.findall(r"[A-Za-zА-Яа-яЁё]", text[:3000])
        if len(letters) < 40 or sum(c.isascii() for c in letters) / len(letters) < 0.6:
            return text
        try:
            from llm import stream_chat
            prof = self.host.llm_profile()
            out = "".join(stream_chat(prof, "Переведи текст на русский язык. Сохрани Markdown, пути к файлам, команды и "
                                            "имена как есть. Ответь только переводом.", [{"role": "user", "content": text[:6000]}]))
            return out.strip() or text
        except Exception as e:  # noqa: BLE001
            log.info("Итог не перевёлся: %s", e)
            return text

    def _system(self, t):
        """Подсказка модели — только НЕИЗМЕННОЕ за время задачи (выпуск 1, docs/HARNESS.md): задача, правила, папка, проект,
        память, уроки, навыки. Время, план, блокнот и критерии — в «Состоянии задачи» в конце каждого запроса (_state):
        так начало запроса байт в байт одно и то же на каждом шаге, и сервер модели (Claude, vLLM, llama.cpp) берёт его из
        кэша. Лёгкий режим (окно ≤ LIGHT_WIN) — короче, без уроков, частей и списка навыков."""
        code = t.code()
        light = bool(t.data.get("light"))
        s = (f"Ты — {t.persona}, голосовой ассистент. Сейчас ты выполняешь задачу В ФОНЕ: пользователь занят своими "
             f"делами. Ты доводишь задачу до конца, как надёжный личный помощник: не бросаешь на полпути, не забываешь, "
             f"зачем всё делается, и держишь человека в курсе.\n\nЗАДАЧА: {t.title}\nЦЕЛЬ: {t.goal}\n\n"
             "В конце каждого запроса — «Состояние задачи»: текущие время, план, критерии готовности и блокнот. Сверяйся с ним "
             "на каждом шаге — он всегда свежий.\n\n"
             "Как работать:\n"
             "1. Сначала разберись и составь план (update_plan — чек-лист). В начале плана — строка «**Готово, когда:** …» "
             "(по чему понятно, что цель достигнута). Отмечай сделанное.\n"
             "2. Всё важное сразу записывай в блокнот (remember): номера, коды, суммы, ответы людей и компаний, "
             "договорённости, сроки. Ранние шаги со временем уходят из памяти — блокнот остаётся.\n"
             "3. Если результат зависит от внешнего (ответ на письмо, обращение, смена статуса, нужное время) — не "
             "заканчивай: запиши в блокнот, чего ждёшь, и вызови wait (через сколько минут или до какого времени вернуться "
             "и что проверить). Потом проверь и продолжай. Так задача может идти часы и дни.\n"
             "4. Сообщай пользователю важное по ходу (notify): что выяснил, что изменилось, что дальше — коротко, по делу.\n"
             "5. Не выдумывай результаты — проверяй инструментами. Без решения пользователя дальше нельзя — ask_user.\n"
             "6. finish — только когда цель достигнута (или точно недостижима): итог в Markdown — что сделано, где результат, "
             "что проверить. Пиши по-русски.\n"
             "7. Нужного инструмента нет в списке (напоминание, погода, расчёт, почта, расшифровка…) — find_tool.\n\n"
             f"Твоя папка: {self.host.workspace.root} (заметки — save_note; файлы, которые прислал пользователь, — "
             f"в «Входящие» там же). Папка этой задачи: {t.dir}.\n\n")
        if t.data.get("folders"):
            s += ("ПАПКИ ЧЕЛОВЕКА (он дал их задаче): " + "; ".join(t.data["folders"]) + ". Читай и ищи в них без вопросов — "
                  "file_read, file_grep, file_glob с полным путём. Менять там — только с разрешения (спрошу сама); лучше — "
                  "копия в outputs/.\n\n")
        if light:
            s += ("МАСТЕРСКАЯ. Результат-файл делай сам: write_file в outputs/, расчёты и сборка — run_python. Пиши файл частями "
                  "(append=true), по ~80 строк. Длинные выводы инструментов лежат в _out/ — читай их file_read кусками. Перед "
                  "finish покажи главный файл (show).")
        else:
            s += ("МАСТЕРСКАЯ. Если результат — файл (страница, дашборд, презентация, калькулятор, игра, таблица, документ, "
                  "расшифровка), делай его сам: write_file в outputs/ (HTML — один самодостаточный файл, CSS и JS внутри), "
                  "run_python — расчёты и сборка файлов, download — скачать. Сначала "
                  "загляни в подходящий навык (use_skill: slides, html-app, html-viz, data-report, media-transcribe, research…). "
                  "Длина одного твоего ответа ограничена: файл длиннее ~120 строк пиши за несколько шагов — write_file с первой частью, "
                  "потом write_file с append=true. Длинный вывод инструмента целиком лежит в _out/ (в ответе — начало и путь): "
                  "читай его file_read кусками, а не запускай заново. Старые результаты со временем убираются из памяти — "
                  "важное записывай в блокнот. Правь файлы куском (file_edit), а не переписывай целиком; ищи по файлам — file_grep и file_glob. Перед finish проверь файл (file_read) и покажи его пользователю (show). Ответ в "
                  "finish — коротко: что получилось и как пользоваться; содержимое файла не пересказывай.")
        if t.data.get("parent"):
            s += ("\n\nТы — помощник: делаешь одну часть большой задачи, параллельно с другими. Не спрашивай пользователя без "
                  "крайней нужды и не уведомляй его — твой итог (finish) прочитает основная задача: пиши в нём суть результата.")
        elif not light:
            s += ("\n\nЧАСТИ. Большая работа из независимых кусков (сведения по нескольким компаниям или городам, несколько "
                  "разделов отчёта, несколько файлов) идёт быстрее, если раздать куски помощникам: spawn_parts — они работают "
                  "одновременно, wait_parts — собрать итоги и файлы (в parts/). Мелкое и связанное делай сама.")
        if code:
            s += (f"\n\nПРОЕКТ: {t.project}. Ты работаешь в его рабочей копии (изменения пользователь проверит и "
                  "примет сам) — смело правь и запускай тесты. Пути — относительно корня проекта (calc.py, tests/…); "
                  "code_run уже выполняется в рабочей копии — не делай cd в папку проекта. Сначала осмотрись: code_list, code_search, code_read "
                  "(README, конфиги, точки входа). Правь точечно (code_edit), следуй стилю проекта. После правок "
                  "запусти тесты/сборку (code_run), если они есть. Перед finish посмотри code_diff.")
            if t.data.get("code_map") is None:          # карта проекта — один раз на задачу (codework.overview)
                try:
                    from codework import overview
                    t.data["code_map"] = overview(code.work if code.work.exists() else code.project)
                except Exception:  # noqa: BLE001
                    log.debug("карта проекта", exc_info=True)
                    t.data["code_map"] = ""
            if t.data.get("code_map"):
                cm = t.data["code_map"] if not light else t.data["code_map"][:3000]
                s += ("\n\nКАРТА ПРОЕКТА (на начало работы; подробности — code_read/code_search):\n" + cm +
                      "\nЦикл работы: найди место → прочитай → поправь (code_edit) → запусти тесты → по ошибкам поправь снова. "
                      "Не меняй тесты, если об этом не просили. Перед finish тесты должны проходить — я проверю. "
                      "Свои тесты пиши по КАЖДОМУ требованию цели и на краевые случаи: цифры, латиница и кириллица, "
                      "пустой ввод, повторы, начало и конец строки — не только на примеры из задачи. Правка всё сломала — "
                      "code_undo. Сервер или другую долгую программу запускай code_run с background=true, проверяй "
                      "(запрос к нему, code_process output) и останавливай.")
        mem = self.host.memory()
        if mem:
            s += "\n\nЧто ты знаешь о пользователе:\n" + (mem if not light else mem[:1500])
        if light:
            return s
        s += Q.lessons_block(self.lessons_path())          # выводы из прошлых задач (quality.reflect)
        s += Q.talk_lessons_block(self.host.workspace.root / Q.TALK_LESSONS_FILE)   # и из поправок в разговоре
        sp = getattr(self.host, "skills_prompt", None)
        return s + (sp() if sp else "")

    def _state(self, t):
        """«Состояние задачи» — последним сообщением каждого запроса (в историю не пишется): время, шаг, критерии готовности,
        план и блокнот. План и цель в конце контекста — модель не уходит от цели на длинной дистанции (Manus todo.md,
        Cline Focus Chain). Объём плана и блокнота — по окну модели."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        now = dt.datetime.now()
        wd = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'][now.weekday()]
        plan = t.plan()
        nb = t.notebook() or "(пока пусто)"
        nb_max = max(1500, min(30000, int(win * 3 * 0.12)))
        plan_max = max(1200, min(12000, int(win * 3 * 0.08)))
        crit = re.search(r"Готово,? когда:?\**:?\s*(.+)", plan)
        out = [f"[Состояние задачи — обновляется на каждом шаге; это не сообщение пользователя]",
               f"Сейчас: {now:%d.%m.%Y %H:%M} ({wd}). Шаг {int(t.data.get('steps') or 0) + 1}."]
        if crit:
            out.append("Критерии готовности: " + crit.group(1).strip()[:600])
        out.append("ТЕКУЩИЙ ПЛАН:\n" + (plan if len(plan) <= plan_max else plan[:plan_max] + "\n…(план длиннее — целиком: file_read план.md)"))
        out.append("БЛОКНОТ ЗАДАЧИ (твоя память):\n" + (nb if len(nb) <= nb_max else nb[:nb_max] + "\n…(блокнот длиннее — целиком: "
                                                                                                "file_read блокнот.md; сократи его — notes)"))
        on = t.data.get("tools_on") or []
        if on:
            out.append("Подключено через find_tool: " + ", ".join(on))
        return "\n\n".join(out)

    # ---------- качество (quality.py): проверка кодом, самопроверка, уроки ----------
    def _opt(self, key):
        """Настройка tasks.<key> (self_check, learn — см. settings.py); None — не задана, считается включённой."""
        try:
            return self.host.s.get("tasks", key)
        except Exception:  # noqa: BLE001
            return None

    def lessons_path(self):
        """Файл уроков в папке ассистента — его видно и можно править в студии."""
        return self.host.workspace.root / Q.LESSONS_FILE

    @staticmethod
    def _q(t):
        """Счётчики качества задачи в data["quality"]: хранятся в задача.json, поэтому переживают передышки и перезапуск.
        Идут в след задачи (_trace) для уроков."""
        return t.data.setdefault("quality", {"tools": {}, "errors": [], "loop_warns": 0, "refusal": 0, "verify_fail": 0, "critic": 0})

    def _ask(self, system, messages):
        """Короткий служебный запрос к модели (самопроверка, уроки): низкая температура, ответ до 900 токенов."""
        prof = self.host.llm_profile()
        if not prof:
            return ""
        return "".join(stream_chat(dict(prof, max_tokens=900, temperature=0.1), system, messages))

    def _web_used(self, t):
        """Пользовалась ли задача интернетом — без этого отказ «нет доступа» считается ложным."""
        used = self._q(t)["tools"]
        return any(used.get(k) for k in ("web_search", "read_webpage", "read_page", "download"))

    def _web_available(self, t):
        return any(x["name"] == "web_search" for x in self._specs(t))

    def _lab_files(self, t):
        """Файлы «Лаборатории» (lab_write, lab_run), созданные или изменённые во время задачи: она пишет туда, а не в
        папку задачи (№368: «list_files и самопроверка должны видеть ту же папку, куда пишет lab_write»)."""
        lab = self.host.workspace.root / "Лаборатория"
        try:
            since = dt.datetime.fromisoformat(str(t.data.get("created") or "")).timestamp() - 5
        except ValueError:
            since = 0
        out = []
        if lab.is_dir():
            for p in sorted(lab.rglob("*")):
                try:
                    if p.is_file() and p.stat().st_mtime >= since:
                        out.append(p)
                except OSError:
                    continue
        return out[:200]

    # №516 (04.11): апостроф в имени («…You Don't.md») обрывал имя — проверка искала «t.md» и трижды отклоняла верный итог
    PROMISE_RX = re.compile(r"([\wА-Яа-яЁё][\wА-Яа-яЁё .()\-'’]{0,80}\.(?:html?|xlsx|xls|csv|pdf|docx|pptx|png|jpe?g|webp|gif|svg|mp3|wav|ogg|mp4|webm|zip|md|py|js))\b", re.I)

    def _promised_missing(self, t, summary):
        """Файлы, названные в итоге, которых нет ни в папке задачи, ни в «Лаборатории», ни в папке ассистента.
        Названный, но не созданный результат — не результат (№368)."""
        names, text = [], summary or ""
        for m in self.PROMISE_RX.finditer(text):
            before = text[max(0, m.start() - 120):m.start()].split()
            if before and ("://" in before[-1] or before[-1].startswith("www.")) and not text[m.start() - 1:m.start()].isspace():
                continue                                   # часть ссылки на сайт — не наш файл
            n = Path(m.group(1).strip().split("/")[-1].split("\\")[-1]).name.strip(" .«»\"'")
            words = n.split()
            cands = [" ".join(words[-k:]) for k in range(1, min(len(words), 12) + 1)]   # «в файле продажи.csv» → «продажи.csv», …
            # рецензия 0.82: «сохранён в файл 'report.md'» — кавычки по краям не часть имени (апостроф внутри — часть: «Don't.md»)
            cands = list(dict.fromkeys(c.strip(" '’\"«»“”„`") for c in cands))
            cands = [c for c in cands if c]
            if cands and cands not in names:
                names.append(cands)
        if not names:
            return []
        have = {p.name.lower() for p in t.dir.rglob("*") if p.is_file()} | {p.name.lower() for p in self._lab_files(t)}
        code = t.code()
        if code is not None:                               # задача по коду: файлы проекта (рабочая копия и сам проект)
            for root in (getattr(code, "work", None), getattr(code, "project", None)):
                try:
                    if root and Path(root).is_dir():
                        for i, p in enumerate(Path(root).rglob("*")):
                            if i > 20000:
                                break
                            have.add(p.name.lower())
                except OSError:
                    pass
        miss = []
        for cands in names[:20]:
            if any(c.lower() in have for c in cands):
                continue
            try:
                import glob as _glob
                if any(any(True for _ in self.host.workspace.root.rglob(_glob.escape(c))) for c in cands):
                    continue
            except (OSError, ValueError):
                pass
            miss.append(cands[0])
        return miss

    GATE_MAX = 3                     # итог отклонён столько раз — задача честно останавливается «не выполнено»

    def _finish_gates(self, t, summary):
        """Проверки перед итогом: ложный отказ -> машинная проверка файлов (и что они показаны), названные в итоге файлы
        существуют -> самопроверка моделью. №368 (28.10): проверки идут при КАЖДОМ finish — отклонённый итог не
        «запоминается проверенным»; спор не бесконечен: после GATE_MAX отказов задача останавливается «не выполнено»
        (t.data["unfinished"]), а не «готово». force_finish (завершаем сами из-за повтора) — тоже «не выполнено».
        -> текст для модели (итог не принят) или None (принимаем — или останавливаем, если стоит unfinished)."""
        q = self._q(t)
        if t.data.get("force_finish"):
            t.data["unfinished"] = t.data.get("unfinished") or self._stop_why(t)
            return None
        note = self._gates(t, summary, q)
        if note is None:
            return None
        t.data["gate_rejects"] = int(t.data.get("gate_rejects") or 0) + 1
        if t.data["gate_rejects"] > self.GATE_MAX:
            why = re.sub(r"^САМОПРОВЕРКА отклонила итог:\s*|^МАШИННАЯ ПРОВЕРКА ФАЙЛОВ НАШЛА БРАК:\s*", "", note).split("\nИсправь")[0].split("\nЭто ОБЪЕКТИВНЫЕ")[0]
            t.data["unfinished"] = f"проверка итога не согласилась {self.GATE_MAX} раза — {why.strip()[:240]}"
            t.journal("⛔ Итог отклонён много раз — останавливаю задачу как «не выполнено».")
            return None
        return note

    DID_RU = {"web_search": "поиск в интернете", "read_page": "чтение страниц", "read_webpage": "чтение страниц",
              "remember": "записи в блокнот", "notes": "записи в блокнот", "write_file": "запись файлов", "run_python": "расчёты",
              "read_file": "чтение файлов", "file_read": "чтение файлов", "file_edit": "правки файлов", "file_grep": "поиск по файлам", "download": "скачивание", "show": "показ результата", "calc": "расчёты",
              "code_edit": "правки кода", "code_run": "запуски в проекте"}

    def _stop_why(self, t):
        """Понятная причина остановки «не выполнено» (force_finish) и что задача успела: человеку — не «повторяла одно и
        то же или перестала действовать» на всё подряд (№448, №460), а что именно случилось и сколько сделано."""
        why = {"loop": "задача несколько раз повторила одно и то же действие с тем же результатом",
               "idle": "модель перестала выполнять действия — несколько раз подряд отвечала только текстом",
               "badcall": "модель пишет действия в виде, который Dewiar не смог разобрать"}.get(
            t.data.get("force_why") or "", "задача повторяла одно и то же или перестала действовать")
        did = {}
        for k, n in (self._q(t).get("tools") or {}).items():
            if k in self.DID_RU:
                did[self.DID_RU[k]] = did.get(self.DID_RU[k], 0) + int(n or 0)
        done, total = (t.data.get("progress") or [0, 0])[:2]
        parts = [f"{k} ×{n}" for k, n in sorted(did.items(), key=lambda x: -x[1])[:4]]
        if total:
            parts.append(f"план — {done} из {total}")
        return why + (f" (успела: {', '.join(parts)})" if parts else "") + " — цель не подтверждена"

    def _gates(self, t, summary, q):
        if not t.data.get("refusal_nudged") and Q.looks_like_refusal(summary) and self._web_available(t) and not self._web_used(t):
            t.data["refusal_nudged"] = True
            q["refusal"] += 1
            t.journal("✋ Проверка перед итогом: отказ «нет доступа», а поиском не пользовался — напоминаю про web_search.")
            return Q.REFUSAL_NUDGE
        shown = [o.get("path") for o in t.data.get("outputs") or []]
        miss = self._promised_missing(t, summary)
        if miss:
            q["verify_fail"] += 1
            t.journal("🔎 В итоге названы файлы, которых нет: " + ", ".join(miss[:8]))
            return ("В итоге назван результат, которого нет на диске: " + ", ".join(miss[:8]) + ". Названный файл — не "
                    "доказательство. Создай его (write_file или run_python в папке задачи, outputs/), проверь (file_read) и "
                    "покажи (show) — или честно напиши в итоге, что сделать не удалось, и снова вызови finish.")
        if True:
            probs = Q.verify_outputs(t.dir, shown)
            if probs:
                q["verify_fail"] += 1
                t.journal("🔎 Машинная проверка файлов нашла брак:\n" + "\n".join("- " + x for x in probs[:8]))
                return Q.summarize(probs)
            outs = [p for p in (t.dir / "outputs").rglob("*") if p.is_file()] if (t.dir / "outputs").is_dir() else []
            if outs and not shown:
                t.journal("✋ Проверка перед итогом: файлы готовы, но пользователю не показаны.")
                return ("Файлы в outputs/ готовы, но ты не показал их пользователю — он их не увидит. Вызови show для главных "
                        "файлов (страница, таблица, документ…), затем снова finish.")
        code = t.code()
        if code is not None and int(t.data.get("tests_gate") or 0) < 2 and self.host.code_auto_run():
            from codework import test_command
            try:
                code.prepare()                            # finish без единого code_* — копии ещё нет
                cmd = test_command(code.work)
            except (CodeError, OSError) as e:
                log.info("проверка тестов перед итогом: %s", e)
                cmd = None
            if cmd:                                       # итог по коду — только когда тесты проекта проходят (два раза спорим)
                out = code.run(cmd, 600)
                if not out.startswith("Код завершения 0"):
                    t.data["tests_gate"] = int(t.data.get("tests_gate") or 0) + 1
                    q["verify_fail"] += 1
                    t.journal(f"🧪 Проверка перед итогом: тесты не проходят ({cmd}).")
                    return (f"Тесты проекта не проходят — итог не принят. Команда: {cmd}\n{out[-2500:]}\n\nИсправь код "
                            "(тесты не меняй, если тебя об этом не просили) и снова запусти тесты. Если падение не связано "
                            "с задачей и было до тебя — объясни это в итоге и снова вызови finish.")
                t.data["tests_gate"] = 9                  # прошли — больше не проверяем
                t.journal(f"🧪 Проверка перед итогом: тесты проходят ({cmd}).")
        if self._opt("self_check") is not False:
            files = []
            for p in sorted(t.dir.rglob("*")):
                rel = p.relative_to(t.dir)
                if p.is_file() and rel.parts[0] not in Q.SERVICE and not rel.parts[0].startswith("рабочая копия"):
                    files.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
            files += [f"Лаборатория/{p.relative_to(self.host.workspace.root / 'Лаборатория').as_posix()} — {p.stat().st_size} байт"
                      for p in self._lab_files(t)]
            facts = (f"Шагов: {t.data.get('steps', 0)}. Инструменты: " +
                     ", ".join(f"{k}×{v}" for k, v in sorted(q["tools"].items(), key=lambda x: -x[1])[:12]) +
                     (f". Показано пользователю: {', '.join(shown)}" if shown else "") +
                     (". Это задача по коду: изменения пользователь примет сам (рабочая копия)." if t.data.get("project") else ""))
            diff = ""
            if code is not None and code.work.exists():
                try:
                    diff = code.diff(limit=max(3000, min(20000, int(int(t.data.get("win") or WIN_DEFAULT) * 3 * 0.3))))
                except Exception:  # noqa: BLE001
                    log.debug("diff для самопроверки", exc_info=True)
            problems = Q.critic(self._ask, f"{t.title}\n{t.goal}", summary, files, facts, diff=diff)
            if problems:
                q["critic"] += 1
                t.journal(f"🧐 Самопроверка вернула итог на доработку: {problems}")
                return Q.critic_note(problems)
        return None

    def _clean(self, t):
        """По готовности удалить служебное: скрипты шагов (_run) и длинные выводы (_out). Остаётся то, что нужно человеку."""
        import shutil
        for name in ("_run", "_out"):
            d = t.dir / name
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    def _trace(self, t, reason):
        """Сохранить след законченной задачи (вне папки ассистента, в STATE_DIR) и, если пора, запустить уроки.
        reason: "final" | "failed" | "loop_detected"."""
        q = self._q(t)
        try:
            from settings import STATE_DIR
        except Exception:  # noqa: BLE001
            return
        Q.save_trace(STATE_DIR / "task_traces", {
            "id": t.id, "goal": f"{t.title}: {t.goal}"[:400], "ok": reason == "final", "reason": reason,
            "steps": t.data.get("steps", 0), "tools": q["tools"], "errors": q["errors"][-10:], "loop_warns": q["loop_warns"],
            "refusal": q["refusal"], "verify_fail": q["verify_fail"], "critic": q["critic"], "usage": q.get("usage") or {},
            "time": _now()})
        self._maybe_reflect(STATE_DIR / "task_traces")

    def _maybe_reflect(self, traces):
        """Не чаще REFLECT_EVERY (время прошлого раза — в файле .last) вывести уроки в отдельном потоке."""
        if self._opt("learn") is False:
            return
        last = traces / ".last"
        try:
            ago = time.time() - float(last.read_text())
        except (OSError, ValueError):
            ago = 1e12
        if ago < float(os.environ.get("DEWIAR_REFLECT_EVERY") or Q.REFLECT_EVERY):
            return

        def run():
            try:
                last.write_text(str(time.time()))            # сразу: даже при ошибке модели не повторять каждую задачу
                n = Q.reflect(self._ask, traces, self.lessons_path())
                if n:
                    self.host.announce(f"Я сделал выводы из прошлых задач: новых правил — {n}. Они в «Память/Уроки задач».")
            except Exception as e:  # noqa: BLE001
                log.info("Уроки задач не получились: %s", e)
        threading.Thread(target=run, name="task-reflect", daemon=True).start()

    def _catalog(self, t):
        """Все инструменты, которые задача МОЖЕТ получить: имя -> описание. Инструменты чата (кроме SKIP_IN_TASK) +
        свои (TASK_TOOLS, WORK_TOOLS — одноимённые инструменты чата заменяются своими) + код (только у задачи с проектом)
        + части (не у части) + find_tool."""
        cat = {}
        for x in self.host.toolbox.specs():
            if x["name"] not in SKIP_IN_TASK:
                cat.setdefault(x["name"], x)
        own = dict(TASK_TOOLS, **WORK_TOOLS)
        if t.data.get("project"):
            own.update(CODE_TOOLS)
        if not t.data.get("parent"):                       # часть сама частей не раздаёт
            own.update(PART_TOOLS)
        own.update(FIND_TOOL)
        for n, (d, prm) in own.items():
            cat[n] = {"name": n, "description": d, "parameters": prm}
        return cat

    def _specs(self, t):
        """Инструменты задачи (выпуск 1): постоянный профиль ≈20 штук в неизменном порядке + подключённые через find_tool
        (t.data["tools_on"]) — в конце, по порядку подключения: список только растёт с конца, начало запроса не меняется.
        Лёгкий режим (маленькое окно) — без частей и навыков."""
        cat = self._catalog(t)
        light = bool(t.data.get("light"))
        names = list(PROFILE_TASK) + list(PROFILE_WORK)
        names += [n for n in PROFILE_CHAT if not (light and n in ("use_skill", "read_skill_file"))]
        if t.data.get("project"):
            names += list(CODE_TOOLS)
        if not light:
            names += list(PART_TOOLS)
        names += list(FIND_TOOL)
        tiny = int(t.data.get("win") or WIN_DEFAULT) < TINY_WIN
        if tiny:                                           # окно меньше 6 тыс.: самое нужное, остальное — find_tool
            names = [n for n in names if n not in TINY_DROP]
        names += [n for n in t.data.get("tools_on") or [] if n not in names]
        out = [cat[n] for n in dict.fromkeys(names) if n in cat]
        if tiny:                                           # …и описания — до первой фразы
            out = [dict(x, description=self._first(x.get("description") or "")) for x in out]
        return out

    @staticmethod
    def _first(d):
        m = re.match(r"(.+?[.!?])(?:\s|$)", d, re.S)
        return (m.group(1) if m else d)[:160]

    @staticmethod
    def _stems(text):
        """Слова для поиска инструмента: нижний регистр, первые 5 букв (грубая основа: «напоминание» ~ «напомни»)."""
        return {w[:5] for w in re.findall(r"[a-zа-яё0-9]{3,}", (text or "").lower().replace("_", " "))}

    def _connect(self, t, name):
        on = list(t.data.get("tools_on") or [])
        if name not in on:
            on.append(name)
            t.data["tools_on"] = on
            t.journal(f"🧰 Подключил инструмент: {name}")

    def _find_tool(self, t, args):
        """find_tool: подходящие инструменты по описанию; connect — подключить до конца задачи."""
        cat = self._catalog(t)
        active = {x["name"] for x in self._specs(t)}
        want = str(args.get("connect") or args.get("name") or "").strip()
        q = str(args.get("query") or "").strip()
        if not want and q in cat:
            want = q
        if want:
            if want in active:
                return f"Инструмент {want} уже доступен — вызывай его."
            if want in cat:
                self._connect(t, want)
                return f"Подключил {want}: {cat[want]['description'][:400]}\nТеперь вызывай его как обычно."
            return self._unknown(t, want)
        qs = self._stems(q)
        scored = []
        for n, x in cat.items():
            if n in active:
                continue
            words = self._stems(n + " " + x.get("description", ""))
            sc = len(qs & words) + (3 if n.lower() in q.lower() else 0)
            if sc:
                scored.append((-sc, n))
        scored.sort()
        if not scored:
            return ("Ничего подходящего не нашлось. Сейчас доступны: " + ", ".join(sorted(active)) + ". Опиши, что нужно "
                    "сделать, другими словами — или обойдись этими.")
        top = [n for _, n in scored[:5]]
        return ("Подходящие инструменты (подключить — find_tool с connect=<имя>, или просто вызови его):\n" +
                "\n".join(f"- {n} — {cat[n]['description'][:220]}" for n in top))

    def _unknown(self, t, name):
        """Модель позвала инструмент, которого нет: понятная ошибка с тем, что есть (а не «выключен пользователем», №…:
        подсказки называли read_page, а на компьютере — read_webpage)."""
        import difflib
        active = [x["name"] for x in self._specs(t)]
        near = difflib.get_close_matches(name, list(self._catalog(t)), n=2, cutoff=0.6)
        return (f"Ошибка: нет такого инструмента «{name}»." + (f" Похоже, нужен: {', '.join(near)}." if near else "")
                + " Есть: " + ", ".join(active) + ". Другие — через find_tool(query).")

    def _coerce(self, t, name, args):
        """Привести аргументы к схеме инструмента (слабые модели шлют список вместо строки и т. п.), см. tools.coerce_args."""
        from tools import coerce_args
        spec = self._catalog(t).get(name)
        return coerce_args((spec or {}).get("parameters"), args)

    def _tool(self, t, name, args):
        """Выполнить вызов модели -> текст результата. Любая ошибка — ответом модели («Ошибка: …»), а не падением задачи.
        _truncated ставит llm.py, когда ответ модели оборвался по лимиту длины и аргументы удалось спасти лишь частично."""
        trunc = isinstance(args, dict) and bool(args.pop("_truncated", False))
        try:
            ca = self._coerce(t, name, args)
            r = self._tool_raw(t, name, ca)
            if name in RETRY_SAFE and isinstance(r, str) and r.startswith(("Ошибка", "Поиск не удался", "Страница не открылась")) \
                    and self._transient(r) and "Как исправить" not in r and not t.cancel.is_set():
                # выпуск 2: безопасный инструмент (поиск, чтение, скачивание) упал на сбое сети — пауза и ещё раз, сам
                t.journal(f"↻ {name}: сбой сети ({self._short(r, 120)}) — повторяю через {RETRY_SEC:g} с.")
                t.cancel.wait(RETRY_SEC)
                if not t.cancel.is_set():
                    r = self._tool_raw(t, name, ca)
            if trunc:
                self._q(t)["errors"].append({"tool": name, "text": "ответ оборвался по лимиту длины"})
                if name == "write_file" and isinstance(r, str) and not r.startswith("Ошибка"):
                    tail = str(args.get("content") or "")[-160:]
                    r += ("\n\nВНИМАНИЕ: твой ответ ОБОРВАЛСЯ по лимиту длины — записана только первая часть файла. Он кончается "
                          f"так: «…{tail}». Допиши продолжение (write_file с append=true) кусками не больше ~120 строк, НЕ переписывая "
                          "файл с нуля.")
                else:
                    r = f"{r}\n\n(Твой ответ оборвался по лимиту длины — аргументы могли дойти не целиком: проверь результат. Делай шаги меньше.)"
            return self._offload(t, name, r)
        except Exception as e:  # noqa: BLE001
            log.exception("задача %s: инструмент %s", t.id, name)
            if not isinstance(e, (ValueError, OSError, TimeoutError)):   # не «плохие аргументы», а ошибка в программе
                self._problem(f"Задача, инструмент {name}: {e.__class__.__name__}: {str(e)[:160]}")
            return (f"Ошибка инструмента {name}: {e}. Как исправить: проверь аргументы (строки — строками, пути — как в "
                    "file_glob) и попробуй ещё раз или иначе.")

    def _out_max(self, t):
        """Сколько знаков вывода инструмента держать в истории: OUT_MAX, при маленьком окне — меньше (~10% окна)."""
        return max(1500, min(OUT_MAX, int(int(t.data.get("win") or WIN_DEFAULT) * 3 * 0.1)))

    def _offload(self, t, name, r):
        """Вывод любого инструмента длиннее _out_max — целиком в _out/<инструмент>-<шаг>.txt, в историю — начало, конец и
        путь (Manus, Anthropic: файловая система как память). read_file и ответы человека не трогаем: read_file сам режет
        куски по размеру, а ответ человека — главное."""
        lim = self._out_max(t)
        if not isinstance(r, str) or len(r) <= lim or name in ("read_file", "file_read", "ask_user", "finish", "wait_parts", "use_skill", "read_skill_file"):
            return r
        n = int(t.data.get("steps") or 0)
        f = t.dir / "_out" / f"{name}-{n}.txt"
        k = 2
        while f.exists():
            f = t.dir / "_out" / f"{name}-{n}-{k}.txt"
            k += 1
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(r, encoding="utf-8")
        except OSError:
            return r[:lim] + "\n…(вывод обрезан)"
        rel = f.relative_to(t.dir).as_posix()
        head, tail = int(lim * 0.65), int(lim * 0.25)
        return (r[:head] + f"\n…[вывод {len(r)} знаков — целиком в файле {rel}: читай его file_read кусками (start/end), "
                "не запускай заново]…\n" + r[-tail:])

    def _tool_raw(self, t, name, args):
        """Собственно выполнение. Сначала свои инструменты задачи, потом инструменты ассистента — с теми же
        включателями, защитой и подтверждениями, что в чате (toolbox.policy/guard, host.confirm).
        Может надолго блокировать поток: ask_user ждёт ответа, confirm — решения человека."""
        if name == "update_plan":
            plan = (args.get("plan") or "").strip()
            if not plan.startswith("#"):
                plan = f"# {t.title}\n\n**Цель:** {t.goal}\n\n{plan}"
            (t.dir / "план.md").write_text(plan + "\n", encoding="utf-8")
            done, total = plan.count("[x]") + plan.count("[X]"), len(re.findall(r"\[[ xX]\]", plan))
            t.data["progress"] = [done, total]
            return f"План сохранён ({done} из {total} пунктов выполнено)."
        if name == "log":
            t.journal("📝 " + (args.get("text") or ""))
            return "Записано."
        if name == "spawn_parts":
            return self._spawn_parts(t, args.get("parts") or [])
        if name == "wait_parts":
            return self._wait_parts(t, float(args.get("minutes") or 60))
        if name == "ask_user":
            q = (args.get("question") or "").strip()
            t.data.update(status="waiting", question=q, question_was=q, asked_at=_now(), ask_reminded=False)
            t.save()
            self._emit(t)
            t.journal(f"❓ Вопрос пользователю: {q}")
            self._push(f"❓ Задача «{t.title}» спрашивает", q[:200], critical=True)
            t.answer_ev.clear()
            t.answer = None
            self.host.ask_user(t, q)
            while not t.answer_ev.wait(1):                # раз в секунду — проверить, не остановили ли задачу
                if t.cancel.is_set():
                    break
            t.data.update(status="running", question="")
            t.save()
            self._emit(t)
            if t.cancel.is_set():
                return "Задачу остановили."
            t.journal(f"💬 Ответ: {t.answer}")
            self._note_human(t, f"На вопрос «{q[:200]}»: {t.answer}")
            return f"Ответ пользователя: {t.answer}"
        if name == "remember":
            fact = re.sub(r"\s+", " ", (args.get("fact") or "").strip())
            if not fact:
                return "Пустой факт — нечего записать."
            nb = t.notebook() or NOTEBOOK_HEAD
            line = f"- {fact} _({dt.datetime.now():%d.%m %H:%M})_"
            if "## Что известно" in nb:
                nb = nb.replace("## Что известно\n", "## Что известно\n" + line + "\n", 1)
            else:
                nb = nb.rstrip() + "\n" + line + "\n"
            t.set_notebook(nb)
            t.journal(f"📌 В блокнот: {fact}")
            return "Записано в блокнот."
        if name == "notes":
            t.set_notebook(args.get("text") or "")
            t.journal("📒 Блокнот переписан.")
            return "Блокнот обновлён."
        if name == "notify":
            text = (args.get("text") or "").strip()
            if not text:
                return "Пустое сообщение."
            import time as _t
            last = t.data.get("notified_at") or 0
            if not args.get("important") and _t.time() - last < 60:     # не чаще раза в минуту, кроме срочного
                t.journal(f"🔕 (не отправил — прошло меньше минуты) {text}")
                return "Только что уже сообщал — это записал в журнал. Сообщи позже, когда будет что-то новое."
            t.data["notified_at"] = _t.time()
            t.journal(f"📣 Сообщил: {text}")
            self._push(f"📌 {t.title}", text, critical=bool(args.get("important")))
            return "Сообщение отправлено пользователю."
        if name == "wait":
            reason = (args.get("reason") or "").strip() or "проверить, что изменилось"
            when = None
            if args.get("until"):
                try:
                    when = dt.datetime.fromisoformat(str(args["until"]).strip().replace(" ", "T"))
                except ValueError:
                    return "Время не понял — until в виде YYYY-MM-DDTHH:MM (местное время) или minutes."
            elif args.get("minutes") is not None:
                try:
                    when = dt.datetime.now() + dt.timedelta(minutes=max(0.05, float(args["minutes"])))
                except (TypeError, ValueError):
                    return "minutes — число минут."
            if when is None:
                return "Скажи, когда вернуться: minutes или until."
            if when < dt.datetime.now():
                return "Это время уже прошло — проверь сейчас."
            when = min(when, dt.datetime.now() + dt.timedelta(days=30))   # не дальше месяца
            # sleep_now — сигнал циклу _run выйти после этого шага; будит _scheduler
            t.data.update(status="sleeping", wake_at=when.isoformat(timespec="seconds"), wait_reason=reason, sleep_now=True)
            t.save()
            t.journal(f"⏳ Жду до {when:%d.%m %H:%M}: {reason}")
            return f"Хорошо, вернусь к задаче {when:%d.%m в %H:%M} (или раньше, если пользователь напишет)."
        if name == "finish":
            # невыполненные пункты плана — один раз напоминаем, дальше — проверки качества (_finish_gates)
            plan = t.plan()
            todo = [m.strip() for m in re.findall(r"^\s*[-*]\s*\[ \]\s*(.+)$", plan, re.M)]
            if todo and not t.data.get("finish_checked"):
                t.data["finish_checked"] = True
                t.journal("✋ Проверка перед итогом: в плане есть невыполненные пункты.")
                return ("Прежде чем закончить, проверь цель. В плане не отмечено: " + "; ".join(todo[:8]) + ". Если это "
                        "сделано — отметь в плане (update_plan) и снова вызови finish. Если ждёшь чего-то внешнего — wait. "
                        "Если сделать нельзя — так и напиши в итоге и снова вызови finish.")
            note = self._finish_gates(t, (args.get("summary") or "").strip())
            if note:
                return note
            summary = self._russian((args.get("summary") or "").strip()) or "Готово."
            if t.data.get("unfinished"):                 # №368: честное «не выполнено» — остановка, а не успех
                summary = f"**Не выполнено:** {t.data['unfinished']}.\n\nЧто успела:\n\n{summary}"
            (t.dir / "итог.md").write_text(f"# Итог: {t.title}\n\n{summary}\n", encoding="utf-8")
            t.data.update(result=summary, finished=True)
            return "Задача завершена." if not t.data.get("unfinished") else "Задача остановлена: не выполнено."
        if name in WORK_TOOLS:
            try:
                return self._work(t, name, args)
            except Exception as e:  # noqa: BLE001
                return f"Ошибка: {e}"
        if name in CODE_TOOLS:
            c = t.code()
            if c is None:
                return "У задачи нет проекта."
            try:
                c.prepare()
                if name == "code_list":
                    return c.list(args.get("pattern", ""))
                if name == "code_read":
                    return c.read(args.get("path", ""), args.get("start") or 1, args.get("end"))
                if name == "code_search":
                    return c.search(args.get("pattern", ""), args.get("glob", ""))
                if name == "code_edit":
                    return c.edit(args.get("path", ""), args.get("old", ""), args.get("new", ""))
                if name == "code_write":
                    return c.write(args.get("path", ""), args.get("content", ""))
                if name == "code_delete":
                    return c.delete(args.get("path", ""))
                if name == "code_diff":
                    return c.diff(limit=30000) or "Изменений пока нет."
                if name == "code_undo":
                    return c.undo(args.get("steps") or 1)
                if name == "code_process":
                    return c.process(args.get("action") or "status", args.get("id") or "")
                if name == "code_run":
                    # безопасность: та же проверка команд (guard.check_command), что в чате; опасное — только с согласия человека,
                    # остальное — без вопроса, если в настройках разрешён автозапуск кода
                    cmd = args.get("command", "")
                    import guard
                    v = guard.check_command(cmd, cwd=str(c.work))
                    if v["level"] == "block":
                        t.journal(f"🛡 Защита не дала: {cmd} — {v['reason']}")
                        return f"Защита Dewiar запретила эту команду: {v['reason']}. Найди другой путь."
                    warn = guard.describe_warn(v) + " " if v["level"] == "warn" else ""
                    if warn or not self.host.code_auto_run():
                        okd, why = self._permit(t, "code_run", f"Задача «{t.title}»: {warn}выполнить в проекте «{cmd}»?")
                        if not okd:
                            return why
                    if args.get("background"):
                        return c.start_bg(cmd)
                    return c.run(cmd, args.get("timeout") or 180)
            except CodeError as e:
                return f"Ошибка: {e}"
            except OSError as e:                     # №222: «Access is denied» на сетевой папке — ошибка шага, а не сбой программы
                return f"Ошибка: нет доступа к файлу {getattr(e, 'filename', '') or ''} ({e.strerror or e}). Обойди этот файл или выбери другую папку."
        if name == "find_tool":
            return self._find_tool(t, args)
        # обычные инструменты ассистента
        on, need = self.host.toolbox.policy(name)
        if name not in self._catalog(t):
            try:
                from tools import TOOLS as _ALL
            except Exception:  # noqa: BLE001
                _ALL = {}
            if not on and name in _ALL and name not in SKIP_IN_TASK:
                return f"Инструмент {name} выключен пользователем (студия → «Руки» → «Умения»). Обойдись без него."
            return self._unknown(t, name)
        if not on:
            return f"Инструмент {name} выключен пользователем."
        if name not in {x["name"] for x in self._specs(t)}:
            self._connect(t, name)                     # позвала знакомый инструмент не из профиля — подключаем до конца задачи
        blocked, force, warn_q = self.host.toolbox.guard(name, args)
        if blocked:
            t.journal(f"🛡 Защита не дала: {name} — {blocked}")
            return f"Защита Dewiar запретила это: {blocked}. Так делать нельзя — найди другой путь или спроси пользователя."
        if need or force:
            okd, why = self._permit(t, name, f"Задача «{t.title}»: {warn_q or self.host.toolbox.describe(name, args)}")
            if not okd:
                return why
        try:
            return self.host.toolbox.run(name, args)
        except Exception as e:  # noqa: BLE001
            return f"Ошибка: {e}"

    # ---------- мастерская: файлы задачи ----------

    @staticmethod
    def _path(t, rel):
        """Безопасность: путь от модели -> абсолютный внутри папки задачи; «..», абсолютные пути и ссылки наружу — ValueError."""
        rel = str(rel or "").strip()
        root = t.dir.resolve()
        try:                                     # модель дала полный путь внутри папки задачи — берём его часть от папки
            ab = Path(rel).expanduser().resolve()
            if Path(rel).expanduser().is_absolute() and (root in ab.parents or ab == root):
                rel = str(ab.relative_to(root))
        except (OSError, ValueError):
            pass
        rel = rel.lstrip("/\\")
        p = (t.dir / rel).resolve()
        if not rel or (t.dir.resolve() not in p.parents and p != t.dir.resolve()):
            raise ValueError("путь вне папки задачи. Как исправить: пиши относительный путь в папке задачи, например "
                             "outputs/app.html")
        return p

    @staticmethod
    def _folders(t):
        """Папки, которые человек дал задаче (start_task folders): [Path] — только существующие."""
        out = []
        for f in t.data.get("folders") or []:
            try:
                p = Path(f).expanduser().resolve()
            except OSError:
                continue
            if p.is_dir():
                out.append(p)
        return out

    def _area(self, t, rel, write=False):
        """Путь от модели в области задачи (выпуск 2): папка задачи (относительный путь) или папки, которые человек дал
        задаче (полный путь). -> (путь, папка человека или None). Вне области — ValueError «что случилось — как исправить».
        Запись в папку человека — только с разрешением (раз на папку за задачу), иначе — в копию в outputs/."""
        raw = str(rel or "").strip()
        try:
            ab = Path(raw).expanduser()
            if ab.is_absolute():
                ab = ab.resolve()
                for f in self._folders(t):
                    if ab == f or f in ab.parents:
                        if write:
                            key = f"write:{f}"
                            if key not in (t.data.get("write_ok") or []):
                                okd, why = self._permit(t, key, f"Задача «{t.title}» хочет изменить файлы в вашей папке {f}. Разрешить?")
                                if not okd:
                                    raise ValueError(f"человек не разрешил менять файлы в {f}. Как исправить: сделай копию "
                                                     "в outputs/ (file_read → write_file) и правь её. " + why)
                                t.data["write_ok"] = (t.data.get("write_ok") or []) + [key]
                                t.journal(f"✍ Разрешено менять файлы в {f}")
                        return ab, f
        except OSError:
            pass
        try:
            if Path(raw).expanduser().is_absolute():
                ab = Path(raw).expanduser().resolve()
                if not (ab == t.dir.resolve() or t.dir.resolve() in ab.parents):
                    raise ValueError("вне")
            return self._path(t, raw), None
        except (ValueError, OSError):
            fs = self._folders(t)
            raise ValueError(f"путь «{raw}» вне папки задачи" + (" и данных ей папок (" + ", ".join(map(str, fs)) + ")" if fs else "")
                             + ". Как исправить: пиши относительный путь в папке задачи (outputs/…)"
                             + (", а в папках человека — полный путь" if fs else ", а нужную папку попроси человека дать задаче")) from None

    def _shown(self, t, p, f):
        """Путь для ответа модели: в папке задачи — относительный, в папке человека — полный."""
        return p.relative_to(t.dir.resolve()).as_posix() if f is None else str(p)

    READ_MAX = 20 << 20                               # file_read и file_edit — текстовые файлы не больше 20 МБ

    @classmethod
    def _load_text(cls, p):
        """Текстовый файл -> (текст с переводами строк \\n, кодировка, был ли CRLF). Кодировка: UTF-8 (с BOM — utf-8-sig),
        иначе cp1251 (рецензия 0.83: file_edit портил cp1251 и CRLF). Не текст или слишком большой — ValueError с советом."""
        size = p.stat().st_size
        if size > cls.READ_MAX:
            raise ValueError(f"{p.name} — {size // (1 << 20)} МБ, это слишком много для чтения целиком. Как исправить: "
                             "ищи в нём file_grep или разбери кодом (run_python) по частям")
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            raise ValueError(f"{p.name} — не текстовый файл ({size} байт). Как исправить: разбери его кодом (run_python: "
                             "pypdf, openpyxl, Pillow…)")
        enc = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            enc = "cp1251"
            text = data.decode(enc, errors="replace")
        crlf = b"\r\n" in data
        return (text.replace("\r\n", "\n") if crlf else text), enc, crlf

    @staticmethod
    def _save_text(p, text, enc, crlf):
        """Записать так же, как было: та же кодировка и те же переводы строк. Символ не кодируется — ValueError."""
        if crlf:
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        try:
            data = text.encode(enc)
        except UnicodeEncodeError as e:
            raise ValueError(f"в файле кодировка {enc}, а в правке есть символ «{text[e.start:e.end]}», которого в ней нет. "
                             "Как исправить: замени его (например, кавычки «» на \"\") или сделай копию файла в UTF-8 (write_file)") from None
        p.write_bytes(data)

    def _read_lines(self, t, p, args, name="file_read"):
        """Кусок файла с номерами строк, не больше _out_max знаков: «показаны строки a–b из N; дальше — start=…»."""
        try:
            text = self._load_text(p)[0]
        except ValueError as e:
            return f"Ошибка: {e}."
        lines = text.splitlines()
        if not lines:
            return "(файл пуст)"
        a, b = max(1, int(args.get("start") or 1)), int(args.get("end") or 0)
        if a > len(lines):
            return f"Ошибка: в файле {len(lines)} строк, а start={a}. Как исправить: start от 1 до {len(lines)}."
        b = min(len(lines), b or a + 399)
        lim, out, size = self._out_max(t), [], 0     # кусок — не больше ~_out_max знаков: история не раздувается
        for i in range(a, b + 1):
            ln = f"{i}: {lines[i - 1]}"
            if out and size + len(ln) > lim:
                b = i - 1
                break
            out.append(ln if len(ln) <= lim else ln[:lim] + f"…(строка обрезана, в ней {len(lines[i - 1])} знаков)")
            size += len(ln) + 1
        return "\n".join(out) + (f"\n… показаны строки {a}–{b} из {len(lines)}; дальше — {name} с start={b + 1}" if b < len(lines) else "")

    def _limit(self, t, items, what, how):
        """Ограничитель ответов: не больше LIST_MAX строк и ~_out_max знаков, дальше — «показано 1–200 из 5000, сузь: …»
        (Anthropic «Writing tools»: ответ с пределом и подсказкой, как сузить)."""
        lim, size, k = self._out_max(t) - 200, 0, 0
        for x in items[:LIST_MAX]:
            if k and size + len(x) + 1 > lim:
                break
            size += len(x) + 1
            k += 1
        if k >= len(items):
            return "\n".join(items)
        return "\n".join(items[:k]) + f"\n… показано 1–{k} из {len(items)} {what}. Сузь: {how}."

    SKIP_SCAN = {"история.json", "история.json.tmp", "задача.json"}

    def _scan_root(self, t, args):
        """Где искать (file_grep, file_glob): path — подпапка задачи или папка человека (полный путь); пусто — папка задачи."""
        raw = str(args.get("path") or "").strip()
        if not raw or raw in (".", "./"):
            return t.dir.resolve(), None
        p, f = self._area(t, raw)
        if not p.exists():
            raise ValueError(f"нет папки «{raw}». Как исправить: посмотри file_glob без path, что есть в папке задачи")
        return p, f

    WALK_MAX = 50000                                  # файлов за один обход (file_grep, file_glob) — дальше не идём

    @staticmethod
    def _glob_rx(pattern):
        """Шаблон file_glob -> регулярное выражение по относительному пути: ** — любые папки, * и ? — внутри имени.
        Безопасность (рецензия 0.83): «..» и полный путь в шаблоне — отказ: шаблон не выводит из области задачи."""
        pat = str(pattern or "**/*").replace("\\", "/").strip() or "**/*"
        parts = pat.split("/")
        if pat.startswith("/") or re.match(r"^[A-Za-z]:", pat) or ".." in parts or pat.startswith("~"):
            raise ValueError("в шаблоне «..» или полный путь. Как исправить: шаблон — внутри папки (например **/*.csv), "
                             "а папку человека передай в path полным путём")
        out, i = "", 0
        while i < len(pat):
            if pat.startswith("**/", i):
                out, i = out + "(?:.*/)?", i + 3
            elif pat.startswith("**", i):
                out, i = out + ".*", i + 2
            elif pat[i] == "*":
                out, i = out + "[^/]*", i + 1
            elif pat[i] == "?":
                out, i = out + "[^/]", i + 1
            else:
                out, i = out + re.escape(pat[i]), i + 1
        return re.compile(out + r"\Z", re.I if os.name == "nt" else 0)

    def _walk(self, t, root, pattern="**/*"):
        """Файлы под root по шаблону. Через os.walk с пределом WALK_MAX, без перехода по ссылкам на папки; файл-ссылка,
        ведущая наружу root, пропускается (рецензия 0.83: symlink и «..» выводили из области задачи). Сортировка — потом."""
        rx = self._glob_rx(pattern)
        root_r = Path(root).resolve()
        task_r = t.dir.resolve()
        out, seen = [], 0
        for dp, dns, fns in os.walk(root_r, followlinks=False):
            d = Path(dp)
            if d == task_r:
                dns[:] = [x for x in dns if not x.startswith(("рабочая копия", "_run"))]
            for fn in fns:
                seen += 1
                if seen > self.WALK_MAX:
                    break
                p = d / fn
                if fn in self.SKIP_SCAN and d == task_r:
                    continue
                rel = p.relative_to(root_r).as_posix()
                if not rx.match(rel):
                    continue
                try:
                    real = p.resolve()
                except OSError:
                    continue
                if not (real == root_r or root_r in real.parents) or not real.is_file():
                    continue
                out.append(p)
            if seen > self.WALK_MAX:
                break
        return sorted(out)

    def _file_tools(self, t, name, args):
        """file_read, file_edit, file_grep, file_glob (выпуск 2 «Руки задачи»)."""
        if name in ("file_read", "read_file"):
            p, f = self._area(t, args.get("path"))
            if not p.is_file():
                if f is None:
                    # №516: путь из find_notes («Заметки/….md») — это папка ассистента, а не папка задачи: читаем оттуда
                    try:
                        from tools import t_read_file
                        w = self.host.workspace.safe(str(args.get("path") or ""))
                        if w.is_file():
                            return t_read_file({"path": w.relative_to(self.host.workspace.root.resolve()).as_posix()},
                                               {"workspace": self.host.workspace})
                    except Exception:  # noqa: BLE001
                        pass
                return (f"Такого файла нет: «{args.get('path')}». Как исправить: посмотри file_glob (или list_files), "
                        "как он называется.")
            return self._read_lines(t, p, args, name)
        if name == "file_edit":
            import textedit as TE
            p, f = self._area(t, args.get("path"), write=True)
            if not p.is_file():
                return f"Ошибка: файла «{args.get('path')}» нет. Как исправить: новый файл создай write_file, а путь проверь file_glob."
            try:
                text, enc, crlf = self._load_text(p)
            except ValueError as e:
                return f"Ошибка: {e}."
            old_, new_ = (str(args.get(k) or "").replace("\r\n", "\n") for k in ("old", "new"))
            try:
                out, line, note = TE.apply_edit(text, old_, new_, bool(args.get("replace_all")))
            except TE.EditError as e:
                return f"Ошибка: {e}"
            bad = TE.syntax_error(out, p.suffix)
            if bad and not TE.syntax_error(text, p.suffix):
                return (f"Ошибка: после правки {p.name} не разбирается ({bad}) — файл НЕ изменён. Как исправить: поправь new "
                        "(скобки, кавычки, закрывающие теги) и повтори file_edit.")
            try:
                self._save_text(p, out, enc, crlf)
            except ValueError as e:
                return f"Ошибка: {e}. Файл НЕ изменён."
            shown = self._shown(t, p, f)
            t.journal(f"✏ Правка {shown}, строка {line}{note}")
            n_new = str(args.get("new") or "").count("\n")
            return f"Изменён {shown}, строки {line}–{line + n_new}{note}." + (f" ⚠ Файл и до правки не разбирался: {bad}." if bad else "")
        if name == "file_glob":
            root, f = self._scan_root(t, args)
            pat = str(args.get("pattern") or "**/*").strip() or "**/*"
            files = self._walk(t, root, pat if "/" in pat or "**" in pat or ".." in pat else "**/" + pat)
            base = t.dir.resolve() if f is None else root
            items = [f"{(p.relative_to(base).as_posix() if f is None else str(p))} — {p.stat().st_size} байт" for p in files]
            if not items:
                return f"Ничего не нашлось по «{pat}»" + (f" в {root}" if f else "") + ". Как исправить: шаблон шире (**/*) или другая папка (path)."
            return self._limit(t, items, "файлов", "шаблон точнее (отчёты/*.md, **/*2024*.csv) или path — подпапка")
        if name == "file_grep":
            pat = str(args.get("pattern") or "")
            try:
                rx = re.compile(pat, re.I)
            except re.error as e:
                rx = re.compile(re.escape(pat), re.I)
                if not pat:
                    return f"Ошибка: пустой pattern ({e}). Как исправить: что искать — слово или регулярное выражение."
            root, f = self._scan_root(t, args)
            g = str(args.get("glob") or "").strip()
            files = [root] if root.is_file() else self._walk(t, root, (g if "/" in g or "**" in g or ".." in g else "**/" + g) if g else "**/*")
            hits, nfiles = [], 0
            base = t.dir.resolve() if f is None else None
            for p in files:
                try:
                    if p.stat().st_size > 5 << 20:
                        continue
                    data = p.read_bytes()
                except OSError:
                    continue
                if b"\0" in data[:4096]:
                    continue                               # не текст
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = data.decode("cp1251", errors="replace")
                got = False
                for i, ln in enumerate(text.splitlines(), 1):
                    if rx.search(ln):
                        where = p.relative_to(base).as_posix() if base is not None and base in p.parents else str(p)
                        hits.append(f"{where}:{i}: {ln.strip()[:200]}")
                        got = True
                nfiles += got
            if not hits:
                return f"Совпадений с «{pat}» нет (просмотрено файлов: {len(files)}). Как исправить: другое слово или шаблон шире, glob пустой."
            return self._limit(t, hits, f"совпадений в {nfiles} файлах", "pattern точнее, glob (*.csv) или path — подпапка")
        return "неизвестный инструмент"

    def _work(self, t, name, args):
        """Инструменты мастерской (WORK_TOOLS)."""
        if name in ("file_read", "read_file", "file_edit", "file_grep", "file_glob"):
            return self._file_tools(t, name, args)
        if name == "write_file":
            p, f = self._area(t, args.get("path"), write=True)
            if f is not None:                              # папка человека (с его разрешения): пишем туда как есть
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "a" if args.get("append") else "w", encoding="utf-8") as fh:
                    fh.write(args.get("content") or "")
                t.journal(f"📄 записал {p} ({p.stat().st_size} байт)")
                return f"Файл {p} — {p.stat().st_size} байт."
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a" if args.get("append") else "w", encoding="utf-8") as f:
                f.write(args.get("content") or "")
            size = p.stat().st_size
            hint = ""
            if p.suffix.lower() in (".html", ".htm"):
                txt = p.read_text(encoding="utf-8", errors="replace")
                if "</html>" not in txt.lower():
                    hint = " (нет </html> — если файл пишется частями, допиши; иначе проверь)"
            t.journal(f"📄 {'дописал' if args.get('append') else 'записал'} {p.relative_to(t.dir).as_posix()} ({size} байт)")
            warn = Q.quick_check(p, p.relative_to(t.dir).as_posix())
            if warn:
                t.journal(warn)
            return f"Файл {p.relative_to(t.dir).as_posix()} — {size} байт{hint}." + (f"\n{warn} Почини до запуска." if warn else "")
        if name == "list_files":
            out = []
            for p in sorted(t.dir.rglob("*")):
                rel = p.relative_to(t.dir)
                if p.is_file() and not rel.parts[0].startswith(("рабочая копия", "_run")) and p.name not in ("задача.json", "история.json", "история.json.tmp", "журнал.md"):
                    out.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
            lab = self._lab_files(t)
            if lab:                                    # №368: что задача положила в «Лабораторию» (lab_write, lab_run)
                root = self.host.workspace.root / "Лаборатория"
                out += ["", "В «Лаборатории» (lab_write/lab_run) за время задачи:"] + \
                       [f"Лаборатория/{p.relative_to(root).as_posix()} — {p.stat().st_size} байт" for p in lab]
            return "\n".join(out[:300]) or "Папка пуста."
        if name == "run_python":
            if not self.host.code_auto_run() and not t.data.get("py_ok"):    # разрешение спрашиваем раз на задачу
                okd, why = self._permit(t, "run_python", f"Задача «{t.title}» хочет запускать свои скрипты Python в папке задачи. Разрешить для этой задачи?")
                if not okd:
                    return why + " Без запуска кода: write_file."
                t.data["py_ok"] = True
                t.save()
            return self._run_python(t, args.get("code") or "", int(args.get("timeout") or 180))
        if name == "show":
            p = self._path(t, args.get("path"))
            if not p.is_file():
                return "Такого файла нет — сначала создай его."
            rel = p.relative_to(t.dir).as_posix()
            outs = [o for o in t.data.get("outputs") or [] if o.get("path") != rel]
            outs.append({"path": rel, "title": (args.get("title") or p.stem)[:120], "time": dt.datetime.now().isoformat(timespec="seconds")})
            t.data["outputs"] = outs[-30:]
            t.save()
            self._emit(t)
            t.journal(f"👁 Показал пользователю: {rel}")
            return f"Показано пользователю: {rel} (студия → «Задачи» → «Результаты»)."
        if name == "transcribe":
            src = str(args.get("path") or "").strip()
            # источник можно взять и вне папки задачи: из папки ассистента или по полному пути
            cands = [t.dir / src, self.host.workspace.root / src, Path(os.path.expanduser(src))]
            p = next((c for c in cands if c.is_file()), None)
            if p is None:
                return "Файл не найден — укажи путь в папке задачи (например downloads/лекция.mp4) или полный путь."
            t.data["activity"] = "расшифровываю запись…"
            self._emit(t)
            segs = self.host.transcribe_file(p, cancel=t.cancel)
            out = t.dir / "outputs"
            out.mkdir(parents=True, exist_ok=True)

            def ts(x, srt=False):                       # секунды -> [мм:сс] / [ч:мм:сс] или 00:00:00,000 для .srt
                h, m, s_ = int(x // 3600), int(x % 3600 // 60), x % 60
                return f"{h:02d}:{m:02d}:{int(s_):02d},{int((s_ % 1) * 1000):03d}" if srt else (f"{h}:{m:02d}:{int(s_):02d}" if h else f"{m:02d}:{int(s_):02d}")
            txt = "\n".join(f"[{ts(a)}] {x}" for a, b, x in segs)
            (out / f"{p.stem}.txt").write_text(txt + "\n", encoding="utf-8")
            (out / f"{p.stem}.srt").write_text("\n".join(f"{i}\n{ts(a, True)} --> {ts(b, True)}\n{x}\n" for i, (a, b, x) in enumerate(segs, 1)), encoding="utf-8")
            t.journal(f"🎙 Расшифровал {p.name}: {len(segs)} фрагментов")
            return (f"Готово: outputs/{p.stem}.txt и outputs/{p.stem}.srt ({len(segs)} фрагментов). Начало:\n" + txt[:6000]
                    + ("\n…(дальше — в файле, читай file_read)" if len(txt) > 6000 else ""))
        if name == "download":
            import httpx
            url = str(args.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                return "Нужна ссылка http(s)://"
            nm = re.sub(r'[\\/:*?"<>|]', "_", (args.get("name") or url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "file"))[:120]
            dst = t.dir / "downloads" / nm
            dst.parent.mkdir(parents=True, exist_ok=True)
            got = 0
            with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(20, read=120),
                              headers={"User-Agent": "Mozilla/5.0 (Dewiar)"}) as r:
                r.raise_for_status()
                with open(dst, "wb") as f:
                    for b_ in r.iter_bytes(1 << 16):
                        got += len(b_)
                        if got > 500 << 20:
                            raise ValueError("файл больше 500 МБ — не качаю")
                        if t.cancel.is_set():
                            raise ValueError("задачу остановили")
                        f.write(b_)
            t.journal(f"⬇ Скачал {nm} ({got // 1024} КБ)")
            return f"Скачано: downloads/{nm} ({got // 1024} КБ)."
        return "неизвестный инструмент"

    @staticmethod
    def _py_env(t, ff):
        """Окружение скриптов задачи. Безопасность: sitecustomize из guard.site_dir разрешает удалять файлы только
        в папке задачи и во временной папке (DEWIAR_ALLOW_DEL). UTF-8 для вывода, Agg — matplotlib без окон,
        FFMPEG — путь к ffmpeg программы."""
        import tempfile
        import guard
        pp = guard.site_dir(t.dir / "_run")
        allow = os.pathsep.join([str(t.dir.resolve()), os.path.realpath(tempfile.gettempdir())])
        old = os.environ.get("PYTHONPATH", "")
        return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", MPLBACKEND="Agg", FFMPEG=ff,
                    PYTHONPATH=pp + (os.pathsep + old if old else ""), DEWIAR_ALLOW_DEL=allow)

    def _run_python(self, t, code, timeout):
        """Сохранить код шагом _run/шагN.py и выполнить в папке задачи (до 600 с) -> код выхода, вывод и подсказка по ошибке."""
        import subprocess
        import sys
        n = len(list(t.dir.glob("_run/*.py"))) + 1
        f = t.dir / "_run" / f"шаг{n}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(code, encoding="utf-8")
        (t.dir / "outputs").mkdir(exist_ok=True)
        py = sys.executable
        if os.name == "nt" and py.lower().endswith("pythonw.exe"):     # pythonw не даёт stdout — скрипту нужен python.exe
            py = py[:-len("pythonw.exe")] + "python.exe"
        try:
            from eyes import ffmpeg_path
            ff = ffmpeg_path() or ""
        except Exception:  # noqa: BLE001
            ff = ""
        try:
            r = subprocess.run([py, str(f)], cwd=str(t.dir), capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=max(5, min(600, timeout)), stdin=subprocess.DEVNULL,
                               env=self._py_env(t, ff),
                               creationflags=0x08000000 if os.name == "nt" else 0)
        except subprocess.TimeoutExpired:
            return f"Остановлено по времени ({timeout} с). Делай работу частями: сохраняй прогресс в файл."
        out = (r.stdout + ("\n[stderr]\n" + r.stderr if r.stderr.strip() else "")).strip()
        t.journal(f"🐍 Python (шаг {n}): код {r.returncode}")
        hint = Q.error_hint(out) if r.returncode else ""
        if r.returncode:
            q = self._q(t)
            q["errors"] = (q["errors"] + [{"tool": "run_python", "text": (r.stderr.strip() or out)[-240:]}])[-10:]
        # длинный вывод целиком — в _out/, модели — начало и конец (_offload в _tool, общий для всех инструментов)
        return f"Код выхода {r.returncode}.\n{out or '(вывода нет)'}" + (f"\n\n{hint}" if hint else "")

    @staticmethod
    def _short(v, n=300):
        """Значение одной строкой для журнала, не длиннее n."""
        v = v["text"] if isinstance(v, dict) else str(v)
        v = v.replace("\n", " ⏎ ")
        return v if len(v) <= n else v[:n] + "…"

    @staticmethod
    def _add_user(msgs, text):
        """Сообщение «от пользователя» в разговор задачи (два подряд — склеиваем: не все модели это принимают)."""
        if msgs and msgs[-1].get("role") == "user" and isinstance(msgs[-1].get("content"), str):
            msgs[-1] = dict(msgs[-1], content=msgs[-1]["content"] + "\n\n" + text)
        else:
            msgs.append({"role": "user", "content": text})

    @staticmethod
    def _note_human(t, text):
        """Ответ человека (ask_user) и его сообщение задаче — сразу в блокнот, раздел «Ответы человека»: при сжатии памяти
        они не теряются (рецензия 0.83: «Казань» пропадала после сжатия)."""
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        if not text:
            return
        nb = t.notebook() or NOTEBOOK_HEAD
        line = f"- {text[:1500]} _({dt.datetime.now():%d.%m %H:%M})_"
        head = "## Ответы человека\n"
        if head in nb:
            nb = nb.replace(head, head + line + "\n", 1)
        else:
            m = re.search(r"^# .*\n+", nb)
            at = m.end() if m else 0
            nb = nb[:at] + head + line + "\n\n" + nb[at:]
        t.set_notebook(nb)

    def _consolidate(self, t, prof, dropped):
        """Важное из шагов, которые уходят из разговора, — в блокнот (переписывает модель). Не вышло — дописываем
        в блокнот краткие действия и результаты как есть, чтобы факты не потерялись."""
        lines = []

        def res(txt):
            txt = str(txt or "")
            return ("Ответ человека" if txt.startswith(("Ответ пользователя", "Ответ на твой вопрос")) else "Результат") + f": {txt[:1500]}"
        for m in dropped:
            c = m.get("content")
            role = m.get("role")
            for x in m.get("tool_calls") or []:
                f = x.get("function") or {}
                lines.append(f"Действие: {f.get('name')} {str(f.get('arguments'))[:300]}")
            if isinstance(c, list):                    # Claude: text, tool_use, tool_result — блоками (рецензия 0.83)
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        lines.append(f"Действие: {b.get('name')} {json.dumps(b.get('input') or {}, ensure_ascii=False)[:300]}")
                    elif b.get("type") == "tool_result":
                        bc = b.get("content")
                        lines.append(res("".join(x.get("text", "") for x in bc if isinstance(x, dict)) if isinstance(bc, list) else bc))
                    elif b.get("type") == "text" and b.get("text"):
                        lines.append(f"{'Модель' if role == 'assistant' else 'Сообщение'}: {b['text'][:1500]}")
            elif c:
                lines.append(res(c) if role == "tool" else f"{'Модель' if role == 'assistant' else 'Сообщение'}: {str(c)[:1500]}")
        # окно модели маленькое — и переписка блокнота короче (иначе она сама не влезет: выпуск 1); слова человека — всегда
        human = [ln for ln in lines if ln.startswith(("Ответ человека", "Сообщение"))]
        lim = max(2000, min(24000, int(int(t.data.get("win") or WIN_DEFAULT) * 3 * 0.3)))
        rest = "\n".join(ln for ln in lines if ln not in human)[-max(500, lim - len("\n".join(human))):]
        text = "\n".join(human)[:lim] + ("\n" if human else "") + rest
        try:
            from llm import stream_chat
            out = "".join(stream_chat(prof, "Ты ведёшь блокнот долгой задачи. Ответь только новым текстом блокнота в Markdown.",
                                      [{"role": "user", "content":
                                        f"Цель задачи: {t.goal}\n\nБлокнот сейчас:\n{t.notebook() or NOTEBOOK_HEAD}\n\n"
                                        f"Ранние шаги, которые уходят из памяти:\n{text}\n\nПерепиши блокнот: сохрани всё, что "
                                        "в нём было, и добавь важное из этих шагов — факты, номера, коды, суммы, ответы людей "
                                        "и компаний, договорённости, что уже сделано, чего ждём, что дальше. Разделы: Что "
                                        "известно / Что решено / Чего ждём / Что дальше. Коротко, без воды."}],
                                      cancel=t.cancel)).strip()
            out = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", out)
            if len(out) > 40:
                t.set_notebook(out)
                t.journal("🧠 Ранние шаги ушли из памяти — главное перенесено в блокнот.")
                return
        except Exception as e:  # noqa: BLE001
            log.info("Блокнот задачи не обновился моделью: %s", e)
        keep = [ln for ln in lines if ln.startswith(("Результат", "Действие", "Сообщение", "Ответ человека"))]
        t.set_notebook((t.notebook() or NOTEBOOK_HEAD).rstrip() + "\n\n## Из ранних шагов (кратко)\n"
                       + "\n".join("- " + ln[:300] for ln in keep)[-6000:])
        t.journal("🧠 Ранние шаги ушли из памяти — их краткие итоги дописаны в блокнот.")

    def _compact(self, t, prof, msgs, budget=None):
        """Разговор задачи больше budget символов: старые шаги (до ~60% бюджета) убираем, важное из них — в блокнот,
        подробности остаются в журнале. Первое сообщение (цель) остаётся. Режем по сообщению модели, чтобы ответы
        инструментов не остались без своих вызовов — такую историю модели отвергают."""
        budget = budget or BUDGET
        size = lambda m: len(json.dumps(m, ensure_ascii=False))  # noqa: E731
        total = sum(size(m) for m in msgs)
        if total <= budget:
            return msgs
        # выпуск 1: сначала дешевле — убрать старые результаты и большие тексты в вызовах (даже в последних шагах, если
        # одного шага хватает, чтобы не влезть: write_file на 10 тыс. знаков при окне 8 тыс.) — шаги и факты остаются
        for keep in (TRIM_AFTER // 2, 2, 0):
            msgs, n = self._trim(t, msgs, keep=keep)
            total = sum(size(m) for m in msgs)
            if n:
                t.journal(f"🧹 Старые результаты убраны из памяти ({n}) — память задачи упёрлась в окно модели.")
            if total <= budget:
                return msgs
        if len(msgs) <= 3:
            return msgs
        k = 1
        while k < len(msgs) - 2 and total > budget * 0.6:
            total -= size(msgs[k])
            k += 1
        while k < len(msgs) - 1 and msgs[k].get("role") != "assistant":
            k += 1
        dropped = msgs[1:k]
        if not dropped:
            return msgs
        self._consolidate(t, prof, dropped)
        first = dict(msgs[0])
        note = "(ранние шаги убраны из памяти — главное перенесено в блокнот задачи, подробности — в журнале)"
        if note not in str(first.get("content")):
            first["content"] = f"{first.get('content')}\n\n{note}"
        return [first] + msgs[k:]

    # ---------- окно и кэш (выпуск 1 «Больших задач», docs/HARNESS.md) ----------

    @staticmethod
    def _window(prof):
        """Окно модели в токенах: из профиля (context_window), у своего сервера — спросить (llm.context_window: LM Studio,
        Ollama, vLLM), у Claude — 200 тыс., иначе WIN_DEFAULT. Ошибка «не хватило окна» уменьшает его для задачи (_run)."""
        try:
            w = int(prof.get("context_window") or prof.get("ctx") or 0)
        except (TypeError, ValueError):
            w = 0
        if not w and prof.get("kind") == "anthropic":
            w = 200000
        if not w:
            try:
                from llm import context_window
                w = int(context_window(prof) or 0)
            except Exception:  # noqa: BLE001
                w = 0
        return w or WIN_DEFAULT

    @staticmethod
    def _reserve(t, prof):
        """Место под ответ модели (токенов): лимит ответа профиля, но не больше четверти окна. Его же задача и шлёт модели
        как max_tokens (рецензия 0.83: окно 4 тыс. — запрос + 2048 на ответ не помещались, задача падала на первом шаге)."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        return max(256, min(int(prof.get("max_tokens") or 2048), win // 4))

    @staticmethod
    def _win_key(prof):
        return f"{prof.get('base_url') or ''}|{prof.get('model') or ''}"

    @staticmethod
    def _size(x):
        return est_tokens(json.dumps(x, ensure_ascii=False))

    def _budget(self, t, prof, system, specs, state):
        """Сколько знаков истории можно держать: доля окна COMPACT_AT минус подсказка, инструменты, состояние и запас на
        ответ; не больше BUDGET (у больших окон — как раньше: дольше держать дороже)."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        reserve = self._reserve(t, prof)                                       # место под ответ (vLLM: запрос + max_tokens ≤ окна)
        # как на деле уходит серверу: строки в JSON (переводы строк — «\\n»), инструменты — в обёртке {"type": "function"}
        fixed = self._size(system) + (self._size([{"type": "function", "function": x} for x in specs]) if specs else 0) + self._size(state)
        return max(1200, min(BUDGET, (min(int(win * COMPACT_AT), win - reserve) - fixed) * 3))

    @staticmethod
    def _calls_of(m):
        """Вызовы в сообщении модели (любой протокол) -> [(id, name, args)]; prompt-режим — по тегам <tool_call>."""
        out = []
        for x in m.get("tool_calls") or []:                               # OpenAI
            f = x.get("function") or {}
            try:
                a = json.loads(f.get("arguments") or "{}")
            except ValueError:
                a = {}
            out.append((x.get("id"), f.get("name"), a if isinstance(a, dict) else {}))
        c = m.get("content")
        if isinstance(c, list):                                          # Claude
            out += [(b.get("id"), b.get("name"), b.get("input") or {}) for b in c if isinstance(b, dict) and b.get("type") == "tool_use"]
        elif isinstance(c, str) and "<tool_call>" in c:                  # функции текстом
            for j in re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", c, re.S):
                try:
                    d = json.loads(j)
                    out.append((None, d.get("name"), d.get("arguments") or {}))
                except ValueError:
                    pass
        return out

    @staticmethod
    def _stub(name, args, text):
        """Заглушка вместо старого результата: что это было и где взять снова."""
        hint = ""
        for k in ("path", "url", "query", "command", "pattern", "name"):
            if isinstance(args, dict) and args.get(k):
                hint = str(args[k])[:160]
                break
        m = re.search(r"_out/[^\s\]:]+\.txt", text or "")
        where = f"целиком — {m.group(0)}" if m else ("перечитай, если нужно" if hint else "повтори, если нужно")
        return f"[убрано из памяти: результат {name}" + (f" ({hint})" if hint else "") + f" — {where}]"

    def _trim(self, t, msgs, keep=None):
        """Чистка: результаты инструментов старше keep шагов (кроме ответов человека и итогов частей) — заглушкой
        «[убрано из памяти: …]», большие тексты в старых вызовах (содержимое write_file, код run_python) — короткой пометкой.
        Шаги и порядок действий остаются — модель видит, что делала. -> (новый список, сколько убрано)."""
        keep = TRIM_AFTER if keep is None else keep
        steps = [i for i, m in enumerate(msgs) if m.get("role") == "assistant" and self._calls_of(m)]
        if len(steps) <= keep:
            return msgs, 0
        cut = steps[-keep] if keep else len(msgs)
        # keep=0 — только большие тексты в вызовах (и в последнем шаге); результат последнего шага модель ещё не видела —
        # его не трогаем никогда (иначе после сжатия она получала заглушку вместо ответа инструмента)
        cut_res = steps[-max(keep, 1)]
        out, n = [dict(m) for m in msgs], 0
        calls = {}
        last_calls = []
        for i in range(len(out)):
            if i >= cut:
                break
            m = out[i]
            cs = self._calls_of(m) if m.get("role") == "assistant" else []
            if cs:
                last_calls = cs
                for cid, nm, a in cs:
                    calls[cid] = (nm, a)
                # большие тексты в аргументах старых вызовов
                if m.get("tool_calls"):
                    tc = []
                    for x in m["tool_calls"]:
                        f = dict(x.get("function") or {})
                        try:
                            a = json.loads(f.get("arguments") or "{}")
                        except ValueError:
                            a = None
                        if isinstance(a, dict):
                            a2 = self._slim_args(f.get("name"), a)
                            if a2 is not a:
                                f["arguments"] = json.dumps(a2, ensure_ascii=False)
                                n += 1
                        tc.append(dict(x, function=f))
                    m["tool_calls"] = tc
                elif isinstance(m.get("content"), list):
                    bl = []
                    for b in m["content"]:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            a2 = self._slim_args(b.get("name"), b.get("input") or {})
                            if a2 is not (b.get("input") or {}):
                                b = dict(b, input=a2)
                                n += 1
                        bl.append(b)
                    m["content"] = bl
                continue
            if i >= cut_res:
                continue
            if m.get("role") == "tool":                                  # OpenAI
                nm, a = calls.get(m.get("tool_call_id"), ("?", {}))
                c = m.get("content")
                if isinstance(c, str) and len(c) > 400 and nm not in NO_TRIM and not c.startswith("[убрано"):
                    m["content"] = self._stub(nm, a, c)
                    n += 1
            elif m.get("role") == "user" and isinstance(m.get("content"), list):   # Claude: tool_result
                bl = []
                for b in m["content"]:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        nm, a = calls.get(b.get("tool_use_id"), ("?", {}))
                        parts = b.get("content")
                        txt = "".join(x.get("text", "") for x in parts if isinstance(x, dict)) if isinstance(parts, list) else str(parts or "")
                        if len(txt) > 400 and nm not in NO_TRIM and not txt.startswith("[убрано") and \
                                not any(isinstance(x, dict) and x.get("type") == "image" for x in (parts if isinstance(parts, list) else [])):
                            b = dict(b, content=[{"type": "text", "text": self._stub(nm, a, txt)}])
                            n += 1
                    bl.append(b)
                m["content"] = bl
            elif m.get("role") == "user" and isinstance(m.get("content"), str) and "<tool_response>" in m["content"]:
                parts = re.split(r"(<tool_response>\n?.*?\n?</tool_response>)", m["content"], flags=re.S)
                k, changed = 0, False
                for j, part in enumerate(parts):
                    if part.startswith("<tool_response>"):
                        nm, a = (last_calls[k][1], last_calls[k][2]) if k < len(last_calls) else ("?", {})
                        k += 1
                        body = part[len("<tool_response>"):-len("</tool_response>")].strip()
                        if len(body) > 400 and nm not in NO_TRIM and not body.startswith("[убрано"):
                            parts[j] = f"<tool_response>\n{self._stub(nm, a, body)}\n</tool_response>"
                            changed = True
                            n += 1
                if changed:
                    m["content"] = "".join(parts)
        return out, n

    @staticmethod
    def _slim_args(name, a):
        """Аргументы старого вызова без больших текстов (тот же объект, если убирать нечего)."""
        big = {k: v for k, v in a.items() if isinstance(v, str) and len(v) > 1500}
        if not big:
            return a
        a2 = dict(a)
        for k, v in big.items():
            where = f" — в файле {a.get('path')}" if a.get("path") else ""
            a2[k] = f"[убрано из памяти: {len(v)} знаков{where}]"
        return a2

    def _fail(self, t, e, bug=False):
        """Задача остановилась с ошибкой: статус, журнал, след для уроков, голос и уведомление, пульс и журнал сбоев."""
        msg = str(e) or e.__class__.__name__
        if bug:
            msg = f"внутренняя ошибка программы ({e.__class__.__name__}: {msg}) — уже записана для разработчика"
        kind = "loop" if msg.startswith("застрял") else ("bug" if bug else ("idle_model" if "не взялась за дело" in msg else "failed"))
        if not bug and ACCESS_RX.search(msg):
            kind = "access"                           # нет прав на файл или папку — ночью повторять бесполезно (night.NO_RETRY)
        t.data.update(status="failed", error=msg, fail_kind=kind, failed_at=_now())   # fail_kind — для ночного обхода (night.py)
        t.journal(f"⚠ Ошибка: {msg}")
        self._trace(t, "loop_detected" if kind == "loop" else ("bug" if bug else "failed"))
        self._problem(f"Задача{' (программа)' if bug else ''}: {e.__class__.__name__ if bug else ''} {str(e)[:200]}".replace("  ", " "))
        if not t.data.get("parent"):
            self.host.announce(f"Задача «{t.title}» остановилась с ошибкой: {msg}")
            self._push(f"⚠ Задача остановилась: {t.title}", msg[:200], critical=True)

    @staticmethod
    def _transient(e):
        """Сбой, который проходит сам: сеть, перегрузка, таймаут, пустой ответ сервера. Узнаём по тексту ошибки
        (сообщения llm.py и серверов) — такой сбой даёт повтор по RETRY_MIN, а не провал задачи."""
        m = str(e).lower()
        return any(k in m for k in ("не отвеч", "не ответил вовремя", "недоступ", "timeout", "timed out", "connect", "подключ", "соедин",
                                    "502", "503", "504", "перегруж", "overload", "temporar", "пустой ответ", "ошибкой 5",
                                    "время вышло", "rate limit", "429", "слишком много запросов", "подождите минуту",
                                    "без текста"))

    def _cycles(self):
        """Сколько кругов по max_steps задача идёт сама: DEWIAR_TASK_CYCLES, настройка tasks.cycles или 15."""
        if CYCLES:
            return CYCLES
        try:
            return max(1, int(self.host.s.get("tasks", "cycles") or 15))
        except (AttributeError, TypeError, ValueError):
            return 15

    def _permit(self, t, key, question):
        """Спросить человека разрешение на действие задачи -> (да?, текст для модели при «нет»).
        Отказ запоминается до конца запуска: то же действие (тот же инструмент) больше не спрашиваем, а модели
        говорим обойтись без него. ASK_DECLINES отказов или ASK_SILENT вопросов подряд без ответа — задача встаёт
        на паузу (pause_now), а не спрашивает без конца и не жжёт токены (№54: «Лаборатория: запись?» раз за разом;
        №58: ночью команды по одной каждые 2 минуты, никто не отвечал)."""
        st = self.__dict__.setdefault("_asks", {}).setdefault(t.id, {"no": set(), "declined": 0, "silent": 0})
        if key in st["no"]:                                   # уже отказали, а модель снова за своё — это тоже в счёт
            st["declined"] += 1
            if st["declined"] >= ASK_DECLINES:
                t.data["pause_now"] = ("Вы уже отказали, а задача снова пробует то же самое — остановил её, чтобы не "
                                       "крутилась впустую. Напишите задаче, как быть, или скажите «продолжи задачу».")
            return False, ("Пользователь уже отказал в этом действии — больше не спрашиваю. Не пробуй то же другим способом: "
                           "обойдись без него или спроси (ask_user), что делать.")
        import inspect
        try:
            takes_cancel = "cancel" in inspect.signature(self.host.confirm).parameters
        except (TypeError, ValueError):
            takes_cancel = False
        ans = self.host.confirm(question, cancel=t.cancel) if takes_cancel else self.host.confirm(question)
        if ans:
            st["silent"] = 0
            return True, ""
        if t.cancel.is_set():
            return False, "Задачу остановили."
        if ans is None:                                       # никто не ответил за 2 минуты
            st["silent"] += 1
            t.journal(f"❔ Нет ответа на вопрос: {question}")
            if st["silent"] >= ASK_SILENT:
                t.data["pause_now"] = ("Задаю вопросы, а ответа нет — остановился, чтобы не спрашивать впустую. "
                                       "Скажите «продолжи задачу», когда будете рядом.")
            return False, ("Пользователь не ответил (его, видимо, нет рядом). Не спрашивай снова то же самое: сделай то, что "
                           "можно без этого, а вопрос запиши в блокнот («Чего ждём»).")
        st["no"].add(key)
        st["declined"] += 1
        st["silent"] = 0
        t.journal(f"✋ Пользователь отказал: {question}")
        if st["declined"] >= ASK_DECLINES:
            t.data["pause_now"] = (f"Вы отказали {st['declined']} раза — остановился, чтобы не спрашивать без конца. "
                                   "Напишите задаче, как быть, или скажите «продолжи задачу».")
        return False, ("Пользователь отказался. Больше это действие не предлагай и не пробуй его другими командами: обойдись "
                       "без него или спроси (ask_user), как быть.")

    @staticmethod
    def _progress_sig(t):
        """Отпечаток продвижения: план (сколько отмечено), блокнот, файлы-результаты и файлы в папке задачи."""
        import hashlib
        try:
            files = sorted(f"{p.relative_to(t.dir)}:{p.stat().st_size}" for p in t.dir.rglob("*")
                           if p.is_file() and p.name not in ("журнал.md", "задача.json", "история.json", "история.json.tmp") and "рабочая копия" not in p.parts)
        except OSError:
            files = []
        h = hashlib.sha1("\n".join([t.plan(), t.notebook(), json.dumps(t.data.get("outputs") or []), *files[:2000]]).encode()).hexdigest()
        return h[:16]

    # ---------- части задачи: помощники работают одновременно ----------

    def _parts(self, t):
        return [c for c in self.tasks.values() if c.data.get("parent") == t.id]

    def _spawn_parts(self, t, parts):
        if t.data.get("parent"):
            return "Ошибка: часть задачи сама частей не раздаёт — сделай эту работу сама."
        parts = [p for p in parts if isinstance(p, dict) and str(p.get("goal") or "").strip()]
        if not parts:
            return "Ошибка: нужен список parts — у каждой части goal (и title)."
        live = [c for c in self._parts(t) if c.status in ALIVE or c.status == "paused"]
        room = PARTS_MAX - len(live)
        if room <= 0:
            return f"Уже работают {len(live)} частей — сначала дождись их (wait_parts)."
        made = []
        for p in parts[:room]:
            title = str(p.get("title") or p["goal"])[:60]
            goal = (f"{p['goal'].strip()}\n\n(Это часть большой задачи «{t.title}»: {t.goal[:600]}\nСделай только эту часть. "
                    "Результат — файлы в outputs/ (покажи их show) и итог в finish: что сделано и главное содержание — "
                    "его прочитает основная задача.)")
            c = self.create(title, goal, project="", start=False, persona=t.data.get("persona") or "", parent=t.id,
                            folders=[str(f) for f in self._folders(t)])     # части видят те же папки человека
            made.append(c)
            t.journal(f"🧩 Часть «{c.title}» отдана помощнику.")
        self._launch_parts(t)
        skipped = len(parts) - len(made)
        return (f"Запущено частей: {len(made)} — " + "; ".join(f"«{c.title}»" for c in made)
                + (f". Ещё {skipped} не поместились (не больше {PARTS_MAX} сразу) — раздай их после wait_parts." if skipped else "")
                + " Они работают одновременно. Пока можешь делать своё, затем вызови wait_parts.")

    def _launch_parts(self, t):
        """Запустить ждущие части так, чтобы одновременно работали не больше PARTS_PARALLEL."""
        parts = self._parts(t)
        running = sum(1 for c in parts if c.thread is not None and c.thread.is_alive())
        for c in parts:
            if running >= PARTS_PARALLEL:
                break
            if c.status == "paused" and not c.data.get("steps") and not (c.thread and c.thread.is_alive()):
                self.start(c.id)
                running += 1

    def _wait_parts(self, t, minutes):
        """Ждать части (блокирует поток задачи, проверяя «стоп»), докидывать ждущие в работу; итоги — текстом,
        файлы outputs/ каждой части — копией в parts/<название>/ папки задачи."""
        import shutil
        import time as _t
        parts = self._parts(t)
        if not parts:
            return "Частей нет — сначала раздай их (spawn_parts)."
        end = _t.monotonic() + max(1.0, min(minutes, 24 * 60)) * 60
        t.data["activity"] = f"жду части: {len(parts)}"
        self._emit(t)
        while not t.cancel.is_set():
            self._launch_parts(t)
            busy = [c for c in parts if c.status in ALIVE or (c.status == "paused" and not c.data.get("steps"))]
            if not busy or _t.monotonic() > end:
                break
            if any(c.status == "waiting" for c in busy):      # часть спрашивает человека — ждать её нет смысла молча
                pass
            t.cancel.wait(2)
        if t.cancel.is_set():
            return "Задачу остановили."
        out = []
        for c in parts:
            line = f"### «{c.title}» — {STATUS_RU.get(c.status, c.status)}"
            if c.status == "done":
                dst = t.dir / "parts" / _clean(c.title)
                src = c.dir / "outputs"
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    files = [str(p.relative_to(t.dir)) for p in dst.rglob("*") if p.is_file()]
                    if files:
                        line += "\nФайлы: " + ", ".join(files[:20])
                line += "\n" + (c.result or "")[:4000]
            elif c.status == "failed":
                line += f": {c.error}"
            elif c.status == "waiting":
                line += f" — спрашивает пользователя: {c.question}"
            elif c.status in ALIVE or c.status == "paused":
                line += " — ещё работает (вызови wait_parts снова позже)"
            out.append(line)
        done = sum(1 for c in parts if c.status == "done")
        t.journal(f"🧩 Части: готово {done} из {len(parts)}.")
        return "\n\n".join(out)

    @staticmethod
    def _beat(t, tool=""):
        """Признак жизни шага (для _watch); шаг ожил после «не отвечает» — снять отметку."""
        import time as _t
        t.beat, t.beat_tool = _t.monotonic(), tool
        if t.data.get("hung_told"):
            t.data.pop("hung_told", None)
            t.journal("▶ Шаг ожил — продолжаю.")

    def _run(self, t):
        """Поток задачи: цикл «модель -> вызовы инструментов» до finish, wait, остановки, ошибки или лимита шагов.
        История сохраняется после каждого шага (продолжение после перезапуска). Временный сбой модели — сон
        и повтор (RETRY_MIN), прочие ошибки — status=failed с объявлением."""
        hist = t.dir / "история.json"
        try:
            msgs = json.loads(hist.read_text(encoding="utf-8")) if hist.exists() else []
        except ValueError:
            msgs = []
        wake = t.data.pop("wake_note", "")
        # чем продолжить разговор — зависит от причины пробуждения (тексты wait_reason задаются ниже и в wait)
        if not msgs:
            msgs = [{"role": "user", "content": f"Начинай задачу: {t.goal}"}]
            t.journal(f"▶ Начал работу ({t.persona}).")
        elif wake and wake.startswith("передышка"):
            self._add_user(msgs, "Продолжай задачу с того места, где остановился (сверься с планом и блокнотом).")
            t.journal("▶ Передышка окончена — продолжаю.")
        elif wake and wake.startswith("модель или сеть"):
            self._add_user(msgs, "Продолжай задачу с того места, где остановился (сервер модели в прошлый раз не ответил).")
            t.journal("↻ Пробую снова после сбоя.")
        elif wake:
            self._add_user(msgs, f"⏰ Ты ждал: «{wake}». Сейчас {dt.datetime.now():%d.%m %H:%M}. Проверь, что изменилось, "
                                 "запиши новое в блокнот и продолжай задачу.")
            t.journal(f"⏰ Вернулся к задаче: {wake}")
        elif not t.data.get("inbox"):
            self._add_user(msgs, "Продолжай задачу с того места, где остановился (сверься с планом и блокнотом).")
            t.journal("▶ Продолжаю работу.")
        max_steps = self.host.max_steps()
        idle, acted, run_steps = 0, False, 0
        chance, bad = False, 0                                    # второй шанс после ответов без действий; вызовы «текстом» подряд
        guard = Q.LoopGuard()                                     # живёт один запуск потока
        self.__dict__.setdefault("_asks", {}).pop(t.id, None)    # отказы и вопросы без ответа — счёт заново на каждый запуск
        t.data.pop("pause_now", None)
        prog_sig, prog_step = self._progress_sig(t), int(t.data.get("steps") or 0)   # «буксует»: шагов без продвижения
        q = self._q(t)
        try:
            prof = self.host.llm_profile()
            if not prof:
                raise LLMError("не выбрана языковая модель")
            # окно модели — на весь запуск (выпуск 1): от него бюджет истории, объём блокнота в состоянии, лёгкий режим
            win = self._window(prof)
            wl = t.data.get("win_learned")
            if isinstance(wl, dict) and wl.get("key") == self._win_key(prof):   # упирались в окно этой же модели — она меньше,
                win = min(win, int(wl.get("win") or win))                     # чем говорит сервер
            elif wl is not None:
                t.data.pop("win_learned", None)               # другая модель (или старая запись) — окно узнаём заново
            t.data.update(win=win, light=win <= LIGHT_WIN)
            system = self._system(t)                      # неизменна весь запуск: начало запроса — из кэша сервера
            ctx_tries = 0
            qu = q.setdefault("usage", {"in": 0, "out": 0, "cached": 0, "req": 0, "est": 0, "ck": 0, "sec": 0.0})
            while not t.cancel.is_set():
                inbox = t.data.pop("inbox", None)
                if inbox:                                         # пользователь написал задаче
                    for x in inbox:
                        self._note_human(t, x.get("text"))
                    self._add_user(msgs, "Сообщение пользователя для этой задачи:\n" + "\n".join(f"— {x['text']}" for x in inbox)
                                   + "\nУчти это (важное — в блокнот) и продолжай.")
                    t.save()
                if run_steps >= max_steps:
                    cyc = int(t.data.get("cycles") or 0) + 1
                    cycles = self._cycles()
                    sig = self._progress_sig(t)                    # продвинулась ли работа за этот круг
                    stale = int(t.data.get("stale_cycles") or 0) + 1 if sig == t.data.get("cycle_sig") else 0
                    t.data.update(cycle_sig=sig, stale_cycles=stale)
                    if stale >= STALE_CYCLES:
                        t.data.update(cycles=0, stale_cycles=0, status="paused")
                        t.journal(f"⏸ {STALE_CYCLES} круга по {max_steps} шагов без продвижения: план, блокнот и файлы не "
                                  "менялись. Остановился, чтобы не тратить время впустую. Напишите задаче, что делать, или «продолжи».")
                        self.host.announce(f"Задача «{t.title}» буксует — остановил её. Загляните в журнал задачи.")
                        break
                    if cyc < cycles:                               # много работы — передышка минуту и дальше сама
                        when = dt.datetime.now() + dt.timedelta(seconds=BREATHER_SEC)
                        t.data.update(cycles=cyc, status="sleeping", wake_at=when.isoformat(timespec="seconds"),
                                      wait_reason=f"передышка после {max_steps} шагов — продолжаю работу")
                        t.journal(f"⏸ Сделал {max_steps} шагов — передышка минуту и продолжаю (круг {cyc} из {cycles}).")
                    else:
                        t.data.update(cycles=0, status="paused")
                        t.journal(f"⏸ Сделал {max_steps * cycles} шагов подряд. Скажите «продолжи задачу», если нужно ещё.")
                        self.host.announce(f"Задача «{t.title}»: очень много шагов подряд — остановился. Можно продолжить.")
                    break
                text, calls = "", []
                self._beat(t)
                specs = self._specs(t)
                state = self._state(t)
                budget = self._budget(t, prof, system, specs, state)
                msgs = self._compact(t, prof, msgs, budget)
                t_call = time.monotonic()
                try:
                    # _tail — «Состояние задачи» в конец запроса (в историю не пишется); _ctx — не резать историю в llm
                    # (_ctx_cut оставил бы ответ инструмента без вызова): «не хватило окна» решаем здесь — сжатием
                    for kind, val in stream_events(dict(prof, _ctx=True, _tail=state, max_tokens=self._reserve(t, prof)), system, msgs,
                                                   cancel=t.cancel, tools=specs):
                        self._beat(t)
                        if kind == "tools":
                            calls = val
                        else:
                            text += val
                except LLMError as e:
                    if ctx_full(e) and ctx_tries < CTX_TRIES and not t.cancel.is_set():
                        # выпуск 1: не хватило окна — сначала сжать и повторить, а не провал задачи
                        ctx_tries += 1
                        req = est_tokens(system) + self._size(specs) + self._size(msgs) + est_tokens(state)
                        learned = max(2048, int((req + self._reserve(t, prof)) * 0.9))   # сервер считает и место под ответ
                        if learned < int(t.data.get("win") or WIN_DEFAULT):
                            t.data.update(win=learned, win_learned={"key": self._win_key(prof), "win": learned}, light=learned <= LIGHT_WIN)
                            system = self._system(t)
                        msgs, _n = self._trim(t, msgs, keep=2)
                        cur = sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs)
                        msgs = self._compact(t, prof, msgs, max(1200, cur // 2))
                        t.journal(f"↻ Модели не хватило окна — сжал память задачи и повторяю шаг (окно ≈{int(t.data['win'])} ток.).")
                        _write_hist(hist, msgs)
                        continue
                    blanks = int(t.data.get("blank_replies") or 0)
                    # «Задачи на часы» (пакет 29.10: «модель думала, но так и не ответила» — 42 раза у 4 человек, и задача
                    # падала): ушла в размышления и не уложилась — это тоже сбой шага, а не конец работы
                    thought = "так и не ответила" in str(e)
                    if ("без текста" not in str(e) and not thought) or blanks >= 3:
                        raise
                    t.data["blank_replies"] = blanks + 1       # пустой ответ — сбой модели: подсказать и продолжить, а не провал
                    if thought:
                        t.journal("↻ Модель ушла в долгие размышления и не успела ответить — прошу действовать короче.")
                        self._add_user(msgs, "Ты слишком долго размышлял(а) и не успел(а) ответить. Не рассуждай длинно: в двух-трёх "
                                             "фразах реши следующий шаг и сразу вызови нужный инструмент (или finish с итогом, если всё "
                                             "сделано). Большой шаг раздели на несколько маленьких.")
                    else:
                        t.journal("↻ Модель ответила пустотой — прошу продолжить.")
                        self._add_user(msgs, "Твой ответ пришёл пустым. Продолжай задачу: вызови нужный инструмент (или finish с итогом, "
                                             "если всё сделано).")
                    continue
                t.data["blank_replies"] = 0
                ctx_tries = 0
                u = take_usage() or {}                     # метрики (выпуск 1): токены, доля кэша — в quality.usage
                qu["req"] += 1
                qu["sec"] = round(float(qu.get("sec") or 0) + time.monotonic() - t_call, 3)
                if u.get("prompt"):
                    qu["in"] += int(u["prompt"])
                else:
                    qu["in"] += est_tokens(system) + self._size(specs) + self._size(msgs) + est_tokens(state)
                    qu["est"] += 1
                if u.get("cached") is not None:
                    qu["cached"] += int(u["cached"] or 0)
                    qu["ck"] += 1
                qu["out"] += int(u.get("out") or est_tokens(text + (json.dumps([c.get("args") for c in calls], ensure_ascii=False) if calls else "")))
                if t.cancel.is_set():
                    break
                t.data["steps"] += 1
                run_steps += 1
                t.data["retries"] = 0                             # модель ответила — счётчик повторов после сбоя сначала
                if text.strip():
                    t.journal("💭 " + text.strip()[:1500])
                if not calls and not t.data.get("refusal_nudged") and Q.looks_like_refusal(text) and self._web_available(t) \
                        and not self._web_used(t):                # «нет доступа к интернету», а поиском не пользовался — раз
                    t.data["refusal_nudged"] = True
                    q["refusal"] += 1
                    t.journal("✋ Модель отказалась («нет доступа»), не попробовав поиск — напоминаю про web_search.")
                    msgs += [{"role": "assistant", "content": text or "…"}, {"role": "user", "content": Q.REFUSAL_NUDGE}]
                    continue
                if not calls:
                    idle += 1
                    nudge = ("Продолжай по плану. Если всё сделано — вызови finish с итогом." if acted else
                             "Ты пока ничего не сделал — только написал текст. Не рассуждай: прямо сейчас вызови нужный "
                             "инструмент (например, выполни команду проверки), результат увидишь в ответе инструмента.")
                    garbled = bool(CALL_MARK_RX.search(text or ""))      # пытался вызвать, но не в том виде
                    bad = bad + 1 if garbled else 0
                    if garbled:
                        nudge = ("Твой вызов не распознан. Вызывай функцию ровно так (одну за раз), без пояснений:\n"
                                 '<tool_call>\n{"name": "<имя функции>", "arguments": {<аргументы>}}\n</tool_call>'
                                 if prompt_tools_mode(prof) else
                                 "Твой вызов не распознан: ты написал его текстом. Вызывай действия штатно — вызовом функции "
                                 "(tool call), без тегов и пояснений в тексте ответа.")
                    t.journal("↻ Модель написала вызов в непонятном виде — объясняю, как вызывать." if garbled else
                              "↻ Модель ответила текстом без действий — напоминаю, что нужно действовать.")
                    msgs += [{"role": "assistant", "content": text or "…"}, {"role": "user", "content": nudge}]
                    if (idle == 2 and not acted or bad == 2) and prof.get("kind") != "anthropic" and prof.get("tools_mode") != "prompt":
                        # «Задачи на часы» (пакет 29.10: «модель так и не взялась за дело» — 9 раз у 7 человек, своя модель):
                        # модель не понимает инструменты полем запроса — пробуем описать их текстом, прежде чем сдаться;
                        # так же — когда она дважды подряд пишет вызов текстом в своём виде (№448: DeepSeek и «DSML»)
                        prof = dict(prof, tools_mode="prompt")
                        idle = 0
                        t.journal("↻ Модель не вызывает действия — описываю их ей текстом и пробую снова.")
                        continue
                    if idle >= 3:                                   # три ответа подряд без действий
                        if not acted:                               # модель вообще не вызывает инструменты — это провал
                            raise LLMError(("модель пишет действия в виде, который Dewiar не смог разобрать, — ни одно не выполнилось. "
                                            if bad >= 2 else "модель так и не взялась за дело — только рассуждала, ни одного действия. ") +
                                           "Выберите в «Мозге» модель, которая умеет действия (инструменты), и запустите задачу снова")
                        if not chance:
                            # №448, №460: после пары шагов модель отвечала текстом (отчёт без finish, вызовы текстом) — и
                            # задача сразу вставала «не выполнено». Сначала второй шанс: прямо сказать, что от неё нужно
                            chance, idle = True, 0
                            msgs[-1] = {"role": "user", "content": IDLE_CHANCE}
                            t.journal("✋ Несколько ответов подряд без действий — даю ещё попытку: действовать или подвести итог (finish).")
                            continue
                        t.data["finish_checked"] = t.data["force_finish"] = True   # завершаем сами — без повторных проверок
                        t.data["force_why"] = "badcall" if bad >= 2 else "idle"
                        self._tool(t, "finish", {"summary": text.strip() or "Работа закончена."})
                        break
                    continue
                idle, acted, chance, bad = 0, True, False, 0
                results = []
                # слова модели перед вызовом (без размышлений <think>) — подпись «что делаю» в карточке
                say = re.sub(r"\s+", " ", re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)).strip()
                for c in calls:
                    t.data["activity"] = (say[:160] if say else ACT_RU.get(c["name"], c["name"]))
                    self._emit(t)
                    self._beat(t, c["name"])
                    r = self._tool(t, c["name"], c.get("args") or {})
                    self._beat(t)
                    q["tools"][c["name"]] = q["tools"].get(c["name"], 0) + 1
                    if isinstance(r, str) and r.startswith(("Ошибка", "Защита Dewiar")):
                        q["errors"] = (q["errors"] + [{"tool": c["name"], "text": r[:240]}])[-10:]
                    loop = guard.observe(c["name"], c.get("args") or {}, r)
                    if loop == "warn":
                        q["loop_warns"] += 1
                        t.journal("🔁 Повторяет одно и то же с тем же результатом — предупреждаю.")
                        r = f"{r}\n\n{Q.LOOP_WARN}"
                    elif loop == "finish":
                        t.data["finish_checked"] = t.data["force_finish"] = True
                        t.data["force_why"] = "loop"
                        t.journal("🔁 Зациклился — прошу закончить с тем, что есть.")
                        r = f"{r}\n\n{Q.LOOP_FINISH}"
                    elif loop == "stop":                           # не послушала LOOP_FINISH — прерываем с ошибкой
                        q["loop_warns"] += 1
                        t.data["looped"] = True
                    t.journal(f"🛠 `{c['name']}` {self._short(json.dumps(c.get('args') or {}, ensure_ascii=False), 200)} → "
                              f"{self._short(r)}")
                    results.append(r)
                    if t.data.get("looped"):
                        break
                    if c["name"] in PROGRESS_TOOLS and isinstance(r, str) and not r.startswith(("Ошибка", "Защита Dewiar")):
                        prog_step = int(t.data["steps"])
                    if t.data.get("finished") or t.cancel.is_set() or t.data.get("sleep_now") or t.data.get("pause_now"):
                        break
                # на каждый вызов нужен ответ, иначе модель отвергнет историю — невыполненные закрываем заглушкой
                results += ["(не выполнено: задача ушла ждать — повтори после пробуждения, если нужно)"] * (len(calls) - len(results))
                msgs += tool_turn_messages(prof, text, calls, results)
                if run_steps % TRIM_EVERY == 0:              # чистка пачкой: кэш ломается раз в TRIM_EVERY шагов, а не каждый
                    msgs, _n = self._trim(t, msgs)
                    if _n:
                        t.journal(f"🧹 Старые результаты убраны из памяти ({_n}) — они в журнале и файлах.")
                msgs = self._compact(t, prof, msgs, budget)
                _write_hist(hist, msgs)
                t.save()
                self._emit(t)
                if t.data.get("finished") or t.data.get("sleep_now"):
                    break
                if not t.data.get("pause_now") and run_steps % 5 == 0:     # продвинулась ли работа (раз в 5 шагов)
                    sig = self._progress_sig(t)
                    if sig != prog_sig:
                        prog_sig, prog_step = sig, int(t.data["steps"])
                    elif int(t.data["steps"]) - prog_step >= STUCK_STEPS:
                        t.data["pause_now"] = (f"{int(t.data['steps']) - prog_step} шагов подряд без продвижения: план, блокнот "
                                               "и файлы не менялись. Остановился, чтобы не тратить время и токены впустую. "
                                               "Напишите задаче, что делать, или скажите «продолжи задачу».")
                        t.data["stuck"] = True
                if t.data.get("pause_now"):
                    why = t.data.pop("pause_now")
                    t.journal(f"⏸ {why}")                          # журнал и голос — до смены статуса: кто увидел «на паузе»,
                    if not t.data.get("parent"):                   # видит и причину
                        self.host.announce(f"Задача «{t.title}» " + ("буксует — остановил её. Загляните в журнал задачи."
                                                                      if t.data.pop("stuck", False) else "на паузе: " + why[:1].lower() + why[1:]))
                    t.data.pop("stuck", None)
                    t.data.update(status="paused", cycles=0, stale_cycles=0, activity="")
                    t.save()
                    self._emit(t)
                    break
                if t.data.pop("looped", False):
                    raise LLMError("застрял: много раз повторил одно и то же действие с тем же результатом. Что уже удалось — "
                                   "в папке задачи; уточните задачу и запустите снова")
            if t.data.get("finished") and t.data.get("unfinished"):
                why = t.data["unfinished"]
                t.journal(f"⛔ Не выполнено: {why}")
                if not t.data.get("parent"):                   # журнал и голос — до смены статуса (как у паузы)
                    # голосом — только причина (счёт «успела: …» — в карточке и журнале)
                    self.host.announce(f"Задача «{t.title}» не выполнена: {why.split(' (успела:')[0][:160]}. Что успела — в папке задачи.")
                    self._push(f"⛔ Не выполнено: {t.title}", why[:200], critical=True)
                t.data.update(status="failed", activity="", error="не выполнено: " + why, fail_kind="unfinished", failed_at=_now())
                self._trace(t, "unfinished")
            elif t.data.get("finished"):
                t.data.update(status="done", activity="")
                t.journal("🏁 Готово.")
                # первая фраза итога без Markdown — для голосового объявления и уведомления
                # первая фраза — до точки или до конца строки (итог часто начинается строкой без точки, а дальше — файлы)
                first = re.split(r"(?<=[.!?])\s|\n", re.sub(r"[#*_`>\[\]]", "", t.result).strip(), maxsplit=1)[0].strip(" -—:")[:200]
                outs = t.data.get("outputs") or []
                where = (f" Результат — «{outs[-1].get('title') or outs[-1].get('path')}»: посмотреть и скачать можно в карточке "
                         "виджета или в студии, «Задачи»." if outs else "")
                if not t.data.get("parent"):                  # часть — без объявлений: итог заберёт главная задача
                    self.host.announce(f"Задача «{t.title}» готова. {first if first.lower().strip('!. ') not in ('готово', '') else ''}{where}".replace("  ", " ").strip())
                    self._push(f"✅ Готово: {t.title}", first or "Итог — в студии, «Задачи»",
                               file=t.dir / "итог.md" if (t.dir / "итог.md").is_file() else None)
                self._clean(t)
                self._trace(t, "final")
            elif t.cancel.is_set() and t.status != "paused":
                t.data["status"] = "stopped"
                t.journal("⏹ Остановлено.")
        except (LLMError, OSError, CodeError) as e:
            n = int(t.data.get("retries") or 0)
            if t.cancel.is_set():
                # GitHub #15 (24.10): человек нажал «Остановить», а зависший запрос потом упал ReadTimeout — повтор
                # назначался без проверки отмены, и start() снимал её. Остановка важнее позднего сбоя: без повтора.
                if t.status != "paused":
                    t.data.update(status="stopped", wake_at="", error="")
                t.journal(f"⏹ Остановлено (запрос к модели завершился позже: {self._short(str(e), 160)}).")
            elif isinstance(e, LLMError) and self._transient(e) and n < len(RETRY_MIN):
                when = dt.datetime.now() + dt.timedelta(minutes=RETRY_MIN[n])      # временный сбой — попробуем позже
                t.data.update(retries=n + 1, status="sleeping", wake_at=when.isoformat(timespec="seconds"),
                              wait_reason="модель или сеть не ответили — пробую снова", error="")
                t.journal(f"⚠ {e}. Попробую снова в {when:%H:%M} (попытка {n + 1} из {len(RETRY_MIN)}).")
            else:
                self._fail(t, e)
        except Exception as e:  # noqa: BLE001 — ошибка в самой программе: та же честная остановка, и разработчику в пульс
            log.exception("задача %s", t.id)
            self._fail(t, e, bug=True)
        finally:
            t.data["activity"] = ""
            if t.data.get("status") in ("done", "failed", "stopped", "paused") and t.code() is not None:
                try:
                    t.code().stop_all()                  # сервер разработки и прочее, что задача запускала в фоне
                except Exception:  # noqa: BLE001
                    log.debug("фоновые процессы задачи", exc_info=True)
            if t.data.get("inbox") and not t.cancel.is_set() and t.status != "failed":
                # пользователь написал, пока задача заканчивала круг, — не теряем: проснётся сразу
                t.data.update(finished=False, finish_checked=False, force_finish=False, verified=False, critic_done=False, gate_rejects=0, unfinished="",
                              status="sleeping", wake_at=_now(),
                              wait_reason="пришло сообщение пользователя")
            try:                                              # история — раньше состояния: увидевший «готово» читает её целой
                _write_hist(hist, msgs)
            except (OSError, NameError):                      # NameError: msgs не успели прочитать
                pass
            t.save()
            self._emit(t)
