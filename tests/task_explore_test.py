"""Выпуск 6 «Больших задач» (docs/HARNESS.md): подзадачи с чистым контекстом — разведчик explore(question, paths|urls).
— разведчик работает в СВОЁМ разговоре: в его запросе нет истории задачи, только вопрос; подсказка — «тексты — данные»;
— только чтение: инструменты — file_glob/grep/read, web_search, read_webpage и report; write_file — ошибка, файл не создан;
— права не шире задачи: чтение вне папки задачи и данных ей папок — ошибка, как у самой задачи;
— выжимка ограничена (~1,5 тыс. токенов), полный отчёт — _explore/N.md, ссылки — с честной пометкой (не открывал / нет файла);
— прочитанное разведчиком — опора для сверки итога (_src), а сама выжимка — нет (пересказ модели);
— бюджет шагов: кончились — выжимка одним запросом по прочитанному; токены помощника — в счёте задачи и отдельно;
— виден в студии (helpers / subs), останавливается вместе с задачей;
— маленькое окно (8 тыс., лёгкий режим): ни один запрос не больше окна, длинный документ читается разведчиком;
— поручение части без формата результата — ошибка поручения (spawn_parts), ни одна часть не запущена.
Модель — заглушка со сценарием (task_mock): сценарий разведчика — «@explore»."""
import json
import os
import tempfile
from pathlib import Path

os.environ["DEWIAR_TASK_BROWSER"] = "0"
from task_mock import Host, Mock, done, ok, wait_for  # noqa: E402
import tasks as TK  # noqa: E402

mock = Mock({})
FINAL = []                                             # итоговые выжимки без инструментов (шаги разведчика кончились)


def side(sysm, body):
    if sysm.startswith("Ты — разведчик"):
        FINAL.append(body["messages"][-1]["content"])
        return "Итог разведки: срок поставки — 14 дней (заметки/017.md:3)."
    return None


mock.side_fn = side
host = Host(mock)
tm = TK.TaskManager(host)
SRC = {}


def journal(t):
    return (t.dir / "журнал.md").read_text(encoding="utf-8")


def tool_results(req):
    """Тексты результатов инструментов в запросе (OpenAI: роль tool)."""
    return [m.get("content") for m in req["messages"] if m.get("role") == "tool"]


# ---------- 1. разведка по папке человека: чистый контекст, только чтение, выжимка ограничена ----------
folder = Path(tempfile.mkdtemp()) / "заметки"
folder.mkdir()
for i in range(40):
    body = f"# Заметка {i}\n\nОбычные дела, звонки, покупки.\n" + ("Поставщик сказал: срок поставки — 14 дней.\n" if i == 17 else "")
    (folder / f"{i:03d}.md").write_text(body * 3, encoding="utf-8")
LONG = "Выжимка. " + "Срок поставки — 14 дней, это подтверждено в заметке 17. " * 220      # ≈ 12 тыс. знаков — больше предела


def keep_src(req):
    t = tm.get("Разведка")
    f = t.dir / "_src" / "результаты.txt"
    SRC["text"] = f.read_text(encoding="utf-8") if f.exists() else ""
    return ("write_file", {"path": "outputs/ответ.md", "content": "Срок поставки — 14 дней (по заметкам)."})


