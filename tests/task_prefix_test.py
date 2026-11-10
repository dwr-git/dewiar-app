"""Выпуск 1 «Больших задач» (docs/HARNESS.md, 04.11): кэш начала запроса. Раньше время с минутами, план и блокнот стояли
в системной подсказке задачи — она менялась каждый шаг, и сервер (Claude, vLLM, llama.cpp) не брал из кэша ни подсказку,
ни историю. Теперь: подсказка и инструменты побайтно одинаковы на шагах 2…N, история только растёт с конца, изменчивое —
последним сообщением «Состояние задачи» (в историю не пишется); у Claude метка кэша — ещё и на последнем блоке истории.
Подключённый через find_tool инструмент встаёт в конец списка. Неизвестный инструмент — понятная ошибка (task_toolname_test)."""
import datetime as dt
import json

from task_mock import Host, Mock, done, ok, wait_for
import llm
import tasks as TK

A = "Кэш начала"
steps = [("update_plan", {"plan": "**Готово, когда:** файл есть\n\n- [ ] записать\n- [ ] проверить"}),
         ("remember", {"fact": "код 777"}),
         ("write_file", {"path": "outputs/итог.md", "content": "# Итог\nвсё хорошо\n"}),
         ("read_file", {"path": "outputs/итог.md"}),
         ("find_tool", {"query": "посчитать выражение калькулятор"}),
         ("find_tool", {"connect": "calc"}),
         ("calc", {"expression": "2+2"}),
         ("log", {"text": "посчитал"}),
         ("remember", {"fact": "2+2=4"}),
         ("list_files", {}),
         ("update_plan", {"plan": "**Готово, когда:** файл есть\n\n- [x] записать\n- [x] проверить"}),
         ("show", {"path": "outputs/итог.md"}),
         ("finish", {"summary": "Готово: итог.md."})]
mock = Mock({A: steps}, window=32768)
host = Host(mock)
tm = TK.TaskManager(host)
t = tm.create(A, "Проверка кэша начала запроса")
ok(wait_for(lambda: t.status in ("done", "failed"), 60), f"задача закончилась ({t.status} {t.error})")
rs = mock.of(A)
ok(len(rs) >= 12, f"шагов модели: {len(rs)}")
sys1 = rs[1]["system"]
ok(all(r["system"] == sys1 for r in rs[1:]), "системная подсказка побайтно одна и та же на шагах 2…N")
now = dt.datetime.now()
ok(f"{now:%d.%m.%Y}" not in sys1 and "код 777" not in sys1 and "ТЕКУЩИЙ ПЛАН" not in sys1,
   "в подсказке нет ни времени, ни блокнота, ни плана")
tools = [json.dumps(r["tools"], ensure_ascii=False) for r in rs]
names = [[x["function"]["name"] for x in r["tools"]] for r in rs]
pre = [r["tools"] for r in rs]
ok(all(pre[k + 1][:len(pre[k])] == pre[k] for k in range(len(pre) - 1)), "инструменты: каждый следующий список начинается с прошлого байт в байт")
ok(names[0] == names[5] and "calc" not in names[5] and names[7][-1] == "calc" and names[7][:-1] == names[0],
   f"find_tool подключил calc — он встал в КОНЕЦ списка, начало не тронуто ({names[7][-3:]})")
ok(12 <= len(names[0]) <= 23, f"профиль задачи — {len(names[0])} инструментов, а не все ~70: {names[0]}")
ok(all(str(r["messages"][-1].get("content", "")).startswith("[Состояние задачи") or "[Состояние задачи" in str(r["messages"][-1].get("content"))
       for r in rs), "«Состояние задачи» — последним сообщением каждого запроса")
st = str(rs[3]["messages"][-1]["content"])
ok(f"{now:%d.%m.%Y}" in st and "ТЕКУЩИЙ ПЛАН" in st and "код 777" in st and "Критерии готовности: файл есть" in st,
   "в состоянии: время, критерии, план, блокнот")


def hist(r):
    m = r["messages"]
    last = m[-1]
    if last["role"] == "user" and str(last.get("content")).startswith("[Состояние задачи"):
        return m[:-1]
    c = str(last.get("content"))
    return m[:-1] + [dict(last, content=c.split("\n\n[Состояние задачи")[0])]


pairs = [(hist(rs[k]), hist(rs[k + 1])) for k in range(len(rs) - 1)]
ok(all(b[:len(a)] == a for a, b in pairs), "история только растёт с конца: прошлый запрос (без состояния) — начало следующего")
ok(not any("[Состояние задачи" in json.dumps(m, ensure_ascii=False) for m in json.loads((t.dir / "история.json").read_text(encoding="utf-8"))),
   "состояние в историю (история.json) не пишется")

# Claude: метка кэша — на последнем блоке истории, состояние — после неё; инструменты и подсказка помечены как раньше
am = [{"role": "user", "content": "Начинай"}, {"role": "assistant", "content": [{"type": "tool_use", "id": "x", "name": "log", "input": {}}]},
      {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": [{"type": "text", "text": "ok"}]}]}]
w = llm.with_tail({"kind": "anthropic"}, am, "[Состояние задачи] план")
ok(w[-1]["content"][-1] == {"type": "text", "text": "[Состояние задачи] план"} and w[-1]["content"][0].get("cache_control")
   and "cache_control" not in json.dumps(am), "Claude: состояние — последним блоком, метка кэша — на последнем блоке истории; исходник не тронут")
w2 = llm.with_tail({"kind": "anthropic"}, am[:2], "S")
ok(w2[1]["content"][-1].get("cache_control") and w2[2] == {"role": "user", "content": [{"type": "text", "text": "S"}]},
   "Claude: история кончается ответом модели — метка на нём, состояние — отдельным сообщением")
o = llm.with_tail({}, [{"role": "user", "content": "a"}], "S")
ok(o == [{"role": "user", "content": "a\n\nS"}], "OpenAI: последнее сообщение пользователя — состояние дописывается к нему")
o2 = llm.with_tail({}, [{"role": "tool", "tool_call_id": "1", "content": "r"}], "S")
ok(o2[-1] == {"role": "user", "content": "S"}, "OpenAI: после ответа инструмента — отдельным сообщением")
u = llm._Collector(anthropic=True)
u.feed_obj({"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 42}})
v = llm._Collector()
v.feed_obj({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 9}})
ok(u.out == 42 and v.out == 9 and v.usage == {"prompt": 100, "cached": None}, "токены ответа: Claude и OpenAI (подсчёт подсказки — как раньше)")
done()
