"""Разложить большой класс ядра (примесь движка в core/engine_*.py, TaskManager в core/tasks.py) на модули по смыслу —
без изменения поведения (чистое ядро, docs/CORE_PLAN.md). Тот же приём, что у команд (commands_*.py): методы переезжают
слово в слово в классы-примеси, исходный класс наследует их (в MRO они идут сразу за ним — кто кого перекрывает, не
меняется).

    python3 tools/split_class.py <план.json> [--write]

План: {"source": "core/engine_answer.py", "cls": "AnswerMixin", "base": "engine_base",
       "rules": {"module": "answer_rules", "doc": "…"},            — необязательно: всё верхнего уровня до класса
       "patch": ["BUDGET", ...],                                    — необязательно
       "mixins": {"answer_prompt": {"cls": "PromptMixin", "doc": "…", "methods": [...]}, ...}}

- rules: определения верхнего уровня (регулярки, помощники, вспомогательные классы) — в свой модуль; исходный файл
  берёт их оттуда по именам (прежние <исходник>.X на месте);
- mixins: методы класса — с комментариями прямо над ними; у модуля — «from <base> import *» (если base задан), явный
  импорт нужных имён из rules и нужные строки импортов исходника; имя, которого нет нигде, — в отчёт;
- base: null — у исходника своя шапка импортов: правилам и примесям достаются нужные им строки импортов слово в слово;
- patch: имена, которые проверки подменяют (BUDGET, dt, stream_events…), — в перенесённом и в оставшемся классе
  читаются через модуль правил (base.X, имя — «alias», по умолчанию base): подмена <rules>.X действует везде;
- без --write — только отчёт.
"""
import ast
import builtins
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILTINS = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
sys.path.insert(0, str(ROOT / "tools"))
from split_module import defined, global_names, locals_of, used  # noqa: E402


def wrap(prefix, names):
    names = sorted(set(names), key=lambda s: (s.lstrip("_").lower(), s))
    line = prefix + ", ".join(names)
    if len(line) <= 118:
        return line
    parts, cur = [], "    "
    for nm in names:
        if len(cur) + len(nm) + 2 > 118:
            parts.append(cur.rstrip())
            cur = "    "
        cur += nm + ", "
    parts.append(cur.rstrip().rstrip(","))
    return prefix + "(\n" + "\n".join(parts) + ")"


def rewrite(seg_lines, first_line, node, patch, prefix):
    """Строки узла (seg_lines начинаются со строки first_line, 1-based) с patch-именами -> prefix + имя."""
    if not patch:
        return seg_lines
    loc = locals_of(node) - global_names(node)
    if prefix.rstrip(".") in loc:
        raise SystemExit(f"имя {prefix.rstrip('.')} в строке {first_line} — местное: возьмите другое «alias» в плане")
    reps = sorted({(y.lineno, y.col_offset, y.end_col_offset, y.id) for y in ast.walk(node)
                   if isinstance(y, ast.Name) and y.id in patch and isinstance(y.ctx, ast.Load) and y.id not in loc},
                  reverse=True)
    seg = list(seg_lines)
    for ln, c0, c1, nm in reps:
        k = ln - first_line
        b = seg[k].encode("utf-8")                      # col_offset — в байтах UTF-8
        seg[k] = (b[:c0] + f"{prefix}{nm}".encode() + b[c1:]).decode("utf-8")
    return seg


