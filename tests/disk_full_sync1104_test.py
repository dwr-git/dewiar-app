"""Сбой пакета 04.11 (компьютер 0.81.2): «dewiar.sync: Синхронизация — OSError: [Errno 28] No space left on device».
Диск заполнен — это не ошибка программы: раньше запись шла в «частые сбои» и автоотчётом разработчику, а в студии в карточке
синхронизации висело «[Errno 28] No space left on device». Теперь любая ошибка «нет места» в журнале ядра — без отчёта,
человеку честно «Диск заполнен… освободите хотя бы 1 ГБ» (раз в 10 минут), в карточке — «на диске нет места — синхронизация
ждёт». Ничего не падает: обмен просто повторится, когда место появится."""
import errno, logging, os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_answer as EA  # noqa: E402
import engine_tools as ET  # noqa: E402


class Eng:
    def __init__(self):
        self.reports, self.problems, self.notes, self.pushes = [], [], [], []

    def report_problem(self, key, text):
        self.reports.append(text)

    def health_problem(self, text):
        self.problems.append(text)

    def note(self, t):
        self.notes.append(t)

    def push(self, title, text="", **k):
        self.pushes.append(title)

    _disk_full_seen = EA.AnswerMixin._disk_full_seen


e = Eng()
h = EA.AnswerMixin._install_report_hook(e)
lg = logging.getLogger("dewiar.sync")
try:
    try:
        raise OSError(errno.ENOSPC, "No space left on device")
    except OSError:
        lg.exception("Синхронизация")
    try:
        raise OSError(errno.ENOSPC, "No space left on device")
    except OSError:
        lg.exception("Синхронизация")
    ok(not e.reports and not e.problems, "диск заполнен — не «сбой программы»: ни автоотчёта, ни строки в пульсе")
    ok(len(e.notes) == 1 and "Диск заполнен" in e.notes[0] and "1 ГБ" in e.notes[0], f"человеку — честно и один раз: {e.notes[:1]}")
    ok(e.pushes == ["На диске нет места"], "и уведомлением")
    logging.getLogger("dewiar.notes").error("Заметка не сохранилась: [Errno 28] No space left on device")
    ok(not e.reports and len(e.notes) == 1, "то же из другого места — без отчёта и без повтора в те же 10 минут")
    try:
        raise ValueError("настоящая ошибка")
    except ValueError:
        lg.exception("Синхронизация")
    ok(len(e.reports) == 1 and len(e.problems) == 1, "настоящая ошибка — как раньше, в отчёт")
finally:
    logging.getLogger().removeHandler(h)

sync = types.SimpleNamespace(status={"ok": False, "error": "[Errno 28] No space left on device", "at": 1}, e2e_status=lambda: {})
fake = types.SimpleNamespace(sync=sync, credentials=lambda: ("tok", "", ""), s=types.SimpleNamespace(get=lambda *a: None),
                             account=types.SimpleNamespace(logged_in=lambda: True))
st = ET.ToolsMixin.sync_public(fake)
ok(st["error"].startswith("на диске нет места"), f"карточка синхронизации в студии: {st['error']!r}")
ok(sync.status["error"].startswith("[Errno 28]"), "само состояние синхронизации не трогаем — только показ")
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
