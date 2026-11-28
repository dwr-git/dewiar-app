"""№1155 и №1156 (28.11, разбор кода человеком): прямые голосовые команды — без модели — обходили настройки «Умений».
«Выключи компьютер» сразу планировало выключение, хотя у питания включено «спрашивать»; «пауза» жала кнопку плеера, хотя
«Кнопки плеера» выключены. Теперь у прямой команды те же права, что у модели: спросить — спрашивает (нет ответа — ничего
не делает), выключено — не жмёт. Отмена выключения — по-прежнему без вопроса."""
import os, sys, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import engine_music  # noqa: E402


class Power:
    def __init__(self): self.done = []
    def schedule(self, act, on_error=None): self.done.append(act); return "Выключаю через минуту"
    def cancel(self): self.done.append("cancel"); return True


class TB:
    def __init__(self, pol): self.pol, self.hooks = pol, {}
    def policy(self, name): return self.pol.get(name, (True, False))


class E(engine_music.MusicMixin):
    def __init__(self, pol, answer):
        self.toolbox, self.power, self.answer = TB(pol), Power(), answer
        self.said, self.asked, self.events = [], [], []
        self.radio = type("R", (), {"playing": False, "paused": False})()
        self.server = False

    def _say_quick(self, msg, text): self.said.append(msg)
    def announce(self, msg): self.said.append(msg)
    def emit(self, *a, **k): self.events.append(a)
    def set_state(self, s): pass
    def note(self, m): pass

    def confirm(self, q, timeout=60, **k):
        self.asked.append(q)
        return self.answer


def run(pol, answer, text="выключи компьютер"):
    e = E(pol, answer)
    r = e._pc_cmd(text)
    for _ in range(50):
        if not any(t.name == "power-ask" and t.is_alive() for t in threading.enumerate()):
            break
        time.sleep(0.02)
    return r, e


r, e = run({"power": (True, False)}, None)
ok(r and e.power.done == ["shutdown"] and not e.asked, "без «спрашивать» — как раньше: выключение сразу (с минутой на отмену)")
r, e = run({"power": (True, True)}, True)
ok(r and e.asked == ["Выключить компьютер?"] and e.power.done == ["shutdown"], f"«спрашивать» включено — спросила, «да» — выключает: {e.asked}")
r, e = run({"power": (True, True)}, False)
ok(r and e.asked and e.power.done == [] and "не трогаю" in " ".join(e.said), f"«нет» — ничего не делает: {e.said}")
r, e = run({"power": (True, True)}, None)
ok(e.power.done == [] and "ничего не делаю" in " ".join(e.said), "никто не ответил — ничего не делает")
r, e = run({"power": (True, True)}, None, "отмени выключение")
ok(r and e.power.done == ["cancel"] and not e.asked, "отмена выключения — без вопроса")
r, e = run({"power": (False, False)}, True)
ok(r is False and e.power.done == [], "питание выключено в «Умениях» — команда не наша (как раньше)")
src = (ROOT / "core/engine_music.py").read_text(encoding="utf-8")
ok('self._music_service() == "yandex") and self.toolbox.policy("media_control")[0]:' in src,
   "№1156: кнопки плеера голосом — только если «Кнопки плеера» разрешены")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
