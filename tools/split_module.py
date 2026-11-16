"""Разложить большой модуль ядра на модули по смыслу — без изменения поведения (чистое ядро, docs/CORE_PLAN.md).

    python3 tools/split_module.py <план.json> [--write]

План: {"source": "core/tools.py", "base": "tools_base", "patch": ["launch", ...],
       "modules": {"tools_web": {"doc": "…", "names": [...], "lines": [[от, до], ...]}, ...},
       "keep": [...]}  — что остаётся в исходном файле (реестр, фасад).

Что делает:
- переносит определения верхнего уровня (функции, классы, константы — с комментариями прямо над ними) в новые модули
  слово в слово, со своими импортами: стандартные — как в исходнике, общие — из модуля-основы, соседние — друг из друга;
- имена, которые проверки подменяют (patch: launch, WIN…), в перенесённом коде читаются через модуль-основу
  (base.launch) — подмена tools_base.launch действует везде;
- исходный файл становится фасадом: всё прежнее доступно под прежними именами (import tools; tools.t_web_search);
- без --write — только отчёт: размеры, зависимости, циклы, имена из фасада, которые нужны модулям (их быть не должно).
"""
import ast
import builtins
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}


def defined(n):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {n.name}
    if isinstance(n, ast.Assign):
        return {t.id for t in n.targets if isinstance(t, ast.Name)} | {e.id for t in n.targets if isinstance(t, ast.Tuple)
                                                                      for e in t.elts if isinstance(e, ast.Name)}
    if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
        return {n.target.id}
    if isinstance(n, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in n.names}
    if isinstance(n, ast.If):                       # if WIN: import winsys
        out = set()
        for x in n.body + n.orelse:
            out |= defined(x)
        return out
    return set()


def used(n):
    """Имена, которые узел читает (глобально): все Name(Load), кроме тех, что он сам присваивает внутри функций."""
    out = set()
    for x in ast.walk(n):
        if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load):
            out.add(x.id)
    return out


def locals_of(n):
    """Имена, которые внутри функций/классов узла — локальные (параметры, присвоения, импорты внутри функции)."""
    loc = set()
    for f in ast.walk(n):
        if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = f.args
            for p in a.args + a.kwonlyargs + a.posonlyargs + ([a.vararg] if a.vararg else []) + ([a.kwarg] if a.kwarg else []):
                loc.add(p.arg)
            for x in ast.walk(f):
                if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                    loc.add(x.id)
                elif isinstance(x, (ast.Import, ast.ImportFrom)):
                    loc |= {(a.asname or a.name).split(".")[0] for a in x.names}
                elif isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and x is not f:
                    loc.add(x.name)
                elif isinstance(x, ast.ExceptHandler) and x.name:
                    loc.add(x.name)
                elif isinstance(x, ast.comprehension):
                    for t in ast.walk(x.target):
                        if isinstance(t, ast.Name):
                            loc.add(t.id)
    return loc


