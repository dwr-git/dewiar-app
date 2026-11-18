"""Синхронизация — основа (чистое ядро 1.0.16 — docs/CORE_PLAN.md): виды записей и пределы, шифрование записи
(_seal/_open), id заметок и фактов, время. Обмен — core/sync.py (Sync, HomeSync), части — sync_*.py; прежние имена
sync.X на месте. Подменять в проверках — здесь (sync_base._now_ms, STATE_DIR, _seal): части читают через основу."""
import hashlib
import json
import logging
import re
import socket
import threading
import time
from pathlib import Path

from settings import CONFIG_DIR, STATE_DIR  # noqa: F401 — CONFIG_DIR: копия id устройства (sync_device, №851)

log = logging.getLogger("dewiar.sync")

BASE_KINDS = ("reminder", "note", "money", "memory")          # знает любой сервер
EXTRA_KINDS = ("soul", "mind", "diary", "dayturn", "taskreq", "task", "vault", "done", "persona", "bill", "pay", "payfile", "pmemory", "safe",
               "plugin", "client", "doc")                   # тот же список $extra в cloud.php; doc — «Мои файлы» на телефоне (0.98); plugin — только между компьютерами (не по Wi-Fi)
VAULT_MAX = 300_000                               # сервер не принимает запись больше 300 КБ — такие заметки не шлём
VAULT_FILES = 15000
CHUNK = 400                                       # изменений за один запрос (сервер берёт до 2000; первая отправка большого хранилища — частями)
DIARY_DAYS = 30                                   # сколько последних дней дневника видно на телефоне
TASKS_SHOWN = 15
NOTES = "Заметки"
MEMORY = Path("Память") / "Обо мне.md"
NOTE_MAX = 300_000
PAD_DIR = "Блокнот"                     # вкладки блокнота у виджета (core/pad.py) — «Заметки/Блокнот/*.md»
# Душа и конституция идут в системную подсказку каждого разговора: с другого устройства принимаем только похожее на них
# (аудит 19.10: кто завладел ключом аккаунта, мог бы подменить поведение помощника). В подсказку и так уходит
# не больше 1800/1400 знаков (soul.MAX_CONST / MAX_SOUL) — длиннее этого предела запись из облака не принимаем вовсе.
MIND_MAX = 8000
DIARY_MAX = 60_000                                  # день дневника — текст, не архив
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")   # управляющие и «невидимые» знаки
CONST_PREV = "Память/Конституция — прежняя.md"
# Сквозное шифрование (sync.e2e, core/synckey.py): что шифруется на устройстве — всё личное. Открытыми остаются только
# метка «шифрование включено» (mind:e2e), задачи для облака (taskreq с cloud — их выполняет сервер) и удаления (пустые).
E2E_KINDS = ("reminder", "note", "money", "memory", "soul", "mind", "diary", "dayturn", "done", "persona", "vault", "task", "taskreq", "pmemory",
             "bill", "pay", "payfile", "safe", "plugin", "client", "doc")   # doc — только зашифрованным или по Wi-Fi;   # client — «Клиенты» (0.89), только зашифрованными; safe и без того шифр мастер-пароля — с e2e он ещё и в конверте ключа синхронизации
# «Платежи» между компьютерами (27.10, владелец: «платежи дома заполнил… а на работе их нет»): bill — счёт, pay — оплата,
# payfile — вложение (платёжка, скриншот) кусками: облако берёт запись до 300 КБ, а зашифрованная на треть длиннее
PF_CHUNK = 150_000
PF_MAX = 6_000_000                                # больше — файл не синхронизируем (запись счёта его всё равно помнит)
E2E_MARK = "mind:e2e"
SEALED_MAX = 290_000                              # сервер не берёт запись больше 300 КБ — зашифрованная на треть длиннее
# «Мои файлы» на всех устройствах (0.98, владелец 14.11): телефон ищет по тексту файлов компьютера, даже когда тот
# выключен. Уходит уже прочитанный текст (отрывки core/knowledge.py), сжатый и только зашифрованным ключом своих
# устройств (или по домашнему Wi-Fi) — облако хранит шифр. Запись doc:<id файла>.<номер куска>; свежие файлы — первыми.
DOC_PART = 120_000                                # знаков в куске: сжатый и зашифрованный — с запасом меньше 300 КБ
DOC_TOTAL = 20_000_000                            # всего текста с одного компьютера (≈ 6 МБ шифра в облаке)


def _mind_text(d, limit):
    """Текст души, конституции или дня дневника из облака: строка, без управляющих и невидимых знаков (ими прячут
    команды от глаз человека), не длиннее limit. Не подходит — None (запись не применяется)."""
    t = d.get("text") if isinstance(d, dict) else None
    if not isinstance(t, str) or len(t) > limit:
        return None
    return _CTRL.sub("", t)
_FACT = re.compile(r"^- (.+?)(?: _\(\d\d\.\d\d\.\d{4}\)_)?\s*$")


def _seal(k, data):
    from synckey import seal_data
    return seal_data(k, data)


def _open(k, data):
    from synckey import open_data
    return open_data(k, data)


def _is_sealed(d):
    return isinstance(d, dict) and bool(d.get("e2e")) and isinstance(d.get("c"), str)


def _now_ms():
    return int(time.time() * 1000)


def _h(data):
    """Отпечаток записи «как она лежит у нас». Только локальный: телефон считает свой иначе, сравнивать их нельзя."""
    return hashlib.sha1(json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _pmem_id(name, text):
    """id факта своей памяти персонажа: «m<отпечаток имени>-<id факта>» — удаление (без текста) найдёт и файл, и строку.
    Так же считает pmemId() в app.js."""
    return "m" + hashlib.sha1(str(name).strip().lower().encode("utf-8")).hexdigest()[:8] + "-" + (_fact_id(text) if text else "")


_NUM_TAIL = re.compile(r"\s*\(\d{1,3}\)$")


def _base_title(title):
    """Название без хвоста « (2)» — его дописывает компьютер, когда имя файла занято (как noteBase в app.js)."""
    return _NUM_TAIL.sub("", " ".join(str(title or "").split()))


def _note_norm(title, text):
    """Текст заметки для сравнения «та же ли»: без «# Название» в начале (компьютер его дописывает, и там может не быть
    « (2)» из имени файла) и лишних пробелов — как noteNorm в app.js."""
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    first = t.split("\n", 1)[0]
    if first.startswith("# ") and _base_title(first[2:]) == _base_title(title):
        t = t[len(first):].strip()
    return re.sub(r"\s+", " ", t)


def _fact_id(text):
    """id строки памяти — по её тексту; нормализация та же, что у factId() в app.js, иначе телефон и компьютер
    разойдутся в id и удаление строки на одном не найдёт её на другом."""
    return "f" + hashlib.sha1(re.sub(r"\s+", " ", text.strip().lower().rstrip(".")).encode("utf-8")).hexdigest()[:12]


def _version():
    try:
        from version import VERSION
        return VERSION
    except Exception:  # noqa: BLE001
        return ""


def default_device_name():
    try:
        return socket.gethostname()[:40] or "Компьютер"
    except OSError:
        return "Компьютер"


class SyncError(Exception):
    pass


class FanEvent(threading.Event):
    """«Есть свои правки — обменяться скорее»: будит и облачную синхронизацию, и домашнюю (HomeSync), если она есть."""
    def __init__(self):
        super().__init__()
        self.also = []

    def set(self):
        super().set()
        for e in self.also:
            e.set()
