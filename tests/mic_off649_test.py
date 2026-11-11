"""№649 (ПК 0.84.2, 11.11, Windows 10): «забывает, что микрофон выключен, при перезагрузке компьютера». Выключенный
кнопкой микрофон (или сочетанием «Позвать Лиру» в режиме вкл/выкл) не запоминался — после перезапуска Dewiar снова
слушал. Теперь выбор кнопки хранится в настройках (ui.mic_off), ядро поднимается с ним; включили кнопкой или вышли из
текстового режима — снова слушает и после перезапуска. Отдых и замок «Только кнопка» — своими путями, их не трогаем."""
import os, sys, tempfile
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
tmp = Path(tempfile.mkdtemp())
os.environ["HOME"] = str(tmp)
os.environ.setdefault("DEWIAR_HOME", str(tmp / "dw"))
sys.path.insert(0, str(ROOT / "core"))
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


from settings import Settings, DEFAULTS  # noqa: E402
import engine_commands as EC  # noqa: E402

ok(DEFAULTS["ui"].get("mic_off") is False, "по умолчанию микрофон включён (ui.mic_off = false)")


class Fake(EC.CommandsMixin):
    def __init__(self, s):
        self.s, self.muted, self.state, self.events = s, False, "idle", []
        self.follow_up_until = 0.0

    def set_state(self, st):
        self.state = st

    def emit(self, kind, **kw):
        self.events.append(kind)

    def cancel_turn(self):
        pass


path = tmp / "settings.json"
f = Fake(Settings(path))
ok(f._mute_keep(f.set_mute(True)) is True, "кнопка: микрофон выключен")
ok(Settings(path).get("ui", "mic_off") is True, "выбор сохранён на диск — после перезапуска тоже выключен")
ok(f._mute_keep(f.set_mute(False)) is False and Settings(path).get("ui", "mic_off") is False, "включили — после перезапуска слушает")
f.set_mute(True)                                    # отдых и другие пути — без _mute_keep: не запоминаются
ok(Settings(path).get("ui", "mic_off") is False, "выключение не кнопкой (отдых) — не запоминается")

src = (ROOT / "core/engine_commands.py").read_text(encoding="utf-8")
ok('return self._mute_keep(self.set_mute(bool(a.get("on"))))' in src, "команда mute (кнопка виджета) запоминает выбор")
ok("return self._mute_keep(self.set_mute(not self.muted))" in src, "mute_toggle (сочетание клавиш) запоминает выбор")
ok("self._mute_keep(self.set_mute(False))" in src, "вышли из текстового режима — микрофон включён и после перезапуска")
eng = (ROOT / "core/engine.py").read_text(encoding="utf-8")
ok('or bool(settings.get("ui", "mic_off")))' in eng, "ядро поднимается с выключенным микрофоном, если так выбрали")
print("\nИТОГ:", "всё прошло" if not fails else f"провалов {len(fails)}")
sys.exit(1 if fails else 0)