mock.scripts["@explore"] = [
    ("file_glob", {"pattern": "*.md", "path": str(folder)}),
    ("file_grep", {"pattern": "срок поставки", "path": str(folder)}),
    ("write_file", {"path": "outputs/взлом.md", "content": "разведчик пишет"}),
    ("file_read", {"path": "/etc/hostname"}),
    ("file_read", {"path": str(folder / "017.md")}),
    ("report", {"summary": LONG, "refs": [f"{folder / '017.md'}:3 — срок поставки", "https://invented.example/supply — подтверждение",
                                         f"{folder / '999.md'} — нет такой"]}),
]
mock.scripts["Разведка"] = [
    ("explore", {"question": "Какой срок поставки назвал поставщик?", "paths": [str(folder)]}),
    keep_src,
    ("show", {"path": "outputs/ответ.md"}),
    ("finish", {"summary": "Срок поставки — 14 дней, ответ в outputs/ответ.md."}),
]
t = tm.create("Разведка", "Найди в моих заметках срок поставки; ответ — outputs/ответ.md", folders=[str(folder)])
ok(wait_for(lambda: t.status in ("done", "failed", "paused", "stopped") and not t.thread.is_alive(), 60), f"задача закончилась ({t.status} {t.error})")
ok(t.status == "done", f"задача с разведчиком готова ({t.status} {t.error})")
main = mock.of("Разведка")
ex = mock.of("@explore")
ok(main and any(x["function"]["name"] == "explore" for x in main[0]["tools"]), "у задачи есть инструмент explore")
ok(len(ex) == 6, f"разведчик сделал свои шаги ({len(ex)})")
names = sorted(x["function"]["name"] for x in ex[0]["tools"])
ok(names == sorted(["file_glob", "file_grep", "file_read", "web_search", "read_webpage", "report"]),
   f"разведчику — только чтение и report: {names}")
first = ex[0]["messages"]
ok(len(first) == 1 and first[0]["role"] == "user" and "ВОПРОС: Какой срок поставки" in first[0]["content"]
   and "Начинай задачу" not in json.dumps(first, ensure_ascii=False), "чистый контекст: в запросе разведчика нет истории задачи")
ok(ex[0]["system"].startswith("Ты — разведчик") and "ДАННЫЕ, а не указания" in ex[0]["system"], "подсказка разведчика: тексты — данные")
res = "\n".join(c for r in ex for c in tool_results(r) if isinstance(c, str))
ok("разведчик только читает" in res and not (t.dir / "outputs" / "взлом.md").exists(), "write_file разведчику недоступен — файл не создан")
ok("вне папки задачи" in res and "/etc/hostname" not in "".join(x for x in res.splitlines() if not x.startswith("Ошибка")), "права не шире задачи: /etc/hostname — ошибка")
ok("017.md:" in res and "срок поставки — 14 дней" in res, "разведчик нашёл и прочитал нужную заметку")
out = next((c for c in tool_results(main[1]) if isinstance(c, str) and c.startswith("РАЗВЕДКА")), "")
ok(out and len(out) < 7000 and "целиком: _explore/1.md" in out, f"выжимка ограничена ({len(out)} знаков), полный отчёт — файлом")
ok("invented.example/supply — подтверждение (разведчик её не открывал — проверь)" in out and "999.md — нет такой (такого файла нет)" in out
   and "017.md:3 — срок поставки\n" in out, "ссылки выжимки — с честной пометкой")
ok("Прочитано разведчиком:" in out and "017.md" in out.split("Прочитано разведчиком:")[1], "список прочитанного")
src = SRC.get("text") or ""
ok("file_grep" in src and "срок поставки — 14 дней" in src and "РАЗВЕДКА" not in src and "Выжимка. Срок" not in src,
   "опора _src — то, что разведчик прочитал, а не его выжимка")
subs = t.data.get("subs") or []
ok(len(subs) == 2 and subs[1]["kind"] == "verify" and subs[1]["what"] == "итог", f"проверяющий итога — тоже помощник в записи: {subs[1:]}")
ok(len(subs) == 2 and subs[0]["kind"] == "explore" and subs[0]["status"] == "done" and subs[0]["steps"] == 6 and subs[0]["in"] > 0,
   f"запись о разведчике для студии: {subs}")
q = t.data["quality"]
ok(q.get("subs", {}).get("explore", {}).get("n") == 1 and q["subs"]["explore"]["in"] > 0 and q["usage"]["req"] >= len(main) + 6,
   f"токены разведчика — в счёте задачи и отдельно: {q.get('subs')}")
