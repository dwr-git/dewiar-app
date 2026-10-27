"""Знания на этом компьютере: документы пользователя в папке «Знания» (внутри папки ассистента).

Без сервера и без интернета: текст достаётся из файлов (.md .txt .html .pdf .docx .odt .csv; extract() берёт и
workspace.read), режется на отрывки ~900 знаков с нахлёстом 150 и ищется по словам (BM25 со своим грубым русским
«стеммингом» — отрезаем окончания; он не тот же, что в recall.py). В индексе — отрывки текста, а не слова: основы
считаются при каждом поиске. Индекс хранится в STATE_DIR/knowledge.json (входит в резервную копию) и пересчитывается
только для изменившихся файлов (по времени и размеру).
"""

import html
import json
import logging
import math
import os
import re
import subprocess
import threading
import zipfile
from pathlib import Path

log = logging.getLogger("dewiar.knowledge")
FOLDER = "Знания"
EXTS = {".md", ".txt", ".html", ".htm", ".pdf", ".docx", ".odt", ".csv"}
CHUNK, OVERLAP = 900, 150
MAX_FILE = 60 * 1024 * 1024
README = """# Знания

Положите сюда свои документы — инструкции, договоры, регламенты, книги, конспекты.
Ассистент найдёт в них ответ, когда вы спросите: «что в моих документах про отпуск?».

Подходят: PDF, Word (.docx), OpenOffice (.odt), текст (.txt, .md), веб-страницы (.html), таблицы .csv.
Всё остаётся на этом компьютере. Папки внутри — можно.
"""

_END = re.compile(r"(ами|ями|ого|его|ому|ему|ыми|ими|ах|ях|ов|ев|ей|ой|ий|ый|ая|яя|ое|ее|ые|ие|ую|юю|ом|ем|ам|ям|"
                  r"ть|ти|ла|ло|ли|ет|ит|ут|ют|ат|ят|ешь|ишь|ем|им|ете|ите|ся|сь|а|я|о|е|ы|и|у|ю|ь)$")


def stem(w):
    """Короткие и нерусские слова — как есть; иначе без одного окончания (основа не короче 3 букв)."""
    w = w.lower().replace("ё", "е")
    if len(w) <= 4 or not re.match(r"[а-я]", w):
        return w
    s = _END.sub("", w)
    return s if len(s) >= 3 else w[:4]


def words(text):
    return [stem(w) for w in re.findall(r"[\wё]+", text.lower()) if len(w) > 1]


# ---------- извлечение текста ----------

