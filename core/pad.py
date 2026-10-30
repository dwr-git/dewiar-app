"""Блокнот у виджета (20.10, просьба владельца: «как в Obsidian — вкладки, одна открыта всегда, туда быстро кидаю, с чем
работаю сейчас: ссылки, разметку, картинки, таблицы, списки с галочками; дома правлю — на работе открыл, и там всё»).

Вкладка — обычная заметка Markdown в «Заметки/Блокнот/<название>.md»: её синхронизирует то же шифрованное хранилище,
что и все заметки (sync.py — компьютеры и телефон), и Obsidian, если он подключён. Картинки — в «Заметки/Блокнот/Вложения/»
(одна папка на все вкладки — переименование вкладки ссылок не ломает) и уходят своим устройствам шифрованным конвертом
(Close.natt_share, у каждого файла — его путь rel: другой компьютер кладёт его туда же).

Порядок вкладок и открытая — свои у каждого компьютера (настройки ui.pad); сами вкладки — общие."""
import base64
import logging
import re
import time
from pathlib import Path

log = logging.getLogger("dewiar.pad")
FOLDER = "Заметки/Блокнот"
ATT = "Вложения"
PAD_MAX = 300_000                      # как заметка в синхронизации (sync.NOTE_MAX)
IMG_MAX = 12 * 1048576
FIRST = "Главное"



def _same_file(a, b):
    """Один и тот же файл (в Windows «Заметки.md» и «заметки.md» — один)."""
    try:
        return a.samefile(b)
    except OSError:
        return False

class PadError(Exception):
    pass


def _name(s, default="Вкладка"):
    """Название вкладки = имя файла: без знаков, запрещённых в Windows, без точек по краям, до 60 знаков."""
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f#\[\]^]", " ", str(s or "")).strip(" .")
    s = re.sub(r"\s+", " ", s)[:60].strip(" .")
    return s or default


