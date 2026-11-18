"""Харнесс, шаг 1 (владелец 15.11: «давай делать» — облегчить вопрос). Каждый вопрос нёс описания всех ~74 действий (≈15 тыс.
токенов из ≈20 тыс.). Теперь: ядро действий — всегда и всегда первым, в одном порядке (кэш начала запроса); модули и пачки
(деньги, близкие, файлы, компьютер, маршруты…) — когда вопрос про них (их слова в core/modules.py), ими пользовались
последние 15 минут, или модель попросила сама (more_tools — в его описании список отложенного). tools.slim false — как раньше."""
import srctext  # noqa: E402 — текст исходника вместе с частями (tests/srctext.py)
import json, os, re, sys, time
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
    def __init__(self, t=None):
        self.t = t or {}

    def get(self, a, b=None):
        return {"tools": self.t, "features": {}, "privacy": {}}.get(a, {})


for g in modules.groups():
    re.compile(g["words"])
ok(all(t in T.TOOLS for g in modules.PACKS for t in g["tools"]), "все действия пачек существуют")
ok(not ({t for g in modules.PACKS for t in g["tools"]} & {t for m in modules.MODULES for t in m.get("tools") or ()}), "действие — либо в модуле, либо в пачке")
ok(all(modules.of(t) is None for g in modules.PACKS for t in g["tools"]), "пачки — ядро: предохранитель и «Возможности» их не касаются")

tb = T.Toolbox(Sett(), None)
tb.hooks.update(sites=object(), mail=type("M", (), {"configured": lambda s: True})())
full = tb.specs()
size = lambda sp: len(json.dumps(sp, ensure_ascii=False))  # noqa: E731
names = lambda sp: [x["name"] for x in sp]  # noqa: E731
hi = tb.specs("Привет, как дела?")
ok(size(hi) < size(full) * 0.55, f"«Привет» — вопрос легче почти вдвое: {size(hi)} из {size(full)} знаков")
ok("more_tools" in names(hi) and "money" in [x for x in hi if x["name"] == "more_tools"][0]["description"], "отложенное — списком в more_tools")
for q, want in (("Купил хлеб за 50 рублей", "money_add"), ("Напиши маме, что опоздаю", "close_send"), ("Сколько места на диске?", "system_status"),
                ("Сделай сайт для кофейни", "site_create"), ("Проверь почту", "read_emails"), ("Как доехать до вокзала?", "route"),
                ("Включи Цоя", "play_music"), ("Поставь напоминание на 9", "set_reminder"), ("Поясни главу 39 ГК РФ", "web_search")):
    ok(want in names(tb.specs(q)), f"«{q}» — есть {want}")
ok("money_add" not in names(hi) and "site_create" not in names(hi) and "send_email" not in names(hi), "«Привет» — без денег, сайтов и почты")
core = [n for n in names(hi) if n != "more_tools"]
ok(names(tb.specs("Купил хлеб за 50 рублей"))[:len(core)] == core, "ядро — впереди и в одном порядке у всех вопросов (кэш начала)")
ok("money_add" in names(tb.specs("Привет", keep={"money"})), "модель попросила «money» — деньги добавлены")
ok(T.TOOLS["more_tools"][3]({"packs": ["money"]}, {}).startswith("Добавлены действия: Деньги"), "more_tools отвечает, что добавлено")
real = T.TOOLS["money_report"]
T.TOOLS["money_report"] = (real[0], real[1], real[2], lambda a, c: "итог", real[4])
try:
    tb.run("money_report", {})
finally:
    T.TOOLS["money_report"] = real
ok("money_add" in names(tb.specs("а за неделю?")), "пользовались деньгами — «а за неделю?» тоже с ними (6 часов)")
tb.__dict__["_used"]["money"] = tb.__dict__["_offered"]["money"] = time.time() - 3600
ok("money_add" in names(tb.specs("Привет")), "через час после денег — набор тот же (кэш начала запроса, отчёт 830)")
tb.__dict__["_used"]["money"] = tb.__dict__["_offered"]["money"] = time.time() - modules.SLIM_RECENT - 1
ok("money_add" not in names(tb.specs("а за неделю?")), "через 6 часов — снова по словам")
tb.s = Sett({"slim": False})
ok(names(tb.specs("Привет")) == names(full), "tools.slim false — весь набор, как раньше")
ea = srctext.text(ROOT, "core/engine_answer.py")
ok("self.toolbox.specs(slim_text)" in ea and "self.toolbox.specs(slim_text, keep=turn.packs)" in ea and '"more_tools"' in ea,
   "разговор: облегчённый набор, more_tools — следующий шаг уже с группой")
print("ИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
