"""Выпуск 2 «Больших задач» — «Руки задачи» (docs/HARNESS.md, 04.11). Раньше у задачи без проекта были только перезапись
файла целиком и дописывание, поиска по файлам не было, а папку человека задача не видела. Теперь:
- file_read — с номерами строк и диапазоном, кусками по размеру;
- file_edit — старый кусок → новый: неточный поиск без учёта отступов (textedit.fuzzy_find — общий с codework),
  несколько совпадений — «встречается N раз, строки …», после правки .py/.json/.html — проверка синтаксиса (сломанное не сохраняется);
- file_grep и file_glob — по папке задачи и по папкам, которые человек дал задаче (folders в start_task): читать — без
  вопросов, менять — с разрешения (раз на папку) или в копию;
- ограничитель ответов «показано 1–200 из N, сузь: …»; безопасные инструменты (поиск, чтение, скачивание) после сбоя
  сети — ещё одна попытка; ошибки — «что случилось — как исправить»."""
import os

os.environ["DEWIAR_TASK_TOOL_RETRY_SEC"] = "0.2"
from task_mock import TMP, Host, Mock, done, ok, wait_for  # noqa: E402
import codework  # noqa: E402
import tasks as TK  # noqa: E402
import textedit  # noqa: E402
import tools as T  # noqa: E402

mock = Mock({})
host = Host(mock)
asked = []
host.confirm = lambda q, cancel=None: (asked.append(q), True)[1]
tm = TK.TaskManager(host)

# папка человека: 300 файлов в 6 подпапках
mine = TMP / "Мои документы"
for i in range(300):
    p = mine / f"раздел{i % 6}" / (f"заметка{i}.md" if i % 3 else f"таблица{i}.csv")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"общая строка {i}\n" + ("здесь КЛЮЧ-42 найдётся\n" if i % 25 == 0 else "ничего\n"), encoding="utf-8")
(mine / "бинарный.bin").write_bytes(b"\0\1\2" + "КЛЮЧ-42".encode())
t = tm.create("Руки", "Проверка инструментов файлов", start=False, folders=[str(mine)])
ok(t.data.get("folders") == [str(mine.resolve())], "задаче дана папка человека (folders)")
ok("ПАПКИ ЧЕЛОВЕКА" in tm._system(t) and str(mine.resolve()) in tm._system(t), "папки человека — в подсказке задачи (неизменной)")
names = [x["name"] for x in tm._specs(t)]
ok({"file_read", "file_edit", "file_grep", "file_glob", "write_file"} <= set(names) and len(names) <= 23,
   f"руки — в профиле задачи ({len(names)} инструментов)")


def run(name, **a):
    return tm._tool(t, name, a)


