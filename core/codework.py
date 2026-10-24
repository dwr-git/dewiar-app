"""Режим «Код»: работа над проектом пользователя в отдельной рабочей копии — сам проект не меняется, пока
пользователь не примет изменения.
  • git-проект — рабочая копия через `git worktree`; незакоммиченные и неотслеживаемые файлы переносятся в неё
    и фиксируются служебным коммитом «исходное состояние»; изменения = diff от этого коммита;
  • без git — копия папки (без IGNORE_DIRS); изменения = побайтовое сравнение файлов.
Режим и исходный коммит лежат в «код.json» рядом с копией. «Принять» (accept) переносит изменения в проект
(git apply или копирование), «Отклонить» (discard) удаляет копию. Создаёт и вызывает — tasks.py.
Все пути инструментов проходят через path(): выход за пределы рабочей копии запрещён.
"""

import difflib
import fnmatch
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path, PurePosixPath

log = logging.getLogger("dewiar.code")

IGNORE_DIRS = {".git", ".ruff_cache", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".mypy_cache", ".idea",
               ".pytest_cache", "target", ".next", ".cache", ".tox", ".gradle", ".dewiar"}
MAX_COPY = 400 * 1024 * 1024        # проект без git крупнее не копируем целиком — просим git init
# мусор от запусков (кэши, байткод) в изменения не попадает: исключается из git add
JUNK = ["__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache", "node_modules", ".ruff_cache", ".coverage"]
GIT_ADD = ["add", "-A", "--", "."] + [f":(exclude,glob)**/{j}" for j in JUNK] + [f":(exclude,glob)**/{j}/**" for j in JUNK]
GIT_ENV = {"GIT_AUTHOR_NAME": "Dewiar", "GIT_AUTHOR_EMAIL": "dewiar@localhost", "GIT_COMMITTER_NAME": "Dewiar",
           "GIT_COMMITTER_EMAIL": "dewiar@localhost"}


class CodeError(Exception):
    """Ошибка, текст которой показывается модели или пользователю как есть."""
    pass


