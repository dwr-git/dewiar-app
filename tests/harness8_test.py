"""HARNESS, выпуск 8 «Как среда Claude» (владелец 12.11: «заложи в Лиру важные вещи и фундаментальные подходы твоего
харнесса — память и контекст, циклы, сабагенты»; docs/HARNESS.md, раздел 4). Проверки по пунктам по мере готовности.

П.2 — сжатие контекста пересказом: модель переписывает блокнот при уходе ранних шагов; строки прежнего блокнота с
числами, кодами, адресами и путями, которых в новом нет, возвращаются (tasks.keep_facts); в пересказе — разделы
«Файлы — что в каждом» и «Ошибки и как обошли», числа — дословно.
П.5 — прочитал, потом правишь: write_file поверх файла, который задача не создавала и не читала (присланный человеком,
его папка), — отказ с подсказкой (file_read → file_edit или новый файл рядом); свои файлы и дописывание — как раньше.
П.7 — ждать события, а не гадать со временем: wait on_file (файл появился или изменился) и on_mail (пришло новое
письмо от кого-то или о чём-то); minutes/until — крайний срок (по умолчанию 3 дня)."""
import os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import tasks  # noqa: E402

old = """# Блокнот
- Номер заказа 4567-123
- Сумма 12 500 руб.
- Почта менеджера ivan@shop.ru
- Страница https://shop.example/order/77
- Файл C:\\\\Users\\\\a\\\\Desktop\\\\отчёт.docx
- Просто мысль без чисел
"""
new = """## Что известно
- Заказ 4567-123 оформлен
## Файлы — что в каждом
- C:\\\\Users\\\\a\\\\Desktop\\\\отчёт.docx — отчёт"""
out = tasks.keep_facts(old, new)
ok(out.startswith(new), "пересказ модели — основа блокнота")
ok("12 500" in out and "ivan@shop.ru" in out and "https://shop.example/order/77" in out, f"потерянные сумма, почта, ссылка — возвращены: {out[len(new):]!r}")
ok(out.count("4567-123") == 1 and out.count("отчёт.docx") == 1, "то, что в пересказе осталось, не дублируется")
ok("Просто мысль" not in out, "строки без фактов не возвращаются (пересказ вправе их сжать)")
ok(tasks.keep_facts("", "x") == "x" and tasks.keep_facts("- 123456", "есть 123456") == "есть 123456", "нечего возвращать — как есть")
src = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
i = src.index("def _consolidate(")
body = src[i:src.index("def _compact(", i)]
ok("Файлы — что в каждом" in body and "Ошибки и как обошли" in body and "дословно" in body, "пересказ по схеме: файлы, ошибки, числа дословно")
ok("t.set_notebook(keep_facts(t.notebook() or \"\", out))" in body, "переписанный блокнот проходит keep_facts")

import tempfile  # noqa: E402


class T:
    def __init__(self, d):
        self.dir, self.data, self.j = d, {}, []

    def journal(self, x):
        self.j.append(x)


td = Path(tempfile.mkdtemp())
t = T(td)
(td / "Входящие").mkdir()
inbox = td / "Входящие" / "договор.txt"
inbox.write_text("текст человека", encoding="utf-8")
B = tasks.TaskManager._blind_overwrite
r = B(t, inbox, {"content": "x"})
ok(r.startswith("Ошибка") and "file_read" in r and "file_edit" in r and t.j, f"чужой файл, не читали — не перезаписываем: {r[:70]}")
ok(B(t, inbox, {"content": "x", "append": True}) == "", "дописывание — можно")
t.data["seen"] = [str(inbox.resolve())]
ok(B(t, inbox, {"content": "x"}) == "", "прочитали — можно")
own = td / "outputs" / "итог.md"
own.parent.mkdir()
own.write_text("моё", encoding="utf-8")
t.data["authored"] = ["outputs/итог.md"]
ok(B(t, own, {"content": "x"}) == "", "свой файл задачи — можно")
ok(B(t, td / "outputs" / "новый.md", {"content": "x"}) == "", "нового файла нет — пишем")
ok('t.data["seen"] = list(dict.fromkeys((t.data.get("seen") or []) + [str(p.resolve())]))' in src
   and "blind = self._blind_overwrite(t, p, args)" in src, "чтение отмечается; write_file проверяет до записи")

