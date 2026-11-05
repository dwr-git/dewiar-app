"""Выпуск 3 «Больших задач» (docs/HARNESS.md): проверка по существу перед «готово». Рецензия 0.84 (сценарии A–I и части):
опору нельзя сделать самой (чтение своих outputs/, запись в _src/, печать своего отчёта скриптом), тривиальный критерий не
снимает файл из цели, команда и ссылка критерия не обходят защиту, ложных возвратов нет (переполненная опора, длинный адрес,
задача 0.83 без опоры, итоги частей), даты, время, версии и пункты — не «цифры без опоры», HTML без сети и без зависаний.
— критерии готовности (set_criteria -> критерии.json) проверяет код: «3 страницы», а их две — итог возвращается;
— ссылка в итоге или отчёте, которой задача не открывала и не видела, — возврат («ссылки без источника»);
— цифра отчёта, которой нет ни в файле с данными, ни в прочитанном, — возврат (один раз);
— проверяющий с чистым контекстом видит выдержки файлов и прочитанных страниц; ответил непонятно — не «ок»: решают
  машинные проверки; настроен tasks.judge_llm — проверяет другая модель;
— верный итог проходит с первого раза: один finish, один вызов проверяющего;
— HTML с ошибкой скрипта — возврат (браузер, если есть Playwright и Chromium).
Модель — заглушка со сценарием (task_mock), «интернет» — локальный: поиск задачи (search_url) и страницы на 127.0.0.1."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ["DEWIAR_TASK_BROWSER"] = "0"
from task_mock import Host, Mock, done, ok, wait_for  # noqa: E402
import tasks as TK  # noqa: E402

PAGES = {"/teplo.html": ("Тепловой насос для дома", "Установка теплового насоса воздух-вода в доме 120 м²: от 650 000 до 900 000 рублей. "
                                                    "COP при −7 °C — от 3,2 до 4."),
         "/minus.html": ("Минусы теплового насоса", "Шум наружного блока 45–55 дБ, при морозе ниже −20 нужен резервный котёл.")}


class PH(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        HITS.append(self.path)
        p = PAGES.get(self.path.split("?")[0]) or ("Страница", "Текст страницы про насосы и отопление.")
        b = f"<html><head><title>{p[0]}</title></head><body><main><h1>{p[0]}</h1><p>{p[1]}</p><p>{'Подробности о монтаже и обслуживании. ' * 12}</p></main></body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)


HITS = []
web = ThreadingHTTPServer(("127.0.0.1", 0), PH)
threading.Thread(target=web.serve_forever, daemon=True).start()
WEB = f"http://127.0.0.1:{web.server_port}"
mock = Mock({})


def search(h):
    return h._json(200, {"results": [{"title": t, "url": WEB + u, "content": x[:80]} for u, (t, x) in PAGES.items()]})


mock.search = search
VERDICT = {}                       # название задачи -> ответ проверяющего (по умолчанию — ok)
SEEN = {}                          # название задачи -> что видел проверяющий


def side(sysm, body):
    if not sysm.startswith("Ты — строгий"):
        return None
    user = body["messages"][-1]["content"]
    title = user.split("ЗАДАЧА:\n", 1)[-1].split("\n", 1)[0]
    SEEN.setdefault(title, []).append(user)
    return VERDICT.get(title, '{"verdict": "ok"}')


mock.side_fn = side
host = Host(mock)
SURL = mock.url.rsplit("/v1", 1)[0]
tm = TK.TaskManager(host)


def last_user(req):
    """Последнее сообщение задаче перед этим запросом (без «Состояния задачи» в конце)."""
    for m in reversed(req["messages"]):
        c = m.get("content")
        if m["role"] in ("user", "tool") and isinstance(c, str) and not c.startswith("[Состояние задачи"):
            return c
    return ""


def run(title, goal, steps, sec=40, **kw):
    mock.scripts[title] = steps
    t = tm.create(title, goal, search_url=SURL, **kw)
    wait_for(lambda: t.status in ("done", "failed", "paused", "stopped"), sec)
    return t


def after(title, i):
    r = [x for x in mock.of(title) if x["i"] == i]
    return last_user(r[0]) if r else ""


def journal(t):
    return (t.dir / "журнал.md").read_text(encoding="utf-8")


# ---------- 1. ссылка-выдумка в отчёте -> возврат ----------
A = "Ссылки"
report = f"# Насос\n\nЦена 650–900 тыс. ₽ ({WEB}/teplo.html), COP 3,2 при −7 °C (https://heat-pumps-fake.ru/cop-2026).\n"
t = run(A, "Исследуй тепловой насос; отчёт — outputs/отчёт.md, ссылка у каждой цифры", [
    ("web_search", {"query": "тепловой насос цена"}),
    ("read_webpage", {"url": WEB + "/teplo.html"}),
    ("write_file", {"path": "outputs/отчёт.md", "content": report}),
    ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md."}),
    ("write_file", {"path": "outputs/отчёт.md", "content": report.replace("https://heat-pumps-fake.ru/cop-2026", WEB + "/teplo.html")}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md."})])
r5 = after(A, 5)
ok("ССЫЛКИ БЕЗ ИСТОЧНИКА" in r5 and "heat-pumps-fake.ru/cop-2026" in r5 and WEB + "/teplo.html" not in r5,
   f"ссылка, которой задача не открывала, — итог возвращён: {r5[:160]}")
ok(t.status == "done" and "🔗" in journal(t), f"ссылку заменили прочитанной — итог принят ({t.status} {t.error})")
seen = "\n".join(SEEN.get(A, []))
ok("ПРОЧИТАННЫЕ ИСТОЧНИКИ" in seen and "650 000 до 900 000" in seen and "ВЫДЕРЖКИ ФАЙЛОВ" in seen and "Цена 650–900" in seen,
   "проверяющий видит выдержки отчёта и прочитанной страницы, а не только имена файлов")
ok(not (t.dir / "_src").exists(), "по готовности опора проверки (_src/) убрана")

# ---------- 2. цифра в отчёте не совпадает с файлом -> возврат ----------
B = "Цифры"
code = ("import csv\nrows=[('Продукты', 30113.25), ('Транспорт', 18100.25)]\n"
        "w=csv.writer(open('outputs/итоги.csv','w',encoding='utf-8',newline=''))\nw.writerow(['категория','сумма'])\n"
        "[w.writerow(r) for r in rows]\nprint('посчитано')")
t = run(B, "Посчитай расходы за год: outputs/итоги.csv и коротко в итоге", [
    ("run_python", {"code": code}),
    ("show", {"path": "outputs/итоги.csv"}),
    ("finish", {"summary": "Готово: outputs/итоги.csv. Продукты — 31 113,25 ₽, транспорт — 18 100,25 ₽."}),
    ("finish", {"summary": "Готово: outputs/итоги.csv. Продукты — 30 113,25 ₽, транспорт — 18 100,25 ₽."})])
r3 = after(B, 3)
ok("ЦИФРЫ БЕЗ ОПОРЫ" in r3 and "31 113,25" in r3 and "18 100,25" not in r3, f"цифра итога, которой нет в файле, — возврат: {r3[:140]}")
ok(t.status == "done" and len(mock.of(B)) == 4, f"цифру исправили — принято ({t.status}, шагов {len(mock.of(B))})")

# ---------- 3. критерий «3 страницы», а их 2 -> возврат ----------
C = "Сайт"
pg = lambda n: ("write_file", {"path": f"outputs/site/{n}.html", "content": f"<!doctype html><html><head><meta name=viewport content='width=device-width'>"  # noqa: E731
                                                                         f"<title>{n}</title></head><body><a href='index.html'>Главная</a> {n}</body></html>"})
t = run(C, "Сайт из трёх страниц в outputs/site/", [
    ("set_criteria", {"items": [{"check": "pages", "target": "outputs/site", "value": "3"},
                                {"check": "contains", "target": "outputs/site/index.html", "value": "Главная"},
                                {"check": "manual", "text": "тёплый стиль"}]}),
    pg("index"), pg("menu"),
    ("show", {"path": "outputs/site/index.html"}),
    ("finish", {"summary": "Сайт готов: outputs/site/."}),
    pg("contacts"),
    ("finish", {"summary": "Сайт готов: outputs/site/."})])
r5 = after(C, 5)
ok("КРИТЕРИИ ГОТОВНОСТИ НЕ ВЫПОЛНЕНЫ" in r5 and "есть 2, нужно 3" in r5, f"«3 страницы», а их две — возврат: {r5[:160]}")
cr = json.loads((t.dir / "критерии.json").read_text(encoding="utf-8"))
ok(t.status == "done" and [r["ok"] for r in cr["results"]] == [True, True, None], f"третья страница — критерии пройдены, «manual» — проверяющему ({t.status}, {[r['ok'] for r in cr['results']]})")
st = [x for x in mock.of(C) if x["i"] == 2][0]["messages"][-1]["content"]
ok("КРИТЕРИИ ГОТОВНОСТИ (код проверит их перед finish)" in st and "страниц в outputs/site: 3" in st, "критерии — в «Состоянии задачи» в конце запроса")
ok("тёплый стиль" in "\n".join(SEEN.get(C, [])), "ручной критерий видит проверяющий")
d = tm.detail(t.id)
ok(len(d["criteria"]) == 3 and d["criteria"][0]["label"].startswith("страниц"), "карточке студии — критерии с итогом проверки")

# ---------- 4. проверяющий отвечает непонятно -> не «ок», решают машинные проверки ----------
D = "Непонятно"
VERDICT[D] = "Ну, в целом вроде нормально, наверное."
t = run(D, "Посчитай итог: outputs/итог.txt", [
    ("run_python", {"code": "open('outputs/итог.txt','w',encoding='utf-8').write('Итого: 1520.40')\nprint('ok')"}),
    ("show", {"path": "outputs/итог.txt"}),
    ("finish", {"summary": "Итого 1 250,40 — в outputs/итог.txt."}),
    ("finish", {"summary": "Итого 1 250,40 — в outputs/итог.txt."}),
    ("finish", {"summary": "Итого 1 520,40 — в outputs/итог.txt."})])
ok("ЦИФРЫ БЕЗ ОПОРЫ" in after(D, 3), "сначала — машинная проверка цифр")
r4 = after(D, 4)
ok("Проверить итог по существу не удалось" in r4 and "1 250,40" in r4, f"проверяющий ответил непонятно — итог НЕ принят: решили машинные проверки: {r4[:120]}")
ok(t.status == "done" and "решили машинные проверки: прошли" in journal(t), f"исправленный итог при непонятном проверяющем принят машинными проверками ({t.status})")
D2 = "Непонятно, но верно"
VERDICT[D2] = "???"
t = run(D2, "Сделай заметку outputs/заметка.md", [("write_file", {"path": "outputs/заметка.md", "content": "# Заметка\n\nВсё по делу.\n"}),
                                                  ("show", {"path": "outputs/заметка.md"}), ("finish", {"summary": "Заметка — outputs/заметка.md."})])
ok(t.status == "done" and len(mock.of(D2)) == 3, "верный итог при непонятном проверяющем — принят с первого раза (машинные проверки прошли)")

# ---------- 5. верный итог — с первого раза: один finish, один вызов проверяющего ----------
E = "Верно"
good = f"# Тепловой насос\n\nУстановка — 650–900 тыс. ₽ ({WEB}/teplo.html); COP 3,2–4 при −7 °C ({WEB}/teplo.html).\nШум 45–55 дБ ({WEB}/minus.html).\n"
steps_e = [
    ("todo_update", {"items": [{"text": "найти источники", "status": "in_progress"}, {"text": "написать отчёт"}]}),
    ("set_criteria", {"items": [{"check": "file", "target": "outputs/отчёт.md"}, {"check": "contains", "target": "outputs/отчёт.md", "value": "COP"}]}),
    ("web_search", {"query": "тепловой насос"}),
    ("read_webpage", {"url": WEB + "/teplo.html"}),
    ("read_webpage", {"url": WEB + "/minus.html"}),
    ("write_file", {"path": "outputs/отчёт.md", "content": good}),
    ("todo_update", {"items": [{"id": 1, "status": "done", "evidence": f"{WEB}/teplo.html"}, {"id": 2, "status": "done", "evidence": "outputs/отчёт.md"}]}),
    ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": f"Отчёт — outputs/отчёт.md: установка 650–900 тыс. ₽, COP 3,2–4 ({WEB}/teplo.html)."})]
t = run(E, "Исследуй тепловой насос; отчёт — outputs/отчёт.md", steps_e)
fin = [x for x in mock.of(E) if x["i"] >= len(steps_e) - 1]
ok(t.status == "done" and len(fin) == 1 and len(SEEN.get(E, [])) == 1, f"верный итог — с первого раза: finish {len(fin)}, проверяющий {len(SEEN.get(E, []))} ({t.status} {t.error})")
ok("🧐 Проверяющий: итог подтверждён" in journal(t), "в журнале — «итог подтверждён»")

# ---------- 6. проверяющий — другая модель (tasks.judge_llm) ----------
judge_mock = Mock({})
J = []


def judge(sysm, body):
    if not sysm.startswith("Ты — строгий"):
        return None
    J.append(body["messages"][-1]["content"])
    return '{"verdict": "revise", "problems": "в заметке нет даты встречи"}' if len(J) == 1 else '{"verdict": "ok"}'


judge_mock.side_fn = judge


class S:
    def get(self, *k):
        if k == ("tasks", "judge_llm"):
            return "judge"
        if k == ("llm", "profiles"):
            return {"judge": {"name": "Сильная", "kind": "openai", "base_url": judge_mock.url, "model": "big"}}
        return {} if k[0] == "tools" else None


host.s = S()
F = "Судья"
t = run(F, "Заметка о встрече: outputs/встреча.md", [("write_file", {"path": "outputs/встреча.md", "content": "# Встреча\n\nОбсудить план.\n"}),
                                                     ("show", {"path": "outputs/встреча.md"}), ("finish", {"summary": "Заметка — outputs/встреча.md."}),
                                                     ("write_file", {"path": "outputs/встреча.md", "content": "# Встреча\n\n12 ноября, обсудить план.\n"}),
                                                     ("finish", {"summary": "Заметка — outputs/встреча.md."})])
ok(J and "встреча.md" in J[0] and not SEEN.get(F), "итог проверила модель из tasks.judge_llm, а не модель задачи")
ok("САМОПРОВЕРКА отклонила итог: в заметке нет даты встречи" in after(F, 3) and t.status == "done", f"её «доработать» вернулось задаче ({t.status})")
del host.s

# ---------- 7. страница с ошибкой скрипта (браузер) ----------
import exam_big  # noqa: E402
if exam_big.browser_ok():
    os.environ["DEWIAR_TASK_BROWSER"] = "1"
    G = "Страница"
    bad = "<!doctype html><html><head><meta name=viewport content='width=device-width'></head><body><h1>Калькулятор</h1><script>calc_missing()</script></body></html>"
    t = run(G, "Калькулятор: outputs/calc.html", [("write_file", {"path": "outputs/calc.html", "content": bad}), ("show", {"path": "outputs/calc.html"}),
                                                  ("finish", {"summary": "Калькулятор — outputs/calc.html."}),
                                                  ("write_file", {"path": "outputs/calc.html", "content": bad.replace("calc_missing()", "1+1")}),
                                                  ("finish", {"summary": "Калькулятор — outputs/calc.html."})], sec=90)
    r3 = after(G, 3)
    ok("СТРАНИЦА С ОШИБКАМИ" in r3 and "calc_missing" in r3, f"ошибка скрипта в браузере — возврат: {r3[:120]}")
    ok(t.status == "done" and "[в браузере] Калькулятор" in "\n".join(SEEN.get(G, [])), f"починили — принято; проверяющий видит страницу, как в браузере ({t.status})")
    os.environ["DEWIAR_TASK_BROWSER"] = "0"
else:
    print("◐ браузера нет (Playwright и Chromium) — проверка страниц в браузере пропущена")
# ---------- 8. рецензия 0.84: опору нельзя сделать самой ----------
FAKE = "https://heat-pumps-fake.ru/cop-2026"
fake = f"# Насос\n\nЦена 650–900 тыс. ₽ ({WEB}/teplo.html). COP 5,7 при −7 °C ({FAKE}). Окупаемость 4,2 года.\n"
ok_rep = f"# Насос\n\nЦена 650–900 тыс. ₽ ({WEB}/teplo.html).\n"
A2 = "A отмыв file_read"
t = run(A2, "Исследуй насос; отчёт outputs/отчёт.md", [
    ("read_webpage", {"url": WEB + "/teplo.html"}), ("write_file", {"path": "outputs/отчёт.md", "content": fake}),
    ("file_read", {"path": "outputs/отчёт.md"}), ("show", {"path": "outputs/отчёт.md"}), ("finish", {"summary": "Отчёт — outputs/отчёт.md"}),
    ("write_file", {"path": "outputs/отчёт.md", "content": ok_rep}), ("finish", {"summary": "Отчёт — outputs/отчёт.md"})])
ok("ССЫЛКИ БЕЗ ИСТОЧНИКА" in after(A2, 5) and FAKE in after(A2, 5) and t.status == "done",
   f"A: чтение своего отчёта (file_read) не делает его ссылки «прочитанными» ({t.status})")
B1_ = "B отмыв _src"
t = run(B1_, "Исследуй насос; отчёт outputs/отчёт.md", [
    ("write_file", {"path": "_src/результаты.txt", "content": f"### read_webpage {{\"url\": \"{FAKE}\"}}\nCOP 5,7\n"}),
    ("write_file", {"path": "outputs/отчёт.md", "content": f"# Насос\n\nCOP 5,7 ({FAKE}).\n"}), ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md"}), ("write_file", {"path": "outputs/отчёт.md", "content": "# Насос\n\nДанных нет.\n"}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md: данных не нашла."})])
ok("служебный файл задачи" in after(B1_, 1) and "ССЫЛКИ БЕЗ ИСТОЧНИКА" in after(B1_, 4), "B: запись в _src/ запрещена, выдуманная ссылка — возврат")
for nm in ("задачи.json", "критерии.json", "блокнот.md"):
    tb = tm.create("B служебные " + nm, "x", start=False)
    ok("служебный файл" in tm._tool_raw(tb, "write_file", {"path": nm, "content": "{}"}), f"B: write_file в {nm} — отказ")
B2_ = "B2 отмыв run_python"
code = f"r={fake!r}\nopen('outputs/отчёт.md','w',encoding='utf-8').write(r)\nprint(r)"
t = run(B2_, "Исследуй насос; отчёт outputs/отчёт.md", [
    ("read_webpage", {"url": WEB + "/teplo.html"}), ("run_python", {"code": code}), ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md"}), ("write_file", {"path": "outputs/отчёт.md", "content": ok_rep}),
    ("finish", {"summary": "Отчёт — outputs/отчёт.md"})])
ok("ССЫЛКИ БЕЗ ИСТОЧНИКА" in after(B2_, 4) and t.status == "done", "B2: скрипт, печатающий свой отчёт, — не источник его ссылок")

# ---------- 9. критерии: служебные отклоняются, файл из цели — всегда ----------
C2 = "C тривиальный критерий"
t = run(C2, "Сделай таблицу outputs/итоги.csv и отчёт outputs/отчёт.md", [
    ("set_criteria", {"items": [{"check": "file", "target": "план.md"}, {"check": "contains", "target": "outputs/отчёт.md", "value": "Отчёт"}]}),
    ("write_file", {"path": "outputs/отчёт.md", "content": "# Отчёт\n\nВсё сделано.\n"}), ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": "Готово: outputs/отчёт.md"}),
    ("write_file", {"path": "outputs/итоги.csv", "content": "a;b\n1;2\n"}), ("finish", {"summary": "Готово: outputs/отчёт.md, outputs/итоги.csv"})])
ok("служебный файл задачи" in after(C2, 1), "C: критерий «план.md есть» отклонён")
ok("outputs/итоги.csv" in after(C2, 4) and "КРИТЕРИИ ГОТОВНОСТИ НЕ ВЫПОЛНЕНЫ" in after(C2, 4) and t.status == "done",
   f"C: свои критерии не снимают файл из цели ({t.status})")

# ---------- 10. команда и ссылка критерия не обходят защиту ----------
import tempfile  # noqa: E402
mark = os.path.join(tempfile.mkdtemp(), "вне-папки.txt")
host.code_auto_run = lambda: False
E2 = "E команда без автозапуска"
t = run(E2, "Посчитай", [("set_criteria", {"items": [{"check": "command", "target": f"echo x > '{mark}'"}]}), ("finish", {"summary": "Готово."})])
cr = json.loads((t.dir / "критерии.json").read_text(encoding="utf-8"))
ok(not os.path.exists(mark) and cr["results"][0]["ok"] is None and "проверит проверяющий" in cr["results"][0]["detail"] and t.status == "done",
   "E: автозапуск выключен — команда критерия не запускается, её проверит проверяющий")
del host.code_auto_run
E3 = "E команда с автозапуском"
t = run(E3, "Посчитай", [("set_criteria", {"items": [{"check": "command", "target": "python3 -c \"print(1)\""}]}), ("finish", {"summary": "Готово."})])
ok("▶ команда критерия: python3" in journal(t) and t.status == "done", "E: команда критерия — в журнале")
HITS.clear()
F2 = "F ссылка во внутреннюю сеть"
t = run(F2, "Проверь", [("set_criteria", {"items": [{"check": "url", "target": WEB + "/admin/reset?all=1"}]}),
                        ("finish", {"summary": "Готово."}), ("set_criteria", {"items": [{"check": "manual", "text": "проверено"}]}),
                        ("finish", {"summary": "Готово."})])
ok(not HITS and "адрес внутренней сети" in after(F2, 2), f"F: критерий-ссылка на 127.0.0.1 не открывается ({HITS})")
ok(TK.TaskManager._url_inner(t, "http://169.254.169.254/latest/meta-data") and TK.TaskManager._url_inner(t, "http://10.0.0.5/")
   and not TK.TaskManager._url_inner(t, SURL + "/a.html"), "F: link-local и частные сети — нельзя; свой поиск задачи — можно")

# ---------- 11. нет ложных возвратов за ссылки ----------
TK.SRC_MAX = 3000
G2 = "G переполненная опора"
t = run(G2, "Отчёт outputs/отчёт.md", [("read_webpage", {"url": WEB + f"/p{i}.html"}) for i in range(5)] + [
    ("write_file", {"path": "outputs/отчёт.md", "content": f"# Отчёт\n\nДанные — {WEB}/p4.html\n"}), ("show", {"path": "outputs/отчёт.md"}),
    ("finish", {"summary": "Готово: outputs/отчёт.md"})])
TK.SRC_MAX = 8 << 20
ok(t.status == "done" and len(mock.of(G2)) == 8, "G: опора переполнена — адрес прочитанной после страницы всё равно виден")
long = WEB + "/doc?token=" + "x" * 700
H2 = "H длинная ссылка"
t = run(H2, "Отчёт outputs/отчёт.md", [("read_webpage", {"url": long}), ("write_file", {"path": "outputs/отчёт.md", "content": f"# Отчёт\n\n{long}\n"}),
                                       ("show", {"path": "outputs/отчёт.md"}), ("finish", {"summary": "Готово: outputs/отчёт.md"})])
ok(t.status == "done" and len(mock.of(H2)) == 4, "H: длинный адрес (700 знаков) — целиком в опоре")
I2 = "I задача 0.83 без опоры"
urls = [WEB + f"/q{i}.html" for i in range(6)]
holder = {}


def wipe(req):
    import shutil
    shutil.rmtree(holder["t"].dir / "_src", ignore_errors=True)
    return ("log", {"text": "обновились до 0.84"})


mock.scripts[I2] = [("read_webpage", {"url": u}) for u in urls] + [
    ("write_file", {"path": "outputs/отчёт.md", "content": "# Отчёт\n\n" + "\n".join(f"- {u}" for u in urls) + "\n"}),
    ("show", {"path": "outputs/отчёт.md"}), wipe, ("finish", {"summary": "Готово: outputs/отчёт.md"})]
holder["t"] = t = tm.create(I2, "Отчёт outputs/отчёт.md", start=False)
tm.start(t.id)
wait_for(lambda: t.status in ("done", "failed", "paused"), 40)
ok(t.status == "done" and len(mock.of(I2)) == 10, f"I: опоры нет (задача 0.83) — она собрана из истории, ложного возврата нет ({t.status})")
P6 = "Сборка частей"
merge = ("import glob\nparts=[open(f,encoding='utf-8').read() for f in sorted(glob.glob('parts/*/*.md'))]\n"
         "open('outputs/отчёт.md','w',encoding='utf-8').write('# Итог\\n\\n'+'\\n'.join(parts))\nprint('собрано частей:', len(parts))")
mock.scripts[P6] = [("run_python", {"code": merge}), ("show", {"path": "outputs/отчёт.md"}), ("finish", {"summary": "Готово: outputs/отчёт.md"})]
t = tm.create(P6, "Собери отчёт из частей в outputs/отчёт.md", start=False)
(t.dir / "parts" / "часть-1").mkdir(parents=True)
(t.dir / "parts" / "часть-1" / "часть.md").write_text("# Часть 1\n\n" + "\n".join(
    f"- Цена {i} — {650 + i * 13} 500 ₽ (https://shop{i}.example.ru/item/{i})" for i in range(12)) + "\n", encoding="utf-8")
tm.start(t.id)
wait_for(lambda: t.status in ("done", "failed", "paused"), 40)
ok(t.status == "done" and len(mock.of(P6)) == 3, f"части: их итоги — опора (ссылки и цены частей не «без источника») ({t.status})")

# ---------- 12. цифры и ссылки: не ложные «без опоры» ----------
import quality as Q  # noqa: E402
ev = 'read_webpage {"url": "https://site.ru/page"} установка от 650 000 до 900 000 ₽, COP 3,4 https://ru.wikipedia.org/wiki/М'
ok(all(not Q.unseen_urls(c, ev) for c in ("См. https://site.ru/page#cop", "https://site.ru/page?utm_source=x", "Источник: https://site.ru/page—там",
                                          "https://ru.wikipedia.org/wiki/%D0%9C")), "ссылка с якорем, utm, тире после и %-кодом — та же ссылка")
pool = Q.number_pool(ev)
fine = ["Выезд 14.11, возврат 21.11.", "Работает с 9.00 до 18.00.", "Нужен Python 3.12 и Node 20.11.", "См. пункт 4.2 и раздел 12.3.",
        "Статья 152 ФЗ, ГОСТ 7.32-2017.", "Итого 1 550 000 ₽ (650 000 + 900 000).", "Установка 650–900 тыс. ₽, COP 3,4."]
ok(all(not Q.unsupported_numbers(c, pool) for c in fine), f"даты, время, версии, пункты, суммы — не «без опоры»: {[Q.unsupported_numbers(c, pool) for c in fine]}")
ok(Q.unsupported_numbers("COP 5,7 и цена 1 234 567 ₽", pool) == ["5,7", "1 234 567"], "выдуманные цифры — без опоры")
ok(Q.parse_verdict('Пример: {"verdict": "ok"}. Мой ответ: {"verdict": "revise", "problems": "нет"}')[0] == "revise"
   and Q.parse_verdict('{"verdict": "revise"}')[0] == "revise" and Q.parse_verdict("ок, всё хорошо")[0] == "unclear",
   "проверяющий: последний объект с verdict; «revise» без подробностей — тоже revise")
if exam_big.browser_ok():
    os.environ["DEWIAR_TASK_BROWSER"] = "1"
    d = TK.Path(tempfile.mkdtemp())
    (d / "font.html").write_text("<!doctype html><html><head><link rel=stylesheet href='http://10.255.255.1/css'></head><body><h1>Привет</h1></body></html>", encoding="utf-8")
    (d / "cdn.html").write_text("<!doctype html><html><head><script src='https://cdn.example.com/chart.js'></script></head><body><h1>x</h1>"
                                "<script>new Chart(1)</script></body></html>", encoding="utf-8")
    import time as _t
    t0 = _t.time()
    hc = Q.html_check([str(d / "font.html"), str(d / "cdn.html")])
    ok(_t.time() - t0 < 15 and not hc[str(d / "font.html")]["errors"] and hc[str(d / "cdn.html")]["soft"]
       and "10.255.255.1" in hc[str(d / "font.html")]["external"][0],
       f"HTML: сеть страницам не даётся — шрифт не вешает проверку, ошибка из-за CDN — замечание, а не брак ({_t.time() - t0:.1f} с)")
    os.environ["DEWIAR_TASK_BROWSER"] = "0"
host.stopping.set()
done()
