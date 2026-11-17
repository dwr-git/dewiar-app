"""Владелец 14.11 (снимок блокнота): «Лира напомнила о заметке… я сказал удалить… теперь в вкладках текстового редактора
несколько версий вкладки „Главное (правка с «HONOR CLK-LX1…»“ без возможности их удалить».
1) Обе стороны держали свою ЗАПЕРТУЮ вкладку «Главное» с разным текстом: каждая считала пришедшую правкой мимо замка,
   клала её рядом копией и отправляла свою снова — копии множились при каждом обмене. Теперь пришла тоже запертая — это
   их последняя правка: обычный обмен, без копии. Та же правка мимо замка второй раз — вторую копию не делаем.
2) Имя копии было длиннее 60 знаков (имя вкладки блокнота) — по обрезанному имени файла не было, «Удалить» молча ничего
   не делало. Теперь копия короче («… (копия с HONOR CLK-LX1, 14.11 08-15)»), а вкладку с длинным именем блокнот находит
   по точному имени — открывается и удаляется."""
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


import workspace as W  # noqa: E402


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


ws = W.Workspace(FakeS()); ws.ensure()
import sync as SY  # noqa: E402
sy = SY.Sync.__new__(SY.Sync)
sy.host, sy.state, sy.status = types.SimpleNamespace(workspace=ws, emit=lambda *a, **k: None), {"map": {}}, {}
sy._dev_name = lambda d: "HONOR CLK-LX1 очень длинное имя телефона"
root = sy._notes_root()
mine = "---\nlocked: true\n---\n\n# Главное\n\nComms — скриншоты\n"
(root / "Главное.md").write_text(mine, encoding="utf-8")
sy.state["map"]["g"] = "Главное.md"
theirs_locked = "---\nlocked: true\n---\n\n# Главное\n\nComms — скриншоты\nУроки универ\n"
sy._apply_note("g", {"title": "Главное", "folder": "", "text": theirs_locked}, False, upd=int(time.time() * 1000))
copies = [x.name for x in root.glob("Главное (*.md")]
ok(not copies and "Уроки универ" in (root / "Главное.md").read_text(encoding="utf-8"),
   f"пришла тоже запертая с другим текстом — их правка принята, копии нет: {copies}")
for i in range(3):                                         # 1.0.26: правка со своего устройства без замка (открыли там и поправили)
    sy._apply_note("g", {"title": "Главное", "folder": "", "text": "# Главное\n\nпоправил на работе\n"}, False, upd=int(time.time() * 1000) + i)
copies = [x.name for x in root.glob("Главное (*.md")]
ok(not copies and "поправил на работе" in (root / "Главное.md").read_text(encoding="utf-8"),
   f"1.0.26: правка со своего устройства принята и у запертой, копий нет (владелец 17.11): {copies}")

import pad as PD  # noqa: E402
pad = PD.Pad(ws, FakeS())
pad.new("Главное")
long = "Главное (правка с «HONOR CLK-LX1» — заметка заперта, 14.11 08-15)"
(pad.root() / f"{long}.md").write_text("старая копия\n", encoding="utf-8")
ok(long in [t["name"] for t in pad.tabs()["tabs"]], "старая копия с длинным именем — во вкладках")
ok("старая копия" in pad.read(long).get("text", ""), "открывается")
pad.delete(long)
ok(not (pad.root() / f"{long}.md").exists() and long not in [t["name"] for t in pad.tabs()["tabs"]], "и удаляется (раньше «Удалить» молча ничего не делало)")
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("noteLockSet(d0.text" not in js and "${base} (копия с другого устройства)" not in js, "телефон: та же логика — копий у запертой больше не делает")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