# ---------- file_read ----------
run("write_file", path="outputs/calc.py", content="def f(x):\n    x = 1\n    return x\n\n\ndef g(y):\n    x = 1\n    return y\n")
r = run("file_read", path="outputs/calc.py", start=2, end=3)
ok(r == "2:     x = 1\n3:     return x\n… показаны строки 2–3 из 8; дальше — file_read с start=4", f"file_read: номера строк и диапазон {r!r}")
ok(run("read_file", path="outputs/calc.py").startswith("1: def f(x):"), "read_file — старое имя, работает так же")
ok("Как исправить" in run("file_read", path="outputs/нет.txt"), "нет файла — «что случилось — как исправить»")
# ---------- file_edit ----------
r = run("file_edit", path="outputs/calc.py", old="    x = 1", new="    x = 2")
ok("встречается 2 раз" in r and "строки 2, 7" in r and "Как исправить" in r, f"неоднозначный кусок — «встречается 2 раз, строки 2, 7»: {r}")
r = run("file_edit", path="outputs/calc.py", old="def g(y):\n    x = 1", new="def g(y):\n    x = 3")
ok(r.startswith("Изменён outputs/calc.py, строки 6–7") and "x = 3" in (t.dir / "outputs/calc.py").read_text(), f"правка куском: {r}")
r = run("file_edit", path="outputs/calc.py", old="def f(x):\nx = 1\nreturn x", new="def f(x):\nx = 5\nreturn x")
txt = (t.dir / "outputs/calc.py").read_text()
ok("без учёта отступов" in r and "    x = 5\n    return x" in txt, f"неточный кусок (без отступов) — найден, отступы как в файле: {r}")
r = run("file_edit", path="outputs/calc.py", old="def h(z):", new="def h(q):")
ok("не найден" in r and "Самый похожий" in r, "кусок не найден — показан самый похожий с номерами строк")
r = run("file_edit", path="outputs/calc.py", old="    return y", new="    return (y")
ok("НЕ изменён" in r and "SyntaxError" in r and "return y" in (t.dir / "outputs/calc.py").read_text(), "правка ломает .py — не сохранена")
run("write_file", path="outputs/d.json", content='{"a": 1, "b": [1, 2]}')
ok("НЕ изменён" in run("file_edit", path="outputs/d.json", old='"b": [1, 2]', new='"b": [1, 2'), "правка ломает .json — не сохранена")
run("write_file", path="outputs/p.html", content="<html><body>\n<div class='a'>\n<p>текст</p>\n</div>\n</body></html>")
ok("НЕ изменён" in run("file_edit", path="outputs/p.html", old="</div>\n", new=""), "правка ломает .html (незакрытый div) — не сохранена")
ok(run("file_edit", path="outputs/p.html", old="<p>текст</p>", new="<p>новый текст</p>").startswith("Изменён"), ".html — верная правка проходит")
ok("заменено вхождений: 2" in run("file_edit", path="outputs/calc.py", old="return", new="return ", replace_all=True), "replace_all — все вхождения")
ok(codework.fuzzy_find is textedit.fuzzy_find and codework.nearest is textedit.nearest, "неточный поиск — общий модуль textedit (и у codework)")
# ---------- область: папка задачи и папки человека ----------
r = run("file_read", path="/etc/hostname")
ok(r.startswith("Ошибка") and "вне папки задачи" in r and "Как исправить" in r and str(mine.resolve()) in r,
   f"чужой путь — отказ с подсказкой, где можно: {r[:160]}")
r = run("file_read", path=str(mine / "раздел0" / "таблица0.csv"))
ok(r.startswith("1: общая строка 0") and not asked, "папка человека: читать — без вопросов")
r = run("file_edit", path=str(mine / "раздел1" / "заметка1.md"), old="ничего", new="кое-что")
ok(r.startswith("Изменён") and len(asked) == 1 and "кое-что" in (mine / "раздел1" / "заметка1.md").read_text(encoding="utf-8"),
   f"папка человека: менять — с разрешения ({len(asked)} вопрос)")
run("file_edit", path=str(mine / "раздел2" / "заметка2.md"), old="ничего", new="тоже")
ok(len(asked) == 1, "разрешение — раз на папку за задачу")
t2 = tm.create("Без разрешения", "x", start=False, folders=[str(mine)])
host.confirm = lambda q, cancel=None: False
r = tm._tool(t2, "write_file", {"path": str(mine / "новый.txt"), "content": "x"})
ok("не разрешил" in r and "outputs/" in r and not (mine / "новый.txt").exists(), f"отказал — не пишем, предлагаем копию в outputs/: {r[:120]}")
host.confirm = lambda q, cancel=None: (asked.append(q), True)[1]
# ---------- file_grep и file_glob: 300 файлов, ограничитель ----------
r = run("file_grep", pattern="ключ-42", path=str(mine))
lines = [x for x in r.splitlines() if "КЛЮЧ-42" in x]
ok(len(lines) == 12 and all(x.startswith(str(mine.resolve())) and ":2: здесь КЛЮЧ-42" in x for x in lines) and "бинарный" not in r,
   f"file_grep по 300 файлам: 12 совпадений с номером строки, без регистра, двоичные пропущены ({len(lines)})")
