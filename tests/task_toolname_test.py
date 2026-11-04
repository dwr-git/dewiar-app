"""Выпуск 1 «Больших задач» (docs/HARNESS.md, 04.11): имена инструментов. Подсказки задачи (IDLE_CHANCE, ACT_RU) и облако
называли read_page, а на компьютере инструмент — read_webpage; модель звала read_page и получала ложное «Инструмент read_page
выключен пользователем». Теперь: имя одно везде; неизвестное имя — «нет такого инструмента, есть: …, похоже: read_webpage»;
find_tool находит инструмент вне профиля по описанию и подключает его до конца задачи; знакомый инструмент не из профиля
модель может позвать и сразу — он подключится сам."""
import json
from pathlib import Path

from task_mock import ROOT, Host, Mock, done, ok, wait_for
import cloudrunner as CR
import quality as Q
import tasks as TK

A = "Имена"
steps = [("read_page", {"url": "https://example.org"}),
         ("find_tool", {"query": "который час в другом городе, мировое время"}),
         ("find_tool", {"connect": "world_time"}),
         ("world_time", {"city": "Токио"}),
         ("calc", {"expression": "6*7"}),
         ("no_such_tool", {}),
         ("finish", {"summary": "Готово."})]
mock = Mock({A: steps})
host = Host(mock)
tm = TK.TaskManager(host)
t = tm.create(A, "Проверка имён инструментов")
ok(wait_for(lambda: t.status in ("done", "failed"), 60), f"задача закончилась ({t.status} {t.error})")
rs = mock.of(A)


def result(i):
    """Ответ инструмента на шаге i — в запросе i+1 (последний ответ инструмента перед состоянием)."""
    ms = rs[i + 1]["messages"]
    return next((m["content"] for m in reversed(ms) if m["role"] == "tool"), "")


r0 = result(0)
ok("нет такого инструмента «read_page»" in r0 and "read_webpage" in r0 and "выключен" not in r0 and "Есть:" in r0,
   f"read_page → понятная ошибка с подсказкой: {r0[:160]}")
r1 = result(1)
ok("world_time" in r1 and "connect" in r1, f"find_tool нашёл по описанию: {r1[:200]}")
ok("Подключил world_time" in result(2) and "world_time" in [x["function"]["name"] for x in rs[3]["tools"]],
   "find_tool connect — инструмент подключён и виден в следующем запросе")
ok("calc" in [x["function"]["name"] for x in rs[5]["tools"]] and t.data.get("tools_on") == ["world_time", "calc"],
   f"знакомый инструмент не из профиля (calc) позван сразу — подключился сам: {t.data.get('tools_on')}")
ok("нет такого инструмента «no_such_tool»" in result(5) and "find_tool" in result(5), "выдуманное имя — «нет такого, есть: …, другие — find_tool»")
ok("🧰 Подключил инструмент: world_time" in (t.dir / "журнал.md").read_text(encoding="utf-8"), "подключение — в журнале")
# имя везде одно
ok("read_page" not in TK.IDLE_CHANCE and "read_page" not in TK.ACT_RU and "read_webpage" in TK.ACT_RU, "IDLE_CHANCE и ACT_RU: read_webpage")
ok("read_page" not in Q.REFUSAL_NUDGE and "read_webpage" in Q.REFUSAL_NUDGE, "напоминание про поиск: read_webpage")
ok([x["name"] for x in CR.CloudToolbox.SPECS if "read" in x["name"]][0] == "read_webpage" and "read_page" not in CR.CLOUD_NOTE,
   "облако: инструмент read_webpage, в подсказке облака — тоже")
bad = [p.parent.name for p in (ROOT / "data/skills").glob("*/SKILL.md") if "read_page" in p.read_text(encoding="utf-8").replace("read_webpage", "")]
ok(not bad, f"навыки называют read_webpage: {bad}")
done()
