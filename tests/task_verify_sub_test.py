"""Выпуск 6 «Больших задач» (docs/HARNESS.md): проверяющий — подагент с чистым контекстом (verify).
— задача зовёт verify по ходу работы: машинные критерии + проверяющий, итог не принимается и не отклоняется — задача
  продолжает и правит по замечаниям;
— у проверяющего чистый контекст (одно сообщение: цель, критерии, выдержки — без разговора задачи);
— он может попросить дочитать ({"verdict":"look","read":[…]}): файлы задачи (строки) — только чтение, с теми же правами
  (/etc/passwd — ошибка, содержимое не уходит); просьб не больше VERIFY_LOOKS, дальше — без этой возможности;
— вечные просьбы дочитать — не «ок»: «непонятный ответ», решают машинные проверки; запросов не больше 2 + VERIFY_LOOKS;
— записи о проверяющем — в студии (helpers), токены — в счёте задачи и отдельно (quality.subs.verify);
— остановили задачу — проверяющий больше не спрашивает модель.
Модель — заглушка со сценарием (task_mock), проверяющий — служебный запрос «Ты — строгий» (side_fn)."""
import json
import os

os.environ["DEWIAR_TASK_BROWSER"] = "0"
from task_mock import Host, Mock, done, ok, wait_for  # noqa: E402
import quality as Q  # noqa: E402
import tasks as TK  # noqa: E402

mock = Mock({})
SEEN = {}                          # название задачи -> [(подсказка, сообщения)] проверяющего
ANSWERS = {}                       # название задачи -> список ответов по порядку (последний повторяется) или callable


def side(sysm, body):
    if not sysm.startswith("Ты — строгий"):
        return None
    user = body["messages"][-1]["content"]
    title = user.split("ЗАДАЧА:\n", 1)[-1].split("\n", 1)[0]
    SEEN.setdefault(title, []).append((sysm, body["messages"][1:]))     # без системного
    a = ANSWERS.get(title) or ['{"verdict": "ok"}']
    if callable(a):
        return a(len(SEEN[title]))
    return a[min(len(SEEN[title]), len(a)) - 1]


mock.side_fn = side
host = Host(mock)
tm = TK.TaskManager(host)


def run(title, goal, steps, sec=40, **kw):
    mock.scripts[title] = steps
    t = tm.create(title, goal, **kw)
    wait_for(lambda: t.status in ("done", "failed", "paused", "stopped") and not (t.thread and t.thread.is_alive()), sec)
    return t


def result_after(title, i):
    """Результат инструмента, который задача увидела в запросе i (последний ответ роли tool)."""
    r = [x for x in mock.of(title) if x["i"] == i]
    if not r:
        return ""
    tools = [m.get("content") for m in r[0]["messages"] if m.get("role") == "tool"]
    return tools[-1] if tools else ""


# ---------- 1. verify по ходу работы: дочитывает строки, находит ошибку; задача правит и сдаёт ----------
A = "Отчёт по ходу"
lines = [f"Строка {i}: расход по статье {i} — {i * 10} ₽." for i in range(1, 121)]
lines[109] = "Итого за месяц: 4200 ₽."
report = "# Отчёт\n\n" + "\n".join(lines) + "\n"
ANSWERS[A] = ['{"verdict": "look", "read": ["outputs/отчёт.md:110-114", "/etc/passwd"]}',
              '{"verdict": "revise", "problems": "строка 112: «Итого за месяц: 4200 ₽», а по статьям выходит 4300 ₽"}',
              '{"verdict": "ok"}']
t = run(A, "Отчёт о расходах за месяц — outputs/отчёт.md, итог должен совпадать со статьями", [
    ("write_file", {"path": "outputs/отчёт.md", "content": report}),
    ("set_criteria", {"items": [{"check": "contains", "target": "outputs/отчёт.md", "value": "Итого за месяц"}]}),
    ("verify", {"what": "outputs/отчёт.md", "criteria": "итог совпадает с суммой статей"}),
    ("file_edit", {"path": "outputs/отчёт.md", "old": "Итого за месяц: 4200 ₽.", "new": "Итого за месяц: 4300 ₽."}),
    ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md."}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md."})])        # первый finish вернут «цифры без опоры» (выпуск 3)
ok(t.status == "done", f"задача готова ({t.status} {t.error})")
r = result_after(A, 3)
ok("Критерии кодом: ✓" in r and "Проверяющий нашёл: строка 112" in r and "finish проверит снова" in r, f"verify вернул замечание и критерии: {r[:220]}")
ok(len(mock.of(A)) >= 6 and "✏ Правка outputs/отчёт.md" in (t.dir / "журнал.md").read_text(encoding="utf-8"),
   f"verify не завершил задачу — она поправила и сдала ({len(mock.of(A))} шагов)")
seen = SEEN.get(A) or []
ok(len(seen) == 3, f"проверяющий: 2 запроса по ходу + 1 на итог ({len(seen)})")
s1, m1 = seen[0]
ok(len(m1) == 1 and "Проверка по ходу работы" in m1[0]["content"] and "Начинай задачу" not in json.dumps(m1, ensure_ascii=False),
   "чистый контекст: одно сообщение, без разговора задачи")