def _git(cwd, *args, check=True, input_=None):
    """Запустить git в cwd -> stdout строкой. input_ байтами — для двоичных патчей. check: при ошибке CodeError.
    Автор коммитов — Dewiar (GIT_ENV), чтобы не зависеть от настроек git пользователя; 0x08000000 — CREATE_NO_WINDOW
    (Windows: без мелькающего окна консоли)."""
    txt = input_ is None or isinstance(input_, str)
    r = subprocess.run(["git", "-C", str(cwd)] + list(args), capture_output=True, text=txt,
                       encoding="utf-8" if txt else None, errors="replace" if txt else None,
                       input=input_, env=dict(os.environ, **GIT_ENV), timeout=120,
                       creationflags=0x08000000 if os.name == "nt" else 0)
    if check and r.returncode:
        raise CodeError(f"git {' '.join(args[:2])}: {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout if isinstance(r.stdout, str) else r.stdout.decode(errors="replace")


def _walk(root: Path, limit=5000):
    """Файлы проекта -> [PurePosixPath относительно root], отсортированные, без IGNORE_DIRS; не больше limit."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".dewiar"))
        for f in sorted(filenames):
            out.append(PurePosixPath(Path(dirpath, f).relative_to(root).as_posix()))   # «/» и в Windows
            if len(out) >= limit:
                return out
    return out


MAX_PROCS = 4
_RUNNING = {}                                   # pid -> Popen (в этом запуске программы)


def _alive(x):
    pr = _RUNNING.get(x.get("pid"))
    if pr is not None:
        return pr.poll() is None
    if os.name == "nt":
        return False                              # после перезапуска программы о старых процессах не знаем
    try:
        os.kill(int(x["pid"]), 0)
        return True
    except (OSError, ValueError, KeyError):
        return False


def _kill(x):
    pid = int(x.get("pid") or 0)
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=0x08000000)
        else:
            import signal
            os.killpg(pid, signal.SIGTERM)       # вся группа: bash и запущенный им сервер
            for _ in range(20):
                if not _alive(x):
                    break
                time.sleep(0.1)
            else:
                os.killpg(pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    pr = _RUNNING.pop(pid, None)
    if pr is not None:
        try:
            pr.wait(3)
        except subprocess.TimeoutExpired:
            pass


def _tail(path, n):
    try:
        b = Path(path).read_bytes()
    except OSError:
        return "(вывода нет)"
    t = b[-n * 2:].decode("utf-8", errors="replace")[-n:]
    return t.strip() or "(пока пусто)"


def check_syntax(p, rel):
    """После записи: Python и JSON — проверить, что файл разбирается. -> "" или предупреждение для модели."""
    try:
        if p.suffix == ".py":
            compile(p.read_text(encoding="utf-8"), str(rel), "exec")
        elif p.suffix == ".json":
            import json
            json.loads(p.read_text(encoding="utf-8"))
    except SyntaxError as e:
        return (f"\n⚠ После правки файл не разбирается: SyntaxError, строка {e.lineno}: {e.msg}"
                + (f"\n    {e.text.rstrip()}" if e.text else "") + "\nИсправь это сразу.")
    except ValueError as e:
        return f"\n⚠ После правки JSON не разбирается: {e}. Исправь это сразу."
    except OSError:
        pass
    return ""


def _norm_line(ln):
    return " ".join(ln.split())


def fuzzy_find(text, old):
    """Найти old в text, не глядя на отступы и пробелы внутри строк. -> (начало, конец, сдвиг отступа) или None.
    Сдвиг — сколько пробелов добавить к строкам new (у модели отступ меньше, чем в файле) или убрать (отрицательный).
    Только если совпадение одно."""
    want = [_norm_line(x) for x in old.strip("\n").split("\n")]
    while want and not want[-1]:
        want.pop()
    if not want or not any(want):
        return None
    lines = text.split("\n")
    hits = []
    for i in range(len(lines) - len(want) + 1):
        if all(_norm_line(lines[i + k]) == want[k] for k in range(len(want))):
            hits.append(i)
            if len(hits) > 1:
                return None
    if not hits:
        return None
    i = hits[0]
    start = sum(len(x) + 1 for x in lines[:i])
    end = start + sum(len(x) + 1 for x in lines[i:i + len(want)]) - 1
    return start, end, lines[i:i + len(want)]


def reindent(old, file_lines, new):
    """Отступы new — как в файле: строки new сопоставляются со строками old (difflib), и каждая берёт отступ своей
    строки файла плюс свою разницу с old; вставленные — от предыдущей строки. Так правка с «плоскими» отступами
    модели ложится в файл с правильной вложенностью."""
    ind = lambda x: len(x) - len(x.lstrip())                       # noqa: E731
    old_l = old.strip("\n").split("\n")
    while old_l and not old_l[-1].strip():
        old_l.pop()
    new_l = new.strip("\n").split("\n")
    sm = difflib.SequenceMatcher(None, [_norm_line(x) for x in old_l], [_norm_line(x) for x in new_l], autojunk=False)
    pair = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                pair[j1 + k] = i1 + k
    out, prev = [], None
    for j, ln in enumerate(new_l):
        if not ln.strip():
            out.append("")
            continue
        if j in pair and pair[j] < len(file_lines):
            i = pair[j]
            d = ind(file_lines[i]) + ind(ln) - ind(old_l[i])
        elif prev:
            d = prev[1] + ind(ln) - prev[0]
        else:
            d = ind(file_lines[0]) + ind(ln) - ind(old_l[0])
        d = max(0, d)
        out.append(" " * d + ln.lstrip())
        prev = (ind(ln), d)
    return "\n".join(out)


def nearest(text, old):
    """Подсказка: самый похожий кусок файла с номерами строк (когда фрагмент не нашёлся)."""
    want = old.strip("\n").split("\n")
    lines = text.split("\n")
    if not lines or not want:
        return ""
    n = len(want)
    best, at = 0.0, 0
    key = "\n".join(_norm_line(x) for x in want)
    for i in range(0, max(1, len(lines) - n + 1)):
        r = difflib.SequenceMatcher(None, key, "\n".join(_norm_line(x) for x in lines[i:i + n])).quick_ratio()
        if r > best:
            best, at = r, i
    if best < 0.5:
        return " Похожего куска нет — прочитай файл (code_read) заново."
    body = "\n".join(f"{j + 1:5d}  {lines[j]}" for j in range(at, min(len(lines), at + n)))
    return f" Самый похожий кусок (строки {at + 1}–{at + n}):\n{body}"


def run_hint(command, out, code, cwd):
    """Подсказка к выводу команды: частые тупики слабых моделей."""
    low = out.lower()
    if "no module named pytest" in low:
        return ("\nПодсказка: pytest здесь не установлен — запусти тесты так: python3 -m unittest discover -s tests -t . -q "
                "(или pip install pytest, если это нужно проекту).")
    if code == 127 or "command not found" in low:
        return "\nПодсказка: такой программы здесь нет — проверь имя или обойдись без неё."
    if code == 5 and "pytest" in command and "no tests ran" in low:
        return "\nПодсказка: pytest не нашёл тестов — проверь путь или имена файлов (test_*.py)."
    return ""


def test_command(root):
    """Как запускать тесты проекта (по его файлам) -> команда или None."""
    import json
    root = Path(root)
    py = "python" if os.name == "nt" else "python3"
    has_py_tests = any(root.glob("tests/test_*.py")) or any(root.glob("test_*.py")) or any(root.glob("tests/**/test_*.py"))
    cfg = " ".join((root / f).read_text(encoding="utf-8", errors="replace") for f in ("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini")
                   if (root / f).is_file())
    if has_py_tests or "[tool.pytest" in cfg or "[pytest]" in cfg:
        r = subprocess.run([py, "-c", "import pytest"], capture_output=True, cwd=root)
        if r.returncode == 0:
            return f"{py} -m pytest -q"
        if (root / "tests").is_dir():
            return f"{py} -m unittest discover -s tests -t . -q"
        return f"{py} -m unittest discover -q"
    pj = root / "package.json"
    if pj.is_file():
        try:
            t = (json.loads(pj.read_text(encoding="utf-8")).get("scripts") or {}).get("test", "")
        except ValueError:
            t = ""
        if t and "no test specified" not in t:
            return "npm test --silent"
    if (root / "Cargo.toml").is_file():
        return "cargo test -q"
    if (root / "go.mod").is_file():
        return "go test ./..."
    return None


def overview(root, limit=6000):
    """Карта проекта для начала работы: дерево файлов (сжато), функции и классы Python/JS, команда тестов."""
    root = Path(root)
    files = _walk(root, limit=3000)
    lines = [f"Файлов: {len(files)}" + (" (показаны первые)" if len(files) > 150 else "")]
    for f in files[:150]:
        lines.append(f"  {f}")
    sym = []
    for f in files[:400]:
        if f.suffix not in (".py", ".js", ".ts", ".mjs") or f.parts[0] in ("tests", "test") and len(sym) > 40:
            continue
        try:
            src = (root / f).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(src) > 400_000:
            continue
        rx = r"^(?:class|def|async def)\s+(\w+)" if f.suffix == ".py" else r"^(?:export\s+)?(?:async\s+)?(?:function|class)\s+(\w+)"
        names = re.findall(rx, src, re.M)
        if names:
            sym.append(f"  {f}: " + ", ".join(names[:25]) + (" …" if len(names) > 25 else ""))
    if sym:
        lines += ["Функции и классы:"] + sym[:120]
    tc = test_command(root)
    lines.append(f"Тесты: {tc}" if tc else "Тестов не нашёл.")
    out = "\n".join(lines)
    return out[:limit] + ("\n…" if len(out) > limit else "")


class CodeWork:
    def __init__(self, project, work_dir):
        self.project = Path(project).expanduser().resolve()
        self.work = Path(work_dir)
        self.meta = self.work.parent / "код.json"
        self.git = (self.project / ".git").exists() and shutil.which("git") is not None

    # ---------- подготовка ----------

    def prepare(self):
        """Создать рабочую копию, если её ещё нет (пишет «код.json»). Проект без единого коммита копируется как без git."""
        if not self.project.is_dir():
            raise CodeError(f"папки проекта нет: {self.project}")
        if self.work.exists():
            return
        self.work.parent.mkdir(parents=True, exist_ok=True)
        if self.git and _git(self.project, "rev-parse", "--verify", "HEAD", check=False).strip():
            _git(self.project, "worktree", "add", "--detach", str(self.work), "HEAD")
            patch = subprocess.run(["git", "-C", str(self.project), "diff", "HEAD", "--binary"], capture_output=True).stdout
            if patch.strip():
                subprocess.run(["git", "-C", str(self.work), "apply", "--whitespace=nowarn"], input=patch, capture_output=True)
            # GitHub #16 (24.10): без -z git отдаёт «новый.py» C-кавычками ("\320\275…"), и файл не находился —
            # в копию не попадали неотслеживаемые файлы с кириллицей. С -z имена как есть, через NUL.
            for rel in filter(None, _git(self.project, "ls-files", "-z", "--others", "--exclude-standard").split("\0")):
                src, dst = self.project / rel, self.work / rel
                if src.is_file():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            _git(self.work, "add", "-A")
            _git(self.work, "commit", "-q", "--allow-empty", "--no-verify", "-m", "dewiar: исходное состояние")
            base = _git(self.work, "rev-parse", "HEAD").strip()
            self.meta.write_text(f'{{"mode": "git", "base": "{base}"}}', encoding="utf-8")
        else:
            size = 0
            for rel in _walk(self.project, limit=200000):
                try:
                    size += (self.project / rel).stat().st_size
                except OSError:                    # №222 (24.10): сетевая папка, файл с ключами без доступа — пропускаем
                    continue
                if size > MAX_COPY:
                    raise CodeError("проект без git больше 400 МБ — инициализируйте git (git init), и я возьму его рабочей копией")
            skipped = []
            try:
                shutil.copytree(self.project, self.work, ignore=shutil.ignore_patterns(*IGNORE_DIRS), symlinks=True)
            except shutil.Error as e:              # часть файлов не прочиталась (нет доступа) — работаем с остальными
                bad = e.args[0] if e.args and isinstance(e.args[0], list) else []
                log.warning("Рабочая копия: не скопировано файлов без доступа — %d", len(bad))
                # GitHub #14 (24.10): нескопированный файл _copy_changes считал удалённым, и «Принять» стирал оригинал.
                # Запоминаем такие пути: их исходного состояния копия не видела — accept их не удаляет и не перезаписывает.
                for item in bad:
                    try:
                        src, dst = Path(item[0]), Path(item[1])
                        rel = src.relative_to(self.project).as_posix()
                    except (TypeError, ValueError, IndexError):
                        continue
                    if dst.is_file() and not src.is_dir():
                        dst.unlink(missing_ok=True)   # обрывок файла после сбоя чтения — не выдаём модели за целый
                    elif dst.exists():
                        continue                      # папка скопирована, не удались только её атрибуты (copystat)
                    skipped.append(rel)
            import json
            self.meta.write_text(json.dumps({"mode": "copy", "skipped": sorted(set(skipped))}, ensure_ascii=False),
                                 encoding="utf-8")
        log.info("Рабочая копия: %s → %s", self.project, self.work)

    @property
    def mode(self):
        import json
        try:
            return json.loads(self.meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"mode": "none"}

    def _to_work(self, text):
        """Путь исходного проекта в пути или команде -> путь рабочей копии (модель видит путь проекта в подсказке и
        делает «cd /путь/проекта && pytest» — а её правки лежат в рабочей копии). -> (текст, заменили ли)."""
        src, dst = str(self.project), str(self.work)
        if not src or src == dst or src not in (text or ""):
            return text, False
        out, i = [], 0
        for m in re.finditer(re.escape(src) + r"(?P<tail>[^\s'\";&|)]*)", text):
            out.append(text[i:m.start()])
            quoted = m.start() > 0 and text[m.start() - 1] in "'\""
            new = dst + m.group("tail")
            out.append(new if quoted or " " not in new else ("'" + new.replace("'", "'\\''") + "'"))
            i = m.end()
        out.append(text[i:])
        return "".join(out), True

    def path(self, rel):
        """Безопасность: путь из инструмента модели -> абсолютный внутри рабочей копии; «..» и ссылки наружу — CodeError."""
        rel = str(rel or ".")
        if str(self.project) and str(self.project) != str(self.work) and rel.startswith(str(self.project)):
            rel = str(self.work) + rel[len(str(self.project)):]          # путь исходного проекта — в рабочую копию
        if os.path.isabs(rel) and (rel == str(self.work) or rel.startswith(str(self.work) + os.sep)):
            rel = os.path.relpath(rel, self.work)
        p = (self.work / str(rel or ".").lstrip("/")).resolve()
        if p != self.work.resolve() and self.work.resolve() not in p.parents:
            raise CodeError("путь вне проекта")
        return p

    # ---------- инструменты ----------

    def list(self, pattern="", limit=400):
        files = [str(p) for p in _walk(self.work)]
        if pattern:
            files = [f for f in files if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(Path(f).name, pattern) or pattern in f]
        more = len(files) - limit
        return "\n".join(files[:limit]) + (f"\n… и ещё {more}" if more > 0 else "") if files else "(ничего)"

    def read(self, rel, start=1, end=None):
        p = self.path(rel)
        if not p.is_file():
            raise CodeError(f"нет файла {rel}")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start or 1))
        end = min(len(lines), int(end) if end else start + 399)
        body = "\n".join(f"{i:5d}  {lines[i - 1]}" for i in range(start, end + 1))
        tail = f"\n… всего строк: {len(lines)}; дальше — read с start={end + 1}" if end < len(lines) else ""
        return (body or "(пустой файл)") + tail

    def search(self, pattern, glob="", limit=80):
        if shutil.which("rg"):
            cmd = ["rg", "-n", "--no-heading", "--max-columns", "200", "-e", pattern]
            if glob:
                cmd += ["-g", glob]
            cmd.append(".")                                  # без пути rg читал бы stdin
            r = subprocess.run(cmd, cwd=self.work, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL,
                               encoding="utf-8", errors="replace")
            lines = r.stdout.splitlines()
        else:
            try:
                rx = re.compile(pattern)
            except re.error:
                rx = re.compile(re.escape(pattern))
            lines = []
            for rel in _walk(self.work):
                if glob and not fnmatch.fnmatch(str(rel), glob) and not fnmatch.fnmatch(rel.name, glob):
                    continue
                try:
                    for i, ln in enumerate((self.work / rel).read_text(encoding="utf-8").splitlines(), 1):
                        if rx.search(ln):
                            lines.append(f"{rel}:{i}:{ln[:200]}")
                except (UnicodeDecodeError, OSError):
                    continue
                if len(lines) > limit * 2:
                    break
        more = len(lines) - limit
        return "\n".join(lines[:limit]) + (f"\n… и ещё {more}" if more > 0 else "") if lines else "Не найдено."

    def write(self, rel, content):
        p = self.path(rel)
        self._snap(rel, p)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content or "", encoding="utf-8")
        return f"{'Изменён' if existed else 'Создан'} {rel} ({len((content or '').splitlines())} строк)" + check_syntax(p, rel)

    def edit(self, rel, old, new):
        p = self.path(rel)
        if not p.is_file():
            raise CodeError(f"нет файла {rel}")
        text = p.read_text(encoding="utf-8")
        if not old:
            raise CodeError("old пустой — укажи фрагмент, который заменить (или code_write для нового файла)")
        n = text.count(old)
        if n > 1:
            lines = [text[:m.start()].count("\n") + 1 for m in re.finditer(re.escape(old), text)][:8]
            raise CodeError(f"фрагмент встречается {n} раз (строки {', '.join(map(str, lines))}) — возьми кусок побольше, "
                            "чтобы он был единственным")
        note = ""
        if n == 0:                                     # слабые модели путают отступы и пробелы в конце строк — ищем мягче
            span = fuzzy_find(text, old)
            if span is None:
                raise CodeError("фрагмент не найден — скопируй кусок точно, с отступами." + nearest(text, old))
            a_, b_, file_lines = span
            new = reindent(old, file_lines, new)
            old = text[a_:b_]
            note = " (фрагмент найден без учёта отступов и пробелов — проверь результат)"
        self._snap(rel, p)
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        at = text.find(old)
        line = text[:at].count("\n") + 1
        return f"Изменён {rel}, строки {line}–{line + new.count(chr(10))}{note}" + check_syntax(p, rel)

    def delete(self, rel):
        p = self.path(rel)
        if not p.exists():
            raise CodeError(f"нет {rel}")
        if p.is_file():
            self._snap(rel, p)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"Удалён {rel}"

    def run(self, command, timeout=180):
        command, moved = self._to_work(command)
        note = ("\n(Путь проекта в команде заменён на рабочую копию — твои правки здесь. Команды и так выполняются в ней: "
                "cd не нужен.)" if moved else "")
        return self._run(command, timeout) + note

    def _run(self, command, timeout=180):
        timeout = max(5, min(900, int(timeout or 180)))
        try:
            if os.name == "nt":                    # Windows: PowerShell; вывод переключаем на UTF-8, иначе кириллица — кракозябры
                ps = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + command
                r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], cwd=self.work,
                                   capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                                   env=dict(os.environ, PYTHONIOENCODING="utf-8", **GIT_ENV), stdin=subprocess.DEVNULL,
                                   creationflags=0x08000000)
            else:
                r = subprocess.run(["bash", "-lc", command], cwd=self.work, capture_output=True, text=True, timeout=timeout,
                                   env=dict(os.environ, **GIT_ENV), stdin=subprocess.DEVNULL)
            out, code = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip(), r.returncode
        except subprocess.TimeoutExpired as e:
            out, code = f"{e.stdout or ''}\nОстановлено: дольше {timeout} с".strip(), -1
        if len(out) > 6000:                        # модели нужны начало (команда, первые ошибки) и конец (итог)
            out = out[:1500] + "\n…\n" + out[-4400:]
        return f"Код завершения {code}\n{out}" + run_hint(command, out, code, self.work)

    # ---------- изменения ----------

    def _copy_changes(self):
        """Без git: [(статус, путь)] — файлы, которые отличаются от проекта. Читает все файлы целиком."""
        work = {str(p) for p in _walk(self.work, limit=200000)}
        proj = {str(p) for p in _walk(self.project, limit=200000)}
        skipped = self.mode.get("skipped") or []
        changed = []
        for rel in sorted(work | proj):
            a, b = self.project / rel, self.work / rel
            if rel in proj and any(rel == s or rel.startswith(s + "/") for s in skipped):
                continue                              # GitHub #14 (24.10): не скопировался при подготовке — не трогаем
            if rel not in proj:
                changed.append(("added", rel))
            elif rel not in work:
                changed.append(("deleted", rel))
            elif a.read_bytes() != b.read_bytes():
                changed.append(("modified", rel))
        return changed

    def changes(self):
        """[(статус, путь)] — что изменено в рабочей копии; статус: "added" | "deleted" | "modified".
        В git-режиме заодно индексирует рабочую копию (git add), переименование считается изменением нового пути."""
        if not self.work.exists():
            return []
        m = self.mode
        if m.get("mode") == "git":
            _git(self.work, *GIT_ADD)
            # GitHub #16 (24.10): -z — и здесь имена с кириллицей без C-кавычек; R/C — два пути, берём новый
            parts = _git(self.work, "diff", "--cached", "-z", "--name-status", m["base"]).split("\0")
            res, i = [], 0
            while i < len(parts) and parts[i]:
                st = parts[i]
                k = 2 if st[0] in "RC" else 1
                rel = parts[i + k] if i + k < len(parts) else ""
                i += k + 1
                if rel:
                    res.append(({"A": "added", "D": "deleted"}.get(st[0], "modified"), rel))
            return res
        return self._copy_changes()

    # ---------- откат правок ----------

    def _snap(self, rel, p):
        """Перед правкой — снимок файла (как был) в стопку отката (папка задачи, _undo). Большие и двоичные — без снимка."""
        try:
            d = self.work.parent / "_undo"
            d.mkdir(parents=True, exist_ok=True)
            existed = p.is_file()
            text = p.read_text(encoding="utf-8") if existed and p.stat().st_size <= 2_000_000 else ""
            if existed and not text and p.stat().st_size:
                return
            import json
            n = len(list(d.glob("*.json")))
            (d / f"{n + 1:05d}.json").write_text(json.dumps({"path": str(rel), "existed": existed, "text": text},
                                                            ensure_ascii=False), encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            log.debug("снимок для отката: %s", rel, exc_info=True)

    def undo(self, steps=1):
        """Отменить последние steps правок (code_write / code_edit / code_delete) -> что вернули."""
        import json
        d = self.work.parent / "_undo"
        snaps = sorted(d.glob("*.json")) if d.is_dir() else []
        if not snaps:
            return "Откатывать нечего: правок ещё не было."
        done = []
        for f in reversed(snaps[-max(1, min(int(steps or 1), 50)):]):
            sn = json.loads(f.read_text(encoding="utf-8"))
            p = self.path(sn["path"])
            if sn["existed"]:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(sn["text"], encoding="utf-8")
                done.append(f"{sn['path']} — как было")
            else:
                p.unlink(missing_ok=True)
                done.append(f"{sn['path']} — удалён (его создала правка)")
            f.unlink()
        return f"Отменено правок: {len(done)}\n" + "\n".join(done)

    # ---------- фоновые процессы (сервер, наблюдатель) ----------

    def _procs_file(self):
        return self.work.parent / "_proc" / "процессы.json"

    def _procs(self):
        import json
        try:
            return json.loads(self._procs_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

    def _save_procs(self, procs):
        import json
        self._procs_file().parent.mkdir(parents=True, exist_ok=True)
        self._procs_file().write_text(json.dumps(procs, ensure_ascii=False), encoding="utf-8")

    def start_bg(self, command, wait=3):
        """Запустить долгую команду в фоне (сервер разработки, наблюдатель) -> id, первые строки вывода."""
        command, _ = self._to_work(command)
        procs = self._procs()
        alive = [x for x in procs if _alive(x)]
        if len(alive) >= MAX_PROCS:
            raise CodeError(f"уже работают {len(alive)} фоновых процесса — останови ненужные (code_process stop)")
        pid_id = f"p{len(procs) + 1}"
        log_path = self.work.parent / "_proc" / f"{pid_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        out = open(log_path, "wb")
        if os.name == "nt":
            ps = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + command
            pr = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], cwd=self.work, stdout=out,
                                  stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=dict(os.environ, PYTHONIOENCODING="utf-8", **GIT_ENV),
                                  creationflags=0x08000000 | 0x00000200)
        else:
            pr = subprocess.Popen(["bash", "-lc", command], cwd=self.work, stdout=out, stderr=subprocess.STDOUT,
                                  stdin=subprocess.DEVNULL, env=dict(os.environ, PYTHONUNBUFFERED="1", **GIT_ENV), start_new_session=True)
        _RUNNING[pr.pid] = pr
        procs.append({"id": pid_id, "pid": pr.pid, "command": command[:300], "log": str(log_path), "started": time.time()})
        self._save_procs(procs)
        time.sleep(max(0.5, min(float(wait or 3), 30)))
        st = "работает" if _alive(procs[-1]) else f"уже завершился (код {pr.poll()})"
        return (f"Фоновый процесс {pid_id}: {st}. Вывод: code_process output {pid_id}; остановить — stop.\n"
                + _tail(log_path, 2500))

    def process(self, action, pid_id=""):
        """status — список; output — хвост вывода; stop — остановить (all — все)."""
        procs = self._procs()
        if action == "status" or not pid_id:
            if not procs:
                return "Фоновых процессов нет."
            return "\n".join(f"{x['id']}: {'работает' if _alive(x) else 'завершён'} — {x['command'][:120]}" for x in procs)
        sel = procs if pid_id == "all" else [x for x in procs if x["id"] == pid_id]
        if not sel:
            raise CodeError(f"нет процесса {pid_id} (список — code_process status)")
        if action == "output":
            return "\n\n".join(f"{x['id']} ({'работает' if _alive(x) else 'завершён'}):\n{_tail(Path(x['log']), 4000)}" for x in sel)
        if action == "stop":
            for x in sel:
                _kill(x)
            return "Остановлено: " + ", ".join(x["id"] for x in sel)
        raise CodeError("action: status, output или stop")

    def stop_all(self):
        """Конец задачи: остановить всё, что она запускала в фоне."""
        for x in self._procs():
            if _alive(x):
                _kill(x)

    def diff(self, limit=200_000):
        """Единый diff всех изменений для показа в студии, обрезанный до limit символов."""
        if not self.work.exists():
            return ""
        m = self.mode
        if m.get("mode") == "git":
            _git(self.work, *GIT_ADD)
            d = _git(self.work, "diff", "--cached", m["base"])
        else:
            parts = []
            for st, rel in self._copy_changes():
                a = [] if st == "added" else (self.project / rel).read_text(encoding="utf-8", errors="replace").splitlines(True)
                b = [] if st == "deleted" else (self.work / rel).read_text(encoding="utf-8", errors="replace").splitlines(True)
                parts.append("".join(difflib.unified_diff(a, b, f"a/{rel}", f"b/{rel}")))
            d = "\n".join(parts)
        return d[:limit]

    def accept(self):
        """Перенести изменения в проект пользователя и удалить рабочую копию -> текст для человека.
        git: патч накладывается на текущее состояние проекта; если проект успели поменять — пробуем --3way,
        не вышло — CodeError, копия остаётся. Без git — копирование файлов поверх проекта."""
        m = self.mode
        n = len(self.changes())                       # до переноса: после него копия и проект совпадают, и счёт был бы 0
        skipped = m.get("skipped") or []
        if m.get("mode") == "git":
            patch = subprocess.run(["git", "-C", str(self.work), "diff", "--cached", "--binary", m["base"]], capture_output=True).stdout
            if not patch.strip():
                return "Изменений нет."
            r = subprocess.run(["git", "-C", str(self.project), "apply", "--whitespace=nowarn"], input=patch, capture_output=True)
            if r.returncode:
                r = subprocess.run(["git", "-C", str(self.project), "apply", "--3way", "--whitespace=nowarn"], input=patch,
                                   capture_output=True)
            if r.returncode:
                raise CodeError("изменения не накладываются на проект (его успели поменять?): "
                                + r.stderr.decode(errors="replace")[-300:])
        else:
            for st, rel in self._copy_changes():
                a, b = self.project / rel, self.work / rel
                if st == "deleted":
                    a.unlink(missing_ok=True)
                else:
                    a.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(b, a)
        self.discard()
        return f"Изменения перенесены в проект ({n} файлов)." + (
            f" Файлы, которые не удалось прочитать при подготовке ({len(skipped)}), остались как были." if skipped else "")

    def discard(self):
        """Удалить рабочую копию (и worktree из списка git) — проект не меняется."""
        self.stop_all()
        if self.mode.get("mode") == "git":
            _git(self.project, "worktree", "remove", "--force", str(self.work), check=False)
            _git(self.project, "worktree", "prune", check=False)
        if self.work.exists():
            shutil.rmtree(self.work, ignore_errors=True)
        self.meta.unlink(missing_ok=True)
