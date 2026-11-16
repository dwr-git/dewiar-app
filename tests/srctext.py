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
    "core/tasks.py": ("core/tasks_*.py",),
    "core/quality.py": ("core/quality_*.py",),
    "core/llm.py": ("core/llm_*.py",),
    "core/engine_audio.py": ("core/ears_*.py",),
    "core/engine_tools.py": ("core/acts_*.py",),
    "core/sync.py": ("core/sync_*.py",),
    "core/sites_render.py": ("core/sites_parts.py", "core/sites_style.py", "core/sites_art.py", "core/sites_blocks.py"),
}


def text(root, rel):
    root = Path(root)
    out = [(root / rel).read_text(encoding="utf-8")]
    for pat in PARTS.get(rel, ()):
        for p in sorted(root.glob(pat)):
            out.append(p.read_text(encoding="utf-8"))
    return "\n".join(out)
