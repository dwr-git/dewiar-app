"""Выпуск 1 «Больших задач» (docs/HARNESS.md, 04.11): окно модели. Своя модель с окном 8 тыс. (vLLM: запрос + max_tokens не
больше max_model_len, иначе ошибка 400 «maximum context length») — длинная задача с большими выводами доходит до finish:
бюджет истории считается от окна, большие выводы уходят в _out/, старые результаты чистятся, включён лёгкий режим
(короче подсказка, без частей). Ошибка «не хватило окна» посреди работы — сжатие и повтор шага, а не провал.
Раньше: описания ~70 инструментов + блокнот + 60 тыс. знаков истории не помещались в 8–16 тыс., и задача падала."""
from task_mock import Host, Mock, done, ok, wait_for
import tasks as TK

W = 8192
A = "Большой отчёт"
steps = [("update_plan", {"plan": "**Готово, когда:** отчёт собран\n\n- [ ] собрать данные\n- [ ] свести\n- [ ] итог"}),
         ("write_file", {"path": "data/исходные.txt", "content": "строка данных номер N;\n" * 400})]
for k in range(10):
    steps += [("run_python", {"code": f"print('результат шага {k}: ' + 'значение ' * 3000)"}),
              ("read_file", {"path": "data/исходные.txt"}),
              ("remember", {"fact": f"шаг {k}: найдено {k * 7} совпадений"})]
mock = Mock({}, window=W)
steps[15] = lambda req: (setattr(mock, "force_ctx", 1), ("log", {"text": "после этого шага окно «переполнится»"}))[1]
steps += [("update_plan", {"plan": "**Готово, когда:** отчёт собран\n\n- [x] собрать данные\n- [x] свести\n- [x] итог"}),
          ("finish", {"summary": "Отчёт собран: 10 шагов данных сведены."})]
mock.scripts[A] = steps
host = Host(mock)
tm = TK.TaskManager(host)
t = tm.create(A, "Собрать большой отчёт по данным")
ok(wait_for(lambda: t.status in ("done", "failed", "paused"), 120), f"задача закончилась ({t.status} {t.error})")
ok(t.status == "done", f"окно 8 тыс.: задача дошла до finish ({t.status}, шагов {t.data.get('steps')}, ошибка: {t.error or '—'})")
rs = mock.of(A)
big = max(r["size"] + int(r["max_tokens"] or 0) for r in rs)
ok(big <= W, f"ни один запрос задачи (с местом под ответ) не больше окна: самый большой {big} из {W}")
ok(not [x for x in mock.over if x > 0], f"сервер ни разу не ответил «не хватило окна» сам: {mock.over}")
side = [x["size"] for x in mock.side]
ok(not side or max(side) <= W, f"служебные запросы (блокнот, самопроверка) тоже в окне: {max(side) if side else 0}")
j = (t.dir / "журнал.md").read_text(encoding="utf-8")
ok("не хватило окна" in j and t.data.get("win_learned"), "«не хватило окна» посреди работы — сжал память и повторил шаг, не провал")
ok(t.data.get("light") and all("spawn_parts" not in [x["function"]["name"] for x in r["tools"]] for r in rs),
   "лёгкий режим: окно ≤ 16 тыс. — без частей")
ok(all("Уроки" not in r["system"] and len(r["system"]) < 5000 for r in rs), f"лёгкий режим: подсказка короткая ({len(rs[0]['system'])} знаков)")
ok(any("целиком в файле _out/" in str(m.get("content")) for r in rs for m in r["messages"]), "большой вывод run_python — в _out/, в истории начало и путь")
ok(any("показаны строки" in str(m.get("content")) for r in rs for m in r["messages"]), "read_file большого файла — кусками по размеру окна")
u = t.data["quality"]["usage"]
ok(u["req"] >= len(rs) - 1 and u["in"] > 0 and u["out"] > 0 and u["ck"] > 0, f"метрики в quality.usage: {u}")
ok("токены:" in t.public().get("metrics", "") and "кэша" in t.public()["metrics"], f"карточка в студии: «{t.public().get('metrics')}»")
done()