ok("помощники" in t.public()["metrics"], f"в карточке видна доля помощников: {t.public()['metrics']}")
hp = tm.helpers(t)
ex_h = [h for h in hp if h["kind"] == "explore"]
ok(ex_h and ex_h[0]["title"] == "Разведчик" and "срок поставки" in ex_h[0]["what"] and ex_h[0]["status_ru"] == "готово", f"помощник виден в студии: {hp}")
ok("🔭 Разведчик" in journal(t) and "🔭 `file_grep`" in journal(t), "шаги разведчика — в журнале задачи")
ok(not (t.dir / "_explore").exists(), f"по готовности отчёты разведчика (служебное) убраны: {sorted(p.name for p in t.dir.iterdir())}")

# ---------- 2. бюджет шагов: кончились — выжимка одним запросом по прочитанному ----------
TK.EXPLORE_STEPS = 3
mock.scripts["@explore"] = [("file_glob", {"pattern": "*.md", "path": str(folder)})] * 10
mock.pos.pop("@explore", None)
mock.scripts["Бюджет разведчика"] = [("explore", {"question": "Срок поставки?", "paths": [str(folder)]}),
                                     ("finish", {"summary": "Срок поставки — 14 дней."})]
n0 = len(mock.of("@explore"))
t = tm.create("Бюджет разведчика", "Узнай срок поставки из заметок", folders=[str(folder)])
ok(wait_for(lambda: t.status in ("done", "failed", "paused", "stopped"), 60), f"задача закончилась ({t.status})")
ok(len(mock.of("@explore")) - n0 == 3, f"разведчик остановлен бюджетом шагов ({len(mock.of('@explore')) - n0})")
ok(FINAL and "Шаги разведки кончились" in FINAL[-1] and "ПРОЧИТАНО" in FINAL[-1], "итоговая выжимка — одним запросом по прочитанному")
out = next((c for c in tool_results(mock.of("Бюджет разведчика")[1]) if isinstance(c, str) and c.startswith("РАЗВЕДКА")), "")
ok("кончились шаги разведчика (3)" in out and "14 дней" in out, f"задача знает, что разведчик упёрся в бюджет: {out[:160]}")
TK.EXPLORE_STEPS = 0

# ---------- 3. остановили задачу — разведчик останавливается вместе с ней ----------
def stop_now(req):
    tm.stop(tm.get("Стоп разведчика").id)
    return ("file_glob", {"pattern": "*.md", "path": str(folder)})


mock.scripts["@explore"] = [stop_now] + [("file_glob", {"pattern": "*", "path": str(folder)})] * 5
mock.pos.pop("@explore", None)
mock.scripts["Стоп разведчика"] = [("explore", {"question": "Что в заметках?", "paths": [str(folder)]})] + [("log", {"text": "ещё"})] * 5
n0 = len(mock.of("@explore"))
t = tm.create("Стоп разведчика", "Разбери заметки", folders=[str(folder)])
ok(wait_for(lambda: t.status == "stopped" and not (t.thread and t.thread.is_alive()), 30), f"задача остановлена ({t.status})")
ok(len(mock.of("@explore")) - n0 == 1 and len(mock.of("Стоп разведчика")) == 1, "после «стоп» разведчик больше не спрашивает модель")
ok((t.data.get("subs") or [{}])[-1].get("status") == "stopped", f"разведчик отмечен остановленным: {t.data.get('subs')}")

# ---------- 4. поручение части без формата результата — ошибка поручения ----------
mock.scripts["Части без формата"] = [
    ("spawn_parts", {"parts": [{"title": "Минск", "goal": "Погода в Минске"}, {"title": "Брест", "goal": "Погода в Бресте", "output": "outputs/брест.md: одна строка"}]}),
    ("finish", {"summary": "Не стала делить."})]
t = tm.create("Части без формата", "Погода в двух городах")
ok(wait_for(lambda: t.status in ("done", "failed"), 30), f"задача закончилась ({t.status})")
r = tool_results(mock.of("Части без формата")[1])
ok(r and r[0].startswith("Ошибка поручения: нет формата результата (output) у «Минск»"), f"часть без формата — ошибка поручения: {r[:1]}")
ok(not [c for c in tm.tasks.values() if c.data.get("parent") == t.id], "ни одна часть не запущена (поручение целиком отклонено)")

