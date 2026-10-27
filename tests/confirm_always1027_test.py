"""№353 (пакет 27.10, 12:22): разбор сервера — двадцать команд, и каждая — «На сервере «…» выполнить? Подробности — на
экране. Скажите «да» или «нет»» целиком; в ответе это выглядело как «циклично повторяет одно и то же». Теперь второй и
дальше вопрос за ход — коротко, а на команду «только посмотреть» можно ответить «всегда» (голосом или кнопкой) — такие
команды на этом сервере дальше без вопроса."""
import os, queue, sys, threading, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from engine_tools import ToolsMixin  # noqa: E402
from engine_base import Turn  # noqa: E402
import tools as T  # noqa: E402


class E(ToolsMixin):
    def __init__(self):
        self.pending_confirm, self.events, self.follow_up_until = None, [], 0

    def emit(self, k, **d):
        self.events.append((k, d))

    def set_state(self, s):
        pass


def ask(e, turn, q, reply, **kw):
    sent = queue.Queue()

    def drain():
        while True:
            x = sent.get()
            if isinstance(x, tuple):
                x[1].set()
                return
            said.append(x)
    said = []
    threading.Thread(target=drain, daemon=True).start()
    out = {}

    def run():
        out["r"] = e._confirm(turn, q, sent, timeout=5, **kw)
    th = threading.Thread(target=run); th.start()
    for _ in range(50):
        if e.pending_confirm:
            break
        time.sleep(0.05)
    if callable(reply):
        reply()
    else:
        e._answer_confirm(reply)
    th.join(6)
    return out.get("r"), said


e = E(); t = Turn(1)
q = "На сервере «стихия-ритма.рф» выполнить: ps aux --sort=-%cpu | head -15?"
r, said = ask(e, t, q, "да", always=True, again=0)
ok(r is True and "всегда" in said[0] and "Подробности — на экране" in said[0], f"первый вопрос — полностью и с «всегда»: {said}")
ok(e.events[0][0] == "confirm" and e.events[0][1].get("always") is True, "окно: кнопка «Всегда» видна для команды «только посмотреть»")
r, said = ask(e, t, q, "да", always=True, again=1)
ok(r is True and said == ["Ещё команда — выполнить?"], f"второй за ход — коротко: {said}")
r, said = ask(e, t, q, "всегда", always=True, again=2)
ok(r == "always", "«всегда» голосом — разрешить такие команды на сервере")
r, said = ask(e, t, q, "больше не спрашивай", always=True, again=2)
ok(r == "always", "«больше не спрашивай» — то же")
r, said = ask(e, t, "Выполнить команду: rm -rf ./tmp?", "всегда", always=False, again=0)
ok(r is True and "всегда" not in said[0], "команда, которая меняет, — «всегда» не запоминается, только «да» на этот раз")
r, _ = ask(e, t, q, "нет", always=True, again=3)
ok(r is False, "«нет» — нет")
r, _ = ask(e, t, q, lambda: (e.pending_confirm.update(answer=True, always=True), e.pending_confirm["event"].set()), always=True, again=0)
ok(r == "always", "кнопка «Всегда» в окне")

tb = T.Toolbox.__new__(T.Toolbox)
ok(tb.server_readonly({"command": "ps aux --sort=-%cpu | head -15; free -m; df -h /"}) and not tb.server_readonly({"command": "systemctl restart nginx"})
   and not tb.server_readonly({"command": "rm -rf /var/log/old"}), "«только посмотреть»: ps, free, df — да; перезапуск и удаление — нет")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok('srv.update(s_["id"], {"ask": "changes"})' in src, "«всегда» сохраняется в настройке сервера (студия → «Серверы»)")
hud = (ROOT / "ui/hud.html").read_text(encoding="utf-8")
ok('id="ya"' in hud and "always: true" in hud, "виджет: кнопка «Всегда»")
print("ИТОГ:", "все проверки пройдены" if not fails else f"не пройдено {len(fails)}")
sys.exit(1 if fails else 0)
