"""№551 (пакет 05.11, ПК 0.82.2, Ollama gemma4:12b по сети): «висит уже 2 часа — обрати внимание на виджет: я спросил дать
права — молчит». Задача «Анализ кода и БД проекта» не знала, где проект, и час перебирала свою папку (план 0 из 11), шаг модели
дважды молчал по 10 минут («Жду ещё»), а «может, тебе дать доступ» ушло в разговор — передать задаче было нечем.
Теперь: сторож (taskguard) ставит на паузу с понятной причиной — шаг молчит вдвое дольше порога или час без единого пункта
плана; разговор передаёт задаче сведения и папки (tell_task, папки — только после «да»); набранный в «Чате» ответ на вопрос
задачи уходит ей; вопрос задачи виден в виджете и «Чате» с кнопками «Да / Нет»."""
import os, re, sys, tempfile, threading, time
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import taskguard as G  # noqa: E402
import tools as TL  # noqa: E402

stop_ev = threading.Event()
alive = threading.Thread(target=stop_ev.wait, daemon=True)
alive.start()


class FakeTask:
    def __init__(self, **kw):
        self.id, self.title = "106bc925", "Анализ кода и БД проекта"
        self.data = {"status": "running", "progress": [0, 11]}
        self.data.update(kw.pop("data", {}))
        self.thread, self.beat, self.beat_tool, self.run_t0 = alive, time.monotonic(), "", time.monotonic()
        self.cancel, self.answer_ev = threading.Event(), threading.Event()
        self.log, self.saved = [], 0
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def status(self):
        return self.data.get("status")

    def journal(self, text):
        self.log.append(text)

    def save(self):
        self.saved += 1


now = time.monotonic()
H, HT = 600.0, 1800.0
# 1) когда пауза
ok(G.why_pause(FakeTask(beat=now - 700), now, H, HT) == "", "шаг молчит 11 мин — ещё ждём (у задачи своё «не отвечает, жду ещё»)")
w = G.why_pause(FakeTask(beat=now - 1300), now, H, HT)
ok("шаг не отвечал 22 мин (модель)" in w and "Ollama" in w and "продолжи задачу" in w, f"модель молчит 22 мин — пауза с причиной и что делать: {w[:90]}")
ok(G.why_pause(FakeTask(beat=now - 1300, beat_tool="run_python"), now, H, HT) == "", "инструмент (код, скачивание) — порог дольше")
ok("инструмент «run_python»" in G.why_pause(FakeTask(beat=now - 3700, beat_tool="run_python"), now, H, HT), "инструмент молчит час — пауза")
w = G.why_pause(FakeTask(run_t0=now - 3700), now, H, HT)
ok("ни одного пункта из 11" in w and "доступ к папке" in w, f"час работы, план 0 из 11 — буксует, подсказка «дайте папку»: {w[:80]}")
ok(G.why_pause(FakeTask(run_t0=now - 3700, data={"progress": [3, 11]}), now, H, HT) == "", "пункты плана отмечаются — работает, не трогаем")
ok(G.why_pause(FakeTask(run_t0=now - 3700, data={"parent": "x"}), now, H, HT) == "", "часть задачи — решает главная")
ok(G.why_pause(FakeTask(run_t0=now - 3700, data={"status": "waiting"}), now, H, HT) == "", "ждёт ответа — не буксует")
ok(G.why_pause(FakeTask(run_t0=now - 3700, thread=None), now, H, HT) == "", "потока нет — сторожить нечего")

# 2) сама пауза
said, pushed, emitted = [], [], []
t = FakeTask(beat=now - 1300)
host = SimpleNamespace(tasks=SimpleNamespace(tasks={t.id: t}, _emit=lambda x: emitted.append(x.status)),
                       announce=said.append, push=lambda title, text: pushed.append(title))
out = G.check(host, now)
ok(out and out[0][0] == t.id, "сторож нашёл зависшую задачу")
ok(t.status == "paused" and t.cancel.is_set() and t.saved, "статус «на паузе», поток получил отмену")
ok(t.log and t.log[0].startswith("⏸ Шаг не отвечал"), f"причина — в журнале задачи: {t.log[:1]}")
ok(said and said[0].startswith("Задача «Анализ кода и БД проекта» на паузе: шаг не отвечал"), "и голосом — понятной фразой")
ok(pushed and emitted == ["paused"], "на телефон и в виджет")
ok(G.check(host, now) == [], "второй раз — не повторяет")
src = (ROOT / "core" / "tasks.py").read_text(encoding="utf-8")
ok('t.cancel.is_set() and t.status != "paused"' in src, "цикл задачи после отмены оставляет «на паузе» (не «остановлено»)")
eng = (ROOT / "core" / "engine_audio.py").read_text(encoding="utf-8") + (ROOT / "core" / "engine.py").read_text(encoding="utf-8")
ok("def _task_guard_loop" in eng and "target=self._task_guard_loop" in eng, "сторож запускается вместе с фоновыми службами")


