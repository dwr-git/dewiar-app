"""Одна клавиша — «Закинуть идею» (окно capture.html): сочетание клавиш на всю систему.

Linux (GNOME, Ubuntu): своё сочетание в настройках клавиатуры GNOME — «custom keybinding» с командой «dewiar --capture»
(запущенный интерфейс получает сигнал-файл и открывает окно). Это настройка самого GNOME: работает и на Wayland, и без
нашего окна в фокусе, а снять её можно и там (Настройки → Клавиатура → Свои сочетания). Свою запись узнаём по пути
…/custom-keybindings/dewiar-capture/ и трогаем только её. Другие рабочие столы — сочетание назначают сами (команду
показывает студия). Windows — RegisterHotKey окна значка в трее (winshell.Tray.hotkey).

Сочетание пишется по-человечески: «Ctrl+Alt+N»; to_gnome / to_win переводят его.

Идея №154 (0.86): второе сочетание — «Позвать Лиру» (по умолчанию Ctrl+Alt+Space): нажали — слушает (как нажатие на лицо),
нажали ещё раз — перестала; или, если выбрано, — включить/выключить микрофон. kind="mic": своя запись GNOME
…/custom-keybindings/dewiar-mic/ с командой «… --mic», на Windows — второй RegisterHotKey того же окна значка."""
import ast
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT = "Ctrl+Alt+N"
DEFAULT_MIC = "Ctrl+Alt+Space"
GN_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
GN_ONE = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
GN_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dewiar-capture/"
NAME = "Dewiar — закинуть идею"
KINDS = {"capture": (GN_PATH, NAME, "--capture"),
         "mic": ("/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/dewiar-mic/", "Dewiar — позвать Лиру", "--mic")}
_MODS = {"ctrl": ("<Control>", 0x2), "control": ("<Control>", 0x2), "alt": ("<Alt>", 0x1), "shift": ("<Shift>", 0x4),
         "super": ("<Super>", 0x8), "win": ("<Super>", 0x8)}
_KEYS = {"space": ("space", 0x20), "пробел": ("space", 0x20), "enter": ("Return", 0x0D)}


def parse(combo):
    """«Ctrl+Alt+N» -> (модификаторы [имя], клавиша) или None, если без модификатора или непонятно."""
    parts = [p.strip().lower() for p in re.split(r"\s*\+\s*", str(combo or "")) if p.strip()]
    if len(parts) < 2 or any(p not in _MODS for p in parts[:-1]):
        return None
    key = parts[-1]
    if not (key in _KEYS or re.fullmatch(r"[a-z0-9]", key) or re.fullmatch(r"f([1-9]|1[0-2])", key)):
        return None
    return parts[:-1], key


def to_gnome(combo):
    p = parse(combo)
    if not p:
        return ""
    mods, key = p
    return "".join(dict.fromkeys(_MODS[m][0] for m in mods)) + (_KEYS[key][0] if key in _KEYS else key.upper() if key.startswith("f") else key)


def to_win(combo):
    """-> (MOD_… | MOD_NOREPEAT, код клавиши) или None."""
    p = parse(combo)
    if not p:
        return None
    mods, key = p
    m = 0x4000
    for x in mods:
        m |= _MODS[x][1]
    vk = _KEYS[key][1] if key in _KEYS else 0x70 + int(key[1:]) - 1 if key.startswith("f") else ord(key.upper())
    return m, vk


def command(root, kind="capture"):
    """Команда для сочетания: тот же Python и ui/app.py, что у работающей программы (установленная — /opt/dewiar/venv…),
    без /usr/bin/dewiar: тот сперва донастраивает службу — лишние полсекунды до окна."""
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(root) / 'ui' / 'app.py'))} {KINDS[kind][2]}"


# ---------- GNOME ----------

def _gs(*args, timeout=4):
    r = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip() or "gsettings не сработал")
    return r.stdout.strip()


def _gv(v):
    """Строка как текст GVariant ('…' с экранированием): иначе gsettings разбирал бы кавычки внутри команды сам."""
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _strv(s):
    s = re.sub(r"^@as\s+", "", (s or "").strip())
    try:
        v = ast.literal_eval(s)
        return [str(x) for x in v] if isinstance(v, (list, tuple)) else []
    except (ValueError, SyntaxError):
        return []


def _unq(s):
    try:
        return str(ast.literal_eval(s))
    except (ValueError, SyntaxError):
        return s.strip("'\"")


def gnome_available():
    """Есть gsettings и схема своих сочетаний GNOME (GNOME, Ubuntu, Unity, Budgie)."""
    if os.name == "nt" or not shutil.which("gsettings"):
        return False
    try:
        return GN_ONE in _gs("list-relocatable-schemas").split() and GN_SCHEMA in _gs("list-schemas").split()
    except Exception:  # noqa: BLE001
        return False


def gnome_state(combo=DEFAULT, kind="capture"):
    """-> {on: наша запись есть в списке, binding, command, conflict: имя другого своего сочетания на ту же клавишу}."""
    GN_PATH = KINDS[kind][0]
    lst = _strv(_gs("get", GN_SCHEMA, "custom-keybindings"))
    want = to_gnome(combo)
    out = {"on": GN_PATH in lst, "binding": "", "command": "", "conflict": ""}
    if out["on"]:
        out["binding"] = _unq(_gs("get", f"{GN_ONE}:{GN_PATH}", "binding"))
        out["command"] = _unq(_gs("get", f"{GN_ONE}:{GN_PATH}", "command"))
    for p in lst:
        if p == GN_PATH:
            continue
        try:
            if _unq(_gs("get", f"{GN_ONE}:{p}", "binding")).lower() == want.lower():
                out["conflict"] = _unq(_gs("get", f"{GN_ONE}:{p}", "name")) or p
        except Exception:  # noqa: BLE001
            continue
    return out


def gnome_set(on, combo, cmd, kind="capture"):
    """Включить (записать нашу запись и добавить в список) или выключить (убрать из списка и сбросить её ключи).
    Чужие сочетания не трогаем; та же клавиша занята своим сочетанием — не включаем. -> (ок, пояснение)."""
    GN_PATH, NAME = KINDS[kind][0], KINDS[kind][1]
    lst = _strv(_gs("get", GN_SCHEMA, "custom-keybindings"))
    if not on:
        if GN_PATH in lst:
            _gs("set", GN_SCHEMA, "custom-keybindings", str([p for p in lst if p != GN_PATH]))
        for k in ("name", "command", "binding"):
            try:
                _gs("reset", f"{GN_ONE}:{GN_PATH}", k)
            except Exception:  # noqa: BLE001
                pass
        return True, "выключено"
    want = to_gnome(combo)
    if not want:
        return False, f"не понял сочетание «{combo}» — например, {DEFAULT if kind == 'capture' else DEFAULT_MIC}"
    st = gnome_state(combo, kind)
    if st["conflict"]:
        return False, f"{combo} уже занято сочетанием «{st['conflict']}» — выберите другое"
    _gs("set", f"{GN_ONE}:{GN_PATH}", "name", _gv(NAME))
    _gs("set", f"{GN_ONE}:{GN_PATH}", "command", _gv(cmd))
    _gs("set", f"{GN_ONE}:{GN_PATH}", "binding", _gv(want))
    if GN_PATH not in lst:
        _gs("set", GN_SCHEMA, "custom-keybindings", str(lst + [GN_PATH]))
    return True, f"{combo} — в любой программе"
