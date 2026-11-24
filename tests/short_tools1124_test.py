"""«Короткая подсказка» (1.0.70, план 24.11, за переключателем tools.short — стенд до/после; пакет 24.11: описания действий —
8 846 ток. на ход в среднем, №1009 — 78 действий с подключённым MCP, у своей модели первые слова через 40–60 с). В вопросе —
13 частых действий; остальное ядро — группами «Мой день» и «Программа», MCP — группой на сервер: по словам вопроса, по
недавнему делу или по просьбе модели (more_tools). Предложенная, но не тронутая группа уходит через 20 минут. Выключено —
всё как было."""
import os, sys, tempfile, time
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_CONFIG_DIR=str(tmp / "cfg"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


import tools as T  # noqa: E402


class S:
    def __init__(self, short):
        self.d = {"tools": {"short": short}}

    def get(self, *k, default=None):
        cur = self.d
        for x in k:
            if not isinstance(cur, dict) or x not in cur:
                return default
            cur = cur[x]
        return cur


class MCP:
    def specs(self):
        return [{"name": f"mcp_seagate-work-organizer_{i}", "description": "[seagate-work-organizer] x", "parameters": {}} for i in range(40)]

    def server_of(self, n):
        return "seagate-work-organizer" if n.startswith("mcp_seagate") else ""

    def has(self, n):
        return n.startswith("mcp_seagate")


names = lambda xs: [x["name"] for x in xs]  # noqa: E731
size = lambda xs: sum(len(str(x)) for x in xs)  # noqa: E731
old, new = T.Toolbox(S(None), None, mcp=MCP()), T.Toolbox(S(True), None, mcp=MCP())
a, b = old.specs("привет, как дела?"), new.specs("привет, как дела?")
ok(len(b) < len(a) and size(b) < size(a) * 0.6, f"простой вопрос: действий {len(a)} → {len(b)}, объём {size(a)} → {size(b)} знаков")
core_b = [n for n in names(b) if n in T.TOOLS and n != "more_tools"]
ok(set(core_b) <= T.SHORT_CORE | {"use_skill", "read_skill_file"} and len(core_b) <= 13, f"в вопросе — только частые: {sorted(core_b)}")
mt = next(x for x in b if x["name"] == "more_tools")["description"]
ok("day — Мой день" in mt and "app — Программа" in mt and "mcp:seagate-work-organizer — подключённая программа" in mt,
   "остальное — в списке групп more_tools: «Мой день», «Программа», MCP-сервер")
ok(not any(n.startswith("mcp_") for n in names(b)), "40 действий MCP в простой вопрос не идут")
for q, want in (("напомни завтра в 9 позвонить маме", "set_reminder"), ("отметь, что уборку я сделал", "mark_done"),
                ("сделай громче", "set_volume"), ("что у меня в календаре на завтра", "calendar_list"),
                ("каждое утро присылай сводку", "schedule_job"), ("найди в интернете курс доллара", "web_search")):
    nb = T.Toolbox(S(True), None)
    ok(want in names(nb.specs(q)), f"«{q}» — есть {want}")
nb = T.Toolbox(S(True), None)
ok("mark_done" in names(nb.specs("ну так", keep={"day"})), "модель попросила «day» — следующим шагом действия «Моего дня» есть")
ok(T.t_more_tools({"packs": ["day"]}, {}).startswith("Добавлены действия: Мой день"), "more_tools знает «day»")
ok("mcp_seagate-work-organizer_0" in names(new.specs("что там на диске seagate?")), "вопрос называет сервер — его действия есть")
# предложенная группа уходит через 20 минут, а пользовались — остаётся на 6 часов
nb = T.Toolbox(S(True), None)
nb.specs("что в календаре")
nb._offered["day"] = time.time() - 25 * 60
ok("calendar_list" not in names(nb.specs("привет")), "предложенная 25 минут назад и не тронутая — ушла")
nb._used["day"] = time.time() - 3600
ok("calendar_list" in names(nb.specs("привет")), "пользовались час назад — осталась")
# выключено — как было
ok(names(old.specs("сделай громче")).count("set_volume") == 1 and any(n.startswith("mcp_") for n in names(a)),
   "tools.short выключен — набор прежний (MCP целиком, ядро целиком)")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
