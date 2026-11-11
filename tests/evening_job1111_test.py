"""Владелец 11.11, 21:05: «в это время у меня подведение итогов. Что-то запустилось, что-то проверилось — и всё,
результат нулевой; какой-то навык проверки договора — я никаких договоров не загружал». В виджете — «Навык — готово»,
«Ход работы (3)»: «Дела: итог», «Деньги: отчёт», навык contract-check — и ни слова итога (итог решил промолчать, а шаги
дела уже показались). Теперь: шаги дела по расписанию в окнах не показываются (только итог или ничего); итогу дня навыки
плагинов не даются (use_skill убран из его инструментов); итог молчит — строка в виджете «рассказать нечего», без голоса."""
import os, sys, threading
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
i, j = et.index("def _use_tool("), et.index("def _reminder_link_files(")
ok(et[i:j].count('self.emit("tool"') == 1 and et[i:j].count("_temit(") >= 7, "шаги дела по расписанию — не в окна (все события «tool» хода — через _temit)")
ok('_temit = (lambda **kw: None) if getattr(turn, "via_job", False)' in et, "у дела по расписанию _temit молчит")
ea = (ROOT / "core/engine_answer.py").read_text(encoding="utf-8")
ok('specs = [x for x in specs if x.get("name") != "use_skill"]' in ea and 'SUMMARY_JOB_RX.search(text.split("»", 1)[0])' in ea,
   "итогу дня навыки плагинов не даются")

import engine_music as EM  # noqa: E402
ok(EM.SUMMARY_JOB_RX.search("Подведи итог дня: что сделано, траты, планы на завтра"), "«Итог дня» узнаётся как итог")


class Fake(EM.MusicMixin):
    def __init__(self, answer):
        self.turn, self.state, self.alarm, self.notes, self.said, self.answer = None, "idle", None, [], [], answer
        self.stopping = threading.Event()

        class R:
            def update(self, *a, **k):
                pass
        self.reminders = R()

    def _bot_for(self, d):
        return None

    def _job_prompt(self, item):
        return "x"

    def ask(self, prompt, via=None, raw=False, shown="", report=None):
        report(True, self.answer)

    def note(self, t):
        self.notes.append(t)

    def emit(self, *a, **k):
        self.said.append((a, k))

    def announce(self, t):
        self.said.append(("announce", t))

    def health_problem(self, *a, **k):
        pass


f = Fake("ТИШИНА")
f._run_job({"id": "1", "text": "Подведи итог дня: что сделано, траты, планы на завтра", "preset": "evening"})
ok(f.notes and "Итог дня" in f.notes[0] and "рассказать нечего" in f.notes[0] and not f.said, f"итог промолчал — строка в виджете, без голоса: {f.notes}")
f = Fake("ТИШИНА")
f._run_job({"id": "2", "text": "Проверь почту: есть ли письма от банка"})
ok(not f.notes and not f.said, "проверка почты без нового — тихо, как раньше")
f = Fake("Сегодня закрыли 3 дела и потратили 40 рублей.")
f._run_job({"id": "3", "text": "Подведи итог дня", "preset": "evening"})
ok(any(x[0] == "announce" for x in f.said) and not f.notes, "итог есть — говорит, как раньше")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
