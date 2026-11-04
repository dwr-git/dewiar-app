"""Выпуск 1 «Больших задач» (docs/HARNESS.md, 04.11): чистка памяти задачи. Результаты инструментов старше TRIM_AFTER шагов
заменяются заглушкой «[убрано из памяти: результат … — перечитай, если нужно]» (пачкой, раз в TRIM_EVERY шагов — кэш
ломается редко); ответы человека не трогаются; большие тексты в старых вызовах (содержимое write_file) — короткой
пометкой. Вывод любого инструмента длиннее OUT_MAX — целиком в _out/ папки задачи, в историю — начало, конец и путь.
Все три протокола истории: OpenAI (role tool), Claude (tool_result), функции текстом (<tool_response>)."""
import json

from task_mock import Host, Mock, done, ok, wait_for
import tasks as TK

A = "Чистка"
seen = {}
mock = Mock({})


def look(req):
    seen["out"] = sorted(p.name for p in (t.dir / "_out").glob("*")) if (t.dir / "_out").is_dir() else []
    seen["big"] = (t.dir / "_out").is_dir() and any(len(p.read_text(encoding="utf-8")) > 9000 for p in (t.dir / "_out").glob("*"))
    return ("log", {"text": "посмотрел"})


steps = [("ask_user", {"question": "Какой формат?"}),
         ("write_file", {"path": "outputs/большой.md", "content": "абзац текста. " * 300}),
         ("run_python", {"code": "print('Ж' * 12000)"}),
         look]
steps += [("run_python", {"code": f"print('строка {k} ' * 120)"}) for k in range(22)]
steps += [("show", {"path": "outputs/большой.md"}), ("finish", {"summary": "Готово."})]
mock.scripts[A] = steps
host = Host(mock)
tm = TK.TaskManager(host)
t = tm.create(A, "Проверка чистки")
ok(wait_for(lambda: t.status == "waiting", 20), "задача спросила человека")
tm.answer(t.id, "Ответ человека: Markdown, коротко " + "очень важно " * 60)
ok(wait_for(lambda: t.status in ("done", "failed"), 90), f"задача закончилась ({t.status} {t.error})")
rs = mock.of(A)
r3 = json.dumps(rs[3]["messages"], ensure_ascii=False)
ok("целиком в файле _out/run_python-" in r3 and r3.count("Ж") < 4000, "вывод 12 тыс. знаков — в историю только начало, конец и путь")
ok(seen.get("big") and seen.get("out"), f"полный вывод лежит в _out/ папки задачи: {seen.get('out')}")
late = rs[-1]["messages"]
lj = json.dumps(late, ensure_ascii=False)
ok("[убрано из памяти: результат run_python" in lj, "старые результаты run_python заменены заглушкой")
ok("очень важно очень важно" in lj, "ответ человека (ask_user) не убирается")
ok("абзац текста. абзац текста. абзац" not in lj and "[убрано из памяти: 4200 знаков — в файле outputs/большой.md]" in lj,
   "содержимое write_file в старом вызове — короткой пометкой с путём")
tail = [m for m in late if m["role"] == "tool"][-3:]
ok(all("[убрано" not in m["content"] for m in tail), "свежие результаты на месте")
ok("🧹" in (t.dir / "журнал.md").read_text(encoding="utf-8"), "чистка отмечена в журнале")
ok(not (t.dir / "_out").exists(), "по готовности _out/ убран (_clean)")

# ---------- форматы истории: Claude и функции текстом ----------
tc = tm.create("Формат", "x", start=False)
big = "данные " * 200
an = [{"role": "user", "content": "Начинай"}]
for k in range(5):
    an += [{"role": "assistant", "content": [{"type": "text", "text": "шаг"}, {"type": "tool_use", "id": f"u{k}", "name": "read_webpage",
                                                                               "input": {"url": f"https://a.ru/{k}"}}]},
           {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"u{k}", "content": [{"type": "text", "text": big}]}]}]
out, n = tm._trim(tc, an, keep=2)
txt = [out[2 + 2 * k]["content"][0]["content"][0]["text"] for k in range(5)]
ok(n == 3 and txt[0] == "[убрано из памяти: результат read_webpage (https://a.ru/0) — перечитай, если нужно]" and txt[4] == big
   and an[2]["content"][0]["content"][0]["text"] == big, f"Claude: старые tool_result — заглушкой со ссылкой ({n}), свежие и исходник целы")
pm = [{"role": "user", "content": "Начинай"}]
for k in range(4):
    pm += [{"role": "assistant", "content": f'<tool_call>\n{{"name": "read_file", "arguments": {{"path": "f{k}.txt"}}}}\n</tool_call>'},
           {"role": "user", "content": f"<tool_response>\n{big}\n</tool_response>"}]
out, n = tm._trim(tc, pm, keep=1)
ok(n == 3 and "read_file (f0.txt)" in out[2]["content"] and out[-1]["content"].count("данные") == 200, "функции текстом: <tool_response> — заглушкой")
done()
