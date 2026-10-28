"""№390 (28.10, Витаха, llama.cpp): задача «застряла» через две минуты — модель написала вызов run_python текстом, с
настоящими переводами строк внутри кода, и разбор его не принял («Вызов функции в тексте не разобран»), а Лира на
«проверь задачу» отвечала «работает» — по памяти разговора. Теперь: вызов текстом с переводами строк и «\\'» разбирается;
к вопросу про задачи — их настоящее состояние (что идёт, что остановилось и почему)."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import llm  # noqa: E402
raw = '\n{"name": "run_python", "arguments": {"code": "import os, glob\nbase = r\'C:\\\\Users\\\\ветал\\\\Documents\\\\Dewiar\'\nfor p in glob.glob(os.path.join(base, \'*\')):\n    print(p)"}}'
c = llm.parse_tool_call(raw)
ok(c and c["name"] == "run_python" and "glob.glob" in c["args"]["code"] and "\n" in c["args"]["code"], f"вызов текстом с переводами строк в коде — разобран: {c}")
c = llm.parse_tool_call('{"name": "write_file", "arguments": {"path": "C:\\Users\\a.md", "content": "it\\\'s ok"}}')
ok(c and c["args"]["path"] == "C:\\Users\\a.md" and c["args"]["content"] == "it's ok", f"«\\U», «\\'» в строке — разобран: {c}")
ok(llm.parse_tool_call('{"name": "get_time", "arguments": {}}') == {"name": "get_time", "args": {}}, "обычный — как раньше")
ok(llm.parse_tool_call("просто текст без вызова") is None, "текст — не вызов")

import engine_answer as EA  # noqa: E402
ok(all(EA.TASK_ASK_RX.search(t) for t in ("почему задача не запущена??", "проверь выполнение задачи", "что с заданием", "ты застряла?"))
   and not EA.TASK_ASK_RX.search("какая погода завтра"), "вопросы про задачи узнаются")


cls = next(v for v in vars(EA).values() if isinstance(v, type) and hasattr(v, "_tasks_now"))
e = types.SimpleNamespace(tasks=types.SimpleNamespace(list=lambda: [
    {"title": "Кинопайплайн 12 шагов", "status": "failed", "status_ru": "не получилось", "error": "застрял: много раз повторил одно и то же действие"},
    {"title": "Архив нейронок", "status": "running", "status_ru": "выполняется", "activity": "пишу файл 3 из 12"}]))
t = cls._tasks_now(e)
ok("«Кинопайплайн 12 шагов» — не получилось (застрял" in t and "«Архив нейронок» — выполняется (пишу файл 3 из 12)" in t and "не по памяти" in t, f"к вопросу — настоящее состояние: {t[:200]}")
e2 = types.SimpleNamespace(tasks=types.SimpleNamespace(list=lambda: []))
ok("Фоновых задач сейчас нет" in cls._tasks_now(e2), "задач нет — так и сказано")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
