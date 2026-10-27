"""Моя музыка (27.10, идея владельца: «папка с музыкой — Лира как диджей»): своя папка с треками, подборки под
настроение и пара слов ведущего между треками. Играет тот же проигрыватель, что и радио (radio.Radio: ffmpeg → наш
вывод звука), поэтому «пауза», «громче», «стоп» и приглушение, пока ассистент говорит, работают как у радио.

  • Library — список треков папки (рекурсивно): название, исполнитель, альбом, год, жанр — из тегов (ID3 у mp3,
    Vorbis у flac/ogg/opus; свой маленький разбор, без сторонних библиотек), иначе из имени файла
    («Кино - Звезда по имени Солнце.mp3») и папок («Кино/1989 - Звезда…/03 Песня.mp3»). Индекс — в файле рядом
    с настройками, пересчитывается по времени изменения файлов: тысячи треков — секунды один раз, дальше мгновенно.
  • match — что играть по просьбе: исполнитель, название, альбом, жанр, настроение («спокойное», «для работы»,
    «бодрое») и «любимое».
  • Dj — очередь, «дальше», «что играет», «в любимое» и фраза ведущего перед треком (intro): коротко, своими словами,
    не перед каждым треком (каждый dj_every-й), без выдумок — только то, что есть в тегах.
"""

import base64
import hashlib
import json
import logging
import os
import random
import re
import struct
import threading
import time
from pathlib import Path

log = logging.getLogger("dewiar.mymusic")
AUDIO_EXT = {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".wma"}
MAX_TRACKS = 20000

# настроение → слова в жанре, названии, папке. «Любимое» — отдельный список (Dj.favs)
MOODS = {
    "calm": ("Спокойное", "спокойн тих расслаб релакс отдох медлен вечер сон уют нежн лирич мягк",
             "ambient chill lounge jazz classical acoustic piano relax lofi lo-fi new age instrumental эмбиент джаз "
             "классика лаунж релакс акустика фортепиано инструментал"),
    "work": ("Для работы", "работ сосредоточ фокус учеб учит думат фон фонов",
             "ambient classical instrumental lofi lo-fi soundtrack post-rock piano электрон эмбиент классика "
             "инструментал саундтрек"),
    "energy": ("Бодрое", "бодр энерг весел драйв зарядк спорт трениров пробежк утр танц",
               "rock pop dance electronic edm house punk metal disco рок поп танц электрон хаус диско панк"),
    "russian": ("Русское", "русск наш отечеств",
                "русский рок русская эстрада шансон бард russian"),
}
MOOD_WORD = {w: k for k, (_, ws, _) in MOODS.items() for w in ws.split()}


def _stem(w):
    return w.lower().replace("ё", "е")[:6]


# ---------- теги: ID3 (mp3), Vorbis comment (flac, ogg, opus) ----------

def _dec(b, enc):
    try:
        if enc == 0:
            return b.decode("latin-1").rstrip("\0")
        if enc == 1:
            return b.decode("utf-16").rstrip("\0")
        if enc == 2:
            return b.decode("utf-16-be").rstrip("\0")
        return b.decode("utf-8", "replace").rstrip("\0")
    except Exception:  # noqa: BLE001
        return ""


