"""№591 (Vijay, 06.11, Windows 11, нестабильный интернет): «очень бесит, когда Лира постоянно сообщает поверх всех окон,
что соединение с таким-то мозгом восстановлено, соединение потеряно. Вечно вылезает посреди экрана, а спрятать нельзя».
В журнале — за полдня три пары «не отвечает — думают модели Dewiar» / «Ваша модель снова на связи», и каждый раз окно
Windows и виджет из трея. Теперь:
— о таком переключении — тихо: без окна системы, виджет из трея не поднимается; строкой в самом виджете;
— «не отвечает» — один раз за 6 часов, «снова на связи» — только если о разрыве говорили; дальше разрывы — в журнал;
— строка «не отвечает» убирается, когда связь вернулась."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_brain, engine_remote  # noqa: E402
toasts, events = [], []
engine_remote.desktop_notify = lambda text, critical=False: toasts.append(text)


class Eng(engine_brain.BrainMixin, engine_remote.RemoteMixin):
    def __init__(self):
        self.status = {"note": ""}
        self.chat = types.SimpleNamespace(notify_on=lambda: False)

    def emit(self, ev, **kw):
        events.append((ev, kw))

    def note(self, t):
        self.status["note"] = t

    def _g(self, t):
        return t


clock = [1000.0]
engine_brain.time = types.SimpleNamespace(monotonic=lambda: clock[0], time=lambda: clock[0], sleep=lambda s: None)
e = Eng()
pushes = lambda: [kw for ev, kw in events if ev == "push"]          # noqa: E731
e._brain_flap("down", "Думают модели Dewiar", "«polza.ai» сейчас не отвечает — подключил модели Dewiar по ключу.")
ok(len(pushes()) == 1 and pushes()[0].get("quiet") and not toasts, "первый разрыв — одно тихое сообщение, без окна Windows")
ok("не отвечает" in e.status["note"], "и строка в виджете")
clock[0] += 1900
e._brain_flap("back", "Ваша модель снова на связи", "Думаю моделью «polza.ai».")
ok(len(pushes()) == 2 and pushes()[1].get("quiet") and e.status["note"] == "", "связь вернулась — одно тихое «снова на связи», строка убрана")
for _ in range(3):                                                    # интернет моргает весь день
    clock[0] += 3600
    e._brain_flap("down", "Думают модели Dewiar", "…")
    clock[0] += 600
    e._brain_flap("back", "Ваша модель снова на связи", "…")
ok(len(pushes()) == 2 and not toasts, f"повторные разрывы и возвраты в те же 6 часов — молча (сообщений {len(pushes())})")
clock[0] += 7 * 3600
e._brain_flap("down", "Думают модели Dewiar", "…")
ok(len(pushes()) == 3, "через 6 часов — можно сказать снова")
# обычные уведомления (напоминания, итоги задач) — как раньше
e.push("Готово", "Задача сделана")
ok(len(toasts) == 1 and not pushes()[-1].get("quiet"), "обычные уведомления — с окном системы, как раньше")
src = (ROOT / "core/engine_brain.py").read_text(encoding="utf-8")
ok(src.count("self._brain_flap(") == 2, "переключение «не отвечает» и возврат — через _brain_flap")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('.on("push", e => { if (e && e.quiet) return; popUp();' in hud, "виджет: тихое сообщение не поднимает его из трея")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