import time as _time  # noqa: E402


class Mail:
    def __init__(self):
        self.items, self.calls = [], 0

    def configured(self):
        return True

    def inbox(self, limit=10, unread=False, query=""):
        self.calls += 1
        return [x for x in self.items if query.lower() in (x["from"] + x["subject"]).lower()]


tm = tasks.TaskManager.__new__(tasks.TaskManager)
tm.host = type("H", (), {"mail": Mail()})()
t2 = T(td)
t2.data.update(folders=[])
t2.title, t2.id = "Ждём", "w1"
on = tm._wake_on(t2, {"on_file": "outputs/ответ.csv", "on_mail": "banki.ru"})
ok(isinstance(on, dict) and on.get("file", "").endswith("ответ.csv") and on.get("sig") is None and on.get("mail") == "banki.ru", f"ожидание по событию записано: {on}")
t2.data["wake_on"] = on
ok(tm._event_due(t2) == "", "пока ничего не случилось — спим")
(td / "outputs" / "ответ.csv").write_text("1;2", encoding="utf-8")
ok("появился" in tm._event_due(t2), "файл появился — просыпаемся")
_time.sleep(0.3)
tm.host.mail.calls = 0
on2 = tm._wake_on(t2, {"on_mail": "Сбербанк"})
t2.data["wake_on"] = on2
tm._event_due(t2)
for _ in range(50):
    if not on2.get("mail_busy"):
        break
    _time.sleep(0.05)
ok(tm._event_due(t2) == "" and tm.host.mail.calls == 1, "письма нет — спим; почту не дёргаем чаще раза в 5 минут")
from email.utils import format_datetime  # noqa: E402
import datetime as _dt  # noqa: E402
tm.host.mail.items.append({"from": "Сбербанк <info@sber.ru>", "subject": "Ответ на обращение", "date": format_datetime(_dt.datetime.now().astimezone())})
on2["mail_checked"] = 0
tm._event_due(t2)
for _ in range(50):
    if not on2.get("mail_busy"):
        break
    _time.sleep(0.05)
ok("Сбербанк" in tm._event_due(t2), "новое письмо пришло — просыпаемся с тем, что пришло")
tm.host.mail.configured = lambda: False
ok(isinstance(tm._wake_on(t2, {"on_mail": "x"}), str), "почта не подключена — честно, ждать письма нечем")
ok('elif t.status == "sleeping" and t.data.get("wake_on") and not alive:' in src, "будильник задач проверяет события")

# экзамен 12.11 (Б4, «Скрипт по выпискам»): всё сделано верно, план 4 из 4 — а «не выполнено: повторила одно и то же».
# План выполнен — повтор значит «пора сдавать»: просьба сдать итог через обычные проверки, а не провал
import quality as Q  # noqa: E402
ok("LOOP_DONE" in dir(Q) and "finish" in Q.LOOP_DONE, "есть подсказка «план выполнен — сдавай итог»")
i = src.index('elif loop == "finish":')
blk = src[i:i + 1400]
ok("pd >= pt" in blk and "Q.LOOP_DONE" in blk and blk.index("Q.LOOP_DONE") < blk.index('force_why"] = "loop"'), "при выполненном плане повтор не помечает задачу «не выполнено»")
# экзамен 12.11 (Б11): перезапуск посреди работы — история не успела записаться, и задача «▶ Начал работу» заново
src = (ROOT / "core/tasks.py").read_text(encoding="utf-8")
i = src.index("begun = bool(")
blk = src[i:i + 1200]
ok("if not msgs and begun:" in blk and "продолжаю, где остановился" in blk and "Не начинай заново" in blk,
   "работа уже шла (шаги, план или файлы), а памяти разговора нет — продолжает, а не начинает заново")
