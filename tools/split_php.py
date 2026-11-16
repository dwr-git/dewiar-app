"""Разложить большой PHP-файл сайта (server/dwrapp/cloud.php) на части по разделам — без изменения поведения (чистое
ядро, docs/CORE_PLAN.md). Части — server/dwrapp/cloud/<имя>.php: только функции и константы своего раздела слово в слово;
cloud.php подключает их (require_once) сразу после вступления, до первого раздела, и остаётся входом: вступление, CLI и
маршруты.

    python3 tools/split_php.py <план.json> [--write]

План: {"source": "server/dwrapp/cloud.php", "dir": "server/dwrapp/cloud", "after": "@mkdir($DATA, 0770, true);",
       "parts": {"db": {"doc": "…", "ranges": [[90, 568]]}, …}}   — строки исходника, включительно

Что проверяется до записи (tools/php_toplevel.php — разбор PHP токенами):
- в диапазонах — только функции, константы, комментарии и пустые строки (ни одной исполняемой строки верхнего уровня);
- ни одна функция не разрезана границей диапазона; ни одна часть не пересекается с другой;
- __FILE__ в переносимом нет; __DIR__ меняется на DWC_DIR (папка входа: часть лежит на папку глубже) — других правок нет.
После записи: php -l каждой части и входа; склейка частей (с __DIR__ обратно) совпадает с вырезанным байт в байт.
У каждой части: declare(strict_types=1) (как у входа — строгие типы действуют пофайлово) и «defined('DWC_RELEASE') ||
exit;» — открытая напрямую по адресу, часть ничего не делает.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    write = "--write" in sys.argv
    src_p = ROOT / plan["source"]
    lines = src_p.read_text(encoding="utf-8").splitlines(keepends=True)
    items = json.loads(subprocess.run(["php", str(ROOT / "tools/php_toplevel.php"), str(src_p)], capture_output=True,
                                      text=True, check=True).stdout)
    taken = {}
    errs = []
    for name, spec in plan["parts"].items():
        for a, b in spec["ranges"]:
            for k in range(a, b + 1):
                if k in taken:
                    errs.append(f"строка {k}: и в {taken[k]}, и в {name}")
                taken[k] = name
    for it in items:
        owners = {taken.get(k) for k in range(it["from"], it["to"] + 1)}
        if it["kind"] == "stmt" and owners != {None}:
            errs.append(f"исполняемая строка {it['from']}–{it['to']} ({it['name']}) попала в часть {owners - {None}}")
        elif len(owners) > 1:
            errs.append(f"{it['kind']} {it['name']} ({it['from']}–{it['to']}) разрезан: {owners}")
    report = []
    files = {}
    cut = []
    for name, spec in plan["parts"].items():
        body = "".join("".join(lines[a - 1:b]) for a, b in spec["ranges"])
        cut.append(body)
        if "__FILE__" in body:
            errs.append(f"{name}: в переносимом есть __FILE__ — поправьте руками")
        if "DWC_DIR" in body:
            errs.append(f"{name}: уже есть DWC_DIR — обратная сверка не выйдет")
        moved = body.replace("__DIR__", "DWC_DIR")
        fns = sum(1 for it in items if it["kind"] == "function" and taken.get(it["from"]) == name)
        doc = "\n".join(" * " + ln if ln else " *" for ln in spec["doc"].split("\n"))
        head = (f"<?php\n/**\n{doc}\n *\n * Часть cloud.php (чистое ядро, 1.0.16 — docs/CORE_PLAN.md): подключается из него, сама ничего не делает.\n"
                f" */\n\ndeclare(strict_types=1);\n\ndefined('DWC_RELEASE') || exit;\n\n")
        files[name] = head + moved.strip("\n") + "\n"
        report.append(f"{name}: {fns} функций, {files[name].count(chr(10))} строк")
    print("\n".join(report))
    if errs:
        print("\n".join("!! " + e for e in errs))
        sys.exit(1)
    if not write:
        return
    anchor = plan["after"]
    out, done = [], False
    drop = set(taken)
    req = ("\n// Разделы сайта — по частям (чистое ядро, 1.0.16 — docs/CORE_PLAN.md): функции и константы каждого раздела — в\n"
           f"// {Path(plan['dir']).name}/*.php, здесь — вступление, CLI и маршруты. Части пишут DWC_DIR вместо __DIR__ (папка входа).\n"
           "const DWC_DIR = __DIR__;\n"
           + "".join(f"require_once __DIR__ . '/{Path(plan['dir']).name}/{n}.php';\n" for n in plan["parts"]))
    for k, ln in enumerate(lines, 1):
        if k in drop:
            continue
        out.append(ln)
        if not done and ln.strip() == anchor:
            out.append(req)
            done = True
    if not done:
        sys.exit(f"не нашлась строка «{anchor}»")
    text = re.sub(r"\n{4,}", "\n\n\n", "".join(out))
    d = ROOT / plan["dir"]
    d.mkdir(parents=True, exist_ok=True)
    for name, t in files.items():
        (d / f"{name}.php").write_text(t, encoding="utf-8")
    src_p.write_text(text, encoding="utf-8")
    bad = []
    for p in [src_p] + [d / f"{n}.php" for n in files]:
        r = subprocess.run(["php", "-l", str(p)], capture_output=True, text=True)
        if r.returncode:
            bad.append(f"{p.name}: {r.stdout.strip()} {r.stderr.strip()}")
    back = []
    for n, body in zip(files, cut):
        t = (d / f"{n}.php").read_text(encoding="utf-8")
        t = t[t.index("defined('DWC_RELEASE') || exit;\n\n") + len("defined('DWC_RELEASE') || exit;\n\n"):]
        if t.replace("DWC_DIR", "__DIR__") != body.strip("\n") + "\n":
            back.append(n)
    print("записано:", ", ".join(f"{n}.php" for n in files), "и", plan["source"])
    print("php -l:", "всё в порядке" if not bad else bad)
    print("сверка с вырезанным:", "байт в байт" if not back else f"РАСХОДИТСЯ: {back}")


if __name__ == "__main__":
    main()
