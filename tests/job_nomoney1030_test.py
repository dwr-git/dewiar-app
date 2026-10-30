"""Дело по расписанию и кончившиеся деньги на ключе сервиса (пакет 30.10: «Дело по расписанию: на ключе нет оплаченного
пакета или закончились деньги» — 16 раз за день у одного компьютера). Повтор через 5 и 15 минут не поможет до пополнения —
как и «не хватило окна модели» (№407): одна попытка, одно уведомление, следующая — по расписанию."""
import os, sys, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_music import MusicMixin  # noqa: E402
import llm  # noqa: E402


class Fake(MusicMixin):
    JOB_RETRY_MIN = [5, 15]

    def __init__(self, answer):
        self.turn, self.state, self.alarm = None, "idle", None
        self.stopping = threading.Event()
        self.answer, self.asks, self.pushes, self.problems, self.waits = answer, 0, [], [], []
        self.reminders = type("R", (), {"update": lambda *a, **k: None})()

    def _job_prompt(self, item): return "сделай"
    def _bot_for(self, d): return None
    def ask(self, prompt, via=None, raw=False, shown="", report=None):
        self.asks += 1
        report(False, self.answer)
    def health_problem(self, text, kind=""): self.problems.append(text)
    def emit(self, kind, **k): self.pushes.append(k)
    def announce(self, t): pass


os.environ["DEWIAR_JOB_RETRY_SCALE"] = "0"
item = {"id": "j1", "text": "Сводка курса", "repeat": {"kind": "daily"}}
f = Fake(llm.NO_MONEY_TEXT)
f._run_job(item)
ok(f.asks == 1 and len(f.problems) == 1 and len(f.pushes) == 1 and "пополните баланс" in f.pushes[0].get("text", ""),
   f"нет денег на ключе — одна попытка и одно уведомление, без повторов через 5 и 15 минут: попыток {f.asks}")
f = Fake("сервер долго не отвечает")
f._run_job(item)
ok(f.asks == 3, f"случайный сбой — повторы как раньше: попыток {f.asks}")
f = Fake(llm.CTX_TEXT)
f._run_job(item)
ok(f.asks == 1, "окно модели (№407) — тоже без повторов")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