def _fix_cp1251(s):
    """Старые русские mp3: теги в cp1251, а записаны как latin-1 («Êèíî» вместо «Кино»)."""
    if s and all(ord(c) < 256 for c in s) and sum(0xC0 <= ord(c) <= 0xFF for c in s) >= max(2, len(s) // 3):
        try:
            return s.encode("latin-1").decode("cp1251")
        except Exception:  # noqa: BLE001
            return s
    return s


def _id3(f):
    out = {}
    head = f.read(10)
    if len(head) == 10 and head[:3] == b"ID3":
        ver = head[3]
        size = (head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]
        data = f.read(min(size, 2_000_000))
        i = 0
        want = {"TIT2": "title", "TPE1": "artist", "TALB": "album", "TDRC": "year", "TYER": "year", "TCON": "genre",
                "TT2": "title", "TP1": "artist", "TAL": "album", "TYE": "year", "TCO": "genre"}
        while i + 10 <= len(data):
            if ver == 2:
                fid, fsz, hl = data[i:i + 3].decode("latin-1", "replace"), int.from_bytes(data[i + 3:i + 6], "big"), 6
            else:
                fid = data[i:i + 4].decode("latin-1", "replace")
                raw = data[i + 4:i + 8]
                fsz = ((raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]) if ver == 4 else int.from_bytes(raw, "big")
                hl = 10
            if not fid.strip("\0") or fsz <= 0 or i + hl + fsz > len(data):
                break
            if fid in want and want[fid] not in out:
                body = data[i + hl:i + hl + fsz]
                if body:
                    v = _dec(body[1:], body[0]).split("\0")[0].strip()
                    out[want[fid]] = _fix_cp1251(v) if body[0] == 0 else v
            i += hl + fsz
    if not out.get("title"):
        try:
            f.seek(-128, os.SEEK_END)
            t = f.read(128)
            if t[:3] == b"TAG":
                g = lambda a, b: _fix_cp1251(t[a:b].split(b"\0")[0].decode("latin-1").strip())  # noqa: E731
                out.update({k: v for k, v in (("title", g(3, 33)), ("artist", g(33, 63)), ("album", g(63, 93)),
                                              ("year", g(93, 97))) if v})
        except OSError:
            pass
    return out


def _vorbis_block(b):
    out = {}
    try:
        n = struct.unpack("<I", b[:4])[0]
        p = 4 + n
        cnt = struct.unpack("<I", b[p:p + 4])[0]
        p += 4
        for _ in range(min(cnt, 200)):
            ln = struct.unpack("<I", b[p:p + 4])[0]
            p += 4
            kv = b[p:p + ln].decode("utf-8", "replace")
            p += ln
            if "=" in kv:
                k, v = kv.split("=", 1)
                k = {"TITLE": "title", "ARTIST": "artist", "ALBUM": "album", "DATE": "year", "GENRE": "genre"}.get(k.upper())
                if k and k not in out:
                    out[k] = v.strip()
    except (struct.error, IndexError):
        pass
    return out


def _flac(f):
    if f.read(4) != b"fLaC":
        return {}
    while True:
        h = f.read(4)
        if len(h) < 4:
            return {}
        last, kind, size = h[0] & 0x80, h[0] & 0x7F, int.from_bytes(h[1:4], "big")
        if kind == 4:
            return _vorbis_block(f.read(size))
        f.seek(size, os.SEEK_CUR)
        if last:
            return {}


def _ogg(f):
    data = f.read(200_000)
    for mark in (b"\x03vorbis", b"OpusTags"):
        i = data.find(mark)
        if i >= 0:
            return _vorbis_block(data[i + len(mark):])
    return {}


def read_tags(path):
    ext = Path(path).suffix.lower()
    try:
        with open(path, "rb") as f:
            if ext == ".mp3":
                return _id3(f)
            if ext == ".flac":
                return _flac(f)
            if ext in (".ogg", ".oga", ".opus"):
                return _ogg(f)
    except OSError:
        pass
    return {}


# ---------- обложки (№361, 27.10: «вместо крутящейся пластинки брать картинку из файла или каталога») ----------
# Порядок: картинка внутри файла (ID3 APIC/PIC у mp3, PICTURE у flac) → картинка в папке альбома (cover, folder,
# front, album, albumart…) → нет (пластинка остаётся заглушкой). Найденное кладём в кэш (state/covers) — одна на
# альбом в папке, чтобы не вынимать заново на каждый трек.
COVER_NAMES = ("cover", "folder", "front", "album", "albumart", "albumartsmall", "обложка", "artwork", "art")
IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
MAX_ART = 12_000_000


def _img_kind(b):
    if b[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return ".webp"
    return ""


def _art_id3(f):
    """-> (байты, расширение) обложки из ID3v2 (APIC — v2.3/2.4, PIC — v2.2); лицевая (тип 3) — в приоритете."""
    head = f.read(10)
    if len(head) < 10 or head[:3] != b"ID3":
        return None
    ver, flags = head[3], head[5]
    size = (head[6] << 21) | (head[7] << 14) | (head[8] << 7) | head[9]
    data = f.read(min(size, MAX_ART + 4096))
    if flags & 0x80:                                   # unsynchronisation: 0xFF 0x00 → 0xFF
        data = data.replace(b"\xff\x00", b"\xff")
    i, best = 0, None
    while i + 10 <= len(data):
        if ver == 2:
            fid, fsz, hl = data[i:i + 3], int.from_bytes(data[i + 3:i + 6], "big"), 6
        else:
            fid = data[i:i + 4]
            raw = data[i + 4:i + 8]
            fsz = ((raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]) if ver == 4 else int.from_bytes(raw, "big")
            hl = 10
        if not fid.strip(b"\0") or fsz <= 0 or i + hl + fsz > len(data):
            break
        if fid in (b"APIC", b"PIC"):
            body = data[i + hl:i + hl + fsz]
            # тип картинки — сразу после MIME (APIC) или трёх букв формата (PIC); сама картинка — по сигнатуре
            ptype = body[4] if fid == b"PIC" else (body[body.find(b"\0", 1) + 1] if body.find(b"\0", 1) > 0 else 0)
            for mark in (b"\xff\xd8\xff", b"\x89PNG", b"RIFF"):
                k = body.find(mark, 2, 600)
                if k > 0:
                    img = body[k:]
                    if _img_kind(img) and (best is None or ptype == 3):
                        best = (img, _img_kind(img))
                    break
            if best and ptype == 3:
                break
        i += hl + fsz
    return best


def _art_flac(f):
    if f.read(4) != b"fLaC":
        return None
    best = None
    while True:
        h = f.read(4)
        if len(h) < 4:
            return best
        last, kind, size = h[0] & 0x80, h[0] & 0x7F, int.from_bytes(h[1:4], "big")
        if kind == 6 and size < MAX_ART:
            b = f.read(size)
            try:
                ptype = struct.unpack(">I", b[:4])[0]
                ml = struct.unpack(">I", b[4:8])[0]
                p = 8 + ml
                dl = struct.unpack(">I", b[p:p + 4])[0]
                p += 4 + dl + 16
                n = struct.unpack(">I", b[p:p + 4])[0]
                img = b[p + 4:p + 4 + n]
                if _img_kind(img) and (best is None or ptype == 3):
                    best = (img, _img_kind(img))
            except struct.error:
                pass
        else:
            f.seek(size, os.SEEK_CUR)
        if last:
            return best


def _art_folder(d):
    """Картинка альбома рядом с треками: cover.jpg, folder.jpg, front.png… (регистр не важен); одна картинка в
    папке — тоже она."""
    try:
        imgs = [x for x in Path(d).iterdir() if x.suffix.lower() in IMG_EXT and x.is_file() and not x.name.startswith(".")]
    except OSError:
        return None
    for name in COVER_NAMES:
        for x in imgs:
            if x.stem.lower() == name or (name == "albumart" and x.stem.lower().startswith("albumart")):
                return x
    return imgs[0] if len(imgs) == 1 else None


class Covers:
    """Обложка трека -> путь к картинке (в кэше или в папке альбома) или None. Запоминает и «нет обложки»."""

    def __init__(self, cache_dir):
        self.dir = Path(cache_dir)
        self._known = {}
        self._lock = threading.Lock()

    def get(self, t):
        path = t.get("path") or ""
        key = hashlib.sha1(f"{os.path.dirname(path)}|{t.get('album') or ''}".encode("utf-8", "replace")).hexdigest()[:20]
        with self._lock:
            if key in self._known:
                return self._known[key]
        found = None
        for ext in IMG_EXT:
            c = self.dir / (key + ext)
            if c.exists():
                found = str(c)
                break
        if not found:
            art = None
            try:
                with open(path, "rb") as f:
                    ext = Path(path).suffix.lower()
                    art = _art_id3(f) if ext == ".mp3" else _art_flac(f) if ext == ".flac" else None
            except OSError:
                art = None
            if art:
                try:
                    self.dir.mkdir(parents=True, exist_ok=True)
                    c = self.dir / (key + art[1])
                    c.write_bytes(art[0])
                    found = str(c)
                except OSError as e:
                    log.info("Обложка не сохранилась: %s", e)
            if not found:
                x = _art_folder(os.path.dirname(path))
                found = str(x) if x else None
        with self._lock:
            self._known[key] = found
        return found


def from_name(path, root):
    """Без тегов: «Исполнитель - Название», «03. Название» в папке «Исполнитель/Альбом»."""
    p = Path(path)
    stem = re.sub(r"^\s*\d{1,3}\s*[-._)]?\s+", "", p.stem).replace("_", " ").strip()
    out = {}
    m = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", stem)
    if m:
        out["artist"], out["title"] = m.group(1).strip(), m.group(2).strip()
    else:
        out["title"] = stem
    try:
        parts = p.relative_to(root).parts[:-1]
    except ValueError:
        parts = ()
    if parts:
        album = re.sub(r"^\s*(?:19|20)\d\d\s*[-–—.]\s*", "", parts[-1]).strip()
        y = re.match(r"^\s*((?:19|20)\d\d)\b", parts[-1])
        if len(parts) >= 2:
            out.setdefault("artist", parts[-2])
            out["album"] = album
        else:
            out.setdefault("artist", album) if not m else out.setdefault("album", album)
        if y:
            out["year"] = y.group(1)
    return out


class Library:
    """Треки папки: [{path, title, artist, album, year, genre}]. Индекс — cache_path (JSON), обновляется scan()."""

    def __init__(self, folder_fn, cache_path):
        self.folder_fn, self.cache_path = folder_fn, Path(cache_path)
        self.tracks, self.folder, self.scanned = [], "", 0.0
        self._lock = threading.Lock()
        self.busy = False
        # ход чтения папки (№361: «при сканировании сетевой папки было бы хорошо видеть прогресс»):
        # phase find — ищем файлы (found растёт), tags — читаем теги (done из total); on_progress — не чаще 2 раз в секунду
        self.progress = {}
        self.on_progress = None
        self.prog_every = 0.5
        self._prog_t = 0.0
        try:
            d = json.loads(self.cache_path.read_text(encoding="utf-8"))
            self.tracks, self.folder, self.scanned = d.get("tracks", []), d.get("folder", ""), d.get("ts", 0.0)
        except (OSError, ValueError):
            pass

    def root(self):
        f = (self.folder_fn() or "").strip()
        return Path(os.path.expanduser(f)) if f else None

    def scan(self, force=False):
        """Пройти папку: новые и изменённые файлы — прочитать теги, остальное взять из индекса. -> число треков."""
        root = self.root()
        if not root or not root.is_dir():
            with self._lock:
                self.tracks, self.folder = [], str(root or "")
            return 0
        with self._lock:
            if self.busy:
                return len(self.tracks)
            self.busy = True
        try:
            old = {t["path"]: t for t in self.tracks} if (self.folder == str(root) and not force) else {}
            out = []
            found = []
            self._prog({"phase": "find", "found": 0}, force=True)
            for dp, dns, fns in os.walk(root):                 # сначала — какие файлы есть (сетевой диск — тут дольше всего)
                dns[:] = [d for d in dns if not d.startswith(".")]
                for fn in fns:
                    if Path(fn).suffix.lower() in AUDIO_EXT and not fn.startswith("."):
                        found.append(os.path.join(dp, fn))
                self._prog({"phase": "find", "found": len(found)})
                if len(found) >= MAX_TRACKS:
                    break
            total = len(found)
            for n, p in enumerate(found[:MAX_TRACKS]):
                if n % 25 == 0:
                    self._prog({"phase": "tags", "done": n, "total": total})
                try:
                    mt = os.path.getmtime(p)
                except OSError:
                    continue
                t = old.get(p)
                if not t or t.get("mt") != mt:
                    info = from_name(p, root)
                    info.update({k: v for k, v in read_tags(p).items() if v})
                    t = {"path": p, "mt": mt, "title": info.get("title") or Path(p).stem,
                         "artist": info.get("artist", ""), "album": info.get("album", ""),
                         "year": str(info.get("year", ""))[:4], "genre": re.sub(r"^\(\d+\)", "", info.get("genre", "")).strip()}
                out.append(t)
            out.sort(key=lambda t: (t["artist"].lower(), t["album"].lower(), t["path"]))
            with self._lock:
                self.tracks, self.folder, self.scanned = out, str(root), time.time()
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.cache_path.with_suffix(".tmp")
                tmp.write_text(json.dumps({"folder": self.folder, "ts": self.scanned, "tracks": out}, ensure_ascii=False),
                               encoding="utf-8")
                os.replace(tmp, self.cache_path)
            except OSError as e:
                log.info("Моя музыка: индекс не записался: %s", e)
            log.info("🎵 Моя музыка: %d треков в «%s»", len(out), root)
            return len(out)
        finally:
            self.busy = False
            self.progress = {}

    def _prog(self, p, force=False):
        self.progress = p
        now = time.monotonic()
        if self.on_progress and (force or now - self._prog_t >= self.prog_every):
            self._prog_t = now
            try:
                self.on_progress(dict(p))
            except Exception:  # noqa: BLE001
                log.exception("Моя музыка: ход чтения")

    def stats(self):
        tr = self.tracks
        return {"tracks": len(tr), "artists": len({t["artist"].lower() for t in tr if t["artist"]}),
                "genres": len({t["genre"].lower() for t in tr if t["genre"]}), "folder": self.folder}

    def artists(self):
        n = {}
        for t in self.tracks:
            if t["artist"]:
                n[t["artist"]] = n.get(t["artist"], 0) + 1
        return sorted(n, key=lambda a: -n[a])

    def mood_of(self, t):
        hay = f"{t['genre']} {t['album']} {t['path']}".lower()
        return [k for k, (_, _, tags) in MOODS.items() if any(w in hay for w in tags.split())]

    def match(self, query, favs=()):
        """Просьба → (список треков, что поняли «Кино» / «спокойное» / «любимое» / ""), пустая — вся папка."""
        q = (query or "").lower().replace("ё", "е").strip(" .,!?«»\"")
        tr = self.tracks
        if not tr:
            return [], ""
        if not q:
            return list(tr), ""
        if re.search(r"любим|избранн", q):
            fs = set(favs)
            got = [t for t in tr if t["path"] in fs]
            return got, "любимое"
        for a in self.artists():                          # исполнитель целиком в просьбе: «поставь Кино»
            al = a.lower().replace("ё", "е")
            if len(al) >= 3 and re.search(r"(?<!\w)" + re.escape(al) + r"(?!\w)", q):
                return [t for t in tr if t["artist"].lower().replace("ё", "е") == al], a
        for key in ("title", "album"):                    # название песни или альбома
            for t in tr:
                v = t[key].lower().replace("ё", "е")
                if len(v) >= 4 and v in q:
                    return ([t] + [x for x in tr if x["artist"] == t["artist"] and x is not t]) if key == "title" else \
                        [x for x in tr if x["album"] == t["album"]], t[key]
        words = [_stem(w) for w in re.findall(r"[а-яa-z0-9-]+", q)]
        moods = [MOOD_WORD[w] for w in words if w in MOOD_WORD] or \
                [MOOD_WORD[k] for w in words for k in MOOD_WORD if len(w) >= 4 and k.startswith(w[:4])]
        if moods:
            m = moods[0]
            got = [t for t in tr if m in self.mood_of(t)]
            return got, MOODS[m][0].lower()
        gw = [w for w in re.findall(r"[а-яa-z0-9-]{3,}", q)]
        for t in tr:                                      # жанр словом из тегов: «поставь джаз из моей музыки»
            g = t["genre"].lower()
            if g and any(w[:4] in g for w in gw):
                return [x for x in tr if x["genre"].lower() == g], t["genre"]
        return [], ""


def label(t):
    a = t.get("artist") or ""
    return f"{a} — «{t['title']}»" if a else f"«{t['title']}»"


INTROS_FIRST = ["Включаю {what}. Начнём с {track}.", "{What} — поехали: {track}.", "Ставлю {what}. Первым — {track}."]
INTROS = ["Дальше — {track}.", "А теперь {track}.", "Следующий — {track}.", "Продолжаем: {track}.", "Сейчас прозвучит {track}."]


def intro(t, first=False, what="музыку из вашей папки", prev=None, rnd=random):
    """Фраза ведущего перед треком — только из тегов, без выдумок: альбом и год, если есть; тот же исполнитель —
    «ещё …»."""
    tr = label(t)
    if first:
        s = rnd.choice(INTROS_FIRST).format(what=what, What=what[:1].upper() + what[1:], track=tr)
    elif prev and prev.get("artist") and prev.get("artist") == t.get("artist"):
        s = f"Ещё {t['artist']}: «{t['title']}»."
    else:
        s = rnd.choice(INTROS).format(track=tr)
    if t.get("album") and t.get("year") and rnd.random() < 0.5 and not first:
        s = s.rstrip(".") + f", с альбома «{t['album']}», {t['year']}."
    return s


class Dj:
    """Очередь и ведущий. play_fn(track) — запустить трек (через radio.Radio), say_fn(text) — сказать. Номер трека в
    очереди — pos; history — что уже играло (для «что играет» и «предыдущий»)."""

    def __init__(self, lib, favs_fn):
        self.lib, self.favs_fn = lib, favs_fn
        self.queue, self.pos, self.what, self.since_talk = [], -1, "", 0

    def start(self, tracks, what="", shuffle=True):
        q = list(tracks)
        if shuffle:
            random.shuffle(q)
        self.queue, self.pos, self.what, self.since_talk = q, -1, what, 0
        return self.next()

    def current(self):
        return self.queue[self.pos] if 0 <= self.pos < len(self.queue) else None

    def next(self):
        if not self.queue:
            return None
        self.pos += 1
        if self.pos >= len(self.queue):                   # очередь кончилась — по кругу, заново перемешав
            random.shuffle(self.queue)
            self.pos = 0
        return self.queue[self.pos]

    def prev(self):
        if self.pos > 0:
            self.pos -= 1
        return self.current()

    def station(self, t):
        """Трек → «станция» для radio.Radio."""
        st = {"name": label(t).replace("«", "").replace("»", ""), "url": t["path"], "tags": "моя-музыка",
              "_track": t, "_mine": True}
        art = self.covers.get(t) if getattr(self, "covers", None) else None
        if art:
            st["art"] = art                                # обложка — виджет и студия показывают её вместо пластинки
        return st

    def now_text(self):
        t = self.current()
        if not t:
            return ""
        s = f"Сейчас играет {label(t)}"
        extra = ", ".join(x for x in (f"альбом «{t['album']}»" if t.get("album") else "", t.get("year") or "",
                                      t.get("genre") or "") if x)
        return s + (f" — {extra}" if extra else "") + (f". Подборка «{self.what}»." if self.what else ".")
