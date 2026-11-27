"""Выбор проверок по изменению (15.11, владелец: «выпуски стали очень долгими… неужели нет подходов, которые сделали бы
Лиру гипер развиваемой»). Полный набор — ~750 проверок и час; изменение обычно трогает несколько файлов, и нужны только
проверки, которые эти файлы читают, — плюс «дымовые» (запуск, разговор, голос, «Мой день»).

Карта «проверка → файлы» (tests/impact.json) строится из двух источников:
  1. запись прогона: DEWIAR_TRACE_DIR=<папка> bash tests/run_quick.sh — каждый процесс Python каждой проверки (и ядро,
     которое она запускает) пишет, какие файлы проекта открыл и какие модули импортировал (tests/trace/sitecustomize.py);
  2. текст самой проверки: пути файлов проекта, которые в нём названы (страницы в браузере, node-скрипты, чтение
     исходников), а страница студии или виджета тянет за собой всю свою папку.

    python3 tools/test_impact.py build <папка записи>     — собрать tests/impact.json
    python3 tools/test_impact.py pick [<с чего>]          — какие проверки гонять для изменений с метки/коммита <с чего>
                                                            (по умолчанию — с последней метки v*), плюс незакоммиченное;
                                                            печатает имена файлов проверок по строке или ALL
    python3 tools/test_impact.py why <файл>               — какие проверки читают этот файл

По функциям (17.11, владелец: «код модульный и хорошо описан — это позволит сократить обязательные проверки»): запись
прогона пишет ещё и какие функции проекта проверка выполнила («fn:core/llm.py::Llm.chat», tests/trace/sitecustomize.py) и
какие исходники .py читала как текст («src:…»); карта функций — tests/impact.fn.json.gz. Изменился файл .py — берём не
все проверки, что его открывали, а только те, что выполняли изменённые функции (правка внутри функции или метода), плюс
читавшие его как текст; константа модуля или класса — проверки функций, где это имя встречается (во всём проекте), и
проверки, в тексте которых оно названо. Что не разобрать (код на уровне модуля, файл не разбирается, нет записи функций) —
по-старому, по файлу. Переводы (i18n.tx.js, data/i18n/text/*.json): только добавились строки — проверки переводов.

Осторожность прежде скорости — ALL (весь набор), если: изменилось устройство прогона (tests/run_*.sh, tests/trace,
этот файл); карты нет или она старая (новые проверки не в ней); изменился файл кода, который не читает ни одна
проверка (не знаем, что он задевает). Документы (.md, CHANGELOG, заметки к выпуску) проверок не требуют.
Полный набор всё равно идёт — после выпуска, в фоне: он ловит редкое, а выпуск не ждёт."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "tests" / "impact.json"
FNMAP = ROOT / "tests" / "impact.fn.json.gz"
RUNNERS = (ROOT / "tests" / "run_quick.sh", ROOT / "tests" / "run_all.sh")

# «дымовые» — всегда: имена, синтаксис ядра, разговор от начала до конца, голос, «Мой день», студия и виджет открываются
SMOKE = ("undefined_names_test.py", "unit_test.py", "tools_unit_test.py", "prompt_tools_test.py", "stage5_unit_test.py",
         "workspace_test.py", "slim_tools1115_test.py", "modules_door1115_test.py", "studio_chat_test.py", "hud_tight_test.py",
         "home1024_test.py", "prefix_cache1104_test.py")
# проверки студии целиком: правка одной её страницы (скрипт, стили) задевает и их
STUDIO_WIDE = re.compile(r"contrast|theme|light|dark|studio|smoke|nav|menu|i18n|undefined|a11y|layout", re.I)
# изменения, после которых выбору доверять нельзя — гоняем всё
INFRA = ("tests/run_quick.sh", "tests/run_all.sh", "tests/trace/", "tools/test_impact.py", "tests/pg_temp.sh")
# не код: проверки не нужны (если файл никто не читает)
DOCS = re.compile(r"(?:^|/)(?:[^/]+\.md|LICENSE|\.gitignore|\.gitattributes)$|^docs/|^tools/academy/", re.I)
# страница тянет свою папку: проверка, что открывает студию в браузере, зависит от всех её скриптов и стилей
PAGES = {"settings.html": ("dir:ui/studio", "dir:ui/assets", "ui/settings.html"),
         "hud.html": ("dir:ui/assets", "ui/hud.html"),
         "assets/www": ("dir:android/assets/www",), "index.html": ("dir:android/assets/www",),
         "webbridge.js": ("dir:android/web", "dir:android/assets/www")}


def runner_tests():
    """Проверки из run_quick.sh и run_all.sh -> множество имён файлов (tests/<имя>)."""
    out = set()
    for f in RUNNERS:
        if f.is_file():
            out |= set(re.findall(r'"\$T/([\w.-]+)"', f.read_text(encoding="utf-8")))
    return out


def repo_files():
    r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    return [x for x in r.stdout.splitlines() if x and not x.startswith("ui/assets/emoji/img/")]


def static_deps(src, files, uniq):
    """Файлы проекта, названные в тексте проверки: путь целиком или уникальное имя файла (≥ 6 знаков)."""
    deps = set()
    for f in files:
        if f in src:
            deps.add(f)
    for base, f in uniq.items():
        if base in src:
            deps.add(f)
    for k, v in PAGES.items():
        if k in src:
            deps.update(v)
    return deps


def build(trace_dir):
    files = repo_files()
    names = {}
    for f in files:
        names.setdefault(f.rsplit("/", 1)[-1], []).append(f)
    uniq = {b: fs[0] for b, fs in names.items() if len(fs) == 1 and len(b) >= 6 and "." in b}
    tests = sorted(runner_tests())
    tr = Path(trace_dir) if trace_dir else None
    deps, traced, fns = {}, 0, {}
    for t in tests:
        p = ROOT / "tests" / t
        src = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        d = static_deps(src, files, uniq) | {"tests/" + t}
        d |= {"src:" + x for x in d if x.endswith(".py") and not x.startswith(("src:", "dir:"))}   # назван в тексте проверки
        tf = tr / (t + ".txt") if tr else None
        if tf and tf.is_file():
            traced += 1
            d.add("trace:")                              # запись прогона есть (по ней видно, что JS проверка не запускала)
            got = {x.strip() for x in tf.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()}
            fns[t] = {x[3:] for x in got if x.startswith("fn:")} | {x[5:] for x in got if x.startswith("jsfn:")}
            d |= {x for x in got if not x.startswith(("fn:", "jsfn:"))}
        deps[t] = d
    idx = sorted({x for d in deps.values() for x in d})
    pos = {x: i for i, x in enumerate(idx)}
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    MAP.write_text(json.dumps({"built_at": head, "traced": traced, "files": idx,
                               "tests": {t: sorted(pos[x] for x in d) for t, d in deps.items()}}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print(f"карта: проверок {len(deps)}, с записью прогона {traced}, файлов {len(idx)} -> {MAP.relative_to(ROOT)}")
    if any(fns.values()):
        import gzip
        keys = sorted({x for v in fns.values() for x in v})
        kp = {x: i for i, x in enumerate(keys)}
        data = json.dumps({"built_at": head, "keys": keys, "tests": {t: sorted(kp[x] for x in v) for t, v in fns.items() if v}},
                          ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        FNMAP.write_bytes(gzip.compress(data, 9, mtime=0))
        print(f"карта функций: {len(keys)} функций у {sum(1 for v in fns.values() if v)} проверок -> {FNMAP.relative_to(ROOT)}")


def load():
    d = json.loads(MAP.read_text(encoding="utf-8"))
    files = d["files"]
    return {t: {files[i] for i in ix} for t, ix in d["tests"].items()}


def last_tag():
    r = subprocess.run(["git", "describe", "--tags", "--abbrev=0", "--match", "v*"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() or "HEAD~1"


def changed(base):
    """Изменённые файлы: с base до HEAD, плюс незакоммиченное и новые файлы."""
    if not base:
        base = last_tag()
    out = set()
    for cmd in (["git", "diff", "--name-only", base, "HEAD"], ["git", "diff", "--name-only", "HEAD"],
                ["git", "ls-files", "--others", "--exclude-standard"]):
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        out |= {x for x in r.stdout.splitlines() if x}
    return sorted(out)


VERSION_FILES = ("core/version.py", "packaging/dewiar-setup", "packaging/DEBIAN/control", "android/src/pro/dewiar/app/BuildInfo.java")
VERSION_LINE = re.compile(r'^(?:VERSION\s*=\s*"[\d.]+"|Version:\s*[\d.]+|public static final (?:String VERSION\s*=\s*"[\d.]+"|int CODE\s*=\s*\d+);)\s*$')


def version_only(f, base):
    """Выпуск поднял номер версии — и только: такие строки не задевают проверки (кроме тех, что про сам номер)."""
    if f not in VERSION_FILES:
        return False
    d = subprocess.run(["git", "diff", "-U0", base, "--", f], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    body = [ln[1:].strip() for ln in d if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    return bool(body) and all(VERSION_LINE.match(b) for b in body if b)


def registrations_only(f, base):
    """Изменение прогона — только добавленные/убранные строки «run …» (так каждая новая проверка встаёт в прогон)?
    -> имена файлов этих проверок или None (менялось что-то ещё — устройство прогона)."""
    if not base:
        r = subprocess.run(["git", "describe", "--tags", "--abbrev=0", "--match", "v*"], cwd=ROOT, capture_output=True, text=True)
        base = r.stdout.strip() or "HEAD~1"
    d = subprocess.run(["git", "diff", "-U0", base, "--", f], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    out = set()
    for ln in d:
        if ln.startswith(("+++", "---", "@@", "diff ", "index ")) or not ln[:1] in "+-":
            continue
        body = ln[1:].strip()
        if not body:
            continue
        m = re.match(r'^(?:[A-Z_]+=\S+\s+)*run\s+".*"\s+\$PY\s+"\$T/([\w.-]+)"\s*$', body)
        if not m:
            return None
        out.add(m.group(1))
    return out


def hits(f, dep):
    """Задевает ли изменение файла f зависимость dep (файл или «dir:папка» — файлы прямо в этой папке)."""
    if dep.startswith("dir:"):
        d = dep[4:].rstrip("/")
        return (f.rsplit("/", 1)[0] if "/" in f else ".") == d
    if dep.startswith("jscov:"):                         # грузила этот скрипт в браузере или node
        return f == dep[6:]
    return f == dep


def load_fn():
    """Карта функций -> {проверка: {"core/x.py::Q", …}} или {} (её нет — выбор только по файлам)."""
    if not FNMAP.is_file():
        return {}
    import gzip
    d = json.loads(gzip.decompress(FNMAP.read_bytes()).decode("utf-8"))
    keys = d["keys"]
    return {t: {keys[i] for i in ix} for t, ix in d["tests"].items()}


def _units(src):
    """Исходник .py -> [(начало, конец, единица, класс ли)]: функции верхнего уровня и методы (вложенные — на счёт
    внешней, как пишет запись), классы — отдельно (тело класса вне методов). None — не разбирается."""
    import ast
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return None
    out = []

    def walk(body, prefix):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = min([n.lineno] + [x.lineno for x in n.decorator_list])
                if isinstance(n, ast.ClassDef):
                    out.append((start, n.end_lineno, prefix + n.name, True))
                    walk(n.body, prefix + n.name + ".")
                else:
                    out.append((start, n.end_lineno, prefix + n.name, False))
    walk(tree.body, "")
    return out, tree


def _unit_at(units, line):
    best = None
    for a, b, u, cls in units:
        if a <= line <= b and (best is None or b - a < best[1] - best[0]):
            best = (a, b, u, cls)
    return best


def _hunks(f, base):
    """git diff -U0 base -- f -> ([строки старого], [строки нового]); удалённое без нового — соседние строки нового."""
    d = subprocess.run(["git", "diff", "-U0", base, "--", f], cwd=ROOT, capture_output=True, text=True).stdout
    old, new = [], []
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", d, re.M):
        a, b, c, e = int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)
        old += list(range(a, a + b))
        new += list(range(c, c + e)) if e else [c, c + 1]
    return old, new


_NAMEIDX = {}


def _name_index():
    """Во всём проекте (кроме проверок): единица кода -> какие имена она упоминает; присваивания уровня модуля -> имена.
    -> (имя -> {"файл::единица"}, имя -> {имена, что из него собраны})."""
    if _NAMEIDX:
        return _NAMEIDX["u"], _NAMEIDX["m"]
    import ast
    by_name, mod = {}, {}
    for f in repo_files():
        if not f.endswith(".py") or f.startswith(("tests/", "tools/academy/")):
            continue
        try:
            src = (ROOT / f).read_text(encoding="utf-8")
        except OSError:
            continue
        r = _units(src)
        if not r:
            continue
        units, tree = r

        def names_in(node):
            return {x.id for x in ast.walk(node) if isinstance(x, ast.Name)} | {x.attr for x in ast.walk(node) if isinstance(x, ast.Attribute)}
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                u = _unit_at(units, n.lineno)
                if u:
                    for nm in names_in(n):
                        by_name.setdefault(nm, set()).add(f"{f}::{u[2]}")
        for n in tree.body:
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                tg = n.targets if isinstance(n, ast.Assign) else [n.target]
                outs = {x.id for t in tg for x in ast.walk(t) if isinstance(x, ast.Name)}
                for nm in names_in(n.value) if n.value is not None else ():
                    mod.setdefault(nm, set()).update(outs)
    _NAMEIDX.update(u=by_name, m=mod)
    return by_name, mod


def _code_part(line):
    """Строка Python без комментария в конце (# вне кавычек) и без пробелов по краям."""
    q, i = None, 0
    while i < len(line):
        c = line[i]
        if q:
            if c == "\\":
                i += 2
                continue
            if c == q:
                q = None
        elif c in "\"'":
            q = c
        elif c == "#":
            return line[:i].strip()
        i += 1
    return line.strip()


def _dict_key_at(value, ln):
    """Строка ln внутри словаря-константы (и вложенных) -> самый внутренний строковый ключ, чья пара её содержит, или None
    (строка — сама скобка словаря, ключ не строка, не словарь — тогда по имени константы, как раньше)."""
    import ast
    if not isinstance(value, ast.Dict):
        return None
    best = None
    stack = [value]
    while stack:
        d = stack.pop()
        for k, v in zip(d.keys, d.values):
            if k is None:
                continue
            a, b = k.lineno, max(k.end_lineno or k.lineno, v.end_lineno or v.lineno)
            if a <= ln <= b:
                if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                    return None
                best = k.value
                if isinstance(v, ast.Dict):
                    stack.append(v)
    return best


_STRIDX = {}


def _str_index():
    """Во всём проекте (кроме проверок): строковая константа -> единицы кода, где она написана ("scene_on" -> {"core/
    answer_prompt.py::PromptMixin._scene_on"}). Только короткие строки-имена (ключи настроек и словарей)."""
    if _STRIDX:
        return _STRIDX
    import ast
    for f in repo_files():
        if not f.endswith(".py") or f.startswith(("tests/", "tools/academy/")):
            continue
        try:
            src = (ROOT / f).read_text(encoding="utf-8")
        except OSError:
            continue
        r = _units(src)
        if not r:
            continue
        units, tree = r
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"[A-Za-z_][\w.-]{1,40}", n.value):
                u = _unit_at(units, n.lineno)
                _STRIDX.setdefault(n.value, set()).add(f"{f}::{u[2]}" if u else f"{f}::")
    return _STRIDX