ok("Осталось таких просьб: 2" in s1 and "verdict\":\"look\"" in s1.replace(" ", ""), "проверяющему можно дочитать (до 2 раз)")
s2, m2 = seen[1]
c2 = m2[0]["content"]
ok("ДОЧИТАНО ПО ТВОЕЙ ПРОСЬБЕ" in c2 and "112: Итого за месяц: 4200 ₽." in c2, "дочитал нужные строки файла задачи")
ok("вне папки задачи" in c2 and "root:" not in c2, "права не шире задачи: /etc/passwd — ошибка, содержимое не ушло")
ok("Осталось таких просьб: 1" in s2, "счёт просьб дочитать уменьшается")
ok("Проверка по ходу работы" not in seen[2][1][0]["content"] and "ИТОГ АССИСТЕНТА:\nОтчёт — outputs/отчёт.md." in seen[2][1][0]["content"],
   "на finish — обычная проверка итога")
subs = [s for s in t.data.get("subs") or [] if s["kind"] == "verify"]
ok(len(subs) == 2 and subs[0]["what"] == "outputs/отчёт.md" and subs[0]["verdict"] == "revise" and subs[0]["steps"] >= 4
   and subs[1]["what"] == "итог" and subs[1]["verdict"] == "ok", f"записи о проверяющем: {subs}")
q = t.data["quality"]
ok(q.get("subs", {}).get("verify", {}).get("n") == 2 and q["subs"]["verify"]["req"] == 3 and q["subs"]["verify"]["in"] > 0,
   f"токены проверяющего — в quality.subs: {q.get('subs')}")
hp = [h for h in tm.helpers(t) if h["kind"] == "verify"]
ok(len(hp) == 2 and hp[0]["title"] == "Проверяющий" and any("строка 112" in h["note"] for h in hp), f"проверяющий виден в студии: {hp}")
j = (t.dir / "журнал.md").read_text(encoding="utf-8")
ok("🧐 Проверяющий: итог подтверждён" in j, "итог подтверждён проверяющим")

# ---------- 2. вечные просьбы дочитать — не «ок»: решают машинные проверки ----------
B = "Вечный look"
ANSWERS[B] = ['{"verdict": "look", "read": ["outputs/итог.md"]}']
t = run(B, "Коротко — outputs/итог.md", [
    ("write_file", {"path": "outputs/итог.md", "content": "Всё хорошо.\n"}),
    ("verify", {"what": "всё"}),
    ("show", {"path": "outputs/итог.md"}),
    ("finish", {"summary": "Итог — outputs/итог.md."})])
seen = SEEN.get(B) or []
ok(t.status == "done", f"задача сдана: машинные проверки прошли ({t.status} {t.error})")
ok(len(seen) == 2 * (2 + TK.VERIFY_LOOKS), f"на каждую проверку — не больше 2 + {TK.VERIFY_LOOKS} запросов ({len(seen)})")
ok("Осталось таких просьб" in seen[1][0] and "Осталось таких просьб" not in seen[2][0] and "Осталось таких просьб" not in seen[3][0],
   "после исчерпания просьб — подсказка без «дочитать»")
r = result_after(B, 2)
ok("ответил непонятно" in r, f"verify честно говорит, что проверяющий не решил: {r[:160]}")
j = (t.dir / "журнал.md").read_text(encoding="utf-8")
ok("решили машинные проверки" in j, "на finish непонятный проверяющий — решают машинные проверки, а не «ок»")

# ---------- 3. остановили задачу — проверяющий больше не спрашивает модель ----------
C = "Стоп проверки"


def stop_then_look(n):
    if n == 1:
        tm.stop(tm.get(C).id)
    return '{"verdict": "look", "read": ["outputs/a.md"]}'


ANSWERS[C] = stop_then_look
t = run(C, "Файл outputs/a.md", [
    ("write_file", {"path": "outputs/a.md", "content": "текст\n"}),
    ("verify", {"what": "outputs/a.md"}),
    ("log", {"text": "дальше"})])
ok(t.status == "stopped", f"задача остановлена ({t.status})")
ok(len(SEEN.get(C) or []) == 1, f"после «стоп» проверяющий не спрашивал модель ({len(SEEN.get(C) or [])})")
ok(len(mock.of(C)) == 2, f"задача не сделала шагов после «стоп» ({len(mock.of(C))})")
ok([s for s in t.data.get("subs") or [] if s["kind"] == "verify"][-1]["status"] == "stopped", "проверяющий отмечен остановленным")

# ---------- 4. выдержка для проверяющего: предел посреди русской буквы — не «РћС‚С‡С‘С‚» ----------
f = t.dir / "outputs" / "ru.md"
f.write_text("# Отчёт\n\nСтрока про расходы.\n" * 20, encoding="utf-8")
cuts = [Q.file_text(f, limit=n) for n in range(40, 60)]
ok(all(c.startswith("# Отчёт") and "Р" not in c.replace("Расход", "") for c in cuts), f"обрезка посреди буквы — всё ещё UTF-8: {cuts[1][:30]!r}")
g = t.dir / "outputs" / "cp.txt"
g.write_bytes("Строка в cp1251 — старый файл.\n".encode("cp1251") * 5)
ok(Q.file_text(g, limit=50).startswith("Строка в cp1251"), "файл в cp1251 по-прежнему читается")

# ---------- 5. разбор просьбы дочитать ----------
ok(Q.parse_look('{"verdict":"look","read":["a.md:1-5","https://x.ru"]}') == ["a.md:1-5", "https://x.ru"], "parse_look: список")
ok(Q.parse_look('{"verdict":"ok"}') == [] and Q.parse_look("мусор") == [], "parse_look: не просьба — пусто")
ok(Q.parse_look('{"verdict":"look","read":"a.md"}') == ["a.md"], "parse_look: строка вместо списка")
ok(Q.parse_verdict('{"verdict":"look","read":["a.md"]}')[0] == "unclear", "просьба дочитать — не вердикт")

host.stopping.set()
done()
