"""Сейф: пароли, пин-коды, коды от домофона, ключи — зашифрованы ключом этого компьютера, лежат отдельно от заметок
(не синхронизируются с Obsidian, не ищутся поиском по заметкам, не уходят в языковую модель).

Голосом: «запомни пароль от вайфая: кот123», «пин-код карты — 4512», «какой пароль от вайфая?» (значение — на экране,
вслух не читается). В студии — раздел «Безопасность» → «Сейф».
Файл сейфа — crypt.seal ключом device_key (без ключа этого компьютера не открыть); в резервную копию сейф попадает
только с паролем (backup.py). Значения не отдаём ни в list(), ни в журнал (mask)."""

import json
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from crypt import CryptError, device_key, seal, unseal

# Фразы сейфа: KEY — о чём речь; SAVE_RX — «запомни пароль от X: значение» (с разделителем), SAVE_LOOSE — без
# разделителя, но значение похоже на секрет (цифры, латиница, цифры словами); GET_RX — «какой пароль от X».
KEY = (r"пароль|пароли|пин-код|пинкод|пин|pin|пин код|код доступа|код от домофона|код домофона|кодовое слово|секретное слово|"
       r"секретный вопрос|ключ api|api-ключ|апи ключ|токен|номер карты|cvv|cvc|логин|код от сейфа|код от двери|код от ворот|"
       r"код от подъезда|код сигнализации|пароль wi-fi|пароль от wi-fi")
SAVE_RX = re.compile(rf"^(?:(?:запомни|запиши|сохрани|положи\s+в\s+сейф|спрячь|добавь\s+в\s+сейф)\s*,?\s+)?(?:что\s+)?(?:мой\s+|моя\s+|мой\s+новый\s+|новый\s+)?"
                     rf"(?P<name>(?:{KEY})(?:\s+(?:(?:от|для|к|на|в|у)\s+)?[^:—=]+?)?)\s*(?::|—|–|=|\s-\s|\s+это\s+|\s+будет\s+|\s+такой\s+|\s+теперь\s+)\s*(?P<value>\S.*)$", re.I)
DW = r"(?:ноль|один|одна|два|две|три|четыре|пять|шесть|семь|восемь|девять)"
SAVE_LOOSE = re.compile(rf"^(?:запомни|запиши|сохрани|положи\s+в\s+сейф)\s*,?\s+(?:что\s+)?(?:мой\s+|моя\s+)?(?P<name>(?:{KEY})(?:\s+.+?)?)\s+"
                        rf"(?P<value>\S*\d\S*|[A-Za-z0-9_@.!#$%^&*+-]{{4,}}|(?:{DW}\s?){{3,}})$", re.I)
GET_RX = re.compile(rf"^(?:а\s+)?(?:какой|какая|какое|скажи|подскажи|покажи|напомни|дай|назови|выведи)\s+(?:мне\s+)?(?:у\s+меня\s+)?(?:мой\s+|моя\s+)?"
                    rf"(?P<name>(?:{KEY})(?:\s+.+?)?)$", re.I)
DIGITS = {"ноль": "0", "один": "1", "одна": "1", "два": "2", "две": "2", "три": "3", "четыре": "4", "пять": "5", "шесть": "6",
          "семь": "7", "восемь": "8", "девять": "9"}


