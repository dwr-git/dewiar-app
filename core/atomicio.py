"""Запись файла целиком «атомарно»: во временный файл рядом, затем подмена (os.replace) — оборванная запись не портит файл.

Пакет 04.11 (Windows): «близкие: сохранить — PermissionError: [Errno 13] Permission denied: '…\\close.tmp'». Временный
файл у всех был с одним и тем же именем (close.tmp): два потока сохраняли разом и мешали друг другу, а антивирус или
индексатор на миг держит только что записанный файл. Здесь у каждой записи своё имя временного файла, а запись и
подмена повторяются несколько раз с растущей паузой; не вышло — исключение, как раньше, и временный файл убран.
"""

import os
import threading
import time
from pathlib import Path

_N = [0]
_LOCK = threading.Lock()


def _tmp_name(path):
    with _LOCK:
        _N[0] += 1
        n = _N[0]
    return path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident() % 100000}.{n}.tmp")


def write_text(path, text, encoding="utf-8", mode=None, tries=5, pause=0.1):
    """Записать text в path через временный файл со своим именем. mode — права (например 0o600). PermissionError (файл
    на миг занят) — до tries попыток с паузой pause, 2·pause, …"""
    write_bytes(path, text.encode(encoding), mode=mode, tries=tries, pause=pause)


def write_bytes(path, data, mode=None, tries=5, pause=0.1):
    path = Path(path)
    for i in range(tries):
        tmp = _tmp_name(path)
        try:
            with open(tmp, "wb") as f:
                f.write(data)
            if mode is not None:
                os.chmod(tmp, mode)
            os.replace(tmp, path)
            return
        except PermissionError:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            if i == tries - 1:
                raise
            time.sleep(pause * (i + 1))
        except BaseException:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
