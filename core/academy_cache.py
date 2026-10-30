"""Видеоуроки — через ядро, в папку на этом компьютере (30.10, владелец, Ubuntu: «„Смотреть“ — бесполезно, и обложки
нет; может, потому что я в подсети сайта, до домена?»). Окно студии грузит картинки и видео само, мимо ядра, — а изнутри
сети сайта публичный домен часто не открывается (роутер не умеет «вернуть» запрос внутрь), домашний же адрес сайта
окну не годится. Ядро знает рабочую дорогу (дома — напрямую, net._LanFirst; иначе — как обычно): оно скачивает файл урока
один раз в STATE_DIR/academy, а окно открывает его с диска. Потом — мгновенно и без сети.

Берём только файлы уроков своего сайта (…/academy/имя.mp4|webm|jpg|png|webp). Старше 60 дней и сверх 3 ГБ — убираем."""

import re
import threading
import time
from pathlib import Path

EXT_RX = re.compile(r"\.(?:mp4|webm|jpe?g|png|webp)$", re.I)
KEEP_DAYS = 60
MAX_BYTES = 3 * 1024 ** 3
_locks, _glock = {}, threading.Lock()


def academy_base(cloud_url):
    from cloud import base_of
    return base_of(cloud_url).rsplit("/", 1)[0] + "/academy/"


def local_name(url, cloud_url):
    """Имя файла в кэше или ValueError, если это не файл урока своего сайта."""
    pub = academy_base(cloud_url)
    u = str(url or "").split("?", 1)[0].split("#", 1)[0]
    if not u.startswith(pub):
        raise ValueError("это не файл видеоурока")
    name = re.sub(r"[^\w.-]", "_", u[len(pub):])[:120]
    if not EXT_RX.search(name) or name.startswith("."):
        raise ValueError("это не файл видеоурока")
    return name


def _prune(root):
    try:
        files = sorted((f for f in root.iterdir() if f.is_file()), key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError:
        return
    total, old = 0, time.time() - KEEP_DAYS * 86400
    for f in files:
        try:
            st = f.stat()
            total += st.st_size
            if st.st_mtime < old or total > MAX_BYTES or f.suffix == ".part" and st.st_mtime < time.time() - 3600:
                f.unlink()
        except OSError:
            pass


def fetch(url, cloud_url, root, timeout=30.0, get=None):
    """-> Path файла на диске (скачанного сейчас или раньше). get(url) — для проверок: -> итератор кусков байтов."""
    name = local_name(url, cloud_url)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    f = root / name
    with _glock:
        lock = _locks.setdefault(name, threading.Lock())
    with lock:                                          # двое просят один урок — качается один раз
        if f.is_file() and f.stat().st_size > 0:
            f.touch()                                   # смотрели — значит нужен, не убираем
            return f
        part = f.with_name(f.name + ".part")
        if get is None:
            import httpx

            def get(u):
                with httpx.stream("GET", u, timeout=httpx.Timeout(timeout, read=timeout), follow_redirects=True) as r:
                    r.raise_for_status()
                    yield from r.iter_bytes(1 << 16)
        try:
            with open(part, "wb") as out:
                for chunk in get(str(url).split("#", 1)[0]):
                    out.write(chunk)
            if part.stat().st_size == 0:
                raise ValueError("сайт прислал пустой файл")
            part.replace(f)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
    _prune(root)
    return f
