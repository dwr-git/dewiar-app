"""Владелец 20.11, 00:31: «Лира туговато стала откликаться, приходится по 5 раз звать её по имени… ложных срабатываний
нет». После 1.0.43 (каждое имя проверяет точная модель) две вещи делали зов тугим:
1) остановили ответ кнопкой — Лира считала это ложным срабатыванием и минуту не слышала имя, хотя имя уже подтвердила
   точная модель (это был зов, а кнопка — просто «хватит»);
2) «Лира, какая погода» целиком, а точная модель написала «Лера, какая погода» — длинную фразу не принимали, хотя быстрый
   слух слышал имя. Теперь: быстрый слух слышал имя и первое слово точной модели заметно на него похоже (≥ 0,7) — зов.
Ложные остаются за бортом: имя в середине фразы, непохожее первое слово, остановка ответа, имя которого не проверяли."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_commands as EC  # noqa: E402
import ears_name as EN  # noqa: E402


class E(EC.CommandsMixin):
    def __init__(self):
        self.muted, self.state, self.wake_time, self._quiet_until = False, "speaking", 0.0, 0.0
        self.status, self.follow_up_until, self.calls = {"note": ""}, 0.0, []
    def interrupt(self, reason, follow=True): self.calls.append(("interrupt", reason, follow)); self.state = "idle"
    def play_tone(self, t): self.calls.append(("tone", t))
    def note(self, t): self.status["note"] = t
    def _g(self, t): return t
    def listen_for_command(self, s=8): self.calls.append(("listen", s)); self.state = "listening"
    def go_sleep(self, word="", media=True): self.calls.append(("sleep", word)); self.state = "idle"
    def _wake_was_false(self, why): self.calls.append(("false", why))


e = E(); e.wake_time = time.monotonic() - 6; e._voice_turn_t = time.monotonic() - 5     # имя подтверждено, отвечает
e.command("ptt", {})
ok(e._quiet_until == 0.0 and not any(c[0] == "false" for c in e.calls) and ("interrupt", "кнопка", False) in e.calls,
   "имя подтвердила точная модель — остановка кнопкой не глушит голос на минуту")
e2 = E(); e2.wake_time = time.monotonic() - 6                                          # без проверки (wake_verify выкл.)
e2.command("ptt", {})
ok(e2._quiet_until > time.monotonic() + 50 and any(c[0] == "false" for c in e2.calls), "имя не проверяли — как раньше: минута тишины")


class N(EN.NameMixin):
    aliases = {"lira": ["Лира", "Лирочка"]}


n = N()
ok(n._name_like("Лера какая погода", 0.7) and n._name_like("Ира, напомни", 0.7), "«Лера, какая погода», «Ира, напомни» — похоже на имя (≥ 0,7)")
ok(not n._name_like("Ладно какая погода", 0.7) and not n._name_like("Ли", 0.7) and not n._name_like("Слушай а лира где", 0.7),
   "непохожее первое слово и имя не в начале — не зов")
ok(n._name_like("Лиру", 0.55) and not n._name_like("спасибо"), "короткое ослышанное — по-прежнему (0,55)")
src = (ROOT / "core/ears_name.py").read_text(encoding="utf-8")
ok("(short and self._name_like(text)) or self._name_like(text, 0.7)" in src and "self.vosk_wake_check == uid and text" in src,
   "послабление — только когда быстрый слух сам слышал имя")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
