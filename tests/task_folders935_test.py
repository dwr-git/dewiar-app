"""№935 (20.11, 1.0.44): «Создать тестовые материалы, основываясь на структуре папки „Тренировка“» — задача не видела папку
и стояла 10 часов, пока человек не дал доступ сам («это всё сказано в файлах задания»). Теперь папка, названная в цели
задачи (полный путь или имя в кавычках после «папка» — если такая одна в Документах, на рабочем столе, в Загрузках), задаче
видна сразу. Весь диск и домашняя папка — никогда; две папки с одним именем — не угадываем."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
import tools_tasks as TT  # noqa: E402

bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


home = Path(tempfile.mkdtemp())
tr = home / "Documents" / "Семашко" / "Проекты" / "Тренировка"
tr.mkdir(parents=True)
(home / "Desktop" / "Отчёт").mkdir(parents=True)
(home / "Documents" / "Отчёт").mkdir(parents=True)
g = TT.guess_folders("Создать тестовые материалы для уровня B1.7, основываясь на структуре папки 'Тренировка'", home=home)
ok(g == [str(tr.resolve())], f"папка по имени — найдена в Документах: {g}")
ok(TT.guess_folders("сделай отчёт по папке «Отчёт»", home=home) == [], "две папки с одним именем — не угадываем")
ok(TT.guess_folders(f"разбери файлы в {tr} и положи итог рядом", home=home) == [str(tr.resolve())], "полный путь — как есть")
ok(TT.guess_folders("разбери папку «Нет такой»", home=home) == [], "нет такой — ничего")
anchor = Path(str(tr.resolve())).anchor
ok(TT.guess_folders(f"посмотри весь диск {anchor}", home=home) == [], "весь диск — никогда")
src = (ROOT / "core/tools_tasks.py").read_text(encoding="utf-8")
ok("found = [x for x in guess_folders(goal) if x not in fl]" in src, "start_task: найденные папки — задаче сразу")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
