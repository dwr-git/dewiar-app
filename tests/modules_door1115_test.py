"""Одна дверь для модулей и предохранитель (1.0 «Надёжность», владелец 15.11: «ядро + плагины… не осьминог, который
бесконечно ломается»; «напоминания и заметки — неотъемлемая часть Лиры, не плагины»).

1. Модули описаны один раз — core/modules.py: инструменты, переключатель «Возможностей», что нужно для работы и подсказка.
   Toolbox.policy и Toolbox._needs спрашивают дверь, а не держат по ветке на каждую службу. Поведение то же (при переделке
   сверено со старым кодом на всех 106 инструментах × подключено/нет × «Возможности» × сервер — расхождений 0).
2. Ядро — не модули: дела, заметки, календарь, деньги, платежи, «Мои файлы», голос, задачи, поиск.
3. Предохранитель: настоящий сбой модуля (не ToolError) 3 раза за 10 минут — модуль на паузе 15 минут: инструментов
   у модели нет, модель знает, что сказать; удача обнуляет счёт; пауза кончилась — снова в строю. Серверы плагинов (MCP) —
   каждый отдельно. Ядро не выключается никогда. Сработал — счётчик «fuse:…» (имена плагинов не считаем)."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import modules  # noqa: E402
import tools as T  # noqa: E402


class Sett:
    def __init__(self, f=None):
        self.f = f or {}

    def get(self, a, b=None):
        return {"features": self.f, "tools": {}, "privacy": {}}.get(a, {})


class O:
    def __init__(self, **k):
        self.__dict__.update(k)


# 1. карта модулей — без опечаток и пересечений
seen, dup = {}, []
for m in modules.MODULES:
    for t in m.get("tools") or ():
        ok(t in T.TOOLS, f"«{m['title']}»: инструмент {t} существует") if t not in T.TOOLS else None
        if t in seen:
            dup.append(t)
        seen[t] = m["id"]
ok(all(t in T.TOOLS for t in seen), "все инструменты модулей есть в TOOLS")
ok(not dup, f"инструмент — ровно в одном модуле ({dup})")
ok(len({m["id"] for m in modules.MODULES}) == len(modules.MODULES), "id модулей не повторяются")
ok(modules.of("site_publish")["id"] == "sites" and modules.of("client_crm")["id"] == "clients", "приставки site_/client_ — свои модули")

# 2. ядро — не модули
CORE = ("set_reminder", "list_reminders", "change_reminder", "cancel_reminder", "mark_done", "save_note", "update_note", "find_notes",
        "calendar_list", "money_add", "money_find", "money_report", "payments", "doc_find", "read_file", "start_task", "task_status",
        "web_search", "weather", "calc", "remember", "run_command")
ok(all(modules.of(n) is None for n in CORE), "дела, заметки, календарь, деньги, «Мои файлы», задачи, поиск — ядро, не модули")

# 3. дверь: «Возможности» и подключение
tb = T.Toolbox(Sett(), None)
ok(tb.policy("send_email") == (False, False) and "почту" in tb._needs("send_email")[0], "почта не подключена — инструмента нет, подсказка «подключите почту»")
tb.hooks["mail"] = O(configured=lambda: True)
ok(tb.policy("send_email")[0] and tb._needs("send_email") is None, "почта подключена — инструмент есть")
tb.hooks["sites"] = object()
ok(tb.policy("site_create")[0], "«Сайты» по умолчанию включены")
tb.s = Sett({"sites": False})
ok(not tb.policy("site_create")[0], "«Сайты» выключены в «Возможностях» — модель о них не знает")
tb.hooks["clients"] = object()
tb.s = Sett()
ok(not tb.policy("client_note")[0], "«Клиенты» по умолчанию выключены")
tb.s = Sett({"clients": True})
ok(tb.policy("client_note")[0] and not tb.policy("client_crm")[0], "«Клиенты» включены; CRM без подключения — нет")
tb.hooks["crm"] = O(connected=lambda: True)
ok(tb.policy("client_crm")[0], "CRM подключена — client_crm есть")

# 4. предохранитель
clock = [1000.0]
tb = T.Toolbox(Sett(), None)
tb.__dict__["_fuse"] = modules.Fuse(now=lambda: clock[0])
trips = []
tb.fuse.on_trip = trips.append
calls = {"n": 0}
real = T.TOOLS["make_podcast"]


def boom(args, ctx):
    calls["n"] += 1
    raise KeyError("voices")


T.TOOLS["make_podcast"] = (real[0], real[1], real[2], boom, real[4])
try:
    def run_podcast():
        try:
            tb.run("make_podcast", {"source": "x"})
        except Exception as e:  # noqa: BLE001
            return e

    ok(isinstance(run_podcast(), KeyError) and tb.policy("make_podcast")[0], "первый сбой — ошибка уходит как раньше, модуль в строю")
    run_podcast()
    ok(tb.policy("make_podcast")[0] and not trips, "два сбоя — ещё в строю")
    run_podcast()
    ok(not tb.policy("make_podcast")[0] and trips == ["podcast"], "третий сбой за 10 минут — «Подкасты» на паузе, счётчик «podcast»")
    ok("make_podcast" not in {x["name"] for x in tb.specs()}, "на паузе — инструмента нет в подсказке модели")
    note = tb.off_note()
    ok("«Подкасты»" in note and "вернётся сама" in note, "модель знает, что сказать человеку")
    n0 = calls["n"]
    ok(isinstance(run_podcast(), T.ToolError) and calls["n"] == n0, "на паузе модуль не дёргают")
    ok(tb.policy("calc")[0] and tb.policy("set_reminder")[0], "ядро работает, пока модуль на паузе")
    clock[0] += modules.FUSE_PAUSE + 1
    ok(tb.policy("make_podcast")[0] and "Подкасты" not in tb.off_note(), "пауза кончилась — модуль снова в строю")

    # ToolError — честный ответ, не сбой; удача обнуляет счёт
    def honest(args, ctx):
        raise T.ToolError("нет такого файла")
    T.TOOLS["make_podcast"] = (real[0], real[1], real[2], honest, real[4])
    for _ in range(5):
        run_podcast()
    ok(tb.policy("make_podcast")[0], "ToolError («нет такого файла») — не сбой: пять раз подряд, а модуль в строю")
    T.TOOLS["make_podcast"] = (real[0], real[1], real[2], boom, real[4])
    run_podcast(); run_podcast()
    T.TOOLS["make_podcast"] = (real[0], real[1], real[2], lambda a, c: "готово", real[4])
    ok(tb.run("make_podcast", {"source": "x"}) == "готово", "удачный вызов проходит")
    T.TOOLS["make_podcast"] = (real[0], real[1], real[2], boom, real[4])
    run_podcast()
    ok(tb.policy("make_podcast")[0], "удача обнулила счёт: 2 сбоя + удача + 1 сбой — ещё в строю")
    clock[0] += modules.FUSE_WINDOW + 1
    run_podcast(); run_podcast()
    ok(tb.policy("make_podcast")[0], "старые сбои (дольше 10 минут) не считаются")
finally:
    T.TOOLS["make_podcast"] = real

# ядро предохранитель не выключает
real_calc = T.TOOLS["calc"]
T.TOOLS["calc"] = (real_calc[0], real_calc[1], real_calc[2], lambda a, c: 1 / 0, real_calc[4])
try:
    for _ in range(6):
        try:
            tb.run("calc", {"expression": "1"})
        except ZeroDivisionError:
            pass
    ok(tb.policy("calc")[0] and not tb.fuse.paused(), "сбои ядра не выключают ядро")
finally:
    T.TOOLS["calc"] = real_calc


# серверы плагинов — каждый отдельно
class FakeMCP:
    def has(self, n): return n.startswith("mcp_")
    def server_of(self, n): return n.split("_")[1]
    def needs_confirm(self, n): return False
    def specs(self): return [{"name": n, "description": "", "parameters": {}} for n in ("mcp_bad_x", "mcp_good_y")]
    def call(self, n, a):
        if n == "mcp_bad_x":
            raise RuntimeError("упал")
        return "ok"


tb2 = T.Toolbox(Sett(), None, mcp=FakeMCP())
got = []
tb2.fuse.on_trip = got.append
for _ in range(3):
    try:
        tb2.run("mcp_bad_x", {})
    except RuntimeError:
        pass
ok(not tb2.policy("mcp_bad_x")[0] and tb2.policy("mcp_good_y")[0] and got == ["mcp:bad"], "сломанный сервер плагина — на паузе, соседний работает")
ok("«bad»" in tb2.off_note(), "модель знает и про плагин на паузе")

# счётчик «чем пользуются»: имена плагинов людей не считаем
eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok('self.toolbox.fuse.on_trip' in eng and '"fuse:" + ("plugin" if k.startswith("mcp:") else k)' in eng, "сработал — «fuse:<модуль>» / «fuse:plugin»")
et = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("на паузе после сбоя" in et and "fuse.tripped" in et, "в разговоре — «на паузе после сбоя», а не «выключен пользователем»")
src = (ROOT / "core/tools.py").read_text(encoding="utf-8")
p = src[src.index("    def policy(self, name):"):src.index("    def specs(self")]
ok("configured()" not in p and "paired()" not in p and 'startswith("site_")' not in p, "в policy больше нет веток отдельных служб — только дверь")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
