"""Отчёт №395 (29.10, Linux): диск заполнился — Python не мог создать даже временный файл («No usable temporary directory»),
звук падал, настройки не сохранялись («No space left on device»), а человек видел только «Микрофон недоступен —
переподключаюсь…». Теперь: такие ошибки узнаются, в виджете — «Диск заполнен (свободно N МБ)… освободите 1 ГБ», а фоновая
проверка раз в 10 минут предупреждает заранее (не чаще раза в 6 ч)."""
import os, sys, types
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


import engine_base as EB  # noqa: E402
ok(EB.disk_full(FileNotFoundError(2, "No usable temporary directory found in ['/tmp', '/var/tmp']")), "«нет временной папки» — это заполненный диск")
ok(EB.disk_full(OSError(28, "No space left on device")) and not EB.disk_full(OSError(2, "No such file")), "ENOSPC — да, «нет файла» — нет")
ok("Диск заполнен" in EB.disk_full_note() and "МБ" in EB.disk_full_note(), f"понятные слова: {EB.disk_full_note()!r}")
import engine_brain as BR  # noqa: E402
notes, pushes = [], []
me = types.SimpleNamespace(note=notes.append, push=lambda *a, **k: pushes.append(a))
os.environ["DEWIAR_DISK_MIN_MB"] = str(10 ** 12)                      # «места мало» при любом диске
ok(BR.BrainMixin._disk_check(me) and len(notes) == 1 and pushes and "диск заполнен" in pushes[0][0], "мало места — сказали в виджете и уведомлением")
BR.BrainMixin._disk_check(me)
ok(len(notes) == 1, "повторно — не раньше чем через 6 часов")
os.environ["DEWIAR_DISK_MIN_MB"] = "0"
ok(BR.BrainMixin._disk_check(types.SimpleNamespace()) is False, "места хватает — молчим")
au = (ROOT / "core/engine_audio.py").read_text(encoding="utf-8")
ok("elif last_err and disk_full(last_err):" in au and "self.note(disk_full_note())" in au, "звук: при заполненном диске — не «микрофон недоступен», а про диск")
ok("self._disk_check()" in (ROOT / "core/engine_brain.py").read_text(encoding="utf-8"), "фоновая проверка раз в 10 минут")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
