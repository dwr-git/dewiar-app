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
from llm import LLMError, stream_chat, stream_events, tool_turn_messages

log = logging.getLogger("dewiar.tasks")

# статусы: running → waiting (ask_user) / sleeping (wait, передышка, повтор после сбоя) → done | failed | stopped;
# paused — остановлена до команды человека (или до автопродолжения после перезапуска)
ACTIVE = ("running", "waiting")
ALIVE = ("running", "waiting", "sleeping")         # задача ещё в работе: sleeping проснётся сама
STATUS_RU = {"running": "выполняется", "waiting": "ждёт ответа", "paused": "на паузе", "done": "готово",
             "failed": "не получилось", "stopped": "остановлена", "sleeping": "ждёт и вернётся"}
BUDGET = int(os.environ.get("DEWIAR_TASK_BUDGET") or 60000)     # сколько разговора задачи держать в памяти (символов)
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
                   "твоей папки (read_file, run_python). minutes — сколько ждать сейчас (по умолчанию 60).",
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
    "read_file": ("Прочитать файл из папки задачи (по 400 строк; start/end — диапазон строк).",
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
ACT_RU = {"write_file": "пишу файл", "read_file": "читаю файл", "list_files": "смотрю файлы", "run_python": "запускаю Python",
          "show": "показываю результат", "transcribe": "расшифровываю запись", "download": "скачиваю файл",
          "web_search": "ищу в интернете", "read_page": "читаю страницу", "update_plan": "обновляю план", "log": "пишу журнал",
          "finish": "подвожу итог", "code_run": "запускаю в проекте", "code_edit": "правлю код", "code_read": "читаю код",
          "remember": "записываю в блокнот", "notes": "обновляю блокнот", "notify": "сообщаю вам", "wait": "жду и вернусь"}
# инструменты чата, которые не нужны внутри задачи
SKIP_IN_TASK = {"start_task", "task_status", "stop_task", "remove_task", "resume_task", "tell_task", "call_persona", "write_diary"}
ACT_RU.update(spawn_parts="раздаю части помощникам", wait_parts="жду части", code_process="смотрю фоновый процесс",
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
        """Перезаписать блокнот (не больше 30 000 символов — он целиком идёт в подсказку каждого шага)."""
        text = (text or "").strip()
        if not text.startswith("#"):
            text = "# Блокнот задачи\n\n" + text
        (self.dir / "блокнот.md").write_text(text[:30000] + "\n", encoding="utf-8")

    def code(self):
        """CodeWork для задачи с проектом, иначе None. Рабочая копия создаётся лениво — при первом code_* (prepare)."""
        return CodeWork(self.data["project"], self.dir / "рабочая копия") if self.data.get("project") else None

    def public(self):
        """Состояние для студии и виджета: data + папка + статус по-русски («вернётся в 14:30»)."""
        d = dict(self.data)
        d["dir"] = str(self.dir)
        d["status_ru"] = STATUS_RU.get(d.get("status"), d.get("status"))
        if d.get("status") == "sleeping" and d.get("wake_at"):
            try:
                w = dt.datetime.fromisoformat(d["wake_at"])
                d["status_ru"] = "вернётся " + (f"в {w:%H:%M}" if w.date() == dt.date.today() else f"{w:%d.%m} в {w:%H:%M}")
            except ValueError:
                pass
        return d

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

    def create(self, title, goal, project="", start=True, persona="", parent=""):
        """Создать папку задачи и начальные файлы; project — папка проекта для режима «Код». Нет папки — ValueError."""
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
                t.data.update(finished=False, finish_checked=False, force_finish=False, verified=False, critic_done=False, refusal_nudged=False, tests_gate=0)
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
        """Подсказка модели на каждый шаг: задача, правила, блокнот, план, проект, память, уроки, навыки.
        Собирается заново каждый шаг — блокнот и план всегда свежие."""
        code = t.code()
        now = dt.datetime.now()
        s = (f"Ты — {t.persona}, голосовой ассистент. Сейчас ты выполняешь задачу В ФОНЕ: пользователь занят своими "
             f"делами. Ты доводишь задачу до конца, как надёжный личный помощник: не бросаешь на полпути, не забываешь, "
             f"зачем всё делается, и держишь человека в курсе.\n\nЗАДАЧА: {t.title}\nЦЕЛЬ: {t.goal}\n"
             f"Сейчас: {now:%d.%m.%Y %H:%M} ({['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'][now.weekday()]}).\n\n"
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
             "что проверить. Пиши по-русски.\n\n"
             f"БЛОКНОТ ЗАДАЧИ (твоя память):\n{t.notebook() or '(пока пусто)'}\n\n"
             f"Твоя папка: {self.host.workspace.root} (заметки — save_note; файлы, которые прислал пользователь, — "
             f"в «Входящие» там же). Папка этой задачи: {t.dir}.\n\n"
             "МАСТЕРСКАЯ. Если результат — файл (страница, дашборд, презентация, калькулятор, игра, таблица, документ, "
             "расшифровка), делай его сам: write_file в outputs/ (HTML — один самодостаточный файл, CSS и JS внутри), "
             "run_python — расчёты и сборка файлов, transcribe — расшифровка аудио/видео, download — скачать. Сначала "
             "загляни в подходящий навык (use_skill: slides, html-app, html-viz, data-report, media-transcribe, research…). "
             "Длина одного твоего ответа ограничена: файл длиннее ~120 строк пиши за несколько шагов — write_file с первой частью, "
             "потом write_file с append=true. Перед finish проверь файл (read_file) и покажи его пользователю (show). Ответ в finish — коротко: что "
             "получилось и как пользоваться; содержимое файла не пересказывай.\n\nТЕКУЩИЙ ПЛАН:\n{t.plan()}")
        if t.data.get("parent"):
            s += ("\n\nТы — помощник: делаешь одну часть большой задачи, параллельно с другими. Не спрашивай пользователя без "
                  "крайней нужды и не уведомляй его — твой итог (finish) прочитает основная задача: пиши в нём суть результата.")
        else:
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
                s += ("\n\nКАРТА ПРОЕКТА (на начало работы; подробности — code_read/code_search):\n" + t.data["code_map"] +
                      "\nЦикл работы: найди место → прочитай → поправь (code_edit) → запусти тесты → по ошибкам поправь снова. "
                      "Не меняй тесты, если об этом не просили. Перед finish тесты должны проходить — я проверю. "
                      "Свои тесты пиши по КАЖДОМУ требованию цели и на краевые случаи: цифры, латиница и кириллица, "
                      "пустой ввод, повторы, начало и конец строки — не только на примеры из задачи. Правка всё сломала — "
                      "code_undo. Сервер или другую долгую программу запускай code_run с background=true, проверяй "
                      "(запрос к нему, code_process output) и останавливай.")
        mem = self.host.memory()
        if mem:
            s += "\n\nЧто ты знаешь о пользователе:\n" + mem
        s += Q.lessons_block(self.lessons_path())          # выводы из прошлых задач (quality.reflect)
        s += Q.talk_lessons_block(self.host.workspace.root / Q.TALK_LESSONS_FILE)   # и из поправок в разговоре
        sp = getattr(self.host, "skills_prompt", None)
        return s + (sp() if sp else "")

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
        return any(used.get(k) for k in ("web_search", "read_page", "read_webpage", "download"))

    def _web_available(self, t):
        return any(x["name"] == "web_search" for x in self._specs(t))

    def _finish_gates(self, t, summary):
        """Проверки перед итогом: ложный отказ -> машинная проверка файлов (и что они показаны) -> самопроверка моделью.
        Каждая — один раз за задачу (флаги в data сбрасывает новое сообщение пользователя, см. tell), чтобы спор
        с проверкой не стал бесконечным. force_finish (завершаем сами) — без проверок.
        -> текст для модели (итог не принят) или None (принимаем)."""
        q = self._q(t)
        if t.data.get("force_finish"):
            return None
        if not t.data.get("refusal_nudged") and Q.looks_like_refusal(summary) and self._web_available(t) and not self._web_used(t):
            t.data["refusal_nudged"] = True
            q["refusal"] += 1
            t.journal("✋ Проверка перед итогом: отказ «нет доступа», а поиском не пользовался — напоминаю про web_search.")
            return Q.REFUSAL_NUDGE
        shown = [o.get("path") for o in t.data.get("outputs") or []]
        if not t.data.get("verified"):
            t.data["verified"] = True
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
        if not t.data.get("critic_done") and self._opt("self_check") is not False:
            t.data["critic_done"] = True
            files = []
            for p in sorted(t.dir.rglob("*")):
                rel = p.relative_to(t.dir)
                if p.is_file() and rel.parts[0] not in Q.SERVICE and not rel.parts[0].startswith("рабочая копия"):
                    files.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
            facts = (f"Шагов: {t.data.get('steps', 0)}. Инструменты: " +
                     ", ".join(f"{k}×{v}" for k, v in sorted(q["tools"].items(), key=lambda x: -x[1])[:12]) +
                     (f". Показано пользователю: {', '.join(shown)}" if shown else "") +
                     (". Это задача по коду: изменения пользователь примет сам (рабочая копия)." if t.data.get("project") else ""))
            diff = ""
            if code is not None and code.work.exists():
                try:
                    diff = code.diff(limit=20000)
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
            "refusal": q["refusal"], "verify_fail": q["verify_fail"], "critic": q["critic"], "time": _now()})
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

    def _specs(self, t):
        """Инструменты задачи: инструменты чата (кроме SKIP_IN_TASK) + TASK_TOOLS + WORK_TOOLS (+ CODE_TOOLS для проекта)."""
        specs = [s for s in self.host.toolbox.specs() if s["name"] not in SKIP_IN_TASK]
        specs += [{"name": n, "description": d, "parameters": p} for n, (d, p) in TASK_TOOLS.items()]
        specs = [x for x in specs if x["name"] not in WORK_TOOLS]          # одноимённые инструменты чата заменяем своими
        specs += [{"name": n, "description": d, "parameters": p} for n, (d, p) in WORK_TOOLS.items()]
        if t.data.get("project"):
            specs += [{"name": n, "description": d, "parameters": p} for n, (d, p) in CODE_TOOLS.items()]
        if not t.data.get("parent"):                       # часть сама частей не раздаёт
            specs += [{"name": n, "description": d, "parameters": p} for n, (d, p) in PART_TOOLS.items()]
        return specs

    def _coerce(self, t, name, args):
        """Привести аргументы к схеме инструмента (слабые модели шлют список вместо строки и т. п.), см. tools.coerce_args."""
        from tools import coerce_args
        spec = next((x for x in self._specs(t) if x["name"] == name), None)
        return coerce_args((spec or {}).get("parameters"), args)

    def _tool(self, t, name, args):
        """Выполнить вызов модели -> текст результата. Любая ошибка — ответом модели («Ошибка: …»), а не падением задачи.
        _truncated ставит llm.py, когда ответ модели оборвался по лимиту длины и аргументы удалось спасти лишь частично."""
        trunc = isinstance(args, dict) and bool(args.pop("_truncated", False))
        try:
            r = self._tool_raw(t, name, self._coerce(t, name, args))
            if trunc:
                self._q(t)["errors"].append({"tool": name, "text": "ответ оборвался по лимиту длины"})
                if name == "write_file" and isinstance(r, str) and not r.startswith("Ошибка"):
                    tail = str(args.get("content") or "")[-160:]
                    r += ("\n\nВНИМАНИЕ: твой ответ ОБОРВАЛСЯ по лимиту длины — записана только первая часть файла. Он кончается "
                          f"так: «…{tail}». Допиши продолжение (write_file с append=true) кусками не больше ~120 строк, НЕ переписывая "
                          "файл с нуля.")
                else:
                    r = f"{r}\n\n(Твой ответ оборвался по лимиту длины — аргументы могли дойти не целиком: проверь результат. Делай шаги меньше.)"
            return r
        except Exception as e:  # noqa: BLE001
            log.exception("задача %s: инструмент %s", t.id, name)
            if not isinstance(e, (ValueError, OSError, TimeoutError)):   # не «плохие аргументы», а ошибка в программе
                self._problem(f"Задача, инструмент {name}: {e.__class__.__name__}: {str(e)[:160]}")
            return f"Ошибка инструмента {name}: {e}. Проверь аргументы (строки — строками) и попробуй ещё раз или иначе."

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
            (t.dir / "итог.md").write_text(f"# Итог: {t.title}\n\n{summary}\n", encoding="utf-8")
            t.data.update(result=summary, finished=True)
            return "Задача завершена."
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
        # обычные инструменты ассистента
        on, need = self.host.toolbox.policy(name)
        if not on:
            return f"Инструмент {name} выключен пользователем."
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
            raise ValueError("путь должен быть внутри папки задачи, например outputs/app.html")
        return p

    def _work(self, t, name, args):
        """Инструменты мастерской (WORK_TOOLS)."""
        if name == "write_file":
            p = self._path(t, args.get("path"))
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
        if name == "read_file":
            p = self._path(t, args.get("path"))
            if not p.is_file():
                return "Такого файла нет — посмотри list_files."
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            a, b = max(1, int(args.get("start") or 1)), int(args.get("end") or 0)
            b = min(len(lines), b or a + 399)
            return "\n".join(f"{i}: {lines[i - 1]}" for i in range(a, b + 1)) + (f"\n… ещё строк: {len(lines) - b}" if b < len(lines) else "")
        if name == "list_files":
            out = []
            for p in sorted(t.dir.rglob("*")):
                rel = p.relative_to(t.dir)
                if p.is_file() and not rel.parts[0].startswith(("рабочая копия", "_run")) and p.name not in ("задача.json", "история.json", "история.json.tmp", "журнал.md"):
                    out.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
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
                    + ("\n…(дальше — в файле, читай read_file)" if len(txt) > 6000 else ""))
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
        if len(out) > 12000:                                  # длинный вывод целиком — в файл, модели — начало и конец
            full = t.dir / "_out" / f"вывод{n}.txt"
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(out, encoding="utf-8")
            out = (out[:6000] + f"\n…[середина вывода — в файле _out/вывод{n}.txt: читай её read_file по частям, не запускай заново]…\n"
                   + out[-5000:])
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

    def _consolidate(self, t, prof, dropped):
        """Важное из шагов, которые уходят из разговора, — в блокнот (переписывает модель). Не вышло — дописываем
        в блокнот краткие действия и результаты как есть, чтобы факты не потерялись."""
        lines = []
        for m in dropped:
            c = m.get("content")
            if isinstance(c, list):
                c = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in c)
            for x in m.get("tool_calls") or []:
                f = x.get("function") or {}
                lines.append(f"Действие: {f.get('name')} {str(f.get('arguments'))[:300]}")
            if c:
                lines.append(f"{'Результат' if m.get('role') == 'tool' else 'Модель' if m.get('role') == 'assistant' else 'Сообщение'}: "
                             f"{str(c)[:1500]}")
        text = "\n".join(lines)[-24000:]
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
        keep = [ln for ln in lines if ln.startswith(("Результат", "Действие"))]
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
        if len(msgs) <= 3 or total <= budget:
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
            c = self.create(title, goal, project="", start=False, persona=t.data.get("persona") or "", parent=t.id)
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
        guard = Q.LoopGuard()                                     # живёт один запуск потока
        self.__dict__.setdefault("_asks", {}).pop(t.id, None)    # отказы и вопросы без ответа — счёт заново на каждый запуск
        t.data.pop("pause_now", None)
        prog_sig, prog_step = self._progress_sig(t), int(t.data.get("steps") or 0)   # «буксует»: шагов без продвижения
        q = self._q(t)
        try:
            prof = self.host.llm_profile()
            if not prof:
                raise LLMError("не выбрана языковая модель")
            while not t.cancel.is_set():
                inbox = t.data.pop("inbox", None)
                if inbox:                                         # пользователь написал задаче
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
                try:
                    for kind, val in stream_events(prof, self._system(t), msgs, cancel=t.cancel, tools=self._specs(t)):
                        self._beat(t)
                        if kind == "tools":
                            calls = val
                        else:
                            text += val
                except LLMError as e:
                    blanks = int(t.data.get("blank_replies") or 0)
                    if "без текста" not in str(e) or blanks >= 3:
                        raise
                    t.data["blank_replies"] = blanks + 1       # пустой ответ — сбой модели: подсказать и продолжить, а не провал
                    t.journal("↻ Модель ответила пустотой — прошу продолжить.")
                    self._add_user(msgs, "Твой ответ пришёл пустым. Продолжай задачу: вызови нужный инструмент (или finish с итогом, "
                                         "если всё сделано).")
                    continue
                t.data["blank_replies"] = 0
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
                    if re.search(r'"(?:tool_name|tool|name|function)"\s*:', text or ""):   # пытался вызвать, но не в том виде
                        nudge = ("Твой вызов не распознан. Вызывай функцию ровно так (одну за раз), без пояснений:\n"
                                 '<tool_call>\n{"name": "<имя функции>", "arguments": {<аргументы>}}\n</tool_call>')
                    t.journal("↻ Модель ответила текстом без действий — напоминаю, что нужно действовать.")
                    msgs += [{"role": "assistant", "content": text or "…"}, {"role": "user", "content": nudge}]
                    if idle >= 3:                                   # три ответа подряд без действий — завершаем сами
                        if not acted:                               # модель вообще не вызывает инструменты — это провал
                            raise LLMError("модель так и не взялась за дело — только рассуждала, ни одного действия. "
                                           "Выберите в «Мозге» модель, которая умеет действия (инструменты), и запустите задачу снова")
                        t.data["finish_checked"] = t.data["force_finish"] = True   # завершаем сами — без повторных проверок
                        self._tool(t, "finish", {"summary": text.strip() or "Работа закончена."})
                        break
                    continue
                idle, acted = 0, True
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
                msgs = self._compact(t, prof, msgs)
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
            if t.data.get("finished"):
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
                t.data.update(finished=False, finish_checked=False, force_finish=False, verified=False, critic_done=False, status="sleeping", wake_at=_now(),
                              wait_reason="пришло сообщение пользователя")
            try:                                              # история — раньше состояния: увидевший «готово» читает её целой
                _write_hist(hist, msgs)
            except (OSError, NameError):                      # NameError: msgs не успели прочитать
                pass
            t.save()
            self._emit(t)
