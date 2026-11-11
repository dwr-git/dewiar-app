"""«Забывает IP» (отзывы): узнала адрес командой — а на «а какой у него провайдер?» искала заново или выдумывала: в истории
разговора оставался только её ответ словами. Теперь то, что узнали инструменты (поиск, погода, команда, файл…), коротко
(до 280 знаков, до 3 за ответ) лежит в истории и идёт модели с последними 4 ответами; пароли — ***; модель не повторяет
эту пометку человеку. И (GitHub #7) повторный запуск на Linux возвращает виджет на экран."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_base as EB  # noqa: E402
import engine_answer as EA  # noqa: E402
import llm  # noqa: E402

f = EB.fact_line("run_command", {"command": "curl -s ifconfig.me"}, "203.0.113.7\n")
ok(f == "run_command(curl -s ifconfig.me) → 203.0.113.7", f"строка находки: {f}")
f = EB.fact_line("web_search", {"query": "x"}, "а" * 1000)
ok(len(f) < 330 and f.endswith("…"), "длинный результат — коротко")
f = EB.fact_line("run_command", {"command": "echo 'Qwerty123' | sudo -S apt update"}, "ok")
ok("Qwerty123" not in f, f"пароль в команде — ***: {f}")

hist = []
for n in range(10):
    hist += [{"role": "user", "content": f"вопрос {n}"},
             {"role": "assistant", "content": f"ответ {n}", "who": "lira", "facts": [f"run_command(ip {n}) → 10.0.0.{n}"]}]
hist.append({"role": "user", "content": "а какой у него провайдер?"})
out = EA.team_window(hist, "lira", lambda p: "Патрик")
with_f = [m["content"] for m in out if "[узнано инструментами" in m["content"]]
# 0.87 (кэш подсказки): не «последние 4» (тогда с каждым новым ответом пометка пропадала у старого и середина разговора
# менялась), а пачками: не больше 2·FACT_TURNS, набор меняется раз в FACT_TURNS новых находок
ok(EB.FACT_TURNS < len(with_f) <= 2 * EB.FACT_TURNS and "10.0.0.9" in with_f[-1] and "10.0.0.1" not in " ".join(with_f),
   f"находки — у последних ответов (не больше {2 * EB.FACT_TURNS}), старые не тянем: {len(with_f)}")
h11 = hist + [{"role": "assistant", "content": "ответ 10", "who": "lira", "facts": ["run_command(ip 10) → 10.0.0.10"]},
                   {"role": "user", "content": "дальше"}]
out11 = EA.team_window(h11, "lira", lambda p: "Патрик")
ok([m["content"] for m in out11[:len(out) - 1]] == [m["content"] for m in out[:-1]],
   "ещё одна находка — начало разговора то же (пометки у старых ответов не пропадают с каждым ответом)")
ok("опирайся на это" in with_f[-1], "модели сказано: опирайся на найденное, не ищи заново")
# пометку модель могла повторить — человеку её не показываем и вслух не читаем
ok(EA.ACTS_RX.sub("", "Провайдер — Ростелеком. [узнано инструментами — опирайся на это: run_command(ip) → 1.2.3.4]").strip() == "Провайдер — Ростелеком.",
   "повторённая пометка из ответа убирается")
cf = llm.CodeFilter()
spoken = cf.feed("Провайдер — Ростелеком.\n[узнано инструментами — опирайся: x]\nВсё.\n")
ok("узнано" not in spoken and "Ростелеком" in spoken and "Всё" in spoken, f"вслух пометку не читаем: {spoken!r}")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("name in FACT_TOOLS" in src and "turn.facts" in src, "находки инструментов копятся в ходе")
ok('"facts": facts' in (ROOT / "core/engine_answer.py").read_text(encoding="utf-8"), "и ложатся в историю с ответом")
app = (ROOT / "ui/app.py").read_text(encoding="utf-8")
ok("api.bring_back()" in app and "_keep_on_screen(gw)" in app[app.index("def bring_back"):app.index("def tray_state")],
   "Linux: повторный запуск — виджет поверх и целиком на экране (GitHub #7)")
# 22.10, владелец: «свернул блокнот вместе с виджетом — после разворачивания открывается только виджет»
import re as _re  # noqa: E402
cls = app[app.index("    def to_tray(self"):app.index("    def tray_state(self")]
ns = {"WIN": True, "_notify": lambda *a: None}
exec("class A:\n" + cls, ns)
a = ns["A"](); a.in_tray, a.popped, a._tray, a._pad_on = False, False, None, True
opened = []
a.pad_hide = lambda: setattr(a, "_pad_on", False); a._hide_now = lambda: None; a.show = lambda: None; a._js = lambda c: None
a.pad_open = lambda: opened.append(1); a._gtk = lambda f: None
a.to_tray(quiet=True); a.from_tray()
import time as _t  # noqa: E402
_t.sleep(0.6)
ok(opened == [1], "блокнот был открыт — вернулся вместе с виджетом")
opened.clear(); a._pad_on = False
a.to_tray(quiet=True); a.from_tray(); _t.sleep(0.6)
ok(opened == [], "блокнот был закрыт — не открываем")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