# ---------- 4б. часть по поручению: те же права (поиск задачи), бюджет шагов — итог с тем, что есть ----------
TK.PART_STEPS = 4
mock.scripts["Бесконечная часть"] = [("remember", {"fact": f"погода, источник {i}"}) for i in range(30)]
mock.scripts["Части с бюджетом"] = [
    ("spawn_parts", {"parts": [{"title": "Бесконечная часть", "goal": "Собери всё о погоде", "output": "outputs/погода.md: таблица",
                                "sources": "поиск задачи", "limits": "не больше 3 источников"}]}),
    ("wait_parts", {"minutes": 1}),
    ("finish", {"summary": "Часть не успела."})]
t = tm.create("Части с бюджетом", "Погода — частями", search_url=mock.url.rsplit("/v1", 1)[0] + "/search")
ok(wait_for(lambda: t.status in ("done", "failed") and not t.thread.is_alive(), 60), f"задача закончилась ({t.status} {t.error})")
kid = next((c for c in tm.tasks.values() if c.data.get("parent") == t.id), None)
ok(kid is not None and kid.data.get("search_url") == t.data.get("search_url") and kid.data.get("brief", {}).get("output") == "outputs/погода.md: таблица",
   "часть получила тот же поиск задачи и поручение")
ok(kid is not None and kid.data.get("limits", {}).get("steps") == 4 and kid.status == "failed" and "бюджет" in (kid.error or ""),
   f"бюджет шагов части: итог с тем, что есть ({kid and kid.status}, {kid and kid.error})")
ok(kid is not None and kid.steps <= 4 + 3 + 1, f"часть не ушла дальше бюджета ({kid and kid.steps} шагов)")
ksys = [r for r in mock.of("Бесконечная часть")][0]["system"]
ok("Формат результата: outputs/погода.md: таблица" in ksys and "Границы: не больше 3 источников" in ksys and "Источники: поиск задачи" in ksys,
   "поручение части — по форме: цель, формат, источники, границы")
wr = tool_results(mock.of("Части с бюджетом")[2])
ok(wr and "Бесконечная часть" in wr[-1] and "бюджет" in wr[-1], f"главная задача знает, почему часть не доделала: {wr[-1][:200] if wr else ''}")
hp = [h for h in tm.helpers(t) if h["kind"] == "part"]
ok(hp and hp[0]["limit"] == 4 and hp[0]["what"] == "outputs/погода.md: таблица", f"часть — в «Помощниках» студии: {hp[:1]}")
tm.delete(t.id)
ok(kid.id not in tm.tasks and not kid.dir.exists(), "удалили задачу — её части ушли вместе с ней")
TK.PART_STEPS = 60
tg = tm.create("Главная с файлом", "Дашборд outputs/дашборд.html и справки", start=False)
real_start = tm.start
tm.start = lambda tid, wake="": tm.tasks[tid]                      # части не запускаем — нужны только их критерии
tm._spawn_parts(tg, [{"title": "Справка Юг", "goal": "Справка по Югу", "output": "outputs/юг.md — итог"}])
tm.start = real_start
kc = next(c for c in tm.tasks.values() if c.data.get("parent") == tg.id)
ok([c["target"] for c in tm._auto_criteria(kc)] == ["outputs/юг.md"], f"критерии части — только её файл, не файл основной задачи: {tm._auto_criteria(kc)}")
old_kid = tm.create("Старая часть", "Сделай раздел outputs/раздел.md\n\n(Это часть большой задачи «Х»: отчёт outputs/отчёт.md\nСделай только эту часть.)",
                    start=False, parent=tg.id)
ok([c["target"] for c in tm._auto_criteria(old_kid)] == ["outputs/раздел.md"], "часть 0.85 без поручения — так же")
tm.delete(tg.id)

