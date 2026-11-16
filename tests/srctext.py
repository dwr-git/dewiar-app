"""Текст исходника для проверок «по тексту» (чистое ядро, docs/CORE_PLAN.md): файл, который разложен на модули, читается
вместе со своими частями — проверка «в коде есть такая строка» не зависит от того, в каком модуле строка теперь живёт.

    import srctext
    src = srctext.text(ROOT, "core/tools.py")        # core/tools.py + core/tools_*.py
"""
from pathlib import Path

# файл -> его части после раскладки (шаблоны относительно корня проекта)
PARTS = {
    "core/tools.py": ("core/tools_*.py",),
    "core/engine_commands.py": ("core/commands_*.py",),
    "core/engine_answer.py": ("core/answer_*.py",),
}


def text(root, rel):
    root = Path(root)
    out = [(root / rel).read_text(encoding="utf-8")]
    for pat in PARTS.get(rel, ()):
        for p in sorted(root.glob(pat)):
            out.append(p.read_text(encoding="utf-8"))
    return "\n".join(out)
