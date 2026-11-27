"""События плагинов на «Пульте» (26.11, владелец про «Jira команды»: «события Лира может показывать в своём Пульте и если
что-то важное, даже произносить… кто в какой доске что добавил, закрыл»).
- плагин объявляет "watch": {"tool", "every"} — ядро само, без модели, зовёт это действие раз в every минут;
- новые события — на круг «Пульта» с именем плагина, повтор того же события — нет; важные — вслух, только если в
  настройках плагина включено «Говорить о важном», и не больше двух за раз («И ещё N — на „Пульте“»);
- ошибка плагина — тихо, следующая попытка по расписанию;
- у «Jira команды» это jira_watch (проверка самого действия — в jira_plugin1125_test.py)."""
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from plugin_watch import Watch  # noqa: E402
import plugins as PL  # noqa: E402

jp = PL.parse_plugin(ROOT / "data/plugins/jira", True)
ok(jp["watch"] == {"tool": "jira_watch", "every": 5}, f"«Jira команды»: события раз в 5 минут (один короткий запрос «что изменилось»): {jp['watch']}")
ok(any(s["key"] == "say_important" and s["type"] == "toggle" and s["default"] is False for s in jp["settings"]),
   "«Говорить о важном» — переключатель, по умолчанию выключен")


class P:
    def __init__(self, say, widget=None):
        self.say, self.widget = say, widget

    def installed(self):
        return [{"id": "jira", "name": "Jira команды", "watch": {"tool": "jira_watch", "every": 2}},
                {"id": "kitchen", "name": "Кухня", "watch": None}]

    def values(self, pid):
        return {"say_important": self.say, **({"widget": self.widget} if self.widget else {})}


T0 = 1_800_000_000
calls, said = [], []
batch = [{"id": "AI-5|1", "ts": T0 - 600, "t": "закрыта AI-5 «Сборка» — Maria", "important": True},
         {"id": "AI-7|2", "ts": T0 - 300, "t": "AI-7 «Тесты» → «В работе» — Artyom", "important": False},
         {"id": "AI-9|3", "ts": T0 - 200, "t": "новая ошибка AI-9 «Падает вход»", "important": True},
         {"id": "AI-4|4", "ts": T0 - 100, "t": "закрыта AI-4 «Логи»", "important": True}]


def call(pid, tool, args):
    calls.append((pid, tool))
    return {"events": batch}


got = []
w = Watch(P(True), call, announce=said.append, on_new=lambda p, new: got.append((p["id"], len(new))))
n = w.tick(T0)
ok(calls == [("jira", "jira_watch")], f"зовётся только плагин с watch, его действие: {calls}")
ok(n == 4 and len(w.day(T0)) == 4 and all(x["k"] == "plugin" and x["src"] == "Jira команды" and x["go"] == "plg:jira" for x in w.day(T0)),
   "события — на круг «Пульта»: с именем плагина и его страницей")
ok(len(said) == 1 and said[0].startswith("Jira команды: закрыта AI-5") and "новая ошибка AI-9" in said[0] and "И ещё 1" in said[0]
   and "AI-7" not in said[0], f"вслух — только важное, два и «ещё N»: {said}")
w.tick(T0 + 60)
ok(got == [("jira", 4)], f"новые события — сразу знак «Пульту»: {got}")
ok(len(calls) == 1, "до следующего раза (2 минуты) не зовётся")
n2 = w.tick(T0 + 121)
ok(len(calls) == 2 and n2 == 0 and len(said) == 1 and len(got) == 1, "то же самое снова — не новое: ни на круг, ни вслух, ни знака")
ok(not w.day(T0 + 13 * 3600), "старше 12 часов — с круга уходит")

said2, cards = [], []
w2 = Watch(P(False), call, announce=said2.append, push=lambda *a: cards.append(a))
w2.tick(T0)
ok(len(w2.day(T0)) == 4 and not said2, "«Говорить о важном» выключено — молча")
ok(cards == [("Jira команды", "закрыта AI-4 «Логи»", "и ещё 3 — на «Пульте»", "plg:jira")],
   f"владелец 26.11: «проходит слишком незаметно» — тихая карточка в виджете: последнее и «ещё N», нажатие — плагин: {cards}")
cards.clear()
Watch(P(False, "Только важные"), call, push=lambda *a: cards.append(a)).tick(T0)
ok(cards and cards[0][2] == "и ещё 2 — на «Пульте»", f"«Только важные» — карточка о трёх важных: {cards}")
cards.clear()
Watch(P(False, "Не показывать"), call, push=lambda *a: cards.append(a)).tick(T0)
ok(not cards, "«Не показывать» — без карточки (на «Пульте» — по-прежнему)")
cards.clear()
Watch(P(True), call, announce=said2.append, push=lambda *a: cards.append(a)).tick(T0)
ok(said2 and not cards, "сказала о важном вслух — карточку не дублирует")


def boom(pid, tool, args):
    raise RuntimeError("плагин не запустился")


w3 = Watch(P(True), boom, announce=said2.append)
ok(w3.tick(T0) == 0 and not w3.day(T0), "плагин упал — тихо, без событий")
ok(Watch(P(True), lambda *a: {"events": "мусор"}).tick(T0) == 0, "кривой ответ — ничего")

# ---------- ядро и «Пульт» ----------
ct = (ROOT / "core/commands_tasks.py").read_text(encoding="utf-8")
ok('out["day"] += pw.day(now)' in ct, "pult_data: события плагинов — в круг дня")
eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok('self.push(title, head, quiet=True, telegram=False, open=open_, head=head, body=body)' in eng, "карточка — тихая: без звука, всплывающего окна и Telegram")
ok('self.emit("plugin_events"' in eng and 'core.on("plugin_events"' in (ROOT / "ui/padpult.js").read_text(encoding="utf-8"), "открытый «Пульт» обновляется сразу")
ok("self._plugin_watch_start()" in eng and "announce=None if self.server else self.announce" in eng, "ядро запускает наблюдение; на сервере — без голоса")
pj = (ROOT / "ui/padpult.js").read_text(encoding="utf-8")
ok('plugin: ["Плагин", "skills"]' in pj and 'x.k === "plugin" && x.go ? x.go' in pj and "kindOf(x)" in pj, "«Пульт»: точка плагина — его имя, нажатие — его страница")
ph = (ROOT / "ui/pad.html").read_text(encoding="utf-8")
ok(".pu-ev .e.plugin .dot { fill: var(--pu-plug); }" in ph and ph.count("--pu-plug:") == 2, "свой цвет точки — в тёмной и светлой теме")
ok("PU.plug = {" in pj and 'lb.classList.toggle("plug", !!plug)' in pj and "PU.plug && Date.now() - PU.plug.seen < 3600e3" in pj,
   "«Пульт»: свежее событие — карточкой сверху и строкой над листом, пока не посмотрели (час)")
dj = (ROOT / "ui/studio/dewiar.js").read_text(encoding="utf-8")
ok("/^plg:[\\w-]+$/.test(String(p" in dj and "#plg:" in dj, "студия открывает «plg:jira» — и открытая, и новым окном")
import json as _j  # noqa: E402
ok(_j.loads((ROOT / "data/i18n/ru.json").read_text(encoding="utf-8")).get("hud.push.open.plg") == "Открыть плагин", "кнопка карточки — «Открыть плагин»")
hj = (ROOT / "ui/studio/home.js").read_text(encoding="utf-8")
ok('if (p.startsWith("plg:")) return hmOpen(p);' in hj, "студия: «plg:jira» с «Пульта» — страница плагина")

print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