class Pad:
    def __init__(self, workspace, settings, emit=None, share=None):
        self.ws, self.s = workspace, settings
        self.emit = emit or (lambda *a, **k: None)
        self.share = share or (lambda rel, paths: None)      # картинки — своим устройствам (engine.note_files_out)

    # ---------- где лежит ----------
    def root(self) -> Path:
        d = self.ws.safe(FOLDER)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _path(self, name) -> Path:
        n = _name(name)
        p = self.root() / f"{n}.md"
        if p.parent != self.root():
            raise PadError("такой вкладки нет")
        return p

    def _ui(self):
        return dict(self.s.get("ui", "pad") or {})

    def _set_ui(self, **kw):
        cur = self._ui()
        cur.update(kw)
        self.s.update({"ui": {"pad": cur}})

    # ---------- вкладки ----------
    def tabs(self):
        """-> {tabs: [{name, mtime, size}], active}. Порядок — свой у компьютера (ui.pad.order), новые с других устройств —
        в конце. Пусто — заводим «Главное»."""
        root = self.root()
        files = {p.stem: p for p in root.glob("*.md") if p.is_file() and not p.name.startswith(".")}
        if not files:
            p = root / f"{FIRST}.md"
            p.write_text("", encoding="utf-8")
            files = {FIRST: p}
        order = [n for n in self._ui().get("order") or [] if n in files]
        rest = sorted((n for n in files if n not in order), key=lambda n: files[n].stat().st_mtime)
        names = order + rest
        out = []
        for n in names:
            try:
                st = files[n].stat()
            except OSError:
                continue
            out.append({"name": n, "mtime": st.st_mtime, "size": st.st_size})
        active = self._ui().get("active")
        if active not in files:
            active = names[0]
        return {"tabs": out, "active": active, "folder": FOLDER}

    def read(self, name):
        p = self._path(name)
        if not p.is_file():
            raise PadError("такой вкладки нет — её могли удалить на другом устройстве")
        self._set_ui(active=p.stem)
        return {"name": p.stem, "text": p.read_text(encoding="utf-8", errors="replace"), "mtime": p.stat().st_mtime}

    def write(self, name, text, base=None):
        """Сохранить вкладку. base — mtime, с которым страница её открыла: если файл с тех пор изменили на другом
        устройстве и текст другой — их вариант сохраняется рядом отдельной вкладкой «… (с другого устройства)», ничего
        не теряется. -> {mtime, conflict?}."""
        text = str(text or "").replace("\r\n", "\n")
        if len(text.encode("utf-8")) > PAD_MAX:
            raise PadError("вкладка слишком большая (до 300 КБ текста) — перенесите часть в новую вкладку")
        p = self._path(name)
        out = {}
        # GitHub №26 (29.10): было «+ 0.5» — правка с другого устройства в пределах полсекунды молча затиралась; страница
        # хранит mtime, который сама получила от save/open, — сравниваем точно (с запасом на округление float)
        if base is not None and p.is_file() and p.stat().st_mtime > float(base) + 0.001:
            theirs = p.read_text(encoding="utf-8", errors="replace")
            if theirs.strip() and theirs != text:
                q = self._free(f"{p.stem} (с другого устройства)")
                q.write_text(theirs, encoding="utf-8")
                out["conflict"] = q.stem
                log.info("Блокнот: «%s» правили и здесь, и на другом устройстве — их вариант во вкладке «%s»", p.stem, q.stem)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(p)
        out["mtime"] = p.stat().st_mtime
        self.emit("pad_saved", name=p.stem)
        return out

    def _free(self, name) -> Path:
        base = _name(name)
        p, k = self.root() / f"{base}.md", 2
        while p.exists():
            p, k = self.root() / f"{base} {k}.md", k + 1
        return p

    def new(self, name=""):
        p = self._free(name or "Вкладка")
        p.write_text("", encoding="utf-8")
        order = [t["name"] for t in self.tabs()["tabs"] if t["name"] != p.stem] + [p.stem]   # новая — справа от всех
        self._set_ui(order=order, active=p.stem)
        return dict(self.tabs(), created=p.stem)

    def rename(self, name, to):
        p = self._path(name)
        if not p.is_file():
            raise PadError("такой вкладки нет")
        to = _name(to)
        q = self.root() / f"{to}.md"
        # GitHub №28 (29.10): в Windows пути без учёта регистра — «заметки» → «Заметки» считалось «то же имя», и
        # переименование молча не делалось. Сравниваем строки имён; тот же файл в другом регистре — переименовываем
        if q.name == p.name:
            return self.tabs()
        if q.exists() and not _same_file(q, p):
            raise PadError("вкладка с таким названием уже есть")
        p.rename(q)
        ui = self._ui()
        self._set_ui(order=[to if n == p.stem else n for n in ui.get("order") or []], active=to if ui.get("active") == p.stem else ui.get("active"))
        return self.tabs()

    def delete(self, name):
        """В корзину (как всё удаление в Dewiar); последняя вкладка не удаляется — очищается."""
        p = self._path(name)
        if not p.is_file():
            return self.tabs()
        if len([x for x in self.root().glob("*.md") if x.is_file()]) <= 1:
            p.write_text("", encoding="utf-8")
            return self.tabs()
        self.ws.remove(p.relative_to(self.ws.ensure()).as_posix())
        self._set_ui(order=[n for n in self._ui().get("order") or [] if n != p.stem])
        return self.tabs()

    def order(self, names):
        self._set_ui(order=[_name(n) for n in names or []][:200])
        return True

    # ---------- картинки ----------
    def attach(self, name, filename, b64):
        """Картинка или файл во вкладку: «Заметки/Блокнот/Вложения/…» -> {line, path, url?}. Своим устройствам — следом."""
        try:
            data = base64.b64decode(str(b64 or "").split(",", 1)[-1])
        except (ValueError, TypeError) as e:
            raise PadError("файл не прочитался") from e
        if not data:
            raise PadError("пустой файл")
        if len(data) > IMG_MAX:
            raise PadError("файл больше 12 МБ")
        d = self.root() / ATT
        d.mkdir(parents=True, exist_ok=True)
        ext = re.sub(r"[^a-z0-9]", "", Path(str(filename or "")).suffix.lower())[:8] or "png"
        stem = _name(Path(str(filename or "")).stem, time.strftime("Снимок %d.%m %H-%M-%S"))[:50]
        out, k = d / f"{stem}.{ext}", 2
        while out.exists():
            out, k = d / f"{stem} ({k}).{ext}", k + 1
        out.write_bytes(data)
        link = f"{ATT}/{out.name}".replace("%", "%25").replace(" ", "%20").replace("(", "%28").replace(")", "%29")
        img = "." + ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
        rel = out.relative_to(self.ws.ensure()).as_posix()
        try:
            self.share(self._path(name).relative_to(self.ws.ensure()).as_posix(), [rel])
        except Exception as e:  # noqa: BLE001 — нет связи: картинка останется здесь, текст уйдёт синхронизацией
            log.info("Блокнот: картинка своим устройствам не ушла: %s", e)
        return {"line": f"![{out.stem}]({link})" if img else f"[{out.name}]({link})", "path": rel, "image": img}

    def file(self, link):
        """Картинка вкладки для показа: ссылка из текста («Вложения/…») -> {url: data:…}."""
        from urllib.parse import unquote
        rel = unquote(str(link or "")).lstrip("./")
        if not rel.startswith(ATT + "/") or ".." in rel:
            raise PadError("это не картинка блокнота")
        return self.ws.note_file(f"{FOLDER}/{rel}")