# ---------- 5. маленькое окно (8 тыс., лёгкий режим): длинный документ читает разведчик, окно не превышено ----------
small = Mock({}, window=8192)
small.side_fn = side
hs = Host(small)
tms = TK.TaskManager(hs)
doc_lines = [f"Строка {i}: обычный текст договора про поставку и оплату, пункт {i}." for i in range(1, 1500)]
doc_lines[1200] = "Строка 1201: штраф за просрочку — 0,5 % в день."
reads = [("file_read", {"path": "downloads/договор.txt", "start": s_}) for s_ in (1, 300, 600, 900, 1190)]
small.scripts["@explore"] = reads + [("report", {"summary": "Штраф за просрочку — 0,5 % в день (downloads/договор.txt:1201).",
                                                 "refs": ["downloads/договор.txt:1201 — штраф"]})]
small.scripts["Договор"] = [("explore", {"question": "Какой штраф за просрочку?", "paths": ["downloads/договор.txt"]}),
                            ("write_file", {"path": "outputs/штраф.md", "content": "Штраф — 0,5 % в день."}),
                            ("show", {"path": "outputs/штраф.md"}),
                            ("finish", {"summary": "Штраф — 0,5 % в день, outputs/штраф.md."})]
t = tms.create("Договор", "Найди в договоре штраф за просрочку; ответ — outputs/штраф.md", start=False)
(t.dir / "downloads").mkdir()
(t.dir / "downloads" / "договор.txt").write_text("\n".join(doc_lines), encoding="utf-8")
tms.start(t.id)
ok(wait_for(lambda: t.status in ("done", "failed", "paused", "stopped"), 60), f"задача закончилась ({t.status} {t.error})")
ok(t.status == "done" and t.data.get("light"), f"окно 8 тыс. — лёгкий режим, задача готова ({t.status})")
ok(not small.over, f"ни один запрос (и разведчика) не больше окна: {small.over}")
mt = sorted(x["function"]["name"] for x in small.of("Договор")[0]["tools"])
ok("explore" in mt and "verify" not in mt and "spawn_parts" not in mt, "в лёгком режиме разведчик есть, частей и проверяющего нет")
ok(len(small.of("@explore")) <= 6, f"в лёгком режиме — не больше 6 шагов разведчика ({len(small.of('@explore'))})")
out = next((c for c in tool_results(small.of("Договор")[1]) if isinstance(c, str) and c.startswith("РАЗВЕДКА")), "")
ok("0,5 % в день" in out and "договор.txt:1201 — штраф\n" in out, f"выжимка со ссылкой на строку: {out[:200]}")
ok(max(r["size"] for r in small.of("@explore")) < 8192, "запросы разведчика укладываются в окно")
ok("РАЗВЕДЧИК." in small.of("Договор")[0]["system"], "в лёгком режиме — короткая подсказка про разведчика")

# ---------- 6. студия: «Помощники» в карточке задачи (части, разведчик, проверяющий), во всех темах ----------
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
    print("⚠ playwright нет — проверка студии пропущена")
