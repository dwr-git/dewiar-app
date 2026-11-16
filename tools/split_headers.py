"""После раскладки (tools/split_module.py, tools/split_class.py): заголовки разделов «# ----» (с комментариями под ними)
— из прежнего файла в новые модули, перед первым определением своего раздела; в исходном файле пустые заголовки
убираются. Работает и для верхнего уровня, и для методов класса (отступ 4).

    python3 tools/split_headers.py <прежний файл> <исходный файл> <модуль>...
"""
import ast
import re
import sys

H = re.compile(r"^\s*#\s*-{3,}")


def nodes(tree):
    for n in tree.body:
        yield n
        if isinstance(n, ast.ClassDef):
            yield from n.body


def name_of(n):
    if hasattr(n, "name"):
        return n.name
    if isinstance(n, ast.Assign):
        for x in n.targets:
            if isinstance(x, ast.Name):
                return x.id
    return None


def main():
    old_p, src_p, mods = sys.argv[1], sys.argv[2], sys.argv[3:]
    orig = open(old_p, encoding="utf-8").read().splitlines(keepends=True)
    starts = sorted((n.lineno if not getattr(n, "decorator_list", None) else min(d.lineno for d in n.decorator_list), n)
                    for n in nodes(ast.parse("".join(orig))) if name_of(n))
    blocks, i = [], 0
    while i < len(orig):
        if H.match(orig[i]):
            j = i + 1
            while j < len(orig) and orig[j].lstrip().startswith("#") and not H.match(orig[j]):
                j += 1
            nxt = next((n for ln, n in starts if ln > j), None)
            blk = orig[i:j] if (j < len(orig) and orig[j].strip() == "") else orig[i:i + 1]
            if nxt is not None:
                blocks.append((name_of(nxt), "".join(blk)))
            i = j
        else:
            i += 1
    for p in [src_p] + mods:
        L = open(p, encoding="utf-8").read().splitlines(keepends=True)
        # сначала убрать из файла все заголовки, затем вставить нужные перед своими определениями
        keep = []
        k = 0
        while k < len(L):
            if H.match(L[k]):
                k += 1
                while k < len(L) and L[k].lstrip().startswith("#") and not H.match(L[k]) and L[k - 1].strip() != "":
                    k += 1
                continue
            keep.append(L[k])
            k += 1
        L = keep
        tt = ast.parse("".join(L))
        ins = []
        for nm, blk in blocks:
            for n in nodes(tt):
                if name_of(n) == nm:
                    s = (min(d.lineno for d in n.decorator_list) if getattr(n, "decorator_list", None) else n.lineno) - 1
                    while s > 0 and L[s - 1].lstrip().startswith("#"):
                        s -= 1
                    ins.append((s, blk))
                    break
        for s, blk in sorted(ins, reverse=True):
            L[s:s] = [blk, "\n"]
        txt = "".join(L)
        txt = re.sub(r"\n{3,}(    (?:#|def |@))", r"\n\n\1", txt)
        txt = re.sub(r"\n{4,}", "\n\n\n", txt).rstrip("\n") + "\n"
        txt = re.sub(r"(?m)^((?:from|import) [^\n]+\n)(class )", r"\1\n\n\2", txt)
        open(p, "w", encoding="utf-8").write(txt)
        print(p, len(ins))


if __name__ == "__main__":
    main()
