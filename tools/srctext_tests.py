"""Проверки, читающие исходник модуля текстом, — на чтение «вместе с частями» (tests/srctext.py), после раскладки модуля
(чистое ядро, docs/CORE_PLAN.md). Меняет (ROOT / "core/X.py").read_text(…) и (ROOT / "core" / "X.py").read_text(…) на
srctext.text(ROOT, "core/X.py") и добавляет импорт srctext, если его нет.

    python3 tools/srctext_tests.py core/engine_audio.py [--write]
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rel = sys.argv[1]
write = "--write" in sys.argv
d, name = rel.rsplit("/", 1)
pat = re.compile(r'\((\w+) / "' + re.escape(rel) + r'"\)\.read_text\((?:encoding="utf-8")?\)|\((\w+) / "' + re.escape(d)
                 + r'" / "' + re.escape(name) + r'"\)\.read_text\((?:encoding="utf-8")?\)')
IMP = "import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)"
for p in sorted((ROOT / "tests").glob("*_test.py")):
    s = p.read_text(encoding="utf-8")
    n = 0

    def sub(m):
        global n
        n += 1
        return f'srctext.text({m.group(1) or m.group(2)}, "{rel}")'
    t = pat.sub(sub, s)
    if not n:
        continue
    if "import srctext" not in t:
        lines = t.split("\n")
        import ast                                       # только настоящие строки верхнего уровня, не текст в строках
        top = [n for n in ast.parse(t).body if n.lineno <= 80]
        sp = [n.end_lineno for n in top if isinstance(n, ast.Expr) and "sys.path" in ast.get_source_segment(t, n)]
        at = (sp[-1] if sp else max(n.end_lineno for n in top if isinstance(n, (ast.Import, ast.ImportFrom)))) - 1
        lines.insert(at + 1, "sys.path.insert(0, str(Path(__file__).resolve().parent))\n" + IMP)
        t = "\n".join(lines)
        if "from pathlib import Path" not in t and "import pathlib" not in t:
            t = t.replace("\nimport ", "\nfrom pathlib import Path\nimport ", 1)
    print(f"{p.name}: {n}")
    if write:
        p.write_text(t, encoding="utf-8")
