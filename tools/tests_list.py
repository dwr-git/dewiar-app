#!/usr/bin/env python3
"""Список всех проверок Dewiar одним файлом (для аварийного архива и новой беседы): разделы и строки tests/run_quick.sh —
что проверяет (как написано в прогоне), файл, откуда взялась (жалоба №…, экзамен, владелец, дата), и проверки только из
run_all.sh. Собирается из самих прогонов — не устаревает.   python3 tools/tests_list.py [файл.md]"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN = re.compile(r'^run\s+"((?:[^"\\]|\\.)*)"\s+(.*)$')


def rows(path):
    sec, out = "", []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r'^echo "== (.+)"', line)
        if m:
            sec = m.group(1)
            continue
        m = RUN.match(line)
        if m:
            f = re.search(r'\$T/([\w./-]+)', m.group(2)) or re.search(r'([\w./-]+_test\.\w+)', m.group(2))
            out.append((sec, m.group(1).replace('\\"', '"'), f.group(1) if f else m.group(2)[:60]))
    return out


def origin(desc, fname):
    """Откуда проверка: номер жалобы/идеи, экзамен, дата в имени файла."""
    n = re.findall(r"№\s?(\d{2,4})", desc) or re.findall(r"(?<!\d)(\d{3})(?!\d)", re.sub(r"\d{4}_test", "", fname))
    who = "экзамен" if re.search(r"экзамен", desc, re.I) else "владелец" if "владелец" in desc else ""
    d = re.search(r"(\d{2})(\d{2})_test", fname)
    parts = ([f"№{n[0]}"] if n else []) + ([who] if who else []) + ([f"{d.group(2)}.{d.group(1)}"] if d and 10 <= int(d.group(1)) <= 12 and 1 <= int(d.group(2)) <= 31 else [])
    return ", ".join(parts)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    quick, full = rows(ROOT / "tests/run_quick.sh"), rows(ROOT / "tests/run_all.sh")
    qf = {f for _, _, f in quick}
    only_all = [r for r in full if r[2] not in qf]
    files = sorted(p.name for p in (ROOT / "tests").glob("*_test.py"))
    listed = qf | {f for _, _, f in full}
    unlisted = [f for f in files if f not in listed]
    md = ["# Проверки Dewiar — полный список", "",
          f"Всего файлов проверок: {len(files)}; в быстром прогоне (`tests/run_quick.sh`): {len(quick)}; только в полном "
          f"(`tests/run_all.sh`): {len(only_all)}. Как устроены и как запускать — `docs/TESTS.md`.", ""]
    sec = None
    for s, d, f in quick:
        if s != sec:
            md += ["", f"## {s or 'Начало'}", "", "| что проверяет | файл | откуда |", "|---|---|---|"]
            sec = s
        md.append(f"| {d.replace('|', '/')} | `{f}` | {origin(d, f)} |")
    if only_all:
        md += ["", "## Только в полном прогоне", "", "| что проверяет | файл | откуда |", "|---|---|---|"]
        md += [f"| {d.replace('|', '/')} | `{f}` | {origin(d, f)} |" for _, d, f in only_all]
    if unlisted:
        md += ["", "## Файлы проверок вне прогонов (вспомогательные или запускаются из других проверок)", "",
               ", ".join(f"`{f}`" for f in unlisted)]
    text = "\n".join(md) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
        print(f"{out}: {len(quick)} + {len(only_all)} проверок")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