def _clean(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    return t.rstrip(" .!?")


def _value(v):
    """Значение без кавычек и точки в конце; продиктованные словами цифры — цифрами."""
    v = v.strip().strip("«»\"'").rstrip(".!")
    w = v.lower().split()
    if w and all(x in DIGITS for x in w):                    # «один два три четыре» → 1234
        return "".join(DIGITS[x] for x in w)
    return v


def parse(text):
    """-> {"op": "save", "name", "value"} | {"op": "get", "name"} | None"""
    t = _clean(text)
    if not t or len(t) > 200:
        return None
    m = SAVE_RX.match(t) or SAVE_LOOSE.match(t)
    if m:
        name, value = _clean(m.group("name")), _value(m.group("value"))
        if value and len(value) <= 120:
            return {"op": "save", "name": name[:1].upper() + name[1:], "value": value}
    m = GET_RX.match(t)
    if m:
        return {"op": "get", "name": _clean(m.group("name"))}
    return None


def mask(text):
    """Для журнала: «пароль от вайфая: кот123» → «пароль от вайфая: •••». Значение в кавычках («кот123», "кот123")
    прячется вместе с ними; не нашли значение в конце фразы (его нормализовали) — фраза заменяется целиком:
    секрет не должен попасть в журнал ни в каком виде."""
    c = parse(text)
    if c and c["op"] == "save":
        t = _clean(text)
        masked, n = re.subn(r"""["'«]?""" + re.escape(c["value"]) + r"""["'»]?[.!]*$""", "•••", t, count=1)
        return masked if n else "🔐 (секрет для сейфа)"
    return text


def _words(s):
    """Основы слов для сравнения названий: первые 5 букв, «wi-fi»/«вайфай» — одно слово."""
    s = re.sub(r"wi-?fi|вай-?\s?фа|вифи", "вайфа", (s or "").lower().replace("ё", "е"))
    return {w[:5] for w in re.findall(r"[\wё]+", s) if len(w) > 1}


class Vault:
    def __init__(self, path, key_path):
        self.path, self.key_path = Path(path), Path(key_path)
        self._lock = threading.RLock()
        self._items = None

    def _key(self, create=False):
        return device_key(self.key_path, create=create)

    def _load(self):
        """Расшифрованный список записей (кэш в памяти). Не открылся — CryptError, а не пустой сейф: иначе первое
        же сохранение затёрло бы его новым."""
        if self._items is not None:
            return self._items
        if not self.path.exists():
            self._items = []
            return self._items
        try:
            self._items = json.loads(unseal(self.path.read_bytes(), self._key()).decode("utf-8")).get("items", [])
        except (CryptError, ValueError, OSError) as e:
            raise CryptError(f"сейф не открывается: {e}") from e
        return self._items

    def _save(self):
        data = json.dumps({"v": 1, "items": self._items}, ensure_ascii=False).encode("utf-8")
        blob = seal(data, self._key(create=True))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")              # через временный файл: оборванная запись не испортит сейф
        tmp.write_bytes(blob)
        tmp.replace(self.path)

    def count(self):
        with self._lock:
            try:
                return len(self._load())
            except CryptError:
                return 0

    def list(self):
        """Без значений — только названия и длина значения (для студии и модели)."""
        with self._lock:
            return [{k: v for k, v in x.items() if k != "value"} | {"length": len(x.get("value", ""))}
                    for x in sorted(self._load(), key=lambda i: i.get("name", "").lower())]

    def get(self, item_id):
        with self._lock:
            return next((dict(x) for x in self._load() if x["id"] == item_id), None)

    def find(self, name):
        """Лучшее совпадение по словам названия и заметки (или None). Слова «пароль», «код»… не считаются: иначе
        «пароль от почты» совпал бы с любым паролем; если кроме них ничего не сказано — считаются."""
        stop = {"от", "для", "на", "к", "у", "мой", "моя", "мое", "мои", "из", "по", "это"}
        want = (_words(name) - stop) - {"парол", "пин", "код", "пин-к", "логин"} or (_words(name) - stop)
        best, score = None, 0
        with self._lock:
            for x in self._load():
                have = _words(x["name"] + " " + x.get("note", "")) - stop
                s = len(want & have)
                if s > score:
                    best, score = x, s
        return dict(best) if best else None

    def put(self, name, value, note="", item_id=None, login=None, url=None):
        """Новая запись или замена: по item_id, а без него — по совпадению названия. -> запись без значения.
        login и url («Сейф паролей», 0.45) — не секрет: видны в списке, по ним ищут; None — оставить как было."""
        name, value = _clean(name)[:120], str(value)
        if not name or not value:
            raise ValueError("нужно название и значение")
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            items = self._load()
            x = next((i for i in items if (item_id and i["id"] == item_id) or (not item_id and i["name"].lower() == name.lower())), None)
            if x:
                x.update(name=name, value=value, note=note if note is not None else x.get("note", ""), updated=now)
            else:
                x = {"id": uuid.uuid4().hex[:10], "name": name, "value": value, "note": note or "", "created": now, "updated": now}
                items.append(x)
            if login is not None:
                x["login"] = str(login).strip()[:160]
            if url is not None:
                x["url"] = str(url).strip()[:300]
            self._save()
            return {k: v for k, v in x.items() if k != "value"}

    def delete(self, item_id):
        with self._lock:
            items = self._load()
            n = len(items)
            self._items = [x for x in items if x["id"] != item_id]
            if len(self._items) != n:
                self._save()
            return n != len(self._items)

    # ---------- для резервной копии ----------

    def export_plain(self):
        """Открытым текстом — только для копии с паролем (backup.make кладёт его в зашифрованный zip)."""
        with self._lock:
            return json.dumps({"v": 1, "items": self._load(), "time": time.time()}, ensure_ascii=False).encode("utf-8")

    def import_plain(self, data, only_new=False):
        """Сливает записи из копии со здешними по названию: одноимённая запись получает значение и заметку из копии
        (id остаётся свой — на него могут ссылаться открытые окна студии), новые добавляются, свои остаются.
        only_new — «Добавить недостающее» из слепка: одноимённые свои не трогаем вовсе.
        Заменять сейф целиком нельзя: записи, сделанные после копии, пропали бы без следа. -> сколько записей взято."""
        got = [x for x in json.loads(data.decode("utf-8")).get("items", []) if isinstance(x, dict) and x.get("name") and x.get("value")]
        if not got:
            return 0
        with self._lock:
            try:
                items = self._load()
            except CryptError:                               # здешний сейф не открывается (ключ не тот) — спасать в нём нечего
                self._items = items = []
            by_name = {i["name"].lower(): i for i in items}
            ids = {i["id"] for i in items}
            for x in got:
                cur = by_name.get(x["name"].lower())
                if cur:
                    if not only_new:
                        cur.update({k: v for k, v in x.items() if k not in ("id", "created")})
                    continue
                x = dict(x)
                if not x.get("id") or x["id"] in ids:          # id из копии занят другой записью — выдаём новый
                    x["id"] = uuid.uuid4().hex[:10]
                ids.add(x["id"])
                items.append(x)
                by_name[x["name"].lower()] = x
            self._save()
            return len(got)