# «посмотреть глазами» (владелец 12.11: «ты смотришь скриншоты результата — было бы здорово, если бы и Лира так умела»)
import llm  # noqa: E402
pg_dir = Path(tempfile.mkdtemp())
(pg_dir / "outputs").mkdir()
page = pg_dir / "outputs" / "index.html"
page.write_text("<!doctype html><html><body style='margin:0'><h1 style='color:#fff;background:#fff'>Кофейня</h1><p>Lorem ipsum</p></body></html>", encoding="utf-8")
hc = Q.html_check([page], roots=[pg_dir])
if hc is None:
    print("⚠ браузера нет — «посмотреть глазами» не проверяю")
else:
    ok(len(hc[str(page)].get("shot") or "") > 1000, "html_check делает снимок страницы (экран телефона)")
    seen = []

    def fake_chat(prof, system, msgs, cancel=None, **k):
        seen.append(msgs)
        yield '{"verdict":"revise","problems":"заголовок белым по белому — не виден; на экране «Lorem ipsum»"}'
    llm.stream_chat, keep = fake_chat, llm.stream_chat
    tmL = tasks.TaskManager.__new__(tasks.TaskManager)
    tmL.host = type("H", (), {"llm_profile": lambda self: {"base_url": "http://m", "model": "v", "kind": "openai"}, "_blind": set(),
                              "s": type("S", (), {"get": lambda self, *a: None})()})()
    tmL._opt = lambda k: None
    tl = T(pg_dir)
    tl.goal, tl.id, tl.cancel = "Сайт кофейни", "l1", None
    qd = {"verify_fail": 0}
    r = tmL._eyes(tl, hc, qd)
    ok(r and r.startswith("ПОСМОТРЕЛА НА СТРАНИЦУ") and "белым по белому" in r and qd["verify_fail"] == 1, f"модель со зрением увидела проблему — задача правит: {(r or '')[:90]}")
    c = seen[0][0]["content"]
    ok(isinstance(c, list) and any(x.get("type") == "image_url" for x in c), "модели ушёл снимок, а не только текст")
    ok(tmL._eyes(tl, hc, qd) is None, "смотрим один раз на задачу")

    def blind_chat(*a, **k):
        raise llm.LLMError("model does not support image input")
        yield ""
    llm.stream_chat = blind_chat
    tl2 = T(pg_dir)
    tl2.goal, tl2.id, tl2.cancel = "Сайт", "l2", None
    ok(tmL._eyes(tl2, hc, {"verify_fail": 0}) is None and "http://m|v" in tmL.host._blind, "модель не видит картинок — без шума, запомнили")
    llm.stream_chat = keep
ok("look = self._eyes(t, hc, q)" in src, "просмотр — в проверке перед «готово», после ошибок браузера")

# п.10: отчёт в конце — итог, файл, один следующий шаг; без пересказа шагов
fin = tasks.TASK_TOOLS["finish"][0]
ok("один следующий шаг" in fin and "Шаги не пересказывай" in fin and "путём" in fin, "finish: итог, файл путём, один следующий шаг, без пересказа шагов")

# «что с задачами?» — одной фразой
it = [{"title": "Отчёт по ценам", "status": "running", "progress": [3, 5]}, {"title": "Сайт кофейни", "status": "waiting"},
      {"title": "Письма", "status": "done", "updated": tasks._now()}, {"title": "Старое", "status": "done", "updated": "2026-01-01T10:00:00"},
      {"title": "Погода", "status": "sleeping"}]
b = tasks.tasks_brief(it)
ok(b == "Коротко: в работе «Отчёт по ценам» — 3 из 5 по плану; ждёт вашего ответа «Сайт кофейни»; на паузе или ждёт события "
   "«Погода»; сегодня готово 1 («Письма»).", f"сводка задач одной фразой: {b}")
ok(tasks.tasks_brief([]) == "" and "tasks_brief(items)" in (Path(tasks.__file__).parent / "tools.py").read_text(encoding="utf-8"),
   "нет задач — без сводки; task_status начинает со сводки")

if fails:
    print(f"\n❌ провалов: {len(fails)}")
    sys.exit(1)
print("\n✅ всё в порядке")
