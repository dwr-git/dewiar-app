"""№516 и №517 (пакет 04.11, компьютер 0.80.0, Xubuntu): «попросил Лиру сделать краткое описание статьи из заметки, где
есть ссылка — статью прочла, саммари создала, но не смогла сохранить результат в мою же заметку» и «заметка сохранилась,
ошибка в выводе: Лира писала, что сохранить не смогла». Журнал задачи: save_note(append) дописал в «Заметки/5 Things
World-Class Engineers Do That You Don't.md», а проверка итога читала имя как «t.md» (апостроф обрывал имя), трижды
отклонила итог и остановила задачу «не выполнено». Теперь: update_note — дописать в существующую заметку по пути или
названию, с однозначным ответом; save_note(append) ищет заметку так же; проверка итога понимает апострофы; read_file в
задаче читает и заметки из папки ассистента; сценарий экзамена «краткое описание — в ту же заметку»."""
import datetime as dt, json, os, sys, tempfile, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
tmp = Path(tempfile.mkdtemp())
os.environ.update(DEWIAR_CONFIG_DIR=str(tmp / "cfg"), DEWIAR_STATE_DIR=str(tmp / "st"), DEWIAR_WORKSPACE=str(tmp / "ws"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import workspace, tools  # noqa: E402,E401
ws = workspace.Workspace(None)
root = ws.ensure()
NAME = "5 Things World-Class Engineers Do That You Don't"
note = root / "Заметки" / f"{NAME}.md"
note.write_text(f"---\ntags: [dev]\n---\n# {NAME}\n\n*4 ноября 2026, 10:30*\n\nhttps://example.com/article\n", encoding="utf-8")
(root / "Заметки" / "Ремонт.md").write_text("# Ремонт\n\nОбои.\n", encoding="utf-8")
(root / "Заметки" / "Ремонт кухни.md").write_text("# Ремонт кухни\n\nПлитка.\n", encoding="utf-8")
(root / "Заметки" / "Ремонт ванной.md").write_text("# Ремонт ванной\n\nТрубы.\n", encoding="utf-8")
rel = f"Заметки/{NAME}.md"

# 1) найти заметку: по пути из find_notes, по названию с другим апострофом и регистром, по части названия
ok(ws.find_note(rel) == rel, "по пути из find_notes")
ok(ws.find_note("5 things world-class engineers do that you don’t") == rel, "по названию — с «’» вместо «'» и в другом регистре")
ok(ws.find_note(f"«{NAME}.md»") == rel, "в кавычках и с .md")
ok(ws.find_note("World-Class Engineers") == rel, "по части названия — единственная подходящая")
ok(ws.find_note("Ремонт") == "Заметки/Ремонт.md", "точное название важнее похожих («Ремонт», а не «Ремонт кухни»)")
for bad, why in (("Отпуск в Сочи", "не нашла"), ("Ремонт к", "несколько"), ("obsidian:Статьи/x.md", "Obsidian")):
    try:
        ws.find_note(bad); r = "нашла"
    except workspace.WorkspaceError as e:
        r = str(e)
    ok(why in r, f"«{bad}» — понятный отказ: {r[:70]}")

# рецензия 0.82: по части названия — только «Заметки»: «Память», дневник, «Лаборатория» не задеваем; несколько похожих — не выбираем
(root / "Память").mkdir(exist_ok=True)
(root / "Память" / "Отпуск в Сочи — планы.md").write_text("# Память\n", encoding="utf-8")
(root / "Лаборатория").mkdir(exist_ok=True)
(root / "Лаборатория" / "Сочи заметка.md").write_text("x\n", encoding="utf-8")
try:
    ws.find_note("Отпуск в Сочи"); r = "нашла"
except workspace.WorkspaceError as e:
    r = str(e)
ok("не нашла" in r, f"часть названия вне «Заметок» («Память/Отпуск в Сочи — планы») не подходит: {r[:60]}")
out = tools.t_save_note({"title": "Отпуск в Сочи", "text": "Билеты", "append": True}, {"workspace": ws})
ok(out.startswith("Такой заметки не было — создал новую") and "Билеты" not in (root / "Память" / "Отпуск в Сочи — планы.md").read_text(encoding="utf-8"),
   "save_note(append) не дописывает в «Память» по похожему названию")
ok(ws.find_note("Память/Отпуск в Сочи — планы.md") == "Память/Отпуск в Сочи — планы.md", "точный путь — как прежде, из любой папки")
out = tools.t_save_note({"title": "Ремонт к", "text": "Плинтус", "append": True}, {"workspace": ws})
ok(out.startswith("Подходящих заметок несколько — создал новую") and "Плинтус" not in (root / "Заметки" / "Ремонт кухни.md").read_text(encoding="utf-8"),
   f"несколько похожих — не выбираем наугад, новая и так и сказано: {out[:60]}")
# заметка в cp1251 — не портим: отказ с понятным текстом, файл байт в байт прежний
cp = root / "Заметки" / "Старая.md"
cp.write_bytes("# Старая\n\nПокупки: хлеб, молоко.\n".encode("cp1251"))
before = cp.read_bytes()
try:
    tools.t_update_note({"note": "Старая", "text": "яйца"}, {"workspace": ws}); r = "записала"
except tools.ToolError as e:
    r = str(e)
ok("UTF-8" in r and cp.read_bytes() == before, f"заметка cp1251 — отказ, файл не испорчен: {r[:70]}")
try:
    tools.t_save_note({"title": "Старая", "text": "яйца", "append": True}, {"workspace": ws}); r = "записала"
except tools.ToolError as e:
    r = str(e)
ok("UTF-8" in r and cp.read_bytes() == before, f"save_note(append) в cp1251 — тоже честный отказ, а не тихая новая заметка: {r[:60]}")

# 2) update_note: дописать в конец и «наверх, под заголовок»; прежний текст на месте
out = tools.t_update_note({"note": rel, "text": "## Краткий итог\n1. Ежемесячный замер роста\n5. Провалы — в инфраструктуру"}, {"workspace": ws})
txt = note.read_text(encoding="utf-8")
ok(out.startswith("Готово, сохранено") and f"«{NAME}»" in out and "Повторно не вызывай" in out, f"ответ однозначный: {out[:80]}")
ok("https://example.com/article" in txt and txt.rstrip().endswith("5. Провалы — в инфраструктуру") and txt.count("# " + NAME) == 1,
   "итог — в конце той же заметки, ссылка и заголовок на месте")
ok(not (root / "Заметки" / f"{NAME} (2).md").exists(), "второй заметки не появилось")
tools.t_update_note({"note": NAME, "text": "**Кратко:** пять привычек сильных инженеров.", "where": "top"}, {"workspace": ws})
txt = note.read_text(encoding="utf-8")
ok(txt.startswith("---\ntags: [dev]\n---\n") and txt.index(f"# {NAME}") < txt.index("**Кратко:**") < txt.index("https://example.com"),
   "where=top — сразу под заголовком, метки сверху остаются")
try:
    tools.t_update_note({"note": "Нет такой", "text": "x"}, {"workspace": ws}); r = "записала"
except tools.ToolError as e:
    r = str(e)
ok("не нашла" in r and "find_notes" in r, f"нет заметки — ошибка с подсказкой, а не новая заметка: {r[:60]}")

# 3) save_note(append) — тот же поиск; не нашлась — так и говорит
out = tools.t_save_note({"title": NAME.replace("'", "’"), "text": "Ещё строка", "append": True}, {"workspace": ws})
ok(out.startswith("Готово, сохранено") and "Ещё строка" in note.read_text(encoding="utf-8")
   and not any(p.name.startswith(NAME[:20]) and p != note for p in (root / "Заметки").iterdir()), "save_note(append) с «’» — дописал в ту же")
out = tools.t_save_note({"title": "Новая мысль", "text": "текст", "append": True}, {"workspace": ws})
ok(out.startswith("Такой заметки не было — создал новую") and (root / "Заметки" / "Новая мысль.md").exists(), "дописать некуда — честно: создал новую")
ok(tools.t_save_note({"title": "Покупки", "text": "молоко"}, {"workspace": ws}).startswith("Записал в папку Dewiar: Заметки/Покупки.md"), "обычная новая заметка — как раньше")

# 4) инструмент виден модели: в списке, в «только безопасном», в главных; просьба «добавь в ту же заметку» — не отбрасывается
ok("update_note" in tools.TOOLS and tools.TOOLS["update_note"][2] == "safe" and "update_note" in tools.SAFE_CORE, "update_note — безопасный инструмент")
import engine_answer, engine_tools  # noqa: E402,E401
ok("update_note" in engine_answer.CORE_TOOLS, "update_note — среди главных (и у модели с маленьким окном)")
ok(engine_tools.UPDATE_ASK_RX.search("подведи итог и добавь его в заметку, из которой начала") and
   engine_tools.NOTE_ASK_RX.search("сделай краткое описание и сохрани в ту же заметку"), "просьба дописать в заметку узнаётся")

# 5) задача: итог с «Don't.md» — не «t.md»; read_file читает заметку из папки ассистента
import tasks  # noqa: E402
tm = tasks.TaskManager.__new__(tasks.TaskManager)
tm.host = types.SimpleNamespace(workspace=ws)
tdir = root / "Задачи" / "2026-11-04 1034 Статья"
(tdir / "outputs").mkdir(parents=True, exist_ok=True)
t = tasks.Task(tdir, {"created": dt.datetime.now().isoformat(timespec="seconds"), "title": "Статья"})
summary = (f"Задача выполнена. Дописала краткий итог в заметку `Заметки/{NAME}.md`: пять привычек. "
           f"Также итог — в {NAME}.md.")
miss = tm._promised_missing(t, summary)
ok(miss == [], f"итог с апострофом в имени заметки — файл найден (было «t.md»): {miss}")
# рецензия 0.82: имя в кавычках — «сохранён в файл 'report.md'» — кавычка не часть имени
(tdir / "outputs" / "report.md").write_text("# Отчёт\n", encoding="utf-8")
for sm in ("Отчёт сохранён в файл 'report.md'.", "Отчёт сохранён в файл ’report.md’.", 'Сохранила в "report.md".', "Готово: «report.md»."):
    miss = tm._promised_missing(t, sm)
    ok(miss == [], f"{sm!r} — файл найден, кавычки по краям не мешают: {miss}")
miss = tm._promised_missing(t, "Сохранено в 'нет такого.md'")
ok(len(miss) == 1 and miss[0].endswith("такого.md") and "'" not in miss[0], f"несуществующий файл в кавычках ловится, имя без кавычек: {miss}")
miss = tm._promised_missing(t, "Сохранила отчёт в outputs/итог продаж.md")
ok(len(miss) == 1 and miss[0].endswith("продаж.md"), f"несуществующий файл по-прежнему ловится: {miss}")
r = tm._work(t, "read_file", {"path": rel})
ok("Краткий итог" in r and "Кратко:" in r, "read_file в задаче: путь из find_notes читается из папки ассистента")
ok(tm._work(t, "read_file", {"path": "Заметки/нет такой.md"}).startswith("Такого файла нет"), "нет и там — как раньше")

# 6) экзамен: краткое описание из заметки — в ту же заметку
sc = {s["id"]: s for s in json.loads((ROOT / "data/exam/scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
s = sc.get("note_summary_same") or {}
ok(s.get("seed", {}).get("notes") and s.get("state", {}).get("note") and "update_note" in s.get("judge", ""),
   "сценарий экзамена «краткое описание из заметки — в ту же заметку»")
print("ИТОГ:", "OK" if not fails else f"{len(fails)} ошибок")
sys.exit(1 if fails else 0)
