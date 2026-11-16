"""Карта ядра (чистое ядро, шаг 0 — docs/CORE_PLAN.md): размеры модулей, кто кого импортирует и что, похоже, мёртвое.

    python3 tools/core_map.py            — сводка: самые большие модули и кандидаты в мёртвое
    python3 tools/core_map.py dead       — только мёртвое (с доказательством: имя больше нигде не встречается)

«Мёртвое» — функция, класс или константа верхнего уровня (и метод класса), имя которых не встречается больше нигде:
ни в коде ядра и окон, ни в телефоне, ни на сервере, ни в данных (строкой — реестры, команды по имени, getattr). Проверки
(tests/) не считаются: код, который зовут только проверки, людям не служит. Это кандидаты — убирать по одному, с прогоном.
"""
import ast
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHERE = ["core", "ui", "android/assets/www", "android/web", "server", "data", "packaging", "tools"]
EXT = {".py", ".js", ".html", ".php", ".json", ".sh", ".md", ".txt", ".css", ".java", ".iss", ".nsi", ".ps1"}
SPECIAL = re.compile(r"^(__\w+__|do_[A-Z]+|log_message|setUp|tearDown|main|run)$")


def corpus():
    words = Counter()
    for d in WHERE:
        base = ROOT / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in EXT and "__pycache__" not in p.parts and p.stat().st_size < 3_000_000:
                try:
                    words.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", p.read_text(encoding="utf-8", errors="ignore")))
                except OSError:
                    pass
    return words


def defs(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append((n.name, n.lineno, "class" if isinstance(n, ast.ClassDef) else "def"))
            if isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out.append((m.name, m.lineno, "method"))
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    out.append((t.id, n.lineno, "const"))
    return out


def main():
    words = corpus()
    mods = sorted((ROOT / "core").glob("*.py"))
    dead = []
    for p in mods:
        for name, line, kind in defs(p):
            if SPECIAL.match(name) or len(name) < 4:
                continue
            if words[name] <= 1:                  # только само определение
                dead.append((p.relative_to(ROOT), line, kind, name))
    if sys.argv[1:2] != ["dead"]:
        sizes = sorted(((len(p.read_text(encoding="utf-8").splitlines()), p.name) for p in mods), reverse=True)
        print("Самые большие модули ядра:")
        for n, name in sizes[:15]:
            print(f"  {n:5}  {name}")
        print(f"Всего модулей: {len(mods)}, строк: {sum(n for n, _ in sizes)}\n")
    print(f"Кандидаты в мёртвое: {len(dead)}")
    for f, line, kind, name in dead:
        print(f"  {f}:{line}  {kind} {name}")


if __name__ == "__main__":
    main()
