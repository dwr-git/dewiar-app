"""Исполнитель задач в облаке Dewiar: служба на сервере сайта, которая делает задачи с телефона, когда компьютера нет.

Поток работы:
1. Телефон кладёт задачу (taskreq с cloud=true) в синхронизацию; облако (cloud.php) запоминает доверенность — удостоверение
   человека, зашифрованное (grant_put).
2. Раз в POLL секунд исполнитель спрашивает очередь (?p=/runner/pending, заголовок X-Runner-Key). Компьютер на связи —
   облако даёт ему 90 с забрать задачу самому; нет — отдаёт сразу.
3. Исполнитель занимает задачу так же, как компьютер (taken_by с prev — второй исполнитель или компьютер получит lost),
   и работает в папке пространства (RUNNER_DIR/<пространство>) обычным TaskManager — с ограничениями облака: без запуска
   программ, скачивания и вопросов к человеку (ответить ему пока негде), поиск и чтение страниц — через облако.
4. Ход и итог — записью task:<id> в синхронизации человека (телефон показывает её в «Задачах» и в разговоре), файлы из
   outputs/ — в ?p=/files (телефон открывает и сохраняет их). Потом задача из очереди удаляется.
Модель и поиск оплачивает человек (запросы идут его доверенностью «dg-<номер>.<ключ исполнителя>»).
Экзамен способностей (кабинет → «Экзамен» → «Начать экзамен»): в ответе очереди — задание exam, его ведёт ExamJob:
своё окружение в RUNNER_DIR/_exam (ставится один раз: httpx, websockets, numpy, Pillow — служба не меняет /opt), запуск
core/exam.py с моделью облака по доверенности служебного ключа, ход и итог — в ?p=/runner/exam (там же «остановить»).

Запуск: python3 core/cloudrunner.py (служба dewiar-runner, см. server/runner/install-runner.sh). Настройки — переменные:
DEWIAR_CLOUD_URL (https://dewiar.pro/dwrapp/cloud.php), DEWIAR_RUNNER_KEY (php cloud.php runner-key),
DEWIAR_RUNNER_DIR (папки пространств), DEWIAR_RUNNER_MODEL (chat), DEWIAR_RUNNER_PARALLEL (3)."""
import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx  # noqa: E402

import tasks as TK  # noqa: E402
from workspace import Workspace  # noqa: E402

log = logging.getLogger("dewiar.runner")
URL = (os.environ.get("DEWIAR_CLOUD_URL") or "https://dewiar.pro/dwrapp/cloud.php").rstrip("/")
KEY = os.environ.get("DEWIAR_RUNNER_KEY") or ""
DIR = Path(os.environ.get("DEWIAR_RUNNER_DIR") or Path.home() / ".local/share/dewiar-runner")
MODEL = os.environ.get("DEWIAR_RUNNER_MODEL") or "chat"
PARALLEL = int(os.environ.get("DEWIAR_RUNNER_PARALLEL") or 3)
POLL = float(os.environ.get("DEWIAR_RUNNER_POLL") or 10)
DEVICE = "pc-cloud"
HOST = __import__("socket").gethostname()[:60]


