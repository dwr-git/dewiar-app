"""Докачка библиотеки Python, которой не оказалось на месте (№455/№464, 01.11: «распознавание падает с
ModuleNotFoundError: onnx_asr» — после переустановки системы установщик поставил не всё: общий список библиотек
обрывается на одной, а без onnx_asr точное распознавание GigaAM молча не работало).

ensure("onnx_asr") — есть библиотека — сразу True; нет — ставим её сами в свою папку STATE_DIR/pylib/pyXY (туда может
писать сам человек: /opt/dewiar/venv и Program Files — только администратор) установщиком, что есть: uv рядом с
программой (/opt/dewiar/bin/uv, его кладёт dewiar-env) или pip этого Python. Только сама библиотека, без зависимостей
(--no-deps): numpy и onnxruntime уже в основном окружении, а второй onnxruntime в своей папке перекрыл бы основной.
Своя папка добавляется в sys.path в КОНЕЦ — ничего из основного окружения она не заменяет. Не вышло — (False, причина
словами): распознаватель скажет человеку, что делать, и пока слушает запасной моделью."""

import importlib
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from settings import APP_DIR, STATE_DIR

log = logging.getLogger("dewiar.pydeps")
# модуль → что ставить (версия — как в requirements.txt)
PACKAGES = {"onnx_asr": "onnx-asr>=0.12"}
_lock = threading.Lock()
_tried = {}                                   # модуль → причина неудачи: второй раз за запуск не качаем


def extra_dir():
    return STATE_DIR / "pylib" / f"py{sys.version_info[0]}{sys.version_info[1]}"


def add_path():
    """Своя папка библиотек — в конец sys.path (вызывается при запуске ядра и после докачки)."""
    d = str(extra_dir())
    if Path(d).is_dir() and d not in sys.path:
        sys.path.append(d)
        importlib.invalidate_caches()


def _python():
    """Консольный Python рядом с этим (в Windows ядро работает в pythonw.exe — у него pip пишет в никуда)."""
    exe = Path(sys.executable)
    if os.name == "nt" and exe.name.lower() == "pythonw.exe" and exe.with_name("python.exe").exists():
        return str(exe.with_name("python.exe"))
    return str(exe)


def _installers(pkg, target):
    """Чем ставить, по порядку: uv программы, uv из PATH, pip этого Python."""
    out = []
    for uv in (APP_DIR / "bin" / ("uv.exe" if os.name == "nt" else "uv"), shutil.which("uv")):
        if uv and Path(uv).exists():
            out.append([str(uv), "pip", "install", "--python", _python(), "--target", str(target), "--no-deps", "-q", pkg])
            break
    out.append([_python(), "-m", "pip", "install", "--disable-pip-version-check", "--no-warn-script-location",
                "--target", str(target), "--no-deps", "-q", pkg])
    return out


def _missing(module, e):
    """ImportError именно этой библиотеки (а не её зависимости или сбоя внутри неё)."""
    return isinstance(e, ModuleNotFoundError) and (e.name or "").split(".")[0] == module


def ensure(module, on_status=None, run=subprocess.run):
    """-> (есть ли библиотека теперь, причина неудачи словами)."""
    add_path()
    try:
        importlib.import_module(module)
        return True, ""
    except ImportError as e:
        if not _missing(module, e) or module not in PACKAGES:
            return False, f"библиотека {module} не загрузилась: {e}"
    with _lock:
        if module in _tried:
            return False, _tried[module]
        pkg, target = PACKAGES[module], extra_dir()
        log.info("📦 Нет библиотеки %s — докачиваю %s в %s", module, pkg, target)
        if on_status:
            on_status(f"Докачиваю недостающую часть распознавания речи ({pkg.split('>')[0]}) — минуту…")
        err = ""
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            err = f"нет доступа к папке {target}: {e}"
        for cmd in ([] if err else _installers(pkg, target)):
            try:
                r = run(cmd, capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
                        creationflags=0x08000000 if os.name == "nt" else 0)
            except (OSError, subprocess.SubprocessError) as e:
                err = str(e)
                continue
            if r.returncode == 0:
                err = ""
                break
            tail = [x for x in ((r.stderr or "") + "\n" + (r.stdout or "")).strip().splitlines() if x.strip()]
            err = tail[-1][:200] if tail else f"код {r.returncode}"
        add_path()
        try:
            importlib.import_module(module)
            log.info("📦 Библиотека %s докачана", module)
            return True, ""
        except ImportError as e:
            why = err or str(e)
            low = why.lower()
            if any(w in low for w in ("connect", "network", "resolve", "timed out", "timeout", "unreachable", "proxy", "ssl")):
                why = "нет связи с pypi.org (интернет или прокси)"
            elif "no module named pip" in low:
                why = "нечем поставить: в этом Python нет pip"
            _tried[module] = f"не хватает библиотеки {module}, и докачать её не вышло: {why}"
            log.warning("📦 %s", _tried[module])
            return False, _tried[module]


def fix_hint():
    """Как поставить библиотеки заново — словами для этой системы."""
    if os.name == "nt":
        return "переустановите Dewiar поверх (установщик с dewiar.pro) — библиотеки поставятся заново"
    if str(APP_DIR).startswith("/opt/dewiar"):
        return "в терминале: sudo /opt/dewiar/dewiar-env — поставит библиотеки заново"
    return "в терминале: pip install -r requirements.txt"
