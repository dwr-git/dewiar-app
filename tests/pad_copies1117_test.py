"""Владелец 17.11, 21:49 (снимок блокнота): «замучился с вкладками редактора: на работе и дома одни и те же вкладки, поправил на
работе, а дома вместо поправленной вижу старую и поправленную по отдельности… поудаляю, наведу порядок — открываю, опять».
Вкладки у него заперты (🔒). С 05.11 запертая не принимала правку со своих же устройств и клала её рядом копией
«(копия с другого устройства)» / «(копия с …, дата)»; удалённая копия возвращалась следующим обменом. Теперь правка со своего
устройства — обычная (новее побеждает) и у запертой; копии, совпавшие со своей вкладкой слово в слово, убираются сами,
копии с другим текстом — остаются. Настоящие core/sync.py (sync_apply), workspace, pad."""
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
events = []
sy = SY.Sync.__new__(SY.Sync)
sy.host, sy.state, sy.status = types.SimpleNamespace(workspace=ws, emit=lambda ev, **k: events.append((ev, k))), {"map": {}}, {}
sy._dev_name = lambda d: "Рабочий"
root = sy._notes_root()
pad = root / "Блокнот"
pad.mkdir(parents=True, exist_ok=True)
LOCK = "---\nlocked: true\n---\n\n"
(pad / "Лира - правки.md").write_text(LOCK + "План: лендинг, харнесс\n", encoding="utf-8")
sy.state["map"]["t1"] = "Блокнот/Лира - правки.md"

# 1) на работе открыли замок, поправили и заперли — дома запертая вкладка принимает правку, копии нет
now = int(time.time() * 1000)
sy._apply_note("t1", {"title": "Лира - правки", "folder": "Блокнот", "text": "План: лендинг, харнесс, оплата\n"}, False, upd=now)
cur = (pad / "Лира - правки.md").read_text(encoding="utf-8")
ok("оплата" in cur and not list(pad.glob("Лира - правки (*.md")), f"правка с работы (замок там открыли) — дома принята, без копии: {sorted(x.name for x in pad.iterdir())}")
sy._apply_note("t1", {"title": "Лира - правки", "folder": "Блокнот", "text": LOCK + "План: лендинг, харнесс, оплата, первая минута\n"}, False, upd=now + 5)
cur = (pad / "Лира - правки.md").read_text(encoding="utf-8")
ok("первая минута" in cur and W._locked(pad / "Лира - правки.md") and not list(pad.glob("Лира - правки (*.md")),
   "и заперли там снова — дома новая версия, запертая, копий нет")

# 2) копии, что уже лежат: совпавшие со своей вкладкой — прочь, с другим текстом — остаются
(pad / "Главное.md").write_text(LOCK + "# Главное\n\nКупить карту\n", encoding="utf-8")
(pad / "Главное (копия с другого устройства).md").write_text("Купить карту\n", encoding="utf-8")
(pad / "Главное (копия с HONOR CLK-LX1, 14.11 08-15).md").write_text("# Главное\n\nКупить   карту\n", encoding="utf-8")
(pad / "Главное (копия с другого устройства) 2.md").write_text("Купить карту\nи ещё важное\n", encoding="utf-8")
(pad / "Лира - правки (копия с другого устройства).md").write_text("План: лендинг, харнесс, оплата, первая минута\n", encoding="utf-8")
(root / "Работа").mkdir(exist_ok=True)
(root / "Работа" / "Отчёт.md").write_text("# Отчёт\n\nИтоги квартала\n", encoding="utf-8")
(root / "Работа" / "Отчёт (конфликт с «Дом», 17.11 10-15).md").write_text("# Отчёт\n\nИтоги квартала\n", encoding="utf-8")
(pad / "Идея (с работы).md").write_text("Купить карту\n", encoding="utf-8")       # не копия — просто скобки в имени
events.clear()
n = sy._copies_tidy()
left = sorted(x.name for x in pad.iterdir())
ok(n == 4 and left == ["Главное (копия с другого устройства) 2.md", "Главное.md", "Идея (с работы).md", "Лира - правки.md"],
   f"убраны 4 копии, совпавшие со своей вкладкой (и с заголовком, и с лишними пробелами), с другим текстом — осталась: {n} {left}")
ok(not (root / "Работа" / "Отчёт (конфликт с «Дом», 17.11 10-15).md").exists() and (root / "Работа" / "Отчёт.md").exists(),
   "и такая же копия конфликта в обычных заметках")
ok(("pad_changed", {"name": "Главное (копия с другого устройства)", "deleted": True}) in events, "открытый блокнот узнаёт, что вкладка ушла")
ok(sy._copies_tidy() == 0, "второй раз убирать нечего")
src = (ROOT / "core/sync.py").read_text(encoding="utf-8")
ok("self._copies_tidy()" in src and src.index("self._copies_tidy()") < src.index("snap = self.snapshot()"),
   "уборка — до снимка обмена: удаление уходит на другие устройства тем же обменом")
js = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
ok("${base} (копия с другого устройства)" not in js, "телефон копий у запертой больше не делает")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