# 3) tell_task: сведения и папки — задаче
class TM:
    def __init__(self, t):
        self.t, self.told = t, []

    def get(self, name):
        if name and name.lower() not in self.t.title.lower():
            raise KeyError(f"нет задачи «{name}»")
        return self.t

    def tell(self, tid, text):
        self.told.append(text)
        return self.t


proj = tmp / "Bot"
proj.mkdir()
t = FakeTask()
tm = TM(t)
r = TL.t_tell_task({"name": "анализ", "folders": [str(proj)]}, {"tasks": tm})
ok(t.data.get("folders") == [str(proj.resolve())] and t.saved, "папка проекта — в папки задачи")
ok(tm.told and "доступ к папкам" in tm.told[0] and str(proj.resolve()) in tm.told[0], "и сообщением задаче: где теперь искать")
ok("Передала задаче" in r and "не говори, что готово" in r, "модели — что передано и что результата ещё нет")
TL.t_tell_task({"text": "База игры — в папке db"}, {"tasks": tm})
ok(tm.told[-1] == "База игры — в папке db", "просто сведения — задаче как есть")
for bad, why in (({}, "пусто"), ({"folders": [str(tmp / "нет")]}, "нет папки"), ({"folders": [Path(tmp).anchor]}, "весь диск")):
    try:
        TL.t_tell_task(bad, {"tasks": tm})
        ok(False, f"tell_task: {why} — должна быть ошибка")
    except TL.ToolError:
        ok(True, f"tell_task: {why} — понятная ошибка")
ok("tell_task" in TL.TOOLS and TL.TOOLS["tell_task"][2] == "safe", "tell_task есть у разговора")
tb = TL.Toolbox(None, None)
reason, must, q = tb.guard("tell_task", {"folders": [str(proj)]})
ok(reason is None and must and q and "Разрешить?" in q, "папки задаче — только после «да» человека")
_, must2, _ = tb.guard("tell_task", {"text": "база — в db"})
ok(not must2, "просто сведения — без вопроса")
ok("tell_task" in __import__("tasks").SKIP_IN_TASK, "сама задача tell_task не получает")

# 4) ответ в «Чате» — ждущей задаче
import engine as E  # noqa: E402
e = E.Engine.__new__(E.Engine)
answered, emits = [], []
wt = SimpleNamespace(id="106bc925", title="Анализ кода и БД проекта")
e.tasks = SimpleNamespace(waiting=lambda: wt, answer=lambda tid, text: answered.append((tid, text)))
e.aliases = {"lira": ["лира"], "patrick": ["патрик"]}
e.task_answer_until = 0.0
e.emit = lambda kind, **k: emits.append((kind, k))
e._g = lambda x: x
ok(e._task_reply("Разрешаю, дай права на папку F:\\Bot"), "«разрешаю, дай права…» — ответ задаче, не новый вопрос")
ok(answered and answered[-1][1].startswith("Разрешаю"), "задача получила ответ")
ok(any(k == "answer" and "Передала в задачу" in d.get("text", "") for k, d in emits), "в чате видно: передала в задачу")
ok(e._task_reply("да"), "«да» — ответ задаче")
ok(not e._task_reply("Патрик, а какая завтра погода?"), "«Патрик, …» — разговор с персонажем, не задаче")
ok(not e._task_reply("Расскажи анекдот про программистов"), "посторонняя просьба через полчаса — разговор")
e.task_answer_until = time.monotonic() + 100
ok(e._task_reply("В папке Bot на диске F"), "сразу после вопроса — любой короткий ответ уходит задаче")
e.tasks = SimpleNamespace(waiting=lambda: None)
ok(not e._task_reply("разрешаю"), "никто не спрашивает — обычный разговор")
cmd = (ROOT / "core" / "engine_commands.py").read_text(encoding="utf-8")
ok("self._task_reply(text)" in cmd, "набранное в «Чате» проверяется на ответ задаче")
ans = (ROOT / "core" / "engine_answer.py").read_text(encoding="utf-8")
ok("TASK_GIVE_RX" in ans and "tell_task" in ans, "«может, тебе дать доступ» при живой задаче — модель видит задачу и tell_task")
import engine_answer as EA  # noqa: E402
ok(EA.TASK_GIVE_RX.search("может тебе дать доступ") and EA.TASK_GIVE_RX.search("стоишь там на одном месте"), "фразы из журнала №551")

# 5) вопрос задачи виден: виджет и «Чат»
hud = (ROOT / "ui" / "hud.html").read_text(encoding="utf-8")
ok('data-tans="Да"' in hud and 'core.call("task_answer"' in hud, "виджет: вопрос задачи с кнопками «Да / Нет»")
chat = (ROOT / "ui" / "studio" / "chat.js").read_text(encoding="utf-8")
ok("function chatTaskQ" in chat and 'core.call("task_answer"' in chat and 'id="ch-tq"' in (ROOT / "ui" / "settings.html").read_text(encoding="utf-8"),
   "«Чат»: вопрос задачи с «Да / Нет» и ответом словами")
stop_ev.set()
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
