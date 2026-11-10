"""№625–628 (08.11, Windows 10, своя модель Qwen3.6-35B в LM Studio): «спрашивает 100 раз одно и то же», «повторяется»,
«не справляется». В журнале: ответ перебивали, пока программа спрашивала «Выполнить действие «pc: FileSystem»? Скажите
«да» или «нет».», — и этот вопрос попадал в историю словами ассистента (…(меня перебили)). Модель стала писать его
сама, текстом, без вызова действия; человек отвечал «Да.» — спрашивать было нечего, и модель снова писала тот же вопрос.
Теперь:
— вопрос программы в историю моими словами не пишется; перебили на нём — пометка «не сделано, ждала разрешения»;
— «да» сразу после такого перебивания — и есть ответ: действие выполняется без второго вопроса;
— старые записи в истории с этим вопросом модель не видит;
— модель всё же написала «Выполнить действие…? Скажите «да» или «нет»» текстом — это вызов текстом (FAKE_NUDGE);
— сценарий экзамена confirm_cut_yes."""
import json, os, sys, threading, time, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import quality  # noqa: E402
Q = "Выполнить действие «pc: FileSystem»? Скажите «да» или «нет»."
model = "Хорошо. Сейчас открою папку с программой и посмотрю конфигурацию. " + Q
ok(quality.fake_call(model, ["mcp_pc_FileSystem"]) == "?", "модель написала вопрос программы сама — это вызов текстом")
ok(quality.fake_call("Удалить это письмо? Скажите «да» или «нет».", []) == "", "свой вопрос модели «да или нет» — не трогаем")
ok(quality.strip_confirm_echo("Сейчас открою папку. " + Q + " Поняла") == "Сейчас открою папку. Поняла", "служебный вопрос убирается из реплики")
ok(quality.strip_confirm_echo("Ещё команда — выполнить? Скажите «да», «нет» или «всегда» — тогда команды, которые только смотрят, "
                              "на этом сервере больше не буду спрашивать.") == "", "и длинный вариант про сервер")

# история для модели: старые записи с вопросом программы
import engine_answer  # noqa: E402
hist = [{"role": "user", "content": "сделай всё"},
        {"role": "assistant", "content": model + " …(меня перебили)", "who": "lira"},
        {"role": "user", "content": "Да."}]
out = engine_answer.team_window(hist, "lira", lambda p: "Лира")
ok(all("Скажите «да»" not in m["content"] and "Выполнить действие" not in m["content"] for m in out),
   f"старый вопрос программы в истории модель не видит: {out[1]['content']!r}")

# перебили на вопросе «Выполнить?»
import engine_remote, engine_tools  # noqa: E402
from engine_base import Turn  # noqa: E402


class Eng(engine_remote.RemoteMixin, engine_tools.ToolsMixin):
    def __init__(self):
        self.history, self.player, self.turn = [], None, None
        self.s = types.SimpleNamespace(get=lambda *a: "lira")
        self.pending_confirm = None
        self.last_turn_time = time.monotonic()

    def switch_persona(self, *a):
        pass


e = Eng()
t = Turn(7)
t.spoken = ["Сейчас открою папку с программой.", Q]
t.sys_said, t.asking = [Q], "pc: FileSystem"
e.turn, e.pending_confirm = t, {"event": threading.Event(), "answer": False}
e._cancel_locked()
last = e.history[-1]["content"]
ok("Скажите" not in last and "Выполнить действие" not in last and last.startswith("Сейчас открою папку с программой."),
   f"в историю — только слова модели: {last!r}")
ok("не сделано" in last and "pc: FileSystem" in last, "с пометкой: действие не сделано, ждала разрешения")
nt = Turn(8); nt.asked = "Да."
ok(e._just_agreed(nt) is True, "«Да.» следующим ходом — это и есть разрешение: второй раз не спрашиваем")
e2 = Eng(); e2.turn = Turn(3)                       # вопрос ещё звучал (ответа не ждали) — тоже «перебили на вопросе»
e2.turn.spoken, e2.turn.sys_said, e2.turn.asking = [Q], [Q], "pc: FileSystem"
e2._cancel_locked()
nt = Turn(5); nt.asked = "Да."
ok(e2._just_agreed(nt) is False, "через ход — уже не считается")
e3 = Eng(); e3.turn = Turn(1); e3.turn.spoken = ["Расскажу коротко."]
e3._cancel_locked()
ok(e3.history[-1]["content"] == "Расскажу коротко. …(меня перебили)" and not getattr(e3, "_confirm_cut", None),
   "перебили не на вопросе — как раньше")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("turn.sys_said = " in src and "turn.asking = title or name" in src, "вопрос программы отмечается как её слова")
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
ok("confirm_cut_yes" in sc and sc["confirm_cut_yes"]["seed"].get("history"), "сценарий экзамена: перебили на «Выполнить?» — «да» делает")
ok('"exam_history"' in (ROOT / "core/exam.py").read_text(encoding="utf-8"), "экзамен умеет положить разговор до сценария")
print("\nИТОГ:", "всё прошло" if not fails else f"не прошло {len(fails)}")
sys.exit(1 if fails else 0)