def _xml_text(xml, para_tag):
    """Текст из XML документа Word/ODT: конец абзаца para_tag — перевод строки, прочие теги — прочь."""
    xml = re.sub(rf"</{para_tag}>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def extract(p: Path) -> str:
    """Текст документа; незнакомый формат — "". PDF — через pypdf (если не установлен — RuntimeError), до 500 страниц;
    скан без текстового слоя даёт пустой текст."""
    ext = p.suffix.lower()
    if ext in (".md", ".txt", ".csv"):
        return p.read_text(encoding="utf-8", errors="replace")
    if ext in (".html", ".htm"):
        t = p.read_text(encoding="utf-8", errors="replace")
        t = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", t)
        t = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>|</div>|</tr>", "\n", t)
        return html.unescape(re.sub(r"<[^>]+>", " ", t))
    if ext == ".docx":
        with zipfile.ZipFile(p) as z:
            return _xml_text(z.read("word/document.xml").decode("utf-8", "replace"), "w:p")
    if ext == ".odt":
        with zipfile.ZipFile(p) as z:
            return _xml_text(z.read("content.xml").decode("utf-8", "replace"), "text:p")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError("для PDF нужна библиотека pypdf") from e
        r = PdfReader(str(p))
        return "\n".join((pg.extract_text() or "") for pg in r.pages[:500])
    return ""


def chunks(text):
    """Отрывки до CHUNK знаков, конец — по абзацу или предложению во второй половине; соседние перекрываются
    на OVERLAP, чтобы ответ на стыке не потерялся."""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    out, i = [], 0
    while i < len(text):
        end = min(len(text), i + CHUNK)
        if end < len(text):                                   # режем по абзацу или предложению
            cut = max(text.rfind("\n\n", i + CHUNK // 2, end), text.rfind(". ", i + CHUNK // 2, end))
            if cut > 0:
                end = cut + 1
        piece = text[i:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        i = max(end - OVERLAP, i + 1)                         # i + 1 — чтобы не зациклиться на коротком отрывке
    return out


# Свои папки (идея 16.10: «поиск по любым папкам»): кроме «Знаний» — папки, которые человек выбрал в студии (Документы,
# рабочая папка…). В индексе их файлы — под ключом «@<полный путь>»; индексируются в фоне (watch), с пределами, чтобы
# не перемалывать весь диск: не больше FOLDER_FILES файлов на папку, файл до EXTRA_MAX, всего до EXTRA_CHUNKS отрывков;
# служебные и скрытые папки пропускаются. Поиск — тот же, по всем сразу; у результата есть key, им открывают файл.
SKIP_DIRS = {"node_modules", "__pycache__", "venv", "site-packages", "AppData", "Library", "$RECYCLE.BIN",
             "System Volume Information", "Windows", "Program Files", "Program Files (x86)", "snap", "go", "target"}
FOLDER_FILES, EXTRA_MAX, EXTRA_CHUNKS = 4000, 30 * 1024 * 1024, 80000


class Knowledge:
    def __init__(self, workspace, index_path, folders=None, extra=None):
        self.ws, self.index_path = workspace, Path(index_path)
        self.folders = folders or (lambda: [])   # -> [полный путь своей папки, …] (настройка knowledge.folders)
        self.extra = extra or (lambda: [])       # -> папки знаний персонажей (27.10): индексируются, но в общий поиск не идут
        self._lock = threading.Lock()
        self.index = self._load()          # rel | «@полный путь» -> {"mtime", "size", "chunks": [..], "error"}
        self._tok = {}                     # ключ -> [основы слов каждого отрывка]: не считать их заново на каждый поиск
        self.fstate = {}                   # своя папка -> {files, indexed, skipped, busy, error}
        self.kick = threading.Event()

    @property
    def root(self):
        """Папка «Знания»; при первом обращении кладёт в неё «О папке.md» с объяснением (в индекс он не входит)."""
        d = self.ws.root / FOLDER
        if not (d / "О папке.md").exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / "О папке.md").write_text(README, encoding="utf-8")
        return d

    def _load(self):
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.index_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.index, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.index_path)
        except OSError as e:
            log.warning("Индекс знаний не сохранён: %s", e)

    def files(self):
        root = self.root
        out = []
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTS and not any(x.startswith(".") for x in p.relative_to(root).parts) \
                    and p.name != "О папке.md":
                out.append(p)
        return out

    def has_files(self):
        """Есть ли где искать: файлы в «Знаниях» или уже прочитанные файлы своих папок."""
        try:
            return bool(self.files()) or any(k.startswith("@") for k in self.index)
        except OSError:
            return False

    def refresh(self):
        """Пересчитать отрывки для новых и изменившихся файлов, забыть удалённые. -> сколько файлов обработано.
        Ошибка чтения файла не прерывает остальные — она остаётся в записи индекса (её видно в списке студии)."""
        with self._lock:
            root, seen, changed = self.root, set(), 0
            for p in self.files():
                rel = p.relative_to(root).as_posix()
                seen.add(rel)
                st = p.stat()
                old = self.index.get(rel)
                if old and old.get("mtime") == st.st_mtime and old.get("size") == st.st_size:
                    continue
                entry = {"mtime": st.st_mtime, "size": st.st_size, "chunks": []}
                try:
                    if st.st_size > MAX_FILE:
                        raise RuntimeError("файл больше 60 МБ")
                    entry["chunks"] = chunks(extract(p))
                    if not entry["chunks"]:
                        entry["error"] = "в файле нет текста (скан без распознавания?)"
                except Exception as e:  # noqa: BLE001
                    entry["error"] = str(e)[:200]
                    log.info("Знания: %s — %s", rel, entry["error"])
                self.index[rel] = entry
                self._forget(rel)
                changed += 1
            for rel in list(self.index):
                if rel not in seen and not rel.startswith("@"):
                    del self.index[rel]
                    self._forget(rel)
                    changed += 1
            if changed:
                self._save()
            return changed

    def _forget(self, key):
        self._tok.pop(key, None)

    def list(self):
        self.refresh()
        return [{"path": rel, "size": e["size"], "chunks": len(e["chunks"]), "error": e.get("error", "")}
                for rel, e in sorted(self.index.items()) if not rel.startswith("@")]

    # ---------- свои папки ----------

    def _walk(self, folder):
        """Файлы своей папки, подходящие для поиска, — по порядку, без скрытых и служебных папок. -> (список, урезано ли)."""
        out, cut = [], False
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith((".", "$")) and d not in SKIP_DIRS)
            for f in sorted(filenames):
                if f.startswith((".", "~$")) or Path(f).suffix.lower() not in EXTS:
                    continue
                if len(out) >= FOLDER_FILES:
                    return out, True
                out.append(Path(dirpath) / f)
        return out, cut

    def refresh_folders(self):
        """Своя папка: новые и изменившиеся файлы — в индекс, пропавшие и убранные папки — из индекса. Долго (PDF,
        тысячи файлов) — поэтому из фонового потока (watch); поиск в это время работает по тому, что уже есть."""
        folders = []
        for f in list(self.folders() or []) + list(self.extra() or []):
            p = Path(os.path.expanduser(str(f))).resolve()
            if p.is_dir() and p not in folders:
                folders.append(p)
        seen, changed = set(), 0
        total = sum(len(e["chunks"]) for k, e in self.index.items() if k.startswith("@"))
        for folder in folders:
            st = self.fstate.setdefault(str(folder), {})
            st.update(busy=True, error="")
            try:
                files, cut = self._walk(folder)
            except OSError as e:
                st.update(busy=False, error=str(e)[:200])
                continue
            st.update(files=len(files), skipped=cut)
            done = 0
            for p in files:
                key = "@" + p.as_posix()
                seen.add(key)
                try:
                    stt = p.stat()
                except OSError:
                    continue
                old = self.index.get(key)
                if old and old.get("mtime") == stt.st_mtime and old.get("size") == stt.st_size:
                    done += 1
                    continue
                entry = {"mtime": stt.st_mtime, "size": stt.st_size, "chunks": []}
                try:
                    if stt.st_size > EXTRA_MAX:
                        raise RuntimeError("файл больше 30 МБ")
                    if total > EXTRA_CHUNKS:
                        raise RuntimeError("в своих папках уже слишком много текста — остальное не ищется")
                    entry["chunks"] = chunks(extract(p))
                    if not entry["chunks"]:
                        entry["error"] = "в файле нет текста"
                except Exception as e:  # noqa: BLE001
                    entry["error"] = str(e)[:200]
                total += len(entry["chunks"]) - len((old or {}).get("chunks") or [])
                with self._lock:
                    self.index[key] = entry
                    self._forget(key)
                changed += 1
                done += 1
                st["indexed"] = done
                if changed % 100 == 0:
                    with self._lock:
                        self._save()
            st.update(indexed=done, busy=False)
        with self._lock:
            for key in [k for k in self.index if k.startswith("@") and k not in seen]:
                del self.index[key]
                self._forget(key)
                changed += 1
            for k in [k for k in self.fstate if Path(k) not in folders]:
                del self.fstate[k]
            if changed:
                self._save()
        if changed:
            log.info("Знания: свои папки — обновлено файлов %d", changed)
        return changed

    def watch(self, every=1200):
        """Фоновый поток: свои папки — при запуске, раз в every секунд и сразу по kick (добавили папку в студии)."""
        while True:
            try:
                self.refresh_folders()
            except Exception:  # noqa: BLE001
                log.exception("Знания: свои папки")
            self.kick.wait(every)
            self.kick.clear()

    def folders_state(self):
        """Для студии: [{path, name, files, indexed, chunks, busy, skipped, error}]."""
        out = []
        for f in self.folders() or []:
            p = Path(os.path.expanduser(str(f))).resolve()
            st = self.fstate.get(str(p), {})
            pre = "@" + p.as_posix() + "/"
            n = sum(len(e["chunks"]) for k, e in list(self.index.items()) if k.startswith(pre))
            out.append({"path": str(p), "name": p.name or str(p), "exists": p.is_dir(), "files": st.get("files"), "indexed": st.get("indexed"),
                        "chunks": n, "busy": bool(st.get("busy")), "skipped": bool(st.get("skipped")), "error": st.get("error", "")})
        return out

    def label(self, key):
        """Как показывать файл: «Знания/…» или «<своя папка>/…»."""
        if not key.startswith("@"):
            return key
        p = Path(key[1:])
        for f in list(self.folders() or []) + list(self.extra() or []):
            base = Path(os.path.expanduser(str(f))).resolve()
            try:
                return (Path(base.name) / p.relative_to(base)).as_posix()
            except ValueError:
                continue
        return p.name

    def file_path(self, key):
        """Ключ из результата поиска -> настоящий путь к файлу (только то, что есть в индексе) или None."""
        key = str(key or "")
        if key not in self.index:
            return None
        p = Path(key[1:]) if key.startswith("@") else self.root / key
        return p if p.is_file() else None

    def search(self, query, limit=5, within=None):
        """-> [{path, score, text}] — лучшие отрывки, не больше двух из файла. Путь файла тоже участвует в поиске.
        within — только в этих своих папках (знания персонажа из папки на компьютере)."""
        self.refresh()
        q = [w for w in words(query) if len(w) > 2] or words(query)     # короткие основы — только если других нет
        if not q:
            return []
        with self._lock:
            items = list(self.index.items())
        def pre(fs):
            return tuple("@" + Path(os.path.expanduser(str(f))).resolve().as_posix().rstrip("/") + "/" for f in fs)
        if within is not None:
            items = [x for x in items if x[0].startswith(pre(within))]
        else:                                    # общий поиск: «Знания» и свои папки, а папки персонажей — только их
            mine, only = pre(self.folders() or []), pre(self.extra() or [])
            items = [x for x in items if not (x[0].startswith(only) and not x[0].startswith(mine))] if only else items
        docs = []
        for rel, e in items:
            tok = self._tok.get(rel)
            if tok is None or len(tok) != len(e["chunks"]):
                name = self.label(rel)
                tok = []
                for c in e["chunks"]:
                    ws_ = words(name + " " + c)
                    cnt = {}
                    for w in ws_:
                        cnt[w] = cnt.get(w, 0) + 1
                    tok.append((cnt, len(ws_)))       # счётчик основ и длина — поиск по тысячам файлов за доли секунды
                self._tok[rel] = tok
            docs.extend((rel, i, c, tok[i]) for i, c in enumerate(e["chunks"]))
        if not docs:
            return []
        n = len(docs)
        avg = sum(d[3][1] for d in docs) / n or 1
        qs = set(q)
        df = {w: sum(1 for d in docs if w in d[3][0]) for w in qs}
        scored = []
        for rel, i, c, (cnt, ln) in docs:
            tf = {w: cnt[w] for w in qs if w in cnt}
            if not tf:
                continue
            s = 0.0
            for w, f in tf.items():
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                # BM25: k1=1.2, b=0.75 (как в recall.py)
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * ln / avg))
            s *= 1 + 0.3 * (len(tf) - 1)                        # совпало больше разных слов — выше
            scored.append((s, rel, i, c))
        scored.sort(key=lambda x: -x[0])
        out, per_file = [], {}
        for s, rel, i, c in scored:
            if per_file.get(rel, 0) >= 2:                       # не больше двух отрывков из одного файла
                continue
            per_file[rel] = per_file.get(rel, 0) + 1
            out.append({"path": self.label(rel), "key": rel, "score": round(s, 2), "text": c})
            if len(out) >= limit:
                break
        return out

    def add(self, name, data: bytes):
        """Документ из студии — в корень «Знаний» под свободным именем. Из name берётся только имя файла: путь
        от браузера не должен увести запись за пределы папки. -> путь внутри «Знаний»."""
        name = Path(str(name or "")).name.strip()
        if not name or Path(name).suffix.lower() not in EXTS:
            raise ValueError("такие файлы не подходят: нужны PDF, Word, ODT, текст, Markdown, HTML или CSV")
        dst = self.root / name
        n = 2
        while dst.exists():
            dst = self.root / f"{Path(name).stem} ({n}){Path(name).suffix}"
            n += 1
        dst.write_bytes(data)
        self.refresh()
        return dst.relative_to(self.root).as_posix()

    def remove(self, rel):
        """Документ — в корзину (как всё удаление в Dewiar, см. workspace.remove); путь проверяется — только внутри
        «Знаний». Не удалось отправить в корзину — ValueError, файл остаётся на месте."""
        p = (self.root / str(rel)).resolve()
        if self.root.resolve() not in p.parents or not p.is_file():
            raise ValueError("нет такого файла в «Знаниях»")
        import guard
        try:
            guard.trash([{"path": str(p), "dir": False, "files": 1, "size": p.stat().st_size}])
        except (guard.Blocked, OSError, subprocess.SubprocessError) as e:
            raise ValueError(f"не удалось убрать «{p.name}» в корзину: {e}") from e
        self.refresh()
        return True
