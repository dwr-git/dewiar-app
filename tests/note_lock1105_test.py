"""Замок на заметке и вкладке блокнота (владелец, 05.11: «в заметках и блокноте иногда информация настолько важная, что
переживаю — не сотру ли случайно. Добавить замочек, который не даст случайно изменить или удалить»).
Компьютер: запертую нельзя изменить, переименовать, дополнить, удалить (и папкой целиком) — ни из студии, ни Лирой
(save_note, update_note, списки, черновики, delete_files); Лира говорит «заметка заперта — сначала откройте замок»;
открыть замок — только руками (note_meta из студии, pad_lock из блокнота), у модели такого инструмента нет.
Блокнот: замок в шапке файла, лист её не показывает и не теряет. Синхронизация и Obsidian: правка с другого устройства
не перетирает запертую молча — ложится рядом копией; пришло «то же, но без замка» — замок открыли там, принимаем."""
import os, sys, tempfile, time, types
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


def raises(fn, word="заперта"):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        return word in str(e)
    return False


import workspace as W  # noqa: E402
import tools as TL  # noqa: E402


class FakeS:
    def __init__(self):
        self.d = {}

    def get(self, *k, default=None):
        if k == ("workspace", "path"):
            return str(tmp / "ws")
        v = self.d
        for x in k:
            v = (v or {}).get(x)
        return default if v is None else v

    def update(self, patch):
        for k, v in patch.items():
            self.d.setdefault(k, {}).update(v)


ws = W.Workspace(FakeS())
ws.ensure()
rel = ws.save_note("Пароли от Wi-Fi", "Дом: секрет-123\nДача: другое-456")
p = ws.safe(rel)
ok(W.LOCKED_MSG == "заметка заперта — сначала откройте замок", "фраза для человека и Лиры — та, что просил владелец")

# 1) запереть (руками — из студии) и что теперь нельзя
n = ws.note_meta(rel, {"locked": True})
ok(n and n["locked"] and W._locked(p), "студия → 🔒: заметка заперта (locked: true в шапке)")
before = p.read_text(encoding="utf-8")
ok(raises(lambda: ws.write(rel, "стёрто")), "студия: правка запертой — нельзя")
ok(raises(lambda: ws.rename(rel, "Другое")), "переименовать — нельзя")
ok(raises(lambda: ws.remove(rel)), "удалить — нельзя")
ok(raises(lambda: ws.update_note("Пароли от Wi-Fi", "ещё строка")), "Лира: update_note — нельзя")
ok(raises(lambda: ws.save_note("Пароли от Wi-Fi", "дописать", append=True)), "Лира: save_note с дописыванием — нельзя")
ok(raises(lambda: ws.note_attach(rel, "фото.png", b"\x89PNG")), "фото к запертой — нельзя")
sub = ws.save_note("Код от сейфа", "1234", folder="Важное")
ws.note_meta(sub, {"locked": True})
ok(raises(lambda: ws.remove_dir("Заметки/Важное"), "запертые"), "папку с запертой заметкой целиком — нельзя (массовое удаление)")
ok(p.read_text(encoding="utf-8") == before, "текст запертой заметки не изменился")
new = ws.save_note("Пароли от Wi-Fi", "новая")
ok(new != rel and ws.safe(new).is_file(), "новая заметка с тем же названием — можно (рядом, «(2)»), запертая цела")
lst = ws.list_add("Список покупок", ["хлеб"])[0]
ws.note_meta(lst, {"locked": True})
ok(raises(lambda: ws.list_add("Список покупок", ["молоко"])), "список заперт — «добавь молоко» не дописывает")

# 2) Лира: инструменты говорят понятно
ctx = {"workspace": ws}
try:
    TL.t_update_note({"note": "Пароли от Wi-Fi", "text": "x"}, ctx)
    ok(False, "update_note запертой должен отказать")
except TL.ToolError as e:
    ok("заметка заперта — сначала откройте замок" in str(e) and "только человек" in str(e), f"update_note: {str(e)[:90]}")
