"""Obsidian: подключение хранилища — заметки ассистента в папке «Dewiar» хранилища, правки с обеих сторон,
удаления — в корзину, конфликт — обе версии; поиск по всему хранилищу; чтение «obsidian:…» только внутри хранилища;
найденные на компьютере хранилища Obsidian."""
import json, os, sys, tempfile, time
from pathlib import Path
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_CONFIG_DIR"] = str(tmp / "cfg")
os.environ["DEWIAR_STATE_DIR"] = str(tmp / "st")
os.environ["XDG_CONFIG_HOME"] = str(tmp / "xdg")
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp / "ws")
os.environ.pop("DEWIAR_WORKSPACE", None)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
ok = lambda c, m: print(("✅ " if c else "❌ ") + m)
from settings import Settings  # noqa: E402
from workspace import Workspace, WorkspaceError  # noqa: E402
from obsidian import Obsidian, ObsidianError, detect  # noqa: E402
from recall import Recall  # noqa: E402

s = Settings(tmp / "cfg" / "settings.json")
ws = Workspace(s)
root = ws.ensure()
vault = tmp / "Мои заметки"
(vault / ".obsidian").mkdir(parents=True)
(vault / "Путешествия").mkdir()
(vault / "Путешествия" / "Отпуск 2026.md").write_text("# Отпуск\n\nЛетим в Тбилиси 12 июля, отель Рустави, бронь 4471.\n", encoding="utf-8")
(vault / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")
(tmp / "xdg/obsidian").mkdir(parents=True)
(tmp / "xdg/obsidian/obsidian.json").write_text(json.dumps({"vaults": {"a1": {"path": str(vault), "ts": 1, "open": True}}}))
ok([v["name"] for v in detect()] == ["Мои заметки"], "хранилища Obsidian на компьютере находятся сами")

ws.save_note("Пароль от вайфая", "кот123")
ws.diary("поговорили о поездке")
ob = Obsidian(s, ws, tmp / "st")
ws.vault_fn = ob.vault
try:
    ob.connect(str(root)); bad_root = False
except ObsidianError:
    bad_root = True
ok(bad_root, "папку самого ассистента хранилищем не сделать")
pub = ob.connect(str(vault))
mir = vault / "DEWIAR"
ok(pub["connected"] and pub["name"] == "Мои заметки" and (mir / "Заметки/Пароль от вайфая.md").is_file()
   and any((mir / "Дневник").glob("*.md")) and (mir / "Память/Обо мне.md").is_file(), "подключили — заметки, дневник и «Обо мне» в заметной папке DEWIAR хранилища")
ok(pub["open"] == "obsidian://open?vault=%D0%9C%D0%BE%D0%B8%20%D0%B7%D0%B0%D0%BC%D0%B5%D1%82%D0%BA%D0%B8", "кнопка «Открыть в Obsidian» — ссылка obsidian://")

time.sleep(0.05)
(mir / "Заметки/Пароль от вайфая.md").write_text("# Пароль от вайфая\n\nкот456 (сменил)\n", encoding="utf-8")
(mir / "Заметки/Идеи.md").write_text("# Идеи\n\n- сад на крыше\n", encoding="utf-8")
st = ob.sync()
ok("кот456" in (root / "Заметки/Пароль от вайфая.md").read_text(encoding="utf-8") and (root / "Заметки/Идеи.md").is_file()
   and st["from_vault"] == 2, "правка и новая заметка в Obsidian — у ассистента")

ws.list_add("Список покупок", ["молоко"])
st = ob.sync()
ok((mir / "Заметки/Список покупок.md").is_file() and st["to_vault"] == 1, "ассистент записал — видно в Obsidian")

(root / "Заметки/Идеи.md").write_text("# Идеи\n\n- сад на крыше\n- теплица\n", encoding="utf-8")
time.sleep(0.05)
(mir / "Заметки/Идеи.md").write_text("# Идеи\n\n- сад на крыше\n- пруд\n", encoding="utf-8")
st = ob.sync()
both = [p.name for p in (root / "Заметки").glob("Идеи*.md")]
ok(st["conflicts"] == 1 and "пруд" in (root / "Заметки/Идеи.md").read_text(encoding="utf-8") and len(both) == 2
   and (mir / "Заметки/Идеи (от ассистента).md").is_file(), "правили с обеих сторон — свежее на месте, вторая версия рядом")

(mir / "Заметки/Список покупок.md").unlink()
st = ob.sync()
ok(not (root / "Заметки/Список покупок.md").exists() and (root / ".Корзина/Заметки/Список покупок.md").is_file(),
   "удалили в Obsidian — у ассистента файл в корзине, не пропал")
(root / "Заметки/Пароль от вайфая.md").unlink()
st = ob.sync()
ok(not (mir / "Заметки/Пароль от вайфая.md").exists() and (vault / ".trash/DEWIAR/Заметки/Пароль от вайфая.md").is_file(),
   "удалили у ассистента — в корзине Obsidian (.trash)")
# отчёт №408 (29.10): хранилище в сетевой папке, один файл без прав — раньше вся сверка падала каждые 20 с
import logging  # noqa: E402
import obsidian as OB  # noqa: E402
_real = OB._hash
(mir / "Заметки/Закрыто.md").write_text("x", encoding="utf-8"); (mir / "Заметки/Открыто.md").write_text("y", encoding="utf-8")
def _deny(p):
    if Path(p).name == "Закрыто.md":
        raise PermissionError(13, "Permission denied", str(p))
    return _real(p)
OB._hash = _deny
_warns = []
_h = logging.Handler(); _h.emit = lambda r: _warns.append(r.getMessage()); logging.getLogger("dewiar.obsidian").addHandler(_h)
st1 = ob.sync(); st2 = ob.sync()
ok(st1.get("skipped") == 1 and st2.get("skipped") == 1 and (root / "Заметки/Открыто.md").is_file() and "нет доступа" in ob.last["error"]
   and sum("Закрыто" in w for w in _warns) == 1, f"файл без прав — пропущен, остальное сверено, в журнале один раз: {st1} {_warns}")
OB._hash = _real; logging.getLogger("dewiar.obsidian").removeHandler(_h)
for _p in (mir / "Заметки/Закрыто.md", mir / "Заметки/Открыто.md", root / "Заметки/Открыто.md", root / "Заметки/Закрыто.md"):
    _p.unlink(missing_ok=True)
ob.sync()
ok(json.loads((vault / ".obsidian/workspace.json").read_text()) == {} and (vault / "Путешествия/Отпуск 2026.md").read_text(encoding="utf-8").startswith("# Отпуск"),
   "свои заметки пользователя и настройки Obsidian не тронуты")

rc = Recall(lambda: ws.root, ob.search_root)
hits = rc.search("где отель в Тбилиси", limit=5)
ok(hits and hits[0]["path"] == "obsidian:Путешествия/Отпуск 2026.md" and hits[0]["kind"] == "obsidian",
   "поиск находит заметку пользователя в Obsidian")
ok(not any(h["path"].startswith("obsidian:DEWIAR/") for h in rc.search("сад на крыше пруд", limit=10)),
   "папка DEWIAR не ищется дважды")
r = ws.read("obsidian:Путешествия/Отпуск 2026.md")
try:
    ws.read("obsidian:../cfg/settings.json"); esc = False
except WorkspaceError:
    esc = True
ok("Рустави" in r["text"] and esc, "заметку из Obsidian можно прочитать целиком, за пределы хранилища — нельзя")
ob.set({"search": False})
ok(not any(h["kind"] == "obsidian" for h in rc.search("Тбилиси отель", limit=5)), "поиск по хранилищу можно выключить")
pub = ob.forget()
ok(not pub["connected"] and (mir / "Заметки/Идеи.md").is_file(), "отключили — папка DEWIAR в хранилище осталась")

# Хранилище с прежней папкой «Dewiar»: заметка, положенная туда в Obsidian, доходит до ассистента; папка становится
# заметной «DEWIAR»; служебные файлы ассистента в хранилище не выносятся
v2 = tmp / "Хранилище 2"
(v2 / ".obsidian").mkdir(parents=True)
(v2 / ".obsidian/appearance.json").write_text(json.dumps({"cssTheme": "Minimal", "enabledCssSnippets": ["мой"]}), encoding="utf-8")
(v2 / "Dewiar/Память").mkdir(parents=True)
(v2 / "Dewiar/Память/Обо мне.md").write_text((root / "Память/Обо мне.md").read_text(encoding="utf-8"), encoding="utf-8")
(v2 / "Dewiar/Запомнить на будущее.md").write_text("# Запомнить\n\nКривая забывания Эббингауза — эффект сбережения.\n", encoding="utf-8")
(v2 / "Dewiar/Идеи").mkdir()
(v2 / "Dewiar/Идеи/Сад.md").write_text("# Сад\n\nтеплица из поликарбоната\n", encoding="utf-8")
(root / "Память/Уроки задач.md").write_text("# Уроки задач\n\n- служебное\n", encoding="utf-8")
s.update({"obsidian": {"folder": "Dewiar"}})
ob.index_info = lambda: {"name": "Лира", "days": [{"day": "2026-10-03", "label": "3 октября 2026", "title": "День, когда получилось", "mood": "🌿"}]}
st = ob.connect(str(v2))
m2 = v2 / "DEWIAR"
ok(m2.is_dir() and not (v2 / "Dewiar").exists() and ob.public()["folder"] == "DEWIAR", "прежняя папка «Dewiar» стала заметной «DEWIAR»")
ok((root / "Заметки/Запомнить на будущее.md").is_file() and "Эббингауза" in (root / "Заметки/Запомнить на будущее.md").read_text(encoding="utf-8")
   and (root / "Заметки/Идеи/Сад.md").is_file(), "заметка, положенная прямо в DEWIAR (и в свою подпапку), — у ассистента в «Заметках»")
ok((m2 / "Запомнить на будущее.md").is_file() and not (m2 / "Заметки/Запомнить на будущее.md").exists() and not (m2 / "Заметки/Идеи/Сад.md").exists(),
   "в Obsidian заметка остаётся там, куда её положили, — без копии в «Заметках»")
(root / "Заметки/Запомнить на будущее.md").write_text("# Запомнить\n\nЭббингауз + интервальные повторения\n", encoding="utf-8")
ob.sync()
ok("интервальные" in (m2 / "Запомнить на будущее.md").read_text(encoding="utf-8"), "правка у ассистента — в ту же заметку в Obsidian")
ob.state_path.unlink()                                   # состояние потерялось (переименовали папку и т. п.) — без дублей
ob.sync()
ok(not list((root / "Заметки").glob("Запомнить на будущее (*.md")) and not (m2 / "Заметки/Запомнить на будущее.md").exists(), "потеря состояния не плодит копии")
(m2 / "Идеи/Сад.md").unlink()
ob.sync()
ok(not (root / "Заметки/Идеи/Сад.md").exists() and (root / ".Корзина/Заметки/Идеи/Сад.md").is_file() and not (root / "Заметки/Идеи").exists()
   and (root / "Заметки").is_dir(), "удалили в Obsidian — у ассистента в корзину, опустевшая подпапка не остаётся")
(m2 / "Черновики").mkdir(); (m2 / "Черновики/Мысль.md").write_text("мысль", encoding="utf-8"); ob.sync()
(root / "Заметки/Черновики/Мысль.md").unlink(); ob.sync()
ok(not (m2 / "Черновики").exists() and (v2 / ".trash/DEWIAR/Черновики/Мысль.md").is_file(), "удалили у ассистента — в Obsidian в корзину, без пустой папки")
(root / "Заметки/Задачи 2026-10-02 1642 Перевод").mkdir(); (root / "Заметки/Письма").mkdir()
names = [n["name"] for n in ws.tree()["items"] if n["name"] == "Заметки"] and [c["name"] for c in next(n for n in ws.tree()["items"] if n["name"] == "Заметки")["children"]]
ok("Письма" not in names and not any(x.startswith("Задачи 2026") for x in names), f"пустые папки в «Папке» убираются сами: {names}")
rel = ws.save_note("План", "текст", "Задачи/2026-10-02 1642 Перевод")
ok(rel == "Заметки/План.md", f"заметка «в папку задачи» — просто в «Заметки», без пустых папок: {rel}")
ok(ws.save_note("Письмо Олегу", "текст", "Письма") == "Заметки/Письма/Письмо Олегу.md", "своя подпапка заметок — по-прежнему можно")
ok(not (m2 / "Память/Уроки задач.md").exists(), "служебные «Уроки задач» в хранилище не выносятся")
idx = (m2 / "DEWIAR.md").read_text(encoding="utf-8") if (m2 / "DEWIAR.md").exists() else ""
ok("[[DEWIAR/Память/Обо мне|Обо мне]]" in idx and "[[DEWIAR/Запомнить на будущее|Запомнить на будущее]]" in idx
   and "«День, когда получилось» 🌿" in idx and "Лира" in idx, "сверху — «DEWIAR.md»: что знает, дневник, заметки (ссылки ведут куда надо)")
ok(not (root / "Заметки/DEWIAR.md").exists(), "оглавление — только в Obsidian, к ассистенту не возвращается")
ap = json.loads((v2 / ".obsidian/appearance.json").read_text(encoding="utf-8"))
css = (v2 / ".obsidian/snippets/dewiar.css").read_text(encoding="utf-8") if (v2 / ".obsidian/snippets/dewiar.css").exists() else ""
ok(ap.get("enabledCssSnippets") == ["мой", "dewiar"] and ap.get("cssTheme") == "Minimal" and 'data-path="DEWIAR"' in css,
   "в Obsidian папка выделена цветом и ✦ (CSS-фрагмент), остальное оформление не тронуто")
ap["enabledCssSnippets"] = ["мой"]; (v2 / ".obsidian/appearance.json").write_text(json.dumps(ap), encoding="utf-8")
ob.sync()
ok(json.loads((v2 / ".obsidian/appearance.json").read_text(encoding="utf-8"))["enabledCssSnippets"] == ["мой"], "выключили выделение в Obsidian — больше не включаем")
