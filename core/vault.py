"""Сейф: пароли, пин-коды, коды от домофона, ключи — зашифрованы ключом этого компьютера, лежат отдельно от заметок
(не синхронизируются с Obsidian, не ищутся поиском по заметкам, не уходят в языковую модель).

Голосом: «запомни пароль от вайфая: кот123», «пин-код карты — 4512», «какой пароль от вайфая?» (значение — на экране,
вслух не читается). В студии — раздел «Безопасность» → «Сейф».
Файл сейфа — crypt.seal ключом device_key (без ключа этого компьютера не открыть); в резервную копию сейф попадает
только с паролем (backup.py). Значения не отдаём ни в list(), ни в журнал (mask).

Сейф между своими устройствами (03.11, группа Telegram: «сейф не синхронизируется с компа на комп… пароли как раз часто
нужны на чужом компе — подглядеть со смартфона»): по желанию, только сквозным шифрованием — SafeKey ниже.
  • Мастер-пароль сейфа → ключ K (PBKDF2-HMAC-SHA256, SAFE_IT повторов, соль 16 байт). Ни пароль, ни K никуда не уходят;
    на компьютере K лежит запечатанным ключом этого компьютера (vault-sync.key) — сейф и так открыт здесь без пароля.
  • Запись «safe:<id>» синхронизации — {"kid", "c": base64url(closecrypto.seal(K, JSON записи))}: название, логин, сайт,
    заметка и пароль — всё внутри шифра. «safe:key» — открытые параметры: соль, повторы, kid, at и check = seal(K,
    SAFE_CHECK) — по нему другое устройство узнаёт, подошёл ли мастер-пароль. Сервер видит только id, время и размер.
  • Телефон (android/assets/www/safe.js) хранит записи как пришли — шифром — и открывает их тем же мастер-паролем."""

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