try:
    TL.t_save_note({"title": "Пароли от Wi-Fi", "text": "x", "append": True}, ctx)
    ok(False, "save_note(append) запертой должен отказать")
except TL.ToolError as e:
    ok("заперта" in str(e), "save_note с дописыванием: отказ с той же фразой")
import guard  # noqa: E402
guard.WORKSPACE[:] = [str(tmp / "ws")] if hasattr(guard, "WORKSPACE") and isinstance(guard.WORKSPACE, list) else getattr(guard, "WORKSPACE", [])
try:
    TL.t_delete_files({"paths": [str(p)]}, ctx)
    ok(False, "delete_files запертой должен отказать")
except TL.ToolError as e:
    ok("заперта" in str(e), f"delete_files: запертую — нет ({str(e)[:70]})")
ok(p.is_file(), "заметка на месте после попытки удалить")
names = set(TL.TOOLS)
ok(not any(k in names for k in ("note_unlock", "unlock_note", "note_meta")), "открыть замок модели нечем — только руками")

# быстрые пути без модели: «запиши в книгу: …» в запертую, «добавь в список» — честный ответ
import engine as E  # noqa: E402
eng = E.Engine.__new__(E.Engine)
eng.workspace, said = ws, []
eng._say_quick = lambda msg, text, via=None, **k: said.append(msg)
book = ws.save_note("Книга", "Глава 1", folder="Черновики")
ws.note_meta(book, {"locked": True})
ok(eng._draft_cmd("Лира, запиши в книгу: герой проснулся рано утром") and said and "заперта" in said[-1], f"черновик заперт: {said[-1:]}")
eng.emit = lambda *a, **k: None
ok(eng._capture({"op": "list", "name": "Список покупок", "items": ["молоко"]}, "добавь молоко в список покупок") and "заперта" in said[-1],
   f"список заперт: {said[-1:]}")

# 3) открыть — руками — и снова можно
ws.note_meta(rel, {"locked": False})
ok(not W._locked(p), "студия → 🔓: замок открыт")
ws.write(rel, before.replace("секрет-123", "новый-789"))
ok("новый-789" in p.read_text(encoding="utf-8"), "после открытия — правка проходит")

# 4) блокнот
import pad as PD  # noqa: E402
pad = PD.Pad(ws, FakeS())
pad.new("Важное")
pad.write("Важное", "Пароль от роутера: admin-42\n")
r = pad.lock("Важное", True)
ok(r["locked"] and next(t for t in pad.tabs()["tabs"] if t["name"] == "Важное")["locked"], "блокнот → 🔒: вкладка заперта, видно в списке вкладок")
rd = pad.read("Важное")
ok(rd["locked"] and not rd["text"].startswith("---") and "admin-42" in rd["text"], "лист не показывает шапку замка, текст на месте")
ok(raises(lambda: pad.write("Важное", "стёрто")) and raises(lambda: pad.rename("Важное", "Другое"))
   and raises(lambda: pad.delete("Важное")) and raises(lambda: pad.attach("Важное", "a.png", "iVBORw0KGgo=")),
   "запертую вкладку не изменить, не переименовать, не удалить, картинку не добавить")
ok(raises(lambda: ws.write("Заметки/Блокнот/Важное.md", "стёрто")), "и через «Заметки» студии — тоже нельзя (это та же заметка)")
pad.lock("Важное", False)
pt = pad._path("Важное")
ws.note_meta(pt.relative_to(ws.ensure()).as_posix(), {"color": "TEAL"})      # шапка с цветом (из студии)
pad.write("Важное", "Пароль от роутера: admin-43\n")
raw = pt.read_text(encoding="utf-8")
ok(raw.startswith("---") and "color: TEAL" in raw and "admin-43" in raw and "locked" not in raw, "открыли — правка проходит, шапку (цвет) лист не теряет")
cmd = (ROOT / "core" / "engine_commands.py").read_text(encoding="utf-8")
ok('cmd == "pad_lock"' in cmd, "команда pad_lock — кнопка 🔒 блокнота")

