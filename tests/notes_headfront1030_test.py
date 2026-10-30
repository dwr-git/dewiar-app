"""№425 (30.10, пользователь: «заметки из Google Keep — после первого импорта всё прекрасно показывало, а сейчас киперовские
метки пропали и цвета тоже; перенести заново неудобно — я уже вносил изменения»). До 0.69 заметка, вернувшаяся с
телефона, получала «# Название» ПЕРЕД шапкой «---» — шапка переставала быть шапкой. Теперь такие файлы читаются как
надо (метки, цвет, без шапки в тексте) и при первом показе списка чинятся: шапка — наверх, правки человека целы,
место в списке (время) — прежнее."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from workspace import front_first, note_front, note_front_set  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


BAD = ("# Заметка 72\n\n---\nsource: Google Keep\nid: 2026-02-18T10_47_55.224+04_00\ntags: [Борьба за выживание]\n"
       "status: цвет: GREEN\n---\n\n# Заметка 72\n\nhttps://example.org\nмоя правка\n")
meta, body = note_front(BAD)
ok(meta.get("tags") == ["Борьба за выживание"] and meta.get("color") == "GREEN", f"заголовок перед шапкой — метки и цвет на месте: {meta}")
ok("source:" not in body and "моя правка" in body and body.count("# Заметка 72") == 1, "шапки в тексте нет, правка цела, заголовок один")
two = front_first("# Косяки (2)\n\n---\nsource: Google Keep\nid: Косяки\n---\n\n# Косяки\n\nПрочитал")
ok(two.startswith("---\n") and "# Косяки (2)" not in two and "# Косяки\n\nПрочитал" in two, "после шапки свой заголовок — наружный не повторяется")
ok(front_first("# Просто заметка\n\nтекст --- и всё\n") == "# Просто заметка\n\nтекст --- и всё\n", "обычная заметка — как была")
ok(front_first("# Заголовок\n\n---\n\nразделитель, не шапка\n") == "# Заголовок\n\n---\n\nразделитель, не шапка\n", "«---» как разделитель — не трогаем")
ok(note_front_set(BAD, {"color": "BLUE"}).startswith("---\n") and "color: BLUE" in note_front_set(BAD, {"color": "BLUE"})
   and note_front_set(BAD, {"color": "BLUE"}).count("source: Google Keep") == 1, "покрасили такую заметку — одна шапка, сверху")

# починка на диске при показе списка
tmp = Path(tempfile.mkdtemp())
os.environ["DEWIAR_WORKSPACE_DIR"] = str(tmp)
from workspace import Workspace  # noqa: E402


class S:
    def get(self, *k, default=None):
        return str(tmp) if k == ("workspace", "path") else default


ws = Workspace(S())
d = Path(ws.safe("Заметки")) / "Google Keep"
d.mkdir(parents=True)
f = d / "Заметка 72.md"
f.write_text(BAD, encoding="utf-8")
os.utime(f, (1_700_000_000, 1_700_000_000))
n = next(x for x in ws.notes() if x["title"] == "Заметка 72")
ok(n["tags"] == ["Борьба за выживание"] and n["color"] == "GREEN" and "source" not in n["snippet"], f"в списке — метки и цвет Keep: {n['tags']}, {n['color']}")
fixed = f.read_text(encoding="utf-8")
ok(fixed.startswith("---\nsource: Google Keep") and "моя правка" in fixed and int(f.stat().st_mtime) == 1_700_000_000,
   "файл починен: шапка наверху, правка цела, время прежнее")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
