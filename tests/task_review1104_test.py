"""Рецензия больших задач (04.11, до выпуска 0.83): три дыры в безопасности, порча файлов, маленькое окно, потеря ответов
человека, экзамен и исполнитель. Каждый пункт рецензии — здесь (сценарии рецензента: sec1, cloud, win, cons, skill, prompt).
1. «..» и полный путь в шаблоне file_grep/file_glob, ссылка (symlink) наружу — не выводят из области задачи.
2. Папки задаче даёт человек: start_task(folders) от модели — только после «да» с перечнем; весь диск и домашняя папка —
   нельзя; детский режим и замок «только папка Dewiar» — нельзя; части получают папки основной задачи.
3. Облако: download, run_python, ask_user, transcribe — ни в профиле, ни через find_tool, ни вызовом по имени.
4–5. file_edit сохраняет кодировку (cp1251, BOM) и CRLF; неточный поиск правит найденное место, а не первое вхождение.
6. Окно 4 тыс. — задача доходит до finish (max_tokens = место под ответ, описания инструментов — до первой фразы);
   запомненное окно — только для той же модели.
7. Ответы человека — сразу в блокнот («Ответы человека»), не теряются при сжатии (формат Claude тоже) и при notes.
8. use_skill не уходит в _out/.  9–12. Экзамен: Б11 без перезапуска — «не проверено»; ядро гасится группой процессов;
   библиотеки больших задач — отдельно и по возможности; весточка до установки; нехватка места — не падение."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from task_mock import ROOT, TMP, Host, Mock, done, ok, wait_for
import cloudrunner as CR  # noqa: E402
import codework  # noqa: E402
import exam  # noqa: E402
import exam_big as EB  # noqa: E402
import llm  # noqa: E402
import tasks as TK  # noqa: E402
import textedit as TE  # noqa: E402
import tools as T  # noqa: E402

mock = Mock({})
host = Host(mock)
asked = []
host.confirm = lambda q, cancel=None: (asked.append(q), True)[1]
tm = TK.TaskManager(host)

# ---------- 1. «..», полный путь, symlink ----------
secret = TMP / "home" / ".ssh"
secret.mkdir(parents=True)
(secret / "id_rsa").write_text("PRIVATE-KEY-XYZ")
t = tm.create("Без папок", "цель", start=False)
rel = os.path.relpath(secret, t.dir)
for name, a in (("file_grep", {"pattern": "PRIVATE", "glob": rel + "/*"}), ("file_glob", {"pattern": rel + "/*"}),
                ("file_glob", {"pattern": str(secret) + "/*"}), ("file_grep", {"pattern": "PRIVATE", "glob": "**/../../../../home/.ssh/*"}),
                ("file_glob", {"pattern": "~/.ssh/*"}), ("file_grep", {"pattern": "PRIVATE", "path": rel}),
                ("file_read", {"path": str(secret / "id_rsa")}), ("file_read", {"path": rel + "/id_rsa"})):
    r = tm._tool(t, name, a)
    ok("PRIVATE-KEY" not in r and "id_rsa —" not in r and ("Как исправить" in r or "Ничего не нашлось" in r or "нет" in r),
       f"{name} {json.dumps(a, ensure_ascii=False)[:70]} — наружу не выходит: {r[:90]!r}")
(t.dir / "outputs").mkdir()
(t.dir / "outputs" / "ссылка.txt").symlink_to(secret / "id_rsa")
(t.dir / "outputs" / "папка").symlink_to(secret, target_is_directory=True)
for name, a in (("file_grep", {"pattern": "PRIVATE"}), ("file_glob", {"pattern": "**/*"}), ("file_read", {"path": "outputs/ссылка.txt"}),
                ("file_read", {"path": "outputs/папка/id_rsa"})):
    r = tm._tool(t, name, a)
    ok("PRIVATE-KEY" not in r and "id_rsa —" not in r and "id_rsa:" not in r, f"ссылка из папки задачи наружу — {name}: {r[:80]!r}")
mine = TMP / "mine"
mine.mkdir()
(mine / "своё.txt").write_text("СВОЁ")
(mine / "link.txt").symlink_to(secret / "id_rsa")
t2 = tm.create("С папкой", "цель", start=False, folders=[str(mine)])
r = tm._tool(t2, "file_grep", {"pattern": "PRIVATE|СВОЁ", "path": str(mine)})
ok("СВОЁ" in r and "PRIVATE" not in r, f"ссылка из папки человека наружу — мимо, своё — находится: {r[:120]!r}")
ok("PRIVATE" not in tm._tool(t2, "file_read", {"path": str(mine / "link.txt")}), "file_read через ссылку из папки человека — отказ")

# ---------- 2. папки от модели — только с «да» человека ----------


class S:
    def __init__(self, files=""):
        self.files = files

    def get(self, *k):
        if k == ("privacy",):
            return {"files": self.files}
        return {} if k[0] == "tools" else None


tb = T.Toolbox(S(), None)
bl, force, q = tb.guard("start_task", {"goal": "x", "folders": [str(mine)]})
ok(not bl and force and str(mine) in q and "Разрешить?" in q, f"start_task(folders) от модели — вопрос человеку с перечнем папок: {q}")
ok(tb.guard("start_task", {"goal": "x"}) == (None, False, None), "без папок — как раньше, без вопроса")
for bad in ("/", str(Path.home()), str(Path.home().parent)):
    bl, force, q = tb.guard("start_task", {"goal": "x", "folders": [bad]})
    ok(bl and "весь диск или вся домашняя папка" in bl, f"«{bad}» — запрещено: {bl}")


class Kids:
    def on(self):
        return True

    def tools(self):
        return {"start_task"}


tk = T.Toolbox(S(), None)
tk.hooks["kids"] = Kids()
ok("детском режиме" in (tk.guard("start_task", {"goal": "x", "folders": [str(mine)]})[0] or ""), "детский режим — папки не даются вовсе")
tl = T.Toolbox(S("folder"), None)
ok("замок" in (tl.guard("start_task", {"goal": "x", "folders": [str(mine)]})[0] or ""), "замок «Файлы: только папка Dewiar» — папку вне её не дать")
try:
    tm.create("Весь диск", "x", start=False, folders=["/"])
    ok(False, "весь диск — отказ и при создании")
except ValueError as e:
    ok("весь диск" in str(e), "весь диск — отказ и при создании задачи (откуда бы ни пришла просьба)")
src = (ROOT / "core/engine_tools.py").read_text(encoding="utf-8")
ok("self.toolbox.guard(name, args)" in src and "if need_confirm or force:" in src, "разговор спрашивает человека, когда guard требует (force)")
tp = tm.create("С частями", "цель", start=False, folders=[str(mine)])
tm.start = lambda tid, wake="": tm.tasks[tid]                      # части не запускаем — нужна только их папка
tm._spawn_parts(tp, [{"title": "часть", "goal": "сделай"}])
part = [x for x in tm.tasks.values() if x.data.get("parent") == tp.id][0]
ok(part.data.get("folders") == [str(mine.resolve())], "часть получает папки основной задачи")
del tm.start

# ---------- 3. облако ----------
ch = Host(mock)
ch.toolbox = CR.CloudToolbox("x")
ch.code_auto_run = lambda: False
ch.confirm = lambda q, cancel=None: False
ch.skills_prompt = lambda: ""
ctm = CR.CloudTasks(ch)
ct = ctm.create("Облако", "цель", start=False)
os.environ["DEWIAR_SANDBOX"] = "guard"         # выпуск 5: без bubblewrap кода в облаке нет (с ним — sandbox_test)
ok(CR.cloud_skip() == CR.CLOUD_SKIP and "run_shell" in CR.CLOUD_SKIP, "облако без bubblewrap: run_python и run_shell недоступны")
cat = ctm._catalog(ct)
ok(not (set(cat) & CR.CLOUD_SKIP) and not ({x["name"] for x in ctm._specs(ct)} & CR.CLOUD_SKIP), "облако: download, run_python, ask_user, transcribe — нет в каталоге")
for qq in ("скачать файл по ссылке", "спросить пользователя", "выполнить код python", "расшифровать запись"):
    r = ctm._tool(ct, "find_tool", {"query": qq})
    ok(not any(n in r for n in CR.CLOUD_SKIP), f"облако: find_tool «{qq}» их не предлагает: {r[:80]!r}")
r = ctm._tool(ct, "find_tool", {"connect": "download"})
ok("нет такого инструмента" in r and "download" not in (ct.data.get("tools_on") or []), "облако: find_tool connect=download — отказ")
for name in sorted(CR.CLOUD_SKIP):
    t0 = time.time()
    r = ctm._tool(ct, name, {"url": "http://127.0.0.1:1/x", "question": "?", "code": "print(1)", "path": "a"})
    ok("в облаке недоступен" in r and time.time() - t0 < 2, f"облако: вызов {name} по имени — «недоступен», сразу")
os.environ.pop("DEWIAR_SANDBOX", None)

# ---------- 4–5. кодировка, CRLF, неточный поиск ----------
f = t.dir / "outputs" / "win.txt"
f.write_bytes("Привет, мир\r\nkey = 1\r\nПока\r\n".encode("cp1251"))
r = tm._tool(t, "file_edit", {"path": "outputs/win.txt", "old": "key = 1", "new": "key = 2"})
ok(f.read_bytes() == "Привет, мир\r\nkey = 2\r\nПока\r\n".encode("cp1251"), f"cp1251 и CRLF сохранены: {r}")
ok("1: Привет, мир" in tm._tool(t, "file_read", {"path": "outputs/win.txt"}), "file_read читает cp1251")
r = tm._tool(t, "file_edit", {"path": "outputs/win.txt", "old": "Пока", "new": "Пока «до встречи» ✓"})
ok("НЕ изменён" in r and "Как исправить" in r and b"\r\n" in f.read_bytes(), f"символа нет в cp1251 — файл не испорчен: {r[:100]}")
g = t.dir / "outputs" / "bom.md"
g.write_bytes(b"\xef\xbb\xbfa = 1\r\nb = 2\r\n")
tm._tool(t, "file_edit", {"path": "outputs/bom.md", "old": "a = 1\nb = 2", "new": "a = 3\nb = 4"})
ok(g.read_bytes() == b"\xef\xbb\xbfa = 3\r\nb = 4\r\n", f"UTF-8 с BOM и CRLF сохранены (кусок через несколько строк): {g.read_bytes()!r}")
(t.dir / "outputs" / "bin.dat").write_bytes(b"abc\0def")
ok("не текстовый" in tm._tool(t, "file_read", {"path": "outputs/bin.dat"}), "file_read: двоичный файл — совет, а не мусор")
src_ = "# пример:     return x\ndef f():\n    return x\n"
out, line, note = TE.apply_edit(src_, "return  x", "return y")
ok(out == "# пример:     return x\ndef f():\n    return y\n" and line == 3, f"неточный поиск правит найденную строку 3, а не комментарий: {out!r}")
proj = TMP / "proj"
proj.mkdir()
(proj / "a.py").write_text(src_)
cw = codework.CodeWork(str(proj), TMP / "work")
cw.prepare()
cw.edit("a.py", "return  x", "return y")
ok((TMP / "work" / "a.py").read_text() == "# пример:     return x\ndef f():\n    return y\n", "то же в коде (codework.edit)")

# ---------- 6. окно 4 тыс. ----------
A = "Окно 4 тыс"
steps = [("update_plan", {"plan": "**Готово, когда:** итог\n\n- [ ] данные"})]
steps += [("run_python", {"code": f"print('шаг {k} ' * 1500)"}) for k in range(6)]
steps += [("update_plan", {"plan": "**Готово, когда:** итог\n\n- [x] данные"}), ("finish", {"summary": "Готово."})]
m4 = Mock({A: steps}, window=4096)
h4 = Host(m4)
tm4 = TK.TaskManager(h4)
t4 = tm4.create(A, "Проверка окна 4096")
ok(wait_for(lambda: t4.status in ("done", "failed", "paused"), 90) and t4.status == "done", f"окно 4096 — задача дошла до finish ({t4.status} {t4.error})")
rs = m4.of(A)
ok(rs and all(r["max_tokens"] == 1024 for r in rs) and not [x for x in m4.over if x > 0],
   f"модели уходит max_tokens = место под ответ (1024), сервер ни разу не отказал: {[r['max_tokens'] for r in rs][:3]} {m4.over}")
ok(rs and all(len(x["function"]["description"]) <= 160 and x["function"]["description"].count(". ") == 0 for x in rs[0]["tools"]),
   "окно меньше 6 тыс. — описания инструментов до первой фразы")
t4.data["win_learned"] = {"key": "http://другой|m", "win": 3000}
ok(TK.TaskManager._win_key(h4.llm_profile()) != t4.data["win_learned"]["key"], "запомненное окно привязано к адресу и модели")
m4.scripts["Другая модель"] = [("finish", {"summary": "Готово."})]
t5 = tm4.create("Другая модель", "x", start=False)
t5.data["win_learned"] = {"key": "http://другой|m", "win": 3000}
tm4.start(t5.id)
ok(wait_for(lambda: t5.status == "done", 30) and "win_learned" not in t5.data and t5.data.get("win") == 4096,
   f"другая модель — запомненное окно сброшено, окно своё ({t5.data.get('win')})")

# ---------- 7. ответы человека ----------
tc = tm.create("Ответы", "цель", start=False)
seen = []
real_sc = llm.stream_chat


def fake(prof, sysm, msgs, cancel=None, **k):
    seen.append(msgs[0]["content"])
    raise llm.LLMError("нет связи")


llm.stream_chat = fake
dropped = [{"role": "assistant", "content": [{"type": "text", "text": "Спрошу"}, {"type": "tool_use", "id": "u1", "name": "ask_user",
                                                                                 "input": {"question": "Какой город?"}}]},
           {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u1", "content": [{"type": "text", "text": "Ответ пользователя: Казань"}]}]},
           {"role": "user", "content": "Сообщение пользователя для этой задачи:\n— бюджет 5000"}]
tm._consolidate(tc, {"kind": "anthropic"}, dropped)
llm.stream_chat = real_sc
nb = tc.notebook()
ok("Казань" in seen[0] and "Действие: ask_user" in seen[0], "Claude: вызовы и ответы (tool_use, tool_result) — в переписку блокнота")
ok("Казань" in nb and "5000" in nb, "модель не ответила — ответ человека и его сообщение всё равно в блокноте")
tc.set_notebook("# Блокнот задачи\n\n")
tm._note_human(tc, "На вопрос «Город?»: Казань")
tc.set_notebook("# Блокнот задачи\n\n## Что известно\n- переписала всё заново\n")
ok("## Ответы человека" in tc.notebook() and "Казань" in tc.notebook(), "модель переписала блокнот (notes) — «Ответы человека» на месте")
A7 = "Спросить город"
m7 = Mock({A7: [("ask_user", {"question": "Какой город?"}), ("finish", {"summary": "Готово."})]})
h7 = Host(m7)
tm7 = TK.TaskManager(h7)
h7.ask_user = lambda t_, q_: threading.Timer(0.2, lambda: tm7.answer(t_.id, "Казань")).start()
t7 = tm7.create(A7, "Узнать город")
ok(wait_for(lambda: t7.status == "done", 30) and "## Ответы человека" in t7.notebook() and "Казань" in t7.notebook(),
   "ответ на ask_user — сразу в блокнот, раздел «Ответы человека»")
tm7.tell(t7.id, "И учти бюджет 7000")
ok(wait_for(lambda: "7000" in t7.notebook() and t7.status == "done", 30), "сообщение человека задаче — тоже в блокнот")

# ---------- 8. use_skill целиком ----------
long_skill = "ИНСТРУКЦИЯ\n" + "правило. " * 1500 + "\nСЕРЕДИНА\n" + "ещё. " * 1000
ok(tm._offload(t, "use_skill", long_skill) == long_skill and tm._offload(t, "read_skill_file", long_skill) == long_skill
   and "_out/" in tm._offload(t, "web_search", long_skill), "use_skill и read_skill_file — целиком, а не в _out/")

# ---------- 9–12. экзамен и исполнитель ----------
d = TMP / "anki"
info = exam.make_fixture("anki", d, 1)
(d / "outputs").mkdir()
(d / "outputs" / "anki.csv").write_text("".join(f"{w};перевод;Пример {w}.\n" for w in info["words"]), encoding="utf-8")
chs = exam.BIG_CHECKS["anki"](d, info, {"status": "done"})
c = [x for x in chs if not x["ok"]]
ok(len(c) == 1 and c[0]["name"] == "перезапуск не проверен" and c[0].get("unchecked"), f"Б11 без перезапуска — «перезапуск не проверен», не «пройдено»: {c}")
es = (ROOT / "core/exam.py").read_text(encoding="utf-8")
ok('"start_new_session": True' in es and "os.killpg(self.proc.pid" in es, "ядро экзамена — своя группа процессов, stop() гасит группу")
co = exam.Core({}, TMP / "core")
co.proc = subprocess.Popen([sys.executable, "-c", "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);"
                            "print(1, flush=True); time.sleep(60)"], start_new_session=True, stdout=subprocess.PIPE)
co.proc.stdout.readline()
import asyncio  # noqa: E402
asyncio.run(co.stop())
time.sleep(0.5)
left = [x for x in subprocess.run(["ps", "-o", "pid=,stat=", "-g", str(co.proc.pid)], capture_output=True, text=True).stdout.splitlines()
        if x.split() and not x.split()[1].startswith("Z")]          # зомби (ждут, пока их уберёт init) — уже не работают
ok(co.proc.poll() is not None and not left, f"stop(): ни ядра, ни его детей не осталось ({left})")
ok("openpyxl" not in CR.EXAM_PROBE and "playwright" not in CR.EXAM_PROBE and CR.BIG_PKGS == ["openpyxl", "playwright"],
   "openpyxl и playwright — не в базовом окружении экзамена, а отдельно для больших задач")
rs_ = (ROOT / "core/cloudrunner.py").read_text(encoding="utf-8")
ok(rs_.index('target=self._beat') < rs_.index("py = self.python()") and "self.big_pkgs(py)" in rs_,
   "весточка «жив» — до установки окружения; библиотеки больших задач — только при big")
ej = CR.ExamJob({"id": "x", "big": True})
ej.home = TMP / "ej"
ej.home.mkdir()
ej.post = lambda *a, **k: None
(ej.home / "pw-browsers.tried").mkdir()                    # запись отметки упадёт с OSError (как при нехватке места)
fake = TMP / "fakepy.sh"
fake.write_text("#!/bin/sh\nexit 1\n")
fake.chmod(0o755)
ok(ej.browser(fake) == ej.home / "pw-browsers", "Chromium: ошибка записи (место на диске) — экзамен не падает")
ok(ej.big_pkgs(fake) is False, "библиотеки больших задач не поставились — экзамен идёт дальше (False, без исключения)")

# ---------- prompt-режим (вызовы текстом): до finish, состояние последним, подсказка неизменна ----------
AP = "Текстом"
psteps = [("update_plan", {"plan": "**Готово, когда:** есть файл\n\n- [ ] файл"})] + [("run_python", {"code": f"print('x{k} ' * 3000)"}) for k in range(8)]
psteps += [("write_file", {"path": "outputs/a.md", "content": "# A\n" + "строка\n" * 200}), ("show", {"path": "outputs/a.md"}),
           ("update_plan", {"plan": "**Готово, когда:** есть файл\n\n- [x] файл"}), ("finish", {"summary": "Готово: outputs/a.md"})]
mp = Mock({}, window=16384)
preqs = []


def handle(h, body):
    sysm = body["messages"][0]["content"]
    if "ЗАДАЧА:" not in sysm:
        return mp.send(h, '{"verdict": "ok"}' if sysm.startswith("Ты — строгий") else "# Блокнот задачи\n\n- сжато\n")
    mp.last_body = body
    i = len(preqs)
    preqs.append(body)
    st = psteps[i] if i < len(psteps) else ("finish", {"summary": "Готово."})
    mp.send(h, f"Шаг {i + 1}.\n<tool_call>\n" + json.dumps({"name": st[0], "arguments": st[1]}, ensure_ascii=False) + "\n</tool_call>")


mp.handle = handle
hp = Host(mp, tools_mode="prompt")
tmp_ = TK.TaskManager(hp)
tpp = tmp_.create(AP, "Проверка режима вызовов текстом")
ok(wait_for(lambda: tpp.status in ("done", "failed", "paused"), 90) and tpp.status == "done", f"вызовы текстом — до finish ({tpp.status} {tpp.error})")
ok(all("Состояние задачи" in json.dumps(b["messages"][-1], ensure_ascii=False) for b in preqs)
   and all("Состояние задачи" not in json.dumps(b["messages"][1:-1], ensure_ascii=False) for b in preqs), "состояние — последним и в историю не оседает")
ok(len({b["messages"][0]["content"] for b in preqs[1:]}) == 1, "подсказка с описанием инструментов текстом — одна на шагах 2…N")
done()