# 5) синхронизация: правка запертой с другого устройства — рядом копией, замок — полем заметки
import sync as SY  # noqa: E402
events = []
host = types.SimpleNamespace(workspace=ws, emit=lambda *a, **k: events.append(a))
sy = SY.Sync.__new__(SY.Sync)
sy.host, sy.state, sy.status = host, {"map": {}}, {}
root = sy._notes_root()
locked_text = "---\nlocked: true\n---\n\n# Сейф\n\nкод 1111\n"
(root / "Сейф.md").write_text(locked_text, encoding="utf-8")
sy.state["map"]["s1"] = "Сейф.md"
sy._apply_note("s1", {"title": "Сейф", "folder": "", "text": "# Сейф\n\nкод 0000 — стёр случайно\n"}, False, upd=int(time.time() * 1000))
ok((root / "Сейф.md").read_text(encoding="utf-8") == locked_text, "правка с другого устройства не перетёрла запертую")
alt = [x for x in root.glob("Сейф (копия с*.md")]
ok(alt and "0000" in alt[0].read_text(encoding="utf-8") and not W._locked(alt[0]), f"их правка — рядом копией без замка: {[x.name for x in alt]}")
ok("note:s1" in getattr(sy, "_note_resend", set()), "запертая уйдёт туда следующим обменом — и вернёт замок")
sy._apply_note("s1", {}, True)
ok((root / "Сейф.md").is_file(), "удаление с другого устройства — запертую не удаляем")
sy._apply_note("s1", {"title": "Сейф", "folder": "", "text": "# Сейф\n\nкод 1111\n"}, False, upd=int(time.time() * 1000) + 5000)
ok(not W._locked(root / "Сейф.md") and "1111" in (root / "Сейф.md").read_text(encoding="utf-8"), "пришло то же без замка (открыли там руками) — замок открыт и здесь")
sy._apply_note("s1", {"title": "Сейф", "folder": "", "text": locked_text}, False, upd=int(time.time() * 1000) + 9000)
ok(W._locked(root / "Сейф.md"), "заперли на другом устройстве — заперта и здесь")
sy._apply_note("s1", {"title": "Сейф", "folder": "Другая", "text": locked_text}, False, upd=int(time.time() * 1000) + 12000)
ok((root / "Сейф.md").is_file(), "перенос запертой в другую папку с другого устройства — не принимаем")

# 6) Obsidian: правка запертой в хранилище — рядом, удаление — возвращаем
import obsidian as OB  # noqa: E402
a, b = tmp / "a.md", tmp / "b.md"
a.write_text(locked_text, encoding="utf-8")
b.write_text("# Сейф\n\nкод 2222\n", encoding="utf-8")
ok(OB._locked_note(a) and not OB._lock_only(a, b), "Obsidian: запертая и её правка — разные")
b.write_text("# Сейф\n\nкод 1111\n", encoding="utf-8")
ok(OB._lock_only(a, b), "Obsidian: отличаются только замком — это открытие замка")
src = (ROOT / "core" / "obsidian.py").read_text(encoding="utf-8")
ok("правка из Obsidian — заметка заперта" in src and "удалили в Obsidian запертую" in src, "Obsidian: правку — рядом, удаление — назад")

# 7) интерфейсы: значок и отказ
notes_js = (ROOT / "ui" / "studio" / "notes.js").read_text(encoding="utf-8")
ok('id="nt-lockh"' in notes_js and "ntLockedNudge" in notes_js and "if (lkd) return ntLockedNudge()" in notes_js,
   "студия: 🔒 у названия, «Изменить» запертой — подсказка открыть замок")
pad_js = (ROOT / "ui" / "pad.js").read_text(encoding="utf-8")
ok('core.call("pad_lock"' in pad_js and 'ED.contentEditable = P.locked ? "false" : "true"' in pad_js and 'id="b-lock"' in (ROOT / "ui" / "pad.html").read_text(encoding="utf-8"),
   "блокнот: 🔒 на панели, запертый лист не правится")
print("ALL OK" if not fails else f"FAILED: {len(fails)}")
sys.exit(1 if fails else 0)