r = run("file_grep", pattern="общая строка", path=str(mine))
import re  # noqa: E402
m = re.search(r"показано 1–(\d+) из 300 совпадений в 300 файлах", r)
ok(m and "Сузь" in r and r.count("\n") == int(m.group(1)) and len(r) <= 4000, f"ограничитель: «показано 1–{m and m.group(1)} из 300, сузь: …», ответ ≤ 4000 знаков")
r = run("file_grep", pattern="общая", path=str(mine), glob="*.csv")
ok("из 100 совпадений в 100 файлах" in r and "заметка" not in r, "file_grep с glob — только *.csv (100)")
r = run("file_glob", pattern="**/*.csv", path=str(mine))
ok("из 100 файлов" in r and "таблица" in r and "байт" in r and "заметка" not in r, f"file_glob: 100 таблиц с размерами, с ограничителем")
ok("из 301 файлов" in run("file_glob", path=str(mine)), "file_glob без шаблона — с ограничителем")
r = run("file_glob", pattern="*.py")
ok(r.strip() == f"outputs/calc.py — {(t.dir / 'outputs/calc.py').stat().st_size} байт", f"file_glob в папке задачи — относительные пути: {r}")
ok("x = 5" in run("file_grep", pattern=r"x = \d") and "задача.json" not in run("file_grep", pattern="Руки"), "file_grep в папке задачи; служебное — мимо")
# ---------- start_task: folders ----------
T.t_start_task({"goal": "Разбери мои документы", "folders": [str(mine)]}, {"tasks": tm})
tn = [x for x in tm.tasks.values() if x.goal == "Разбери мои документы"][0]
ok(tn.data.get("folders") == [str(mine.resolve())], "start_task(folders=…) — папки доходят до задачи")
tm.stop(tn.id)
try:
    tm.create("x", "y", start=False, folders=[str(TMP / "нет такой")])
    ok(False, "несуществующая папка — ошибка")
except ValueError as e:
    ok("папки нет" in str(e), "несуществующая папка — ошибка при создании")

# ---------- повтор безопасного инструмента после 503 ----------
calls = []


def search(h):
    calls.append(1)
    if len(calls) == 1:
        h.send_response(503)
        h.end_headers()
        return
    return h._json(200, {"results": [{"title": "Тепловой насос", "url": "https://example.org/hp", "content": "COP 3–4"}]})


mock.search = search


class S2:
    def get(self, *k):
        return f"http://127.0.0.1:{mock.srv.server_port}" if k == ("tools", "search_url") else ({} if k[0] == "tools" else None)


host.toolbox = T.Toolbox(S2(), None)
host.toolbox.hooks["workspace"] = host.workspace
r = run("web_search", query="тепловой насос")
j = (t.dir / "журнал.md").read_text(encoding="utf-8")
ok(len(calls) == 2 and "Тепловой насос" in r and "↻ web_search: сбой сети" in j, f"поиск упал с 503 — повторён сам и удался ({len(calls)} запроса)")
calls.clear()
mock.search = lambda h: (calls.append(1), h._json(500, {"error": "boom"}))[1]
r = run("web_search", query="ещё")
ok(len(calls) == 2 and r.startswith("Ошибка"), "две неудачи — честная ошибка, без бесконечных повторов")
calls.clear()
r = run("file_edit", path="outputs/нет.py", old="a", new="b")
ok("Как исправить" in r, "не повторяем небезопасное и «нет файла» — сразу совет")

# ---------- целиком: задача правит файл куском через модель ----------
A = "Правка куском"
mock.scripts[A] = [("write_file", {"path": "outputs/отчёт.md", "content": "# Отчёт\n\nИтого: 100\n"}),
                   ("file_edit", {"path": "outputs/отчёт.md", "old": "Итого: 100", "new": "Итого: 120"}),
                   ("show", {"path": "outputs/отчёт.md"}), ("finish", {"summary": "Отчёт исправлен."})]
ta = tm.create(A, "Исправь итог в отчёте")
ok(wait_for(lambda: ta.status in ("done", "failed"), 30) and ta.status == "done" and "Итого: 120" in (ta.dir / "outputs/отчёт.md").read_text(encoding="utf-8"),
   f"задача через модель: write_file → file_edit → готово ({ta.status} {ta.error})")
done()