def global_names(n):
    out = set()
    for x in ast.walk(n):
        if isinstance(x, ast.Global):
            out |= set(x.names)
    return out


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    write = "--write" in sys.argv
    src_path = ROOT / plan["source"]
    src = src_path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    body = tree.body
    doc_end = body[0].end_lineno if isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) else 0
    # узлы верхнего уровня с комментариями прямо над ними (без пустой строки между) — кроме заголовков разделов «# ---»
    nodes = []
    for n in body[1 if doc_end else 0:]:
        start = (min(d.lineno for d in n.decorator_list) if getattr(n, "decorator_list", None) else n.lineno) - 1
        while start > 0 and lines[start - 1].lstrip().startswith("#") and not re.match(r"#\s*-{3,}", lines[start - 1].strip()) \
                and not lines[start - 1].startswith((" ", "\t")):
            start -= 1
        nodes.append({"n": n, "start": start, "end": n.end_lineno, "def": defined(n)})
    imports = [x for x in nodes if isinstance(x["n"], (ast.Import, ast.ImportFrom))]
    imp_name = {}                                     # имя -> строка импорта для него
    for x in imports:
        n = x["n"]
        for a in n.names:
            nm = (a.asname or a.name).split(".")[0]
            if isinstance(n, ast.Import):
                imp_name[nm] = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
            else:
                imp_name[nm] = ("from", n.module, a.name, a.asname)
    # куда что
    where = {}
    for mod, spec in plan["modules"].items():
        for nm in spec.get("names", []):
            where[nm] = mod
        for a, b in spec.get("lines", []):
            for x in nodes:
                if a <= x["n"].lineno <= b and not isinstance(x["n"], (ast.Import, ast.ImportFrom)):
                    for nm in x["def"]:
                        where.setdefault(nm, mod)
    keep = set(plan.get("keep", []))
    owner = {}                                        # узел -> модуль
    for i, x in enumerate(nodes):
        if isinstance(x["n"], (ast.Import, ast.ImportFrom)):
            continue
        mods = {where[d] for d in x["def"] if d in where and d not in keep}
        if len(mods) > 1:
            raise SystemExit(f"узел в строке {x['n'].lineno} ({x['def']}) — в разные модули: {mods}")
        if mods:
            owner[i] = mods.pop()
    name_mod = {}
    for i, m in owner.items():
        for d in nodes[i]["def"]:
            name_mod[d] = m
    facade_defs = {d for i, x in enumerate(nodes) if i not in owner and not isinstance(x["n"], (ast.Import, ast.ImportFrom)) for d in x["def"]}
    base = plan["base"]
    patch = set(plan.get("patch", []))
    report, deps, files = [], {m: set() for m in plan["modules"]}, {}
    for mod, spec in plan["modules"].items():
        idx = [i for i, m in owner.items() if m == mod]
        idx.sort()
        if not idx:
            report.append(f"{mod}: пусто")
            continue
        mine = {d for i in idx for d in nodes[i]["def"]}
        need = set()
        for i in idx:
            n = nodes[i]["n"]
            need |= used(n) - (locals_of(n) - global_names(n))
        need -= mine | BUILTINS
        std, frm, rewrites = [], {}, []
        for nm in sorted(need):
            if nm in patch and mod != base:
                rewrites.append(nm)
            elif nm in imp_name:
                v = imp_name[nm]
                if isinstance(v, str):
                    std.append(v)
                else:
                    frm.setdefault(v[1], []).append(v[2] + (f" as {v[3]}" if v[3] else ""))
            elif nm in name_mod:
                frm.setdefault(name_mod[nm], []).append(nm)
                deps[mod].add(name_mod[nm])
            elif nm in facade_defs:
                report.append(f"!! {mod} берёт из фасада «{nm}» — перенесите его в {base} или в модуль")
            else:
                report.append(f"?  {mod}: имя «{nm}» не найдено (встроенное? из if-импорта?)")
        # текст: узлы слово в слово, с подменой patch-имён на base.X
        chunks = []
        for i in idx:
            x = nodes[i]
            seg = lines[x["start"]:x["end"]]
            if rewrites and mod != base:
                reps = []
                for y in ast.walk(x["n"]):
                    if isinstance(y, ast.Name) and y.id in patch and isinstance(y.ctx, ast.Load) and y.id not in (locals_of(x["n"]) - global_names(x["n"])):
                        reps.append((y.lineno, y.col_offset, y.end_col_offset, y.id))
                reps.sort(reverse=True)
                seg = list(seg)
                for ln, c0, c1, nm in reps:
                    k = ln - 1 - x["start"]
                    s = seg[k]
                    # col_offset — в байтах UTF-8
                    b = s.encode("utf-8")
                    seg[k] = (b[:c0] + f"{'base'}.{nm}".encode() + b[c1:]).decode("utf-8")
            chunks.append("".join(seg).rstrip("\n") + "\n")
        head = [f'"""{spec["doc"]}"""']
        std_mods = sorted(set(std), key=lambda s: (not s.startswith("import "), s))
        third = []
        if std_mods:
            head.append("\n".join(s for s in std_mods))
        froms = []
        for m, names in sorted(frm.items(), key=lambda kv: (kv[0] not in ("datetime", "pathlib"), kv[0])):
            names = sorted(set(names), key=lambda s: (s.lstrip("_").lower(), s))
            line = f"from {m} import " + ", ".join(names)
            if len(line) > 118:
                body_ = ", ".join(names)
                parts, cur = [], "    "
                for nm in names:
                    if len(cur) + len(nm) + 2 > 118:
                        parts.append(cur.rstrip())
                        cur = "    "
                    cur += nm + ", "
                parts.append(cur.rstrip().rstrip(","))
                line = f"from {m} import (\n" + "\n".join(parts) + ")"
            froms.append(line)
        if rewrites:
            froms.append(f"import {base} as base          # {', '.join(sorted(rewrites))} — через основу: проверки подменяют их там")
        text = "\n\n".join(head) + ("\n\n" + "\n".join(froms) if froms else "") + "\n\n\n" + "\n\n".join(chunks)
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        files[mod] = text
        report.append(f"{mod}: {len(idx)} определений, {text.count(chr(10))} строк; зависит от: {', '.join(sorted(deps[mod])) or '—'}")
    # циклы
    def cyc(m, path):
        for d in deps.get(m, ()):
            if d in path:
                return path[path.index(d):] + [d]
            r = cyc(d, path + [d])
            if r:
                return r
        return None
    for m in deps:
        c = cyc(m, [m])
        if c:
            report.append("!! цикл: " + " → ".join(c))
            break
    print("\n".join(report))
    if not write:
        return
    # фасад: без перенесённых узлов, с импортом всего перенесённого (прежние имена на месте)
    drop = set()
    for i in owner:
        drop |= set(range(nodes[i]["start"], nodes[i]["end"]))
    first = min(nodes[i]["start"] for i in owner)
    out = []
    order = [m for m in plan["modules"] if m in files]
    reexp = []
    for m in order:
        names = sorted({d for i, mm in owner.items() if mm == m for d in nodes[i]["def"]} - set(plan.get("no_reexport", ())),
                       key=lambda s: (s.lstrip("_").lower(), s))
        body_, cur = [], "    "
        for nm in names:
            if len(cur) + len(nm) + 2 > 118:
                body_.append(cur.rstrip())
                cur = "    "
            cur += nm + ", "
        body_.append(cur.rstrip().rstrip(","))
        reexp.append(f"from {m} import (  # noqa: F401,E402 — прежние имена tools.* на месте\n" + "\n".join(body_) + ")")
    for k, ln in enumerate(lines):
        if k == first:
            out.append(plan.get("facade_note", "") + "\n".join(reexp) + "\n\n\n")
        if k in drop:
            continue
        out.append(ln)
    facade = re.sub(r"\n{4,}", "\n\n\n", "".join(out))
    for m, t in files.items():
        (src_path.parent / f"{m}.py").write_text(t, encoding="utf-8")
    src_path.write_text(facade, encoding="utf-8")
    print("записано:", ", ".join(f"{m}.py" for m in files), "и фасад", plan["source"])


if __name__ == "__main__":
    main()
