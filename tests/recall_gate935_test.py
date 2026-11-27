"""«Ум Лиры», ворота внимания (отчёт №935, 20.11): «Задача „Создание тестовых материалов B1.7“ — эта задача меня интересует»
поднимала к вопросу старые итоги задач про Obsidian — совпали общие «задача» и «интересует». Теперь общие слова (задача,
файл, папка, работа, интересует…) сами записи не тянут: нужны слова темы, и в найденном тоже."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from recall import Recall  # noqa: E402

bad = 0


def ok(c, m):
    global bad
    bad += 0 if c else 1
    print(("✅ " if c else "❌ ") + m)


ws = Path(tempfile.mkdtemp())
for rel, txt in {
    "Задачи/2026-10-24 2043 Починить связи в Obsidian/итог.md": "# Итог задачи\n\nЗадача выполнена: связи в Obsidian починены. Если интересует подробнее — журнал задачи.",
    "Задачи/2026-10-28 1721 В obsidian порядок/итог.md": "# Итог задачи\n\nЗадача: навести порядок в Obsidian. Интересует ли вас продолжение работы?",
    "Задачи/2026-11-18 1931 Создание тестовых материалов B1.7/итог.md": "# Итог\n\nСозданы тестовые материалы для уровня B1.7 в формате MD по структуре папки «Тренировка».",
    "Заметки/Маша.md": "# Маша\n\nДень рождения Маши — 12 марта.",
}.items():
    (ws / rel).parent.mkdir(parents=True, exist_ok=True)
    (ws / rel).write_text(txt, encoding="utf-8")
r = Recall(lambda: ws)
c = r.context("Задача «Создание тестовых материалов B1.7»  эта задача меня интресует")
ok("B1.7" in c and "Obsidian" not in c, f"нужная задача — да, про Obsidian — нет: {c[:160]!r}")
ok(r.context("что там с задачей, меня интересует результат") == "", "одни общие слова — к вопросу ничего")
ok("12 марта" in r.context("Когда у Маши день рождения?"), "обычный вопрос по заметке — как раньше")
ok("Obsidian" in r.context("как там порядок в Obsidian?"), "тема названа — задача про Obsidian находится")
print("ИТОГ:", "всё в порядке" if not bad else f"ошибок {bad}")
sys.exit(1 if bad else 0)