import closecrypto as CC
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
PAGE_MAX = 50000          # секретная страница: десятки паролей, ключей и адресов — с запасом
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
        self.on_change = None            # своя правка (не из синхронизации) — синхронизации поторопиться (engine: sync.soon.set)

    def _changed(self):
        if callable(self.on_change):
            try:
                self.on_change()
            except Exception:  # noqa: BLE001
                pass

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
        """Без значений — только названия и длина значения (для студии и модели); у страницы — ещё число строк."""
        with self._lock:
            return [{k: v for k, v in x.items() if k != "value"} | {"length": len(x.get("value", ""))}
                    | ({"lines": sum(1 for ln in x.get("value", "").splitlines() if ln.strip())} if x.get("kind") == "page" else {})
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

    def put(self, name, value, note="", item_id=None, login=None, url=None, kind=None):
        """Новая запись или замена: по item_id, а без него — по совпадению названия (того же вида). -> запись без значения.
        login и url («Сейф паролей», 0.45) — не секрет: видны в списке, по ним ищут; None — оставить как было.
        kind="page" — секретная страница (29.10, владелец: «много паролей или секретов в кучу, как на обычной странице,
        но чтобы тоже безопасно лежало и шифровалось»): то же шифрование, значение — текст до PAGE_MAX знаков."""
        name, value = _clean(name)[:120], str(value)
        page = kind == "page"
        if not name or not value.strip():
            raise ValueError("страница пустая — впишите текст или удалите её" if page and name else "нужно название и значение")
        if len(value) > (PAGE_MAX if page else 5000):
            raise ValueError(f"слишком длинно: до {PAGE_MAX if page else 5000} знаков" + ("" if page else " — для длинного есть «Страница»"))
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            items = self._load()
            x = next((i for i in items if (item_id and i["id"] == item_id)
                      or (not item_id and i["name"].lower() == name.lower() and (i.get("kind") == "page") == page)), None)
            if x:
                x.update(name=name, value=value, note=note if note is not None else x.get("note", ""), updated=now, mt=_ms())
            else:
                x = {"id": uuid.uuid4().hex[:10], "name": name, "value": value, "note": note or "", "created": now, "updated": now, "mt": _ms()}
                if page:
                    x["kind"] = "page"
                items.append(x)
            if login is not None:
                x["login"] = str(login).strip()[:160]
            if url is not None:
                x["url"] = str(url).strip()[:300]
            self._save()
        self._changed()
        return {k: v for k, v in x.items() if k != "value"}

    def delete(self, item_id):
        with self._lock:
            items = self._load()
            n = len(items)
            self._items = [x for x in items if x["id"] != item_id]
            gone = len(self._items) != n
            if gone:
                self._save()
        if gone:
            self._changed()
        return gone

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
                        cur.update({k: v for k, v in x.items() if k not in ("id", "created")}, mt=_ms())   # новое время: уйдёт и на другие устройства
                    continue
                x = dict(x, mt=_ms())
                if not x.get("id") or x["id"] in ids:          # id из копии занят другой записью — выдаём новый
                    x["id"] = uuid.uuid4().hex[:10]
                ids.add(x["id"])
                items.append(x)
                by_name[x["name"].lower()] = x
            self._save()
        self._changed()
        return len(got)

    # ---------- синхронизация между своими устройствами (core/sync.py, вид «safe») ----------

    def sync_items(self):
        """Все записи со значениями — только для шифрования в синхронизацию. Сейф не открылся — CryptError (не пустой
        список: иначе синхронизация сочла бы записи удалёнными)."""
        with self._lock:
            return [dict(x) for x in self._load()]

    def sync_put(self, x):
        """Запись с другого устройства (уже расшифрованная): кладётся как есть, с тем же id и временем. -> взяли ли."""
        x = item_clean(x)
        if x is None:
            return False
        with self._lock:
            items = self._load()
            cur = next((i for i in items if i["id"] == x["id"]), None)
            if cur is not None:
                cur.clear()
                cur.update(x)
            else:
                items.append(x)
            self._save()
        return True

    def sync_drop(self, item_id):
        """Удалено на другом устройстве: без on_change — это не своя правка."""
        with self._lock:
            items = self._load()
            keep = [x for x in items if x["id"] != item_id]
            if len(keep) == len(items):
                return False
            self._items = keep
            self._save()
            return True


def _ms():
    return int(time.time() * 1000)


def item_ms(x):
    """Когда запись правили, мс: поле mt (с 03.11), у прежних — по updated (местное время этого компьютера)."""
    try:
        return int(x.get("mt") or 0) or int(datetime.fromisoformat(str(x.get("updated") or x.get("created"))).timestamp() * 1000)
    except (TypeError, ValueError):
        return 0


ITEM_ID = re.compile(r"[0-9a-z]{6,24}")


def item_clean(x):
    """Запись сейфа из синхронизации — только известные поля разумной длины; не подходит — None."""
    if not isinstance(x, dict) or not ITEM_ID.fullmatch(str(x.get("id") or "")):
        return None
    name, value = str(x.get("name") or "").strip()[:120], x.get("value")
    page = x.get("kind") == "page"
    if not name or not isinstance(value, str) or not value.strip() or len(value) > (PAGE_MAX if page else 5000):
        return None
    try:
        mt = max(0, int(x.get("mt") or 0))
    except (TypeError, ValueError):
        mt = 0
    out = {"id": x["id"], "name": name, "value": value, "note": str(x.get("note") or "")[:300],
           "created": str(x.get("created") or "")[:32], "updated": str(x.get("updated") or "")[:32], "mt": mt}
    if page:
        out["kind"] = "page"
    for k, n in (("login", 160), ("url", 300)):
        if x.get(k):
            out[k] = str(x[k]).strip()[:n]
    return out


# ---------- ключ сейфа из мастер-пароля (см. шапку) ----------

SAFE_IT = 600_000                   # повторов PBKDF2-HMAC-SHA256 (OWASP 2023); число — в «safe:key», менять можно для новых
SAFE_CHECK = b"dewiar-safe-v1"
SAFE_MIN = 8                        # мастер-пароль — не короче


def safe_derive(password, salt, it):
    """Ключ 32 байта из мастер-пароля. NFC — чтобы «ё», набранная на телефоне и на компьютере по-разному, давала тот же
    ключ (safeDerive в safe.js делает то же)."""
    pw = unicodedata.normalize("NFC", str(password)).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", pw, bytes(salt), int(it), 32)


def safe_meta_ok(m):
    """Открытые параметры сейфа из облака: правильной формы — True."""
    try:
        return (isinstance(m, dict) and len(CC.b64d(m.get("salt"))) == 16 and 100_000 <= int(m.get("it")) <= 10_000_000
                and re.fullmatch(r"[0-9a-f]{8,32}", str(m.get("kid") or "")) is not None and int(m.get("at") or 0) > 0
                and len(CC.b64d(m.get("check"))) == 48 + len(SAFE_CHECK))
    except (TypeError, ValueError):
        return False


def safe_meta_new(password, it=SAFE_IT):
    """Новый мастер-пароль -> (ключ, открытые параметры)."""
    if len(str(password or "")) < SAFE_MIN:
        raise ValueError(f"мастер-пароль — не короче {SAFE_MIN} знаков: им открывается сейф на телефоне и других компьютерах")
    salt = secrets.token_bytes(16)
    k = safe_derive(password, salt, it)
    return k, {"v": 1, "salt": CC.b64e(salt), "it": int(it), "kid": secrets.token_hex(8), "at": _ms(),
               "check": CC.b64e(CC.seal(k, SAFE_CHECK))}


def safe_try(password, meta):
    """Мастер-пароль к этим параметрам: подошёл — ключ, нет — None."""
    if not safe_meta_ok(meta):
        return None
    k = safe_derive(password, CC.b64d(meta["salt"]), int(meta["it"]))
    try:
        return k if CC.unseal(k, CC.b64d(meta["check"])) == SAFE_CHECK else None
    except CC.CloseCryptoError:
        return None


def safe_seal(k, kid, x):
    return {"kid": kid, "c": CC.b64e(CC.seal(k, json.dumps(x, ensure_ascii=False, sort_keys=True).encode("utf-8")))}


def safe_open(k, d):
    return json.loads(CC.unseal(k, CC.b64d(d.get("c"))).decode("utf-8"))


def safe_hash(k, kid, x):
    """Отпечаток записи для sync.json — HMAC ключом сейфа: обычный хэш открытого пин-кода из 4 цифр подбирается мгновенно."""
    return hmac.new(k, kid.encode() + b"|" + json.dumps(x, ensure_ascii=False, sort_keys=True).encode("utf-8"), hashlib.sha256).hexdigest()[:16]


class SafeKey:
    """Ключ сейфа на этом компьютере (vault-sync.key, запечатан ключом компьютера) и последние известные параметры сейфа
    из облака (vault-sync.meta.json — открытые, как и в облаке). Есть ключ — сейф синхронизируется (см. Sync._safe_on)."""

    def __init__(self, path, device_key_path):
        self.path, self.device_key_path = Path(path), Path(device_key_path)
        self.meta_path = self.path.with_name(self.path.stem + ".meta.json")
        self._cache = None
        self._lock = threading.Lock()

    def _dk(self):
        return device_key(self.device_key_path, create=True)

    def get(self):
        """-> {"k": 32 байта, "meta": параметры} или None."""
        with self._lock:
            if self._cache is None:
                try:
                    d = json.loads(unseal(self.path.read_bytes(), self._dk()).decode("utf-8"))
                    k = CC.b64d(d["k"])
                    self._cache = {"k": k, "meta": d["meta"]} if len(k) == 32 and safe_meta_ok(d.get("meta")) else {}
                except FileNotFoundError:
                    self._cache = {}
                except Exception:  # noqa: BLE001 — ключ компьютера сменился: мастер-пароль спросим заново
                    self._cache = {}
            return self._cache or None

    def set(self, k, meta):
        if len(k) != 32 or not safe_meta_ok(meta):
            raise ValueError("ключ сейфа — 32 байта и правильные параметры")
        blob = seal(json.dumps({"k": CC.b64e(k), "meta": meta}).encode("utf-8"), self._dk())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        tmp.replace(self.path)
        with self._lock:
            self._cache = {"k": bytes(k), "meta": dict(meta)}
        self.note(meta)

    def forget(self):
        with self._lock:
            self._cache = {}
        try:
            self.path.unlink()
        except OSError:
            pass

    def remote(self):
        """Последние параметры сейфа, известные этому компьютеру (свои или из облака), или None."""
        try:
            m = json.loads(self.meta_path.read_text(encoding="utf-8"))
            return m if safe_meta_ok(m) else None
        except (OSError, ValueError):
            return None

    def note(self, meta):
        """Параметры из облака: запоминаем более поздние (по at). -> сменились ли."""
        cur = self.remote()
        if not safe_meta_ok(meta) or (cur and int(cur["at"]) > int(meta["at"])) or cur == meta:
            return False
        self.meta_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.meta_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(meta), encoding="utf-8")
        tmp.replace(self.meta_path)
        return True

    def active(self):
        """Ключ, которым сейчас синхронизировать, или None: ключа нет, либо мастер-пароль сменили на другом устройстве
        позже (в облаке новые параметры — старым ключом их записи не открыть, свои шифровать им незачем)."""
        cur = self.get()
        if not cur:
            return None
        r = self.remote()
        if r and r["kid"] != cur["meta"]["kid"] and int(r["at"]) > int(cur["meta"]["at"]):
            return None
        return cur