def lan_url(url=None):
    """Сайт на этой же машине (DEWIAR_CLOUD_URL = http://127.0.0.1:9099/dwrapp/cloud.php) -> тот же адрес с адресом этой
    машины в домашней сети (http://192.168.1.46:9099/dwrapp/cloud.php) или "". Его сайт раздаёт программам со входом:
    дома они ходят к сайту напрямую, а не через прокси или VPN (cloud.php: lan_info)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    u = urlparse(url or URL)
    if u.hostname not in ("127.0.0.1", "localhost"):
        return ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))                   # пакет не уходит: так система называет адрес основной сети
            ip = s.getsockname()[0]
    except OSError:
        return ""
    try:
        if not ipaddress.ip_address(ip).is_private or ip.startswith(("127.", "172.17.")):
            return ""
    except ValueError:
        return ""
    return f"{u.scheme}://{ip}{':' + str(u.port) if u.port else ''}{u.path}"


LAN = lan_url()
try:
    from version import VERSION
except ImportError:
    VERSION = ""
NAME = "Облако Dewiar"
FILE_MAX = 10 * 1024 * 1024
FINAL = ("done", "failed", "stopped")
# в облаке нельзя: запуск кода и скачивание на сервере сайта, расшифровка (нет моделей слуха), вопросы к человеку
CLOUD_SKIP = {"run_python", "download", "transcribe", "ask_user"}
CLOUD_NOTE = ("\n\nТЫ РАБОТАЕШЬ В ОБЛАКЕ DEWIAR (компьютер человека выключен): запускать программы и скачивать файлы "
              "нельзя — делай файлы сам (write_file), сведения ищи web_search и read_webpage. Спросить человека сейчас нельзя: "
              "решай сам разумно и напиши в итоге, что выбрал. Итог и файлы из outputs/ человек получит на телефон.")


_skills = []


def skills():
    """Встроенные навыки Dewiar (data/skills) — одни на всех людей."""
    if not _skills:
        from skills import Skills
        _skills.append(Skills(_NoSettings()))
    return _skills[0]


def _cred(grant):
    return f"{grant}.{KEY}"


EXAM_PKGS = ["httpx", "websockets", "numpy", "Pillow"]
EXAM_PROBE = "import httpx, websockets, numpy, PIL"
# только для «Больших задач» и «по возможности» (рецензия 0.83: обычный экзамен из-за них не должен ломаться):
# openpyxl — таблицы Б4, Б6; playwright — сайт Б5 в браузере на ширине телефона (сам Chromium — ExamJob.browser)
BIG_PKGS = ["openpyxl", "playwright"]
BIG_PROBE = "import openpyxl, playwright"
BROWSER_RETRY_S = 7 * 86400                         # Chromium не скачался — пробуем снова не раньше чем через неделю
# весточка «жив» раз в EXAM_BEAT с: в ответ кабинет говорит «остановить» — так отмена доходит за ~10 с, даже когда сценарий
# ждёт модель или судью минутами (04.11: «Остановить» висело, пока сценарий не кончится)
EXAM_BEAT = float(os.environ.get("DEWIAR_EXAM_BEAT") or 10)
EXAM_CANCELLED = 3                                   # exam.py вышел сам: доступ к модели отозван (экзамен остановлен)


class ExamJob(threading.Thread):
    """Экзамен из кабинета: окружение → core/exam.py → ход и итог в кабинет. Кабинет сказал «остановить» — останавливаем.
    Ход — строки «[i/n] группа — сценарий» из exam.py; пока сценарий долгий — весточка «жив» раз в EXAM_BEAT секунд."""

    def __init__(self, job):
        super().__init__(daemon=True, name="exam")
        self.job, self.proc, self.cancel, self.done = job, None, False, threading.Event()
        self.state = "preparing"                     # что слать весточкой «жив» (_beat): пока ставится окружение — preparing
        self.home = DIR / "_exam"
        self.where = {}

    def post(self, state, **kw):
        if state in ("preparing", "running"):
            self.state = state
        try:
            r = httpx.post(URL, params={"p": "/runner/exam"}, json={"id": self.job["id"], "state": state, **self.where, **kw},
                           headers={"X-Runner-Key": KEY}, timeout=120 if state == "done" else 20)
            d = r.json() if r.status_code < 400 else {}
            if r.status_code >= 400:
                log.warning("экзамен: кабинет ответил %s", r.status_code)
        except (httpx.HTTPError, ValueError) as e:
            log.info("экзамен: кабинет: %s", e)
            return {}
        if d.get("cancel"):
            if not self.cancel:
                log.info("экзамен %s: остановлен из кабинета", self.job["id"])
            self.cancel = True
            self.kill()                              # каждый раз: отмена могла прийти, пока процесса ещё не было
        return d

    def kill(self):
        """Остановить экзамен со всем, что он запустил (ядро, задачи): вся группа процессов — сначала по-хорошему, через 5 с — сразу."""
        import signal
        p = self.proc
        if not p or p.poll() is not None:
            return
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, AttributeError):
            p.terminate()

        def hard():
            try:
                p.wait(5)
            except Exception:  # noqa: BLE001
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, AttributeError):
                    p.kill()
        threading.Thread(target=hard, daemon=True, name="exam-kill").start()

    def python(self):
        """Окружение экзамена — своё, в папке исполнителя (служба не может менять /opt); ставится один раз."""
        import subprocess
        if os.environ.get("DEWIAR_EXAM_PYTHON"):              # проверки: готовый Python со всем нужным
            return Path(os.environ["DEWIAR_EXAM_PYTHON"])
        venv = self.home / "venv"
        py = venv / "bin/python3"
        if py.exists() and subprocess.run([str(py), "-c", EXAM_PROBE], capture_output=True).returncode == 0:
            return py
        self.post("preparing", note="Ставлю окружение для экзамена — один раз, минуты две")
        r = subprocess.run([sys.executable, "-m", "venv", "--clear", str(venv)], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise RuntimeError("не создалось окружение Python: " + (r.stderr or r.stdout)[-300:])
        r = subprocess.run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", *EXAM_PKGS],
                           capture_output=True, text=True, timeout=1500)
        if r.returncode:
            raise RuntimeError("не поставились библиотеки экзамена (нет доступа к PyPI?): " + (r.stderr or r.stdout)[-300:])
        return py

    def big_pkgs(self, py):
        """openpyxl и playwright — для «Больших задач», по возможности: не поставились — экзамен идёт (Б4, Б6 честно не
        сдаются без openpyxl у модели, Б5 — «не проверено» без браузера). -> поставлены ли."""
        import subprocess
        try:
            if subprocess.run([str(py), "-c", BIG_PROBE], capture_output=True).returncode == 0:
                return True
            self.post("preparing", note="Ставлю библиотеки для больших задач (таблицы, браузер) — один раз")
            r = subprocess.run([str(py), "-m", "pip", "install", "-q", "--disable-pip-version-check", *BIG_PKGS],
                               capture_output=True, text=True, timeout=1500)
        except (OSError, subprocess.TimeoutExpired) as e:
            log.warning("библиотеки больших задач не поставились: %s", e)
            return False
        if r.returncode:
            log.warning("библиотеки больших задач не поставились: %s", (r.stderr or r.stdout)[-300:])
        return r.returncode == 0

    def browser(self, py):
        """Chromium для проверок в браузере (Б5) — в папку исполнителя (PLAYWRIGHT_BROWSERS_PATH), один раз: headless shell
        ~110 МБ скачать, ~260 МБ на диске, 1–3 минуты. Библиотеки системы для него ставит install-runner.sh (от root).
        Не вышло — экзамен идёт без браузера: Б5 в отчёте «не проверено (нет браузера)». -> папка браузеров."""
        import subprocess
        where = self.home / "pw-browsers"
        ok_f, tried = where / ".ok", self.home / "pw-browsers.tried"
        if ok_f.exists():
            return where
        try:
            if time.time() - float(tried.read_text()) < BROWSER_RETRY_S:
                return where
        except (OSError, ValueError):
            pass
        self.post("preparing", note="Ставлю браузер для проверок экзамена (Chromium) — один раз, минуты две")
        env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=str(where))
        env.pop("PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", None)
        r = None
        for args in (["install", "--only-shell", "chromium"], ["install", "chromium"]):   # --only-shell — Playwright 1.49+
            try:
                r = subprocess.run([str(py), "-m", "playwright", *args], env=env, capture_output=True, text=True, timeout=1200)
            except (OSError, subprocess.TimeoutExpired) as e:
                log.warning("браузер экзамена не поставился: %s", e)
                r = None
                break
            if r.returncode == 0:
                break
        try:                                             # место на диске кончилось — не роняем экзамен (рецензия 0.83)
            if r is not None and r.returncode == 0:
                where.mkdir(parents=True, exist_ok=True)
                ok_f.write_text(str(time.time()))
                log.info("браузер экзамена (Chromium) поставлен в %s", where)
            else:
                tried.write_text(str(time.time()))
                log.warning("браузер экзамена не поставился — Б5 будет «не проверено»: %s", ((r.stderr or r.stdout) if r else "")[-300:])
        except OSError as e:
            log.warning("браузер экзамена: %s", e)
        return where

    def _beat(self):
        while not self.done.wait(EXAM_BEAT):
            self.post("stopping" if self.cancel else self.state)

    def run(self):
        try:
            self._run()
        except Exception as e:  # noqa: BLE001
            log.exception("экзамен")
            self.post("failed", note=f"Исполнитель: {e}"[:600])
        finally:
            self.done.set()

    def _run(self):
        import shutil
        import subprocess
        j = self.job
        log.info("экзамен %s: модель %s%s", j["id"], j.get("model"), ", с долгими" if j.get("long") else "")
        self.home.mkdir(parents=True, exist_ok=True)
        self.post("preparing", note="Готовлю экзамен")
        # весточка «жив» — с самого начала: установка окружения и Chromium идёт минутами, отмена из кабинета должна доходить
        threading.Thread(target=self._beat, daemon=True, name="exam-beat").start()
        py = self.python()
        if self.cancel:
            self.post("cancelled")
            return
        # своя папка у каждого прогона: перезапустился исполнитель посреди прогона (кабинет отдал его снова, resume) —
        # partial.json с пройденными сценариями цел, и экзамен продолжается с того места, а не с первого сценария
        out = self.home / "out" / re.sub(r"[^\w-]", "_", str(j["id"]))
        part = out / "partial.json"
        resume = bool(j.get("resume")) and part.exists()
        for old in (self.home / "out").glob("*") if (self.home / "out").is_dir() else []:
            if old != out:
                shutil.rmtree(old, ignore_errors=True) if old.is_dir() else old.unlink(missing_ok=True)
        if not resume:
            shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True, exist_ok=True)
        rep_f = out / "report.json"
        rep_f.unlink(missing_ok=True)
        prof = {"name": "Dewiar Облако", "kind": "openai", "base_url": f"{URL}?p=", "api_key": _cred(j["grant"]),
                "model": j.get("model") or MODEL, "cloud": True, "title": j.get("title") or j.get("model") or MODEL}
        env = {k: v for k, v in os.environ.items() if k not in ("DEWIAR_RUNNER_KEY",)}
        env.update(DEWIAR_EXAM_LLM=json.dumps(prof, ensure_ascii=False), PYTHONUNBUFFERED="1", HOME=str(self.home))
        if j.get("big") and not os.environ.get("DEWIAR_EXAM_PYTHON") and self.big_pkgs(py) and not self.cancel:
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(self.browser(py))   # большие задачи: Б5 — в браузере
        args = [str(py), str(Path(__file__).resolve().parent / "exam.py"), "--out", str(out), "--json-out", str(rep_f)]
        if j.get("long"):
            args.append("--long")
        if j.get("big"):                        # большие задачи (кабинет → «Экзамен» → галочка «Большие задачи»)
            args.append("--big")
        if j.get("lean"):                       # проба короткой инструкции (кабинет → «Экзамен» → галочка)
            args.append("--lean")
        if j.get("only"):
            args += ["--only", ",".join(j["only"])]
        args += ["--partial", str(part)] + (["--resume"] if resume else [])
        self.post("running", note="Продолжаю экзамен с места, где исполнитель перезапустился" if resume else "Экзамен идёт")
        if self.cancel:                              # остановили, пока готовились, — не начинаем
            self.post("cancelled")
            return
        # своя группа процессов: при отмене гасится всё — и exam.py, и ядро, и то, что ядро запустило
        self.proc = subprocess.Popen(args, cwd=str(self.home), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                     start_new_session=True)
        if self.cancel:
            self.kill()
        tail = []
        for line in self.proc.stdout:
            line = line.rstrip()
            tail = (tail + [line])[-40:]
            m = re.match(r"^\[(\d+)/(\d+)\] (.+)$", line)
            if m:
                self.where = {"i": int(m[1]), "n": int(m[2]), "title": m[3][:160]}
                self.post("running")
        code = self.proc.wait()
        self.done.set()
        if code == EXAM_CANCELLED and not self.cancel:   # exam.py сам увидел 403: доступ к модели отозван — остановлен
            self.cancel = True
            log.info("экзамен %s: доступ к модели отозван — остановлен", j["id"])
        if self.cancel:
            self.post("cancelled", note="Остановлен")
            return
        if code or not rep_f.exists():
            self.post("failed", note="\n".join(tail)[-1500:])
            return
        d = self.post("done", report=json.loads(rep_f.read_text(encoding="utf-8")))
        log.info("экзамен %s: готов, в кабинете №%s", j["id"], d.get("run"))


def _now_ms():
    return int(time.time() * 1000)


class CloudToolbox:
    """Инструменты чата для задачи в облаке: только поиск и чтение страниц — через облако, доверенностью человека."""

    SPECS = [
        {"name": "web_search", "description": "Найти в интернете свежую информацию (новости, погода, курсы, факты). "
         "Возвращает список результатов со ссылками.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                                                                        "required": ["query"]}},
        {"name": "read_webpage", "description": "Прочитать текст страницы по ссылке (после web_search — чтобы узнать подробности).",
         "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}},
        {"name": "use_skill", "description": "Загрузить инструкции навыка по имени (из списка навыков) и следовать им.",
         "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
        {"name": "read_skill_file", "description": "Прочитать дополнительный файл навыка (путь из списка файлов навыка).",
         "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "path": {"type": "string"}}, "required": ["name", "path"]}},
    ]

    def __init__(self, cred):
        self.cred = cred

    def specs(self):
        return list(self.SPECS)

    def policy(self, name):
        return True, False

    def guard(self, name, args):
        return False, False, ""

    def describe(self, name, args):
        return name

    def run(self, name, args):
        if name == "use_skill":
            return skills().use(str(args.get("name", "")))
        if name == "read_skill_file":
            return skills().read_file(str(args.get("name", "")), str(args.get("path", "")))
        h = {"Authorization": "Bearer " + self.cred}
        if name == "web_search":
            r = httpx.get(URL, params={"p": "/search", "q": str(args.get("query") or "")[:400]}, headers=h, timeout=40)
            d = r.json()
            if r.status_code >= 400:
                return "Поиск не удался: " + str((d.get("error") or {}).get("message") or r.status_code)
            res = d.get("results") or []
            return "\n\n".join(f"{i + 1}. {x.get('title')}\n{x.get('url')}\n{x.get('snippet')}" for i, x in enumerate(res)) or "Ничего не нашлось."
        if name in ("read_webpage", "read_page"):     # read_page — старое имя (так звали подсказки до 0.83)
            r = httpx.get(URL, params={"p": "/fetch", "url": str(args.get("url") or "")}, headers=h, timeout=60)
            d = r.json()
            if r.status_code >= 400:
                return "Страница не открылась: " + str((d.get("error") or {}).get("message") or r.status_code)
            return str(d.get("text") or "")[:20000]
        return f"Инструмент {name} в облаке недоступен."


class SpaceWorkspace(Workspace):
    """Папка ассистента одного человека на сервере: RUNNER_DIR/<пространство>/Dewiar."""

    def __init__(self, path):
        super().__init__(None)
        self._root = Path(path)

    @property
    def root(self):
        return self._root


class _NoSettings:
    def get(self, *k):
        return None


class CloudTasks(TK.TaskManager):
    """Задачи в облаке: без запуска кода, скачивания, расшифровки и вопросов человеку (CLOUD_SKIP) — ни в профиле, ни через
    find_tool, ни вызовом по имени (рецензия 0.83: find_tool подключал download — запрос на 127.0.0.1 с сервера сайта —
    и ask_user, который ждал ответа вечно)."""

    def _catalog(self, t):
        return {k: v for k, v in super()._catalog(t).items() if k not in CLOUD_SKIP}

    def _specs(self, t):
        return [s for s in super()._specs(t) if s["name"] not in CLOUD_SKIP]

    def _tool_raw(self, t, name, args):
        if name in CLOUD_SKIP:
            return (f"Ошибка: {name} в облаке недоступен — задача идёт на сервере Dewiar, компьютер человека выключен. "
                    "Как исправить: обойдись без него (файлы — write_file, сведения — web_search и read_webpage) и напиши в "
                    "итоге, что сделать не удалось.")
        return super()._tool_raw(t, name, args)

    def _system(self, t):
        return super()._system(t) + CLOUD_NOTE


class Space:
    """Задачи одного человека (пространство синхронизации u<id> или k<id>)."""

    def __init__(self, runner, space, grant):
        self.runner, self.space, self.grant = runner, space, grant
        self.dir = DIR / re.sub(r"[^\w-]", "_", space)
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "grant").write_text(grant, encoding="utf-8")
        os.chmod(self.dir / "grant", 0o600)
        self.workspace = SpaceWorkspace(self.dir / "Dewiar")
        self.toolbox = CloudToolbox(_cred(grant))
        self.s = _NoSettings()
        self.stopping = runner.stopping
        self.reqs = self._load_reqs()                 # id задачи -> id заявки taskreq
        self._dirty, self._lock = set(), threading.Lock()
        self.tasks = CloudTasks(self)

    # ---------- Host для TaskManager ----------
    def persona_name(self):
        return "Агент"

    def memory(self):
        return ""

    def skills_prompt(self):
        return skills().prompt()

    def llm_profile(self):
        return {"name": NAME, "kind": "openai", "base_url": URL + "?p=", "api_key": _cred(self.grant), "model": MODEL}

    def max_steps(self):
        return 80

    def code_auto_run(self):
        return False

    def confirm(self, q):
        return False

    def ask_user(self, t, q):
        pass

    def announce(self, text):
        log.info("[%s] %s", self.space, text)

    def push(self, title, text="", critical=False, file=None):
        log.info("[%s] %s: %s", self.space, title, text)

    def emit(self, kind, **kw):
        t = kw.get("task")
        if kind == "task" and isinstance(t, dict) and t.get("id"):
            with self._lock:
                self._dirty.add(t["id"])

    # ---------- заявки ----------
    def _load_reqs(self):
        try:
            return json.loads((self.dir / "reqs.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_reqs(self):
        (self.dir / "reqs.json").write_text(json.dumps(self.reqs, ensure_ascii=False), encoding="utf-8")

    def busy(self):
        return sum(1 for t in self.tasks.tasks.values() if t.status not in FINAL and t.status != "paused")

    def take(self, req):
        """Занять заявку в облаке и начать задачу. -> True, если заняли."""
        d = dict(req["data"])
        r = self.sync([{"kind": "taskreq", "id": req["id"], "data": dict(d, taken_by=DEVICE), "updated": _now_ms(), "prev": req["updated"]}])
        if r is None or "taskreq:" + req["id"] in (r.get("lost") or []):
            return False
        goal = str(d.get("goal") or d.get("title") or "").strip()
        t = self.tasks.create(str(d.get("title") or goal[:50]), goal + "\n\n(Задачу поставили с телефона — результат он увидит.)")
        self.reqs[t.id] = req["id"]
        self._save_reqs()
        with self._lock:
            self._dirty.add(t.id)
        log.info("[%s] взял задачу «%s»", self.space, t.title)
        return True

    # ---------- обмен с облаком ----------
    def sync(self, changes):
        body = {"since": 1 << 60, "device": DEVICE, "name": NAME, "kinds": ["taskreq", "task"], "changes": changes}
        try:
            r = httpx.post(URL, params={"p": "/sync"}, json=body, headers={"Authorization": "Bearer " + _cred(self.grant)}, timeout=40)
            return r.json() if r.status_code < 400 else None
        except (httpx.HTTPError, ValueError) as e:
            log.info("[%s] синхронизация: %s", self.space, e)
            return None

    def _upload(self, t):
        """Файлы-результаты задачи — в облако (один раз каждый). -> [{name, id, size, title}]."""
        sent = t.data.setdefault("cloud_files", {})
        outs = [(o.get("path"), o.get("title")) for o in t.data.get("outputs") or []]
        if not outs and (t.dir / "outputs").is_dir():
            outs = [(p.relative_to(t.dir).as_posix(), p.stem) for p in sorted((t.dir / "outputs").rglob("*")) if p.is_file()][:8]
        files = []
        for rel, title in outs[:12]:
            p = t.dir / str(rel or "")
            if not p.is_file() or p.stat().st_size > FILE_MAX:
                continue
            key = f"{rel}|{p.stat().st_size}|{int(p.stat().st_mtime)}"
            if key not in sent:
                try:
                    r = httpx.post(URL, params={"p": "/files", "name": p.name}, content=p.read_bytes(),
                                   headers={"Authorization": "Bearer " + _cred(self.grant)}, timeout=120)
                    if r.status_code >= 400:
                        continue
                    sent[key] = r.json()["id"]
                except (httpx.HTTPError, ValueError, KeyError):
                    continue
            files.append({"name": p.name, "id": sent[key], "size": p.stat().st_size, "title": str(title or p.stem)[:120]})
        t.save()
        return files

    def flush(self):
        """Ход изменившихся задач — в синхронизацию; законченные — с файлами, и их заявки из очереди удаляем."""
        with self._lock:
            ids, self._dirty = self._dirty, set()
        changes, sent_del = [], []
        for tid in ids:
            t = self.tasks.tasks.get(tid)
            if t is None:
                continue
            dd = t.data
            item = {"title": dd.get("title", ""), "status": dd.get("status", ""), "goal": str(dd.get("goal", ""))[:400],
                    "result": str(dd.get("result", ""))[:4000], "error": str(dd.get("error", ""))[:300],
                    "activity": str(dd.get("activity", ""))[:200], "updated": dd.get("updated", ""), "created": dd.get("created", ""),
                    "outputs": [str(o.get("path", ""))[-80:] for o in (dd.get("outputs") or [])][:8], "where": "cloud",
                    "steps": dd.get("steps", 0)}
            if t.status in FINAL:
                item["files"] = self._upload(t)
            changes.append({"kind": "task", "id": "c" + t.id, "data": item, "updated": _now_ms()})
            if t.status in FINAL and tid in self.reqs:
                changes.append({"kind": "taskreq", "id": self.reqs[tid], "data": {}, "updated": _now_ms(), "deleted": True})
                sent_del.append(tid)
        if not changes:
            return
        if self.sync(changes) is None:                     # облако не ответило — повторим в следующий раз
            with self._lock:
                self._dirty |= ids
            return
        # забываем только те заявки, удаление которых правда ушло: задача, закончившаяся, пока шёл этот обмен, ещё помечена
        # «изменилась» — её удаление уйдёт следующим (раньше заявка забывалась без удаления и висела в очереди — проверка моргала)
        done = [tid for tid in ids if tid in self.reqs and (self.tasks.tasks.get(tid) is None or tid in sent_del)]
        for tid in done:
            self.reqs.pop(tid, None)
        if done:
            self._save_reqs()


class Runner:
    def __init__(self):
        self.spaces, self.stopping = {}, threading.Event()
        self.exam = None
        DIR.mkdir(parents=True, exist_ok=True)
        for d in sorted(DIR.iterdir()) if DIR.is_dir() else []:      # после перезапуска — продолжить начатое
            g = d / "grant"
            if d.is_dir() and g.exists() and (d / "reqs.json").exists():
                try:
                    sp = Space(self, d.name, g.read_text(encoding="utf-8").strip())
                    if sp.reqs:
                        self.spaces[d.name] = sp
                except Exception:  # noqa: BLE001
                    log.exception("пространство %s", d.name)

    def busy(self):
        return sum(s.busy() for s in self.spaces.values())

    def pending(self):
        try:
            r = httpx.get(URL, params={"p": "/runner/pending"}, timeout=30,
                          headers={"X-Runner-Key": KEY, "X-Runner-Host": HOST, "X-Runner-Version": VERSION,   # кабинет → «Сервер»
                                   "X-Runner-Lan": LAN})
            if r.status_code >= 400:
                log.warning("Очередь задач: облако ответило %s", r.status_code)
                return []
            d = r.json()
            self.exam_offer(d.get("exam"))
            return d.get("tasks") or []
        except (httpx.HTTPError, ValueError) as e:
            log.info("Очередь задач: %s", e)
            return []

    def exam_offer(self, job):
        """Кабинет просит экзамен: один за раз; тот же, что уже идёт, — не начинаем заново."""
        if not job or not job.get("id") or not job.get("grant"):
            return
        if self.exam and self.exam.is_alive():
            return
        if self.exam and self.exam.job.get("id") == job["id"]:
            return                                       # этот уже прошёл (итог отправлен) — кабинет вот-вот узнает
        self.exam = ExamJob(job)
        self.exam.start()

    def once(self):
        for req in self.pending():
            if self.busy() >= PARALLEL:
                break
            sp = self.spaces.get(req["space"])
            if sp is None:
                sp = self.spaces[req["space"]] = Space(self, req["space"], req["grant"])
            else:
                sp.grant = req["grant"]                 # свежая доверенность (прежняя могла истечь)
                sp.toolbox.cred = _cred(req["grant"])
                (sp.dir / "grant").write_text(req["grant"], encoding="utf-8")
            if req["id"] in sp.reqs.values():
                continue
            try:
                sp.take(req)
            except Exception:  # noqa: BLE001
                log.exception("задача %s/%s", req["space"], req["id"])
        for sp in list(self.spaces.values()):
            sp.flush()

    def run(self):
        log.info("Исполнитель задач Dewiar: %s, папки %s, одновременно %d", URL, DIR, PARALLEL)
        while not self.stopping.is_set():
            try:
                self.once()
            except Exception:  # noqa: BLE001
                log.exception("исполнитель")
            self.stopping.wait(POLL)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    for noisy in ("httpx", "httpcore"):          # опрос очереди каждые несколько секунд — не засоряем журнал службы
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if len(KEY) < 24:
        sys.exit("Нет ключа исполнителя: DEWIAR_RUNNER_KEY (на сервере сайта: php cloud.php runner-key)")
    Runner().run()


if __name__ == "__main__":
    main()
