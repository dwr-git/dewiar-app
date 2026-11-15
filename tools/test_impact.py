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
RUNNERS = (ROOT / "tests" / "run_quick.sh", ROOT / "tests" / "run_all.sh")

# «дымовые» — всегда: имена, синтаксис ядра, разговор от начала до конца, голос, «Мой день», студия и виджет открываются
SMOKE = ("undefined_names_test.py", "unit_test.py", "tools_unit_test.py", "prompt_tools_test.py", "stage5_unit_test.py",
         "workspace_test.py", "slim_tools1115_test.py", "modules_door1115_test.py", "studio_chat_test.py", "hud_tight_test.py",
         "home1024_test.py", "prefix_cache1104_test.py")
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
    deps, traced = {}, 0
    for t in tests:
        p = ROOT / "tests" / t
        src = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        d = static_deps(src, files, uniq) | {"tests/" + t}
        tf = tr / (t + ".txt") if tr else None
        if tf and tf.is_file():
            traced += 1
            d |= {x.strip() for x in tf.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()}
        deps[t] = d
    idx = sorted({x for d in deps.values() for x in d})
    pos = {x: i for i, x in enumerate(idx)}
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    MAP.write_text(json.dumps({"built_at": head, "traced": traced, "files": idx,
                               "tests": {t: sorted(pos[x] for x in d) for t, d in deps.items()}}, ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    print(f"карта: проверок {len(deps)}, с записью прогона {traced}, файлов {len(idx)} -> {MAP.relative_to(ROOT)}")


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
    return f == dep


def pick(base=None, verbose=True):
    """-> ("ALL", причина) или (список проверок, пояснения)."""
    if not MAP.is_file():
        return "ALL", ["карты проверок нет — tools/test_impact.py build"]
    deps = load()
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
        if f in ("tests/run_quick.sh", "tests/run_all.sh"):
            continue
        if f.startswith("tests/") and f.rsplit("/", 1)[-1] in have:
            chosen.add(f.rsplit("/", 1)[-1])
            why.append(f"{f}: сама проверка")
            continue
        if version_only(f, base or last_tag()):
            vt = [t for t in have if "version" in t]
            chosen.update(vt)
            why.append(f"{f}: только номер версии — проверки номера ({len(vt)})")
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