if sync_playwright:
    import re
    from task_mock import ROOT
    te = tm.get("Разведка")
    d = tm.detail(te.id)
    d["helpers"] = [{"id": "p1", "kind": "part", "task": "kid1", "title": "Брест", "what": "outputs/брест.md: таблица цен, у каждой цифры ссылка",
                     "status": "running", "status_ru": "выполняется", "activity": "читаю страницу", "steps": 12, "limit": 60, "tokens": 48200, "at": "2"},
                    {"id": "v2", "kind": "verify", "title": "Проверяющий", "what": "outputs/отчёт.md", "status": "done", "status_ru": "готово",
                     "verdict": "revise", "note": "строка 112: итог 4200 ₽, а по статьям 4300 ₽", "steps": 4, "tokens": 6200, "at": "1"}] + d["helpers"]
    d["budget_pct"] = 54                               # выпуск 7: бюджет задачи — в шапке карточки
    kid = dict(d, id="kid1", title="Брест", parent=te.id, helpers=[])
    CORE = """(() => { const ready = () => { if (!window.core) return setTimeout(ready, 5);
        core.retry = () => {}; core.connect = () => {}; if (core.ws) { core.ws.onclose = null; core.ws.onerror = null; try { core.ws.close(); } catch (e) {} }
        window.TASK = TASK_JSON; window.KID = KID_JSON; window.CALLS = [];
        core.call = async (c, a) => { window.CALLS.push([c, a]); if (c === "task_get") return a.id === "kid1" ? window.KID : window.TASK;
          if (c === "tasks_list") return [window.TASK, window.KID]; return null; };
        setTimeout(() => core.emit("hello", {}), 200); };
      ready(); })();""".replace("TASK_JSON", json.dumps(d, ensure_ascii=False)).replace("KID_JSON", json.dumps(kid, ensure_ascii=False))
    with sync_playwright() as p:
        b = p.chromium.launch()
        for skin in ("", "neusky", "neudusk"):
            errs = []
            pg = b.new_page(viewport={"width": 1300, "height": 900})
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route(re.compile(r"^https?://"), lambda r_: r_.abort())
            pg.add_init_script("window.pywebview = { api: new Proxy({}, { get: () => () => Promise.resolve(true) }) };")
            pg.add_init_script(CORE)
            pg.goto((ROOT / "ui/settings.html").as_uri() + "?port=1" + (f"&skin={skin}" if skin else ""))
            pg.wait_for_timeout(1500)
            pg.evaluate("document.querySelector('nav button[data-p=\"tasks\"]').click()")
            pg.wait_for_timeout(300)
            pg.evaluate("openTask('%s')" % te.id)
            pg.wait_for_timeout(400)
            pg.click('#t-view [data-tab="plan"]')
            pg.wait_for_timeout(400)
            txt = pg.inner_text("#t-view")
            ok(pg.locator("#t-view .hlp").count() == len(d["helpers"]) and "ПОМОЩНИКИ" in txt.upper() and "Разведчик" in txt
               and "вернул на доработку" in txt and "шагов 12 из 60" in txt, f"студия ({skin or 'по умолчанию'}): помощники в карточке задачи")
            ok(pg.locator("#t-view .fhead .tbud.half").inner_text() == "бюджет 54 %", "бюджет задачи — в шапке карточки (половина — янтарным)")
            if os.environ.get("DEWIAR_SHOTS"):
                pg.locator("#t-view").screenshot(path=os.environ["DEWIAR_SHOTS"] + f"/task-helpers-{skin or 'default'}.png")
            if not skin:
                pg.evaluate("S = S || {}; S.ui = S.ui || {}; S.llm = S.llm || { profiles: {} }; S.tasks = S.tasks || {}; loadTasks()")
                pg.wait_for_timeout(300)
                ok("часть задачи" in pg.evaluate("document.querySelector('#t-list').textContent"), "в списке задач часть помечена")
                pg.click('#t-view [data-hopen="kid1"]')
                pg.wait_for_timeout(400)
                ok(pg.evaluate("window.CALLS.some(c => c[0] === 'task_get' && c[1].id === 'kid1')") and pg.inner_text("#t-view .fhead b") == "Брест",
                   "«Открыть» у части — её карточка")
                pg.set_viewport_size({"width": 860, "height": 900})
                pg.evaluate("openTask('%s')" % te.id)
                pg.wait_for_timeout(400)
                ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "узкое окно — без горизонтальной прокрутки")
                if os.environ.get("DEWIAR_SHOTS"):
                    pg.locator("#t-view").screenshot(path=os.environ["DEWIAR_SHOTS"] + "/task-helpers-narrow.png")
            ok(not errs, f"без ошибок на странице ({skin or 'по умолчанию'}): {errs[:2]}")
            pg.close()
        b.close()

host.stopping.set()
hs.stopping.set()
done()