def main():
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    write = "--write" in sys.argv
    src_path = ROOT / plan["source"]
    src = src_path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == plan["cls"])
    base = plan.get("base")
    base_names = set()
    if base:
        base_names = {n for n in dir(__import__(base)) if not n.startswith("__")}
    patch = set(plan.get("patch") or ())
    rules = plan.get("rules")
    alias = plan.get("alias", "base")                  # имя модуля правил в коде: base.X (своё, если base занято)
    # строки импортов верхнего уровня исходника: имя -> строка
    imp_line = {}
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno < cls.lineno:
            for a in n.names:
                nm = (a.asname or a.name).split(".")[0]
                if isinstance(n, ast.Import):
                    imp_line[nm] = f"import {a.name}" + (f" as {a.asname}" if a.asname else "")
                else:
                    imp_line[nm] = ("from", n.module, a.name + (f" as {a.asname}" if a.asname else ""))

    def import_block(names):
        std, frm = [], {}
        for nm in sorted(names):
            v = imp_line[nm]
            if isinstance(v, str):
                std.append(v)
            else:
                frm.setdefault(v[1], []).append(v[2])
        local = lambda m: (src_path.parent / f"{m.split('.')[0]}.py").exists()      # свои модули ядра — после стандартных
        out = sorted(set(s for s in std if not local(s.split()[1])))
        out += [wrap(f"from {m} import ", ns) for m, ns in sorted(frm.items()) if not local(m)]
        loc = sorted(set(s for s in std if local(s.split()[1])))
        loc += [wrap(f"from {m} import ", ns) for m, ns in sorted(frm.items()) if local(m)]
        return out + ([""] if out and loc else []) + loc

    report, files = [], {}
    head_base = [f"from {base} import *  # noqa: F401,F403 — общие импорты и помощники движка"] if base else []

    # 1) верхний уровень до класса -> rules
    top = [n for n in tree.body if n.lineno < cls.lineno and not isinstance(n, (ast.Import, ast.ImportFrom))
           and not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant))]
    rule_names = set()
    start = end = None
    if rules and top:
        start = top[0].lineno - 1
        while start > 0 and lines[start - 1].startswith("#"):
            start -= 1
        end = top[-1].end_lineno
        need = set()
        for n in top:
            rule_names |= defined(n)
            need |= used(n) - (locals_of(n) - global_names(n))
        body = "".join(lines[start:end]).rstrip("\n") + "\n"
        head = [f'"""{rules["doc"]}"""'] + head_base
        if not base:
            head += import_block(((need - BUILTINS - rule_names) | patch) & set(imp_line))   # подменяемые — и здесь
        files[rules["module"]] = "\n".join(head) + "\n\n" + body
        report.append(f"{rules['module']}: {len(top)} определений, {body.count(chr(10))} строк")
    src_top = {d for n in tree.body if n.lineno > cls.end_lineno for d in defined(n)}   # то, что после класса

    # 2) методы -> примеси
    spans = {}
    for n in cls.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            s = (min(d.lineno for d in n.decorator_list) if n.decorator_list else n.lineno) - 1
            while s > 0 and lines[s - 1].startswith("    #"):
                s -= 1
            spans[n.name] = (s, n.end_lineno, n)
    drop, imports, moved = set(), [], set()
    for mod, spec in plan["mixins"].items():
        need, chunks, pat = set(), [], False
        for nm in spec["methods"]:
            if nm not in spans:
                raise SystemExit(f"нет метода {nm} в {plan['cls']}")
            if nm in moved:
                raise SystemExit(f"метод {nm} — в двух примесях")
            moved.add(nm)
            s, e, n = spans[nm]
            u = used(n) - (locals_of(n) - global_names(n))
            pat |= bool(u & patch)
            need |= u - patch
            chunks.append("".join(rewrite(lines[s:e], s + 1, n, patch, alias + ".")).rstrip("\n") + "\n")
            drop |= set(range(s, e))
        need -= BUILTINS
        from_rules = sorted(need & rule_names)
        from_imp = (need - rule_names - base_names) & set(imp_line)
        from_src = sorted((need - rule_names - base_names) & src_top)
        missing = sorted(need - rule_names - base_names - src_top - set(imp_line))
        if from_src:
            report.append(f"!! {mod}: берёт из {src_path.stem} то, что после класса: {from_src} — так нельзя (цикл)")
        if missing:
            report.append(f"?  {mod}: имена не найдены: {missing}")
        head = [f'"""{spec["doc"]}"""'] + head_base + import_block(from_imp)
        if from_rules and rules:
            head.append(wrap(f"from {rules['module']} import ", from_rules))
        if pat and rules:
            head.append(f"import {rules['module']} as {alias}  # подменяемые в проверках имена — через основу")
        files[mod] = "\n".join(head) + "\n\n\n" + f"class {spec['cls']}:\n" + "\n".join(chunks)
        report.append(f"{mod}: {spec['cls']} — {len(spec['methods'])} методов, {files[mod].count(chr(10))} строк")
        imports.append(f"from {mod} import {spec['cls']}")
    # оставшиеся методы класса тоже читают patch-имена через основу
    keep_rw = {}
    if patch and rules:
        for nm, (s, e, n) in spans.items():
            if nm not in moved:
                seg = rewrite(lines[s:e], s + 1, n, patch, alias + ".")
                if seg != lines[s:e]:
                    keep_rw[s] = (e, seg)
    print("\n".join(report))
    if not write:
        return
    out, k = [], 0
    while k < len(lines):
        ln = lines[k]
        if start is not None and start <= k < end:
            if k == start:
                out.append(wrap(f"from {rules['module']} import ", rule_names) + "  # noqa: F401 — прежние имена на месте\n")
                if keep_rw:
                    out.append(f"import {rules['module']} as {alias}  # подменяемые в проверках имена — через основу\n")
                if start is not None:
                    out.append("\n".join(imports) + "\n")
            k += 1
            continue
        if start is None and k == cls.lineno - 1:
            out.append("\n".join(imports) + "\n\n\n")
        if k in drop:
            k += 1
            continue
        if k in keep_rw:
            e, seg = keep_rw[k]
            out += seg
            k = e
            continue
        out.append(ln)
        k += 1
    text = "".join(out)
    bases = ", ".join(spec["cls"] for spec in plan["mixins"].values())
    text = re.sub(rf"^class {plan['cls']}(\([^)]*\))?:", lambda m: f"class {plan['cls']}({bases}):", text, count=1, flags=re.M)
    text = re.sub(r"\n{3,}(    def |    @)", r"\n\n\1", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    for m, t in files.items():
        (src_path.parent / f"{m}.py").write_text(t, encoding="utf-8")
    src_path.write_text(text, encoding="utf-8")
    print("записано:", ", ".join(f"{m}.py" for m in files), "и", plan["source"])


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "core"))
    main()
