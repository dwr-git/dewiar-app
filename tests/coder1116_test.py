"""Кодер глазами человека (16.11): «каждую секунду просил подтверждения, проговаривая вслух одну и ту же фразу; жмёшь — он
всё равно договаривает… не сразу понял, что он папку скопировал к себе… „Посмотреть“ показывал старый вариант».
- «Всегда» в вопросе задачи — это действие в этой задаче больше не спрашиваем; вслух — только первый вопрос задачи;
  ответили кнопкой — недосказанный вопрос замолкает (опасная команда — по-прежнему каждый раз).
- Задача над проектом показывает файл из рабочей копии (живой), карточка говорит, что работа идёт в копии.
- Показ результата не перезагружается на каждое событие задачи — только когда файл правда изменился (mtime)."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import os, sys, tempfile, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tasks as TS  # noqa: E402


class Host:
    def __init__(self, answers): self.answers, self.calls = list(answers), []

    def confirm(self, question, timeout=120, cancel=None, always=False, quiet=False):
        self.calls.append({"q": question, "always": always, "quiet": quiet})
        return self.answers.pop(0)


class T:
    def __init__(self): self.id, self.cancel, self.data, self.log = "t1", threading.Event(), {}, []
    def journal(self, x): self.log.append(x)


tm = TS.TaskManager.__new__(TS.TaskManager)
tm.host = Host(["always", True])
t = T()
r1 = tm._permit(t, "run_shell", "Задача «Сайт»: выполнить «python build.py»?")
r2 = tm._permit(t, "run_shell", "Задача «Сайт»: выполнить «python build.py --fast»?")
ok(r1[0] and r2[0] and len(tm.host.calls) == 1, f"«Всегда» — та же команда задачи дальше без вопроса (спрошено {len(tm.host.calls)} раз)")
ok(tm.host.calls[0]["always"] and not tm.host.calls[0]["quiet"], "первый вопрос — вслух и с «Всегда»")
r3 = tm._permit(t, "write_files", "Задача «Сайт» хочет изменить файлы. Разрешить?")
ok(r3[0] and tm.host.calls[-1]["quiet"], "второй вопрос задачи — на экране, без голоса")
src = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
ok('"code_run" + (":" + cmd if warn else "")' in src and '"run_shell" + (":" + cmd[:300] if warn else "")' in src,
   "опасная команда (предупреждение защиты) — своим ключом: «Всегда» её не пропускает")

ea = srctext.text(ROOT, "core/engine_answer.py")
i = ea.index("    def confirm(self, question")
c = ea[i:i + 4200]
ok("quiet=False" in c and 'tag="confirm"' in c and 'getattr(t, "tag", "") == "confirm"' in c and "self.player.stop()" in c,
   "ответили кнопкой — вопрос задачи дальше не договаривается")
er = (ROOT / "core/engine_remote.py").read_text(encoding="utf-8")
ok("def announce(self, text, tag=\"\"):" in er and "turn.tag = tag" in er, "сказанное по своей инициативе помечено, что это вопрос")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok("e.always_title" in hud, "кнопка «Всегда» объясняет: «для этой задачи больше не спрашивать»")

# показ — из рабочей копии
d = Path(tempfile.mkdtemp())
(d / "рабочая копия").mkdir()
(d / "рабочая копия" / "index.html").write_text("<h1>новое</h1>", encoding="utf-8")
(d / "index.html").write_text("<h1>старое</h1>", encoding="utf-8")
t2 = T()
t2.dir, t2.data, t2.title = d, {"project": "/home/u/site"}, "Сайт"
t2.save = lambda: None
tm._emit = lambda t: None
out = tm._run_tool(t2, "show", {"path": "index.html"}) if hasattr(tm, "_run_tool") else None
if out is None:
    ok("рабочая копия/\" + rel0" in src, "задача над проектом показывает файл из рабочей копии (по тексту)")
else:
    ok(t2.data["outputs"][-1]["path"] == "рабочая копия/index.html", f"показ — живой файл из рабочей копии: {t2.data.get('outputs')}")
tj = (ROOT / "ui/studio/tasks.js").read_text(encoding="utf-8")
ok("Работаю в копии вашей папки" in tj, "карточка задачи над проектом: работа в копии, проект — после «Принять изменения»")
ok("o0.mtime" in tj and "tKeepView.dataset.key === vkey" in tj and "mtime=(t.dir" in src,
   "показ результата не перезагружается на каждое событие — только когда файл изменился")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