def py_changed(f, base):
    """Что задело изменение .py по функциям -> ({"f::единица"}, {имена констант}, причина отказа или "")."""
    import ast
    if not (ROOT / f).is_file():
        return set(), set(), "файл удалён"
    old_src = subprocess.run(["git", "show", f"{base}:{f}"], cwd=ROOT, capture_output=True, text=True)
    if old_src.returncode:
        return set(), set(), "новый файл"
    ru, rn = _units(old_src.stdout), _units((ROOT / f).read_text(encoding="utf-8"))
    if not ru or not rn:
        return set(), set(), "не разбирается"
    old_lines, new_lines = _hunks(f, base)
    # 20.11: поправили только комментарий в конце строки ("scene": False,  # …) — код тот же: строку не считаем
    ot, nt = old_src.stdout.splitlines(), (ROOT / f).read_text(encoding="utf-8").splitlines()
    oc = [_code_part(ot[i - 1]) for i in old_lines if 0 < i <= len(ot)]
    nc = [_code_part(nt[i - 1]) for i in new_lines if 0 < i <= len(nt)]
    old_lines = [i for i in old_lines if 0 < i <= len(ot) and _code_part(ot[i - 1]) not in nc]
    new_lines = [i for i in new_lines if 0 < i <= len(nt) and _code_part(nt[i - 1]) not in oc]
    units, names, imports = set(), set(), False
    for lines, (us, tree), src in ((old_lines, ru, old_src.stdout), (new_lines, rn, (ROOT / f).read_text(encoding="utf-8"))):
        text = src.splitlines()
        for ln in lines:
            if ln < 1 or ln > len(text):
                continue
            u = _unit_at(us, ln)
            if u and not u[3]:
                units.add(f"{f}::{u[2]}")
                continue
            body = text[ln - 1].strip()
            if not body or body.startswith("#"):
                continue                                  # пустая строка и комментарий ничего не меняют
            stmt = None
            nodes = (tree.body if not u else next((n.body for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                                                   and min([n.lineno] + [x.lineno for x in n.decorator_list]) == u[0]), []))
            for n in nodes:
                if n.lineno <= ln <= (n.end_lineno or n.lineno):
                    stmt = n
                    break
            if stmt is None:
                continue
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                tg = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                tnames = {x.id for t in tg for x in ast.walk(t) if isinstance(x, ast.Name)}
                key = _dict_key_at(getattr(stmt, "value", None), ln)
                if key:
                    # 20.11 (владелец: «выпуски очень долгие»): правка одного ключа словаря-константы (settings.DEFAULTS:
                    # "scene_on": None) задевала всех, кто трогает DEFAULTS, — 174 проверки. Теперь — ключ: код, где он
                    # назван строкой, и проверки, что его называют (pick)
                    names |= {"key:" + key} | {"keyof:" + n for n in tnames}
                    continue
                names |= tnames
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                imports = True                            # что именно сменилось в импортах — ниже, по всему файлу
            elif isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) and isinstance(stmt.value.value, str):
                continue                                  # строка-описание модуля или класса
            else:
                return set(), set(), f"код уровня {'класса' if u else 'модуля'} (строка {ln})"
    if imports:
        # 1.0.24: в длинный «from quality_answer import (…)» дописали два имени — изменилось не всё, что там названо.
        # Новое имя задевает только тех, кто его использует (а они и так в изменении); убранное или взятое из другого
        # модуля — всех, кто его использует
        def imp(tree):
            out = set()
            for n in tree.body:
                if isinstance(n, ast.Import):
                    out |= {(a.name, (a.asname or a.name).split(".")[0]) for a in n.names}
                elif isinstance(n, ast.ImportFrom):
                    out |= {(f"{'.' * n.level}{n.module or ''}.{a.name}", a.asname or a.name) for a in n.names}
            return out
        a, b = imp(ru[1]), imp(rn[1])
        gone = {nm for _, nm in a - b}
        names |= gone
    return units, names, ""


