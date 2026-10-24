"""Остановить Dewiar перед установкой обновления: все его python/pythonw из папки установки (кроме себя).
Запускает установщик (packaging/windows/dewiar.nsi, STOP_DEWIAR) своим же Python из папки Dewiar. Раньше это делал
PowerShell с -ExecutionPolicy Bypass — антивирусы (Kaspersky, PDM:Trojan.Win32.Generic) видели в этом поведение вируса
и убирали Dewiar (комментарии к ролику, 20.10). Только стандартная библиотека и psutil, если он есть."""
import os
import sys
import time


def _long(p):
    """Windows: полный путь вместо короткого 8.3 (C:\\Users\\B03C~1 → C:\\Users\\Иван): установщик для пути с русскими
    буквами ставит в ту же папку коротким именем, а запущенный python виден полным. Не Windows — как есть."""
    if os.name != "nt":
        return p
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetLongPathNameW(str(p), buf, 32768)
        return buf.value if n else p
    except Exception:  # noqa: BLE001
        return p


def targets(inst, procs, me):
    """[pid] процессов python из папки inst. procs — [(pid, путь к exe)]; me — свой номер (себя не трогаем)."""
    root = os.path.normcase(os.path.abspath(_long(inst))).rstrip("\\/") + os.sep
    out = []
    for pid, exe in procs:
        if pid == me or not exe:
            continue
        e = os.path.normcase(os.path.abspath(_long(exe)))
        if e.startswith(root) and os.path.basename(e) in ("python.exe", "pythonw.exe", "python", "pythonw"):
            out.append(pid)
    return out


def main(argv):
    if len(argv) < 2:
        return 2
    try:
        import psutil
    except ImportError:
        return 0                                     # без psutil — хватит остановки по номерам из ui.pid / core.pid
    procs = []
    for p in psutil.process_iter(["pid", "exe"]):
        try:
            procs.append((p.info["pid"], p.info["exe"] or ""))
        except (psutil.Error, OSError):
            continue
    pids = targets(argv[1], procs, os.getpid())
    for pid in pids:
        try:
            psutil.Process(pid).kill()
        except (psutil.Error, OSError):
            pass
    if pids:
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