def i18n_additive(f, base):
    """Словарь переводов только пополнился (старые строки те же) -> True."""
    if not (f == "ui/assets/i18n.tx.js" or re.match(r"^data/i18n/text/\w+\.json$", f)):
        return False
    def parse(t):
        t = t.strip()
        if f.endswith(".js"):
            t = t[t.index("{"):t.rstrip().rstrip(";").rindex("}") + 1]
        return json.loads(t)
    old = subprocess.run(["git", "show", f"{base}:{f}"], cwd=ROOT, capture_output=True, text=True)
    try:
        a, b = parse(old.stdout), parse((ROOT / f).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False

    def sub_ok(x, y):
        if isinstance(x, dict) and isinstance(y, dict):
            return all(k in y and sub_ok(v, y[k]) for k, v in x.items())
        return x == y
    return old.returncode == 0 and sub_ok(a, b)


def whatsnew_prepended(base):
    """«Что нового» — сверху новые записи, прежние не тронуты (так меняется в каждом выпуске) -> True."""
    f = "data/whatsnew.json"
    old = subprocess.run(["git", "show", f"{base}:{f}"], cwd=ROOT, capture_output=True, text=True)
    try:
        a, b = json.loads(old.stdout), json.loads((ROOT / f).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    return old.returncode == 0 and isinstance(a, list) and isinstance(b, list) and len(b) > len(a) and b[len(b) - len(a):] == a


# ---------- JS по функциям (20.11, владелец: «телефон — по функциям… да, давай сделаем») ----------
# Телефон (app.js из частей www-src/app), виджет (hud.html), общие скрипты ui/assets и android/assets/www. Запись прогона
# (tests/trace/sitecustomize.py) пишет, какие функции JS выполнились в браузере и node («jsfn:») и чьё покрытие снято
# («jscov:<файл>»). Изменилась функция верхнего уровня — проверки, что её выполняли; константа — проверки функций, где
# она названа; плюс проверки, что читают файл текстом и называют что-то из изменённых строк. Проверка без покрытия этого
# файла — по-старому, по файлу. Код верхнего уровня (не функция и не константа), разметка и стили hud.html — по файлу.
JS_FN = re.compile(r"^(?:android/assets/www/[\w.-]+\.js|android/www-src/app/[\w.-]+\.js|ui/assets/[\w.-]+\.js|ui/hud\.html)$")
_JS_START = re.compile(r"^(?:(?:export\s+)?(?:async\s+)?function\s*\*?\s*([\w$]+)|class\s+([\w$]+)|(?:const|let|var)\s+([\w$]+|\{[^}]*\}|\[[^\]]*\]))")
_JS_FNVAL = re.compile(r"=\s*(?:async\s+)?(?:function\b|\([^()]*\)\s*=>|[\w$]+\s*=>)")
_JS_KW = set("""break case catch class const continue debugger default delete do else export extends finally for function if import
in instanceof let new return super switch this throw try typeof var void while with yield async await true false null undefined
document window length push slice split join replace trim String Number Object Array Math JSON Date Promise console style
classList textContent innerHTML addEventListener querySelector querySelectorAll getElementById setTimeout clearTimeout""".split())


def _js_lines(src, html):
    """Строки, что относятся к скрипту: для .html — только внутри <script> без src; -> множество номеров строк (с 1)."""
    lines = src.splitlines()
    if not html:
        return set(range(1, len(lines) + 1))
    out, on = set(), False
    for i, ln in enumerate(lines, 1):
        low = ln.lower()
        if on and "</script>" in low:
            on = False
            continue
        if on:
            out.add(i)
        elif "<script" in low and "src=" not in low.split(">", 1)[0] and "</script>" not in low:
            on = True
    return out


def _js_units(src, html=False):
    """Исходник JS (или страница) -> [(начало, конец, имя, вид)]: вид "fn" — функция верхнего уровня (и const f = () =>),
    "const" — константа или класс (имя — первое из объявленных), "stmt" — прочий код верхнего уровня. Граница — следующая
    строка с начала строки (стиль проекта: тело с отступом). Многострочные /* … */ и строки-комментарии — не границы."""
    lines = src.splitlines()
    js = _js_lines(src, html)
    starts, inc = [], False
    for i, ln in enumerate(lines, 1):
        if i not in js:
            if starts and starts[-1][3] != "gap":
                starts.append((i, "", "", "gap"))
            continue
        t = ln.strip()
        if inc:
            inc = "*/" not in t
            continue
        if t.startswith("/*") and "*/" not in t:
            inc = True
            continue
        if not ln or ln[0] in " \t}])" or not t or t.startswith(("//", "/*", "*")):
            continue
        m = _JS_START.match(ln)
        if m and (m.group(1) or m.group(2)):
            starts.append((i, m.group(1) or m.group(2), "fn" if m.group(1) else "const", ""))
        elif m:
            names = re.findall(r"[\w$]+", m.group(3)) if m.group(3)[0] in "{[" else [m.group(3)]
            kind = "fn" if len(names) == 1 and _JS_FNVAL.search(ln[m.end():m.end() + 80]) else "const"
            starts.append((i, ",".join(names), kind, ""))
        else:
            starts.append((i, "", "stmt", ""))
    out = []
    for k, (a, nm, kind, gap) in enumerate(starts):
        if gap:
            continue
        b = (starts[k + 1][0] - 1) if k + 1 < len(starts) else len(lines)
        out.append((a, b, nm, kind))
    return out


def _js_comment(t):
    t = t.strip()
    return not t or t.startswith(("//", "/*", "*")) and not re.search(r"\*/\s*\S", t)


def js_changed(f, base):
    """Изменение JS -> ({функции верхнего уровня}, {константы}, {строки изменений}, причина отказа или "")."""
    html = f.endswith(".html")
    if not (ROOT / f).is_file():
        return set(), set(), [], "файл удалён"
    old = subprocess.run(["git", "show", f"{base}:{f}"], cwd=ROOT, capture_output=True, text=True)
    if old.returncode:
        return set(), set(), [], "новый файл"
    new_src = (ROOT / f).read_text(encoding="utf-8")
    old_lines, new_lines = _hunks(f, base)
    fns, consts, text = set(), set(), []
    for lines, src in ((old_lines, old.stdout), (new_lines, new_src)):
        units, body, js = _js_units(src, html), src.splitlines(), _js_lines(src, html)
        inside = _js_block_comment_lines(src)
        for ln in lines:
            if ln < 1 or ln > len(body):
                continue
            if _js_comment(body[ln - 1]) or ln in inside:
                continue                                   # пустая строка и комментарий ничего не меняют
            if ln not in js:
                return set(), set(), [], f"разметка или стили (строка {ln})"
            u = next((x for x in units if x[0] <= ln <= x[1]), None)
            if u is not None and u[3] == "stmt" and re.match(r"\s*(?:N\.on|document\.addEventListener|window\.addEventListener)\(", body[u[0] - 1]):
                # 20.11: подписка на событие (N.on("stt_level", e => …)) — не «весь файл», а проверки, что называют её слова
                fns.add("__stmt__")
                text.append(body[ln - 1])
                text.append(body[u[0] - 1])
                continue
            if u is None or u[3] == "stmt":
                return set(), set(), [], f"код верхнего уровня (строка {ln})"
            (fns if u[3] == "fn" else consts).update(u[2].split(","))
            text.append(body[ln - 1])
    return fns, consts, text, ""


_JSIDX = {}


def _js_block_comment_lines(src):
    """Номера строк внутри /* … */ (продолжение многострочного комментария без «*» в начале строки — тоже комментарий)."""
    out, pos = set(), 0
    while True:
        a = src.find("/*", pos)
        if a < 0:
            return out
        b = src.find("*/", a + 2)
        if b < 0:
            return out
        la, lb = src.count("\n", 0, a) + 1, src.count("\n", 0, b) + 1
        if src.rfind("\n", 0, a) < a and not src[src.rfind("\n", 0, a) + 1:a].strip():
            out |= set(range(la, lb + 1))             # комментарий с начала строки — строки целиком
        else:
            out |= set(range(la + 1, lb + 1))
        pos = b + 2


def _js_name_index(f):
    """Файл JS -> (имя -> {функции верхнего уровня, где оно названо}, имя -> {константы, собранные с ним},
    {имена в коде верхнего уровня})."""
    if f in _JSIDX:
        return _JSIDX[f]
    src = (ROOT / f).read_text(encoding="utf-8")
    body = src.splitlines()
    by, cby, stmt = {}, {}, set()
    for a, b, nm, kind in _js_units(src, f.endswith(".html")):
        words = set(re.findall(r"[A-Za-z_$][\w$]*", "\n".join(body[a - 1:b])))
        if kind == "stmt":
            stmt |= words
        for w in words:
            if kind == "fn":
                by.setdefault(w, set()).add(nm)
            elif kind == "const":
                cby.setdefault(w, set()).update(nm.split(","))
    _JSIDX[f] = (by, cby, stmt)
    return by, cby, stmt


def js_pick(f, base, deps, fnmap, have, ch):
    """Изменение JS-файла -> (проверки, пояснение) или (None, причина — тогда по файлу)."""
    key = f
    if f.startswith("android/www-src/app/"):
        if "android/assets/www/app.js" not in ch:
            return None, "часть изменена, а app.js не собран"
        key = "android/assets/www/app.js"           # части собраны в app.js: функции те же, покрытие записано по нему
    if not any("jscov:" + key in d for d in deps.values()):
        return None, "в карте нет покрытия JS этого файла"
    fns, consts, text, fail = js_changed(f, base)
    if fail:
        return None, fail
    by, cby, stmt = _js_name_index(f)
    on_ev = "__stmt__" in fns
    fns = fns - {"__stmt__"}
    units, todo, seen, every = set(fns), set(consts), set(), False
    while todo:                                         # константа -> функции, где она названа (и константы из неё)
        nm = todo.pop()
        seen.add(nm)
        units |= by.get(nm, set())
        todo |= cby.get(nm, set()) - seen
        every |= nm in stmt                             # названа в коде верхнего уровня — он идёт у всех, кто грузит файл
    keys = {f"{key}::{u}" for u in units}
    texts = {}

    def src(t):
        if t not in texts:
            texts[t] = (ROOT / "tests" / t).read_text(encoding="utf-8", errors="replace")
        return texts[t]
    toks = _tokens(text) | fns | seen
    common = {w for w in toks if sum(1 for t in have if w in src(t)) > 20}   # слово есть в десятках проверок — не отличает
    toks -= common - fns - seen
    rx = re.compile(r"(?<![\w$])(?:" + "|".join(re.escape(t) for t in sorted(toks, key=len, reverse=True)) + r")(?![\w$])") if toks else None
    out = set()
    for t, d in deps.items():
        if t not in have or not (any(hits(f, x) or hits(key, x) for x in d) or "jscov:" + key in d):
            continue
        if "jscov:" + key not in d:
            if ("trace:" in d and not any(x.startswith("jscov:") for x in d) and rx
                    and not re.search(r"\bnode\b|playwright|chromium|vm\.|eval\(", src(t))):
                if rx.search(src(t)):                   # JS не запускала вовсе — читает текст: нужна, если называет изменённое
                    out.add(t)
                continue
            out.add(t)                                  # покрытия этого файла у проверки нет — осторожно, по файлу
        elif every or fnmap.get(t, set()) & keys:
            out.add(t)
        elif on_ev and rx and rx.search(src(t)):
            out.add(t)                                  # подписка на событие: проверка называет её событие или слова
        elif rx and (key in d or (f != key and ("www-src" in src(t) or f.rsplit("/", 1)[-1] in src(t)))) and rx.search(src(t)):
            out.add(t)                                  # читает исходник текстом и называет изменённое
    short = sorted(units)
    return out, (f"{len(out)} по функциям JS ({', '.join(short[:6])}{' …' if len(short) > 6 else ''}"
                 + (f"; константы: {', '.join(sorted(seen)[:4])}" if seen else "") + (" — в коде верхнего уровня: все, кто грузит" if every else "") + ")")


def _tokens(lines):
    """Отличительные слова изменённых строк: имена (от 4 знаков) и слова в кавычках — по ним проверки, что читают
    исходник текстом («'ACT_CUE' in app»)."""
    out = set()
    for ln in lines:
        for w in re.findall(r"[A-Za-z_$][\w$-]{3,}|[А-Яа-яЁё][А-Яа-яЁё-]{4,}", ln):
            if w not in _JS_KW:
                out.add(w)
    return out

CSS_TXT = re.compile(r"^(?:android/assets/www/[\w.-]+\.css|ui/assets/[\w.-]+\.css)$")
PHP_TXT = re.compile(r"^server/dwrapp/(?:[\w-]+/)*[\w.-]+\.php$")
UI_WIDE = re.compile(r"contrast|theme|light|dark|look|layout|smoke|boot|tablet|web_wide|neu|skin", re.I)


def _changed_lines(f, base):
    """Изменённые строки файла: старые (из base) и новые (рабочие) — текстом."""
    old_lines, new_lines = _hunks(f, base)
    old = subprocess.run(["git", "show", f"{base}:{f}"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    new = (ROOT / f).read_text(encoding="utf-8", errors="replace").splitlines() if (ROOT / f).is_file() else []
    return ([old[i - 1] for i in old_lines if 0 < i <= len(old)], [new[i - 1] for i in new_lines if 0 < i <= len(new)], old, new,
            old_lines, new_lines)


def _rx_words(words):
    return re.compile(r"(?<![\w$-])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![\w$-])") if words else None


def text_pick(f, base, deps, have):
    """20.11 (владелец: «выпуски очень долгие»): app.css и файлы сайта — по смыслу правки, а не по файлу целиком (app.css
    задевал 320 проверок, cloud.php — 260). CSS: id и классы изменённых правил (и селектор правила, где правка внутри) —
    проверки, что грузят файл и называют их, и проверки вида целиком (контраст, темы, планшет). PHP: имена функций, где
    правка, и отличительные слова изменённых строк (и их части через «_») — проверки, что ходят в файл и называют их.
    -> (проверки, пояснение) или (None, причина — тогда по файлу)."""
    if not (ROOT / f).is_file():
        return None, "файл удалён"
    old_t, new_t, old, new, old_n, new_n = _changed_lines(f, base)
    words = set()
    if f.endswith(".css"):
        for lines, nums in ((old, old_n), (new, new_n)):
            for i in nums:
                if not (0 < i <= len(lines)):
                    continue
                j = i - 1                                    # правило, где правка: вверх до строки с «{» без «}»
                while j >= 0 and "{" not in lines[j]:
                    j -= 1
                for ln in {lines[i - 1], lines[j] if j >= 0 else ""}:
                    sel = ln.split("{", 1)[0] if "{" in ln else ln
                    words |= set(re.findall(r"[#.]([A-Za-z][\w-]{2,})", sel))
                    words |= set(re.findall(r"--([\w-]{3,})", ln))           # свои переменные (--bandpad)
        why = "по правилам CSS"
    else:
        for lines, nums in ((old, old_n), (new, new_n)):
            for i in nums:
                j = i - 1
                while j >= 0 and not re.match(r"\s*(?:function\s+\w+|\}\s*$)", lines[j] if j < len(lines) else ""):
                    j -= 1
                m = re.match(r"\s*function\s+(\w+)", lines[j]) if 0 <= j < len(lines) else None
                if m:
                    words.add(m.group(1))
        toks = _tokens(old_t + new_t)
        words |= toks | {p for t in toks for p in re.split(r"[_-]", t) if len(p) >= 4}
        why = "по функциям и словам PHP"
    texts = {}

    def src(t):
        if t not in texts:
            texts[t] = (ROOT / "tests" / t).read_text(encoding="utf-8", errors="replace")
        return texts[t]
    users = [t for t, d in deps.items() if t in have and any(hits(f, x) for x in d)]
    common = {w for w in words if sum(1 for t in users if w in src(t)) > max(25, len(users) // 3)}
    rx = _rx_words(words - common)
    out = {t for t in users if (rx and rx.search(src(t))) or (f.endswith(".css") and UI_WIDE.search(t))}
    if not words:
        return None, "не нашёл, что изменилось"
    return out, f"{len(out)} {why} ({', '.join(sorted(words - common)[:6])}{' …' if len(words - common) > 6 else ''})"


def pick(base=None, verbose=True):
    """-> ("ALL", причина) или (список проверок, пояснения)."""
    if not MAP.is_file():
        return "ALL", ["карты проверок нет — tools/test_impact.py build"]
    deps = load()
    fnmap = load_fn()
    have = runner_tests()
    new = sorted(have - set(deps))
    ch = changed(base)
    why = []
    added = set()
    for f in ch:
        if f in ("tests/run_quick.sh", "tests/run_all.sh"):
            reg = registrations_only(f, base)
            if reg is not None:                        # только записи «run …» — новые проверки, устройство то же
                added |= reg
                why.append(f"{f}: только новые записи проверок ({len(reg)})")
                continue
        if f.startswith(INFRA):
            return "ALL", [f"изменилось устройство прогона: {f}"]
    chosen = set(t for t in SMOKE if t in have)
    for t in new:                                   # новые проверки — в карте их ещё нет: гоняем их самих
        chosen.add(t)
    chosen |= {t for t in added if t in have}
    unknown = []
    for f in ch:
        if f in ("tests/run_quick.sh", "tests/run_all.sh", "tests/impact.json", "tests/impact.fn.json.gz"):
            continue                                   # записи проверок — выше; сама карта проверок ничего не задевает
        if f.startswith("tests/") and f.rsplit("/", 1)[-1] in have:
            chosen.add(f.rsplit("/", 1)[-1])
            why.append(f"{f}: сама проверка")
            continue
        if version_only(f, base or last_tag()):
            vt = [t for t in have if "version" in t]
            chosen.update(vt)
            why.append(f"{f}: только номер версии — проверки номера ({len(vt)})")
            continue
        if i18n_additive(f, base or last_tag()):
            it = [t for t in have if "i18n" in t]
            chosen.update(it)
            why.append(f"{f}: переводы только пополнились — проверки переводов ({len(it)})")
            continue
        if f == "data/whatsnew.json" and whatsnew_prepended(base or last_tag()):
            wt = {t for t in have if re.search(r"whatsnew|Что нового", (ROOT / "tests" / t).read_text(encoding="utf-8", errors="replace"))}
            chosen.update(wt)
            why.append(f"{f}: сверху новая запись, старые те же — проверки «Что нового» ({len(wt)})")
            continue
        if f.endswith(".py") and fnmap:
            units, names, fail = py_changed(f, base or last_tag())
            if not fail:
                by_name, mod = _name_index()
                keys = {n[4:] for n in names if n.startswith("key:")}
                keyof = {n[6:] for n in names if n.startswith("keyof:")}
                names = {n for n in names if not n.startswith(("key:", "keyof:"))}
                if keys:                                  # ключ словаря-константы: где он назван строкой
                    sidx = _str_index()
                    units |= {u for k in keys for u in sidx.get(k, set()) if not u.endswith("::")}
                todo, seen_n = set(names), set()
                while todo:                               # константа, собранная из другой константы, — тоже
                    nm = todo.pop()
                    seen_n.add(nm)
                    units |= by_name.get(nm, set())
                    todo |= mod.get(nm, set()) - seen_n
                ts = {t for t, fs in fnmap.items() if fs & units}
                ts |= {t for t, d in deps.items() if "src:" + f in d}                   # читают исходник как текст
                if seen_n:
                    rx = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(n) for n in sorted(seen_n)) + r")(?!\w)")
                    for t in have:                       # проверка сама называет константу («sites_base.TEXT_MAX»)
                        p = ROOT / "tests" / t
                        if f.rsplit("/", 1)[-1][:-3] in (src := p.read_text(encoding="utf-8", errors="replace")) and rx.search(src):
                            ts.add(t)
                if keys:                                  # проверки, что называют ключ («"scene_on"») или словарь с файлом
                    krx = re.compile(r"""["'](?:""" + "|".join(re.escape(k) for k in sorted(keys)) + r""")["']""")
                    nrx = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(n) for n in sorted(keyof)) + r")(?!\w)") if keyof else None
                    stem = f.rsplit("/", 1)[-1][:-3]
                    for t in have:
                        src_t = (ROOT / "tests" / t).read_text(encoding="utf-8", errors="replace")
                        if krx.search(src_t) or (nrx and stem in src_t and nrx.search(src_t)):
                            ts.add(t)
                # файл открыт процессом с записью — его вызовы записаны; прочитан текстом — «src:» выше. Без записи функций
                # вовсе (проверка не запускала код проекта под записью) — осторожно, по файлу
                ts |= {t for t, d in deps.items() if any(hits(f, x) for x in d) and t not in fnmap}
                chosen.update(t for t in ts if t in have)
                short = sorted(u.split("::", 1)[1] for u in units if u.startswith(f + "::"))
                why.append(f"{f}: {len(ts)} по функциям ({', '.join(short[:6])}{' …' if len(short) > 6 else ''}"
                           + (f"; имена: {', '.join(sorted(seen_n)[:4])}" if seen_n else "")
                           + (f"; ключи: {', '.join(sorted(keys)[:4])}" if keys else "") + ")")
                continue
            why.append(f"{f}: по файлу — {fail}")
        if JS_FN.match(f) and fnmap:
            ts, note = js_pick(f, base or last_tag(), deps, fnmap, have, ch)
            if ts is not None:
                chosen.update(ts)
                why.append(f"{f}: {note}")
                continue
            why.append(f"{f}: по файлу — {note}")
        if CSS_TXT.match(f) or PHP_TXT.match(f):
            ts, note = text_pick(f, base or last_tag(), deps, have)
            if ts is not None:
                chosen.update(ts)
                why.append(f"{f}: {note}")
                continue
            why.append(f"{f}: по файлу — {note}")
        m = re.match(r"^ui/studio/([\w-]+)\.(?:js|css)$", f)
        if m and (ROOT / f).is_file():
            # страница студии: её проверки (называют страницу) и проверки студии целиком — контраст, темы, переводы,
            # меню, «дым» (17.11: класс облака перекрасил надпись в «Устройствах» — это ловит контраст). Синтаксис и
            # загрузку всех скриптов ловят «дымовые» — студия открывается в них целиком
            stem = re.compile(r"(?<![\w-])" + re.escape(m.group(1)) + r"s?(?![\w-])|studio/" + re.escape(m.group(1)) + r"\.", re.I)
            ts = set()
            for t, d in deps.items():
                if t in have and any(hits(f, x) for x in d):
                    if STUDIO_WIDE.search(t) or stem.search((ROOT / "tests" / t).read_text(encoding="utf-8", errors="replace")):
                        ts.add(t)
            chosen.update(ts)
            why.append(f"{f}: {len(ts)} — проверки страницы «{m.group(1)}» и студии целиком")
            continue
        ts = [t for t, d in deps.items() if any(hits(f, x) for x in d)]
        if ts:
            chosen.update(t for t in ts if t in have)
            why.append(f"{f}: {len(ts)}")
        elif DOCS.search(f) or f.startswith(("data/whatsnew.json", "RELEASE_NOTES", "CHANGELOG")):
            why.append(f"{f}: документ — проверки не нужны")
        elif not (ROOT / f).exists():
            why.append(f"{f}: удалён")
            ts = [t for t, d in deps.items() if any(x.startswith("dir:") and hits(f, x) for x in d)]
            chosen.update(t for t in ts if t in have)
        else:
            unknown.append(f)
    if unknown:
        return "ALL", [f"этот файл не читает ни одна проверка — не знаю, что он задевает: {', '.join(unknown[:5])}"]
    return sorted(chosen), why


def main(argv):
    if len(argv) >= 2 and argv[1] == "build":
        build(argv[2] if len(argv) > 2 else "")
        return 0
    if len(argv) >= 2 and argv[1] == "why":
        deps = load()
        for f in argv[2:]:
            ts = sorted(t for t, d in deps.items() if any(hits(f, x) for x in d))
            print(f"{f}: {len(ts)} — " + ", ".join(ts[:40]) + (" …" if len(ts) > 40 else ""))
        return 0
    if len(argv) >= 2 and argv[1] == "pick":
        res, why = pick(argv[2] if len(argv) > 2 else None)
        for w in why:
            print("# " + w, file=sys.stderr)
        if res == "ALL":
            print("ALL")
        else:
            print(f"# проверок: {len(res)} из {len(runner_tests())}", file=sys.stderr)
            print("\n".join(res))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
