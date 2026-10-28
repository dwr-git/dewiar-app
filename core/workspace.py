"""Рабочая папка ассистента (~/Dewiar, в Windows — «Документы\\Dewiar»): всё, что он делает, лежит обычными файлами.

    Заметки/        — заметки и списки в Markdown (синхронизируются с телефоном — sync.py, и с Obsidian — obsidian.py)
    Знания/, Навыки/ — документы для поиска (knowledge.py) и навыки; Задачи/ — папки задач (tasks.py)
    Лаборатория/    — скрипты, которые он пишет для задач, и их вывод (.log); запуск — lab_run под guard
    Дневник/        — дневник, файл на день ГГГГ-ММ-ДД.md (diary.py); Финансы/ — money.py
    Память/Обо мне.md — что он о вас знает; строки «- факт _(дд.мм.гггг)_» — этот формат разбирает sync.py
    Напоминания.md  — список активных напоминаний (пересобирается сам)
Все пути снаружи проходят через safe(): выйти из папки нельзя. Удаление — только в корзину (guard.trash)."""

import datetime as dt
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("dewiar.workspace")

if os.name == "nt":          # Windows: «Документы\Dewiar» (с учётом переноса «Документов» в OneDrive)
    try:
        import winsys
        DEFAULT_DIR = winsys.known_folder("Documents") / "Dewiar"
    except Exception:  # noqa: BLE001
        DEFAULT_DIR = Path.home() / "Documents" / "Dewiar"
else:
    DEFAULT_DIR = Path.home() / "Dewiar"
if os.environ.get("DEWIAR_WORKSPACE_DIR"):     # проверки и переносные установки — своя папка по умолчанию
    DEFAULT_DIR = Path(os.environ["DEWIAR_WORKSPACE_DIR"])
FALLBACK_DIR = Path(os.environ.get("DEWIAR_WORKSPACE_FALLBACK") or (Path.home() / "Dewiar"))
FOLDERS = ("Заметки", "Знания", "Навыки", "Лаборатория", "Дневник", "Память")
MEMORY = Path("Память") / "Обо мне.md"
PERSONA_MEM = Path("Память") / "Персонажи"   # своя память персонажа (0.56, по желанию): «Память/Персонажи/Патрик.md»


def persona_mem_rel(who):
    """Файл своей памяти персонажа по имени (имя — как в «Персонажах»; лишние знаки — прочь). -> Path"""
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "", str(who or "")).strip(" .")[:40] or "Персонаж"
    return PERSONA_MEM / f"{name}.md"


def persona_mem_head(who):
    return (f"# Обо мне — память {who}\n\nЧто {who} знает о вас — только для этого персонажа (своя память, студия → «Персонажи»). "
            "Другие персонажи этого не видят. Можно править и стирать — это ваш файл.\n\n")


TEXT_EXT = {".md", ".txt", ".py", ".sh", ".log", ".json", ".csv", ".yaml", ".yml", ".html", ".js", ".toml", ".ini", ".htm", ".svg",
            ".tsv", ".css", ".xml", ".srt", ".vtt", ".ts", ".bat", ".ps1"}
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября",
          "декабря"]

README = """# Папка Dewiar

Здесь ассистент хранит то, что делает для вас. Это обычные файлы — открывайте, правьте, удаляйте.

- **Заметки** — заметки и списки. Скажите: «Агент, запиши…», «составь список покупок».
- **Лаборатория** — скрипты, которые ассистент пишет для задач, и их вывод. Видно, чем он был занят.
- **Дневник** — его дневник: жизнь рядом с вами. Днём — короткие мысли после разговоров, ночью — запись о прожитом дне и выводы на завтра. Читать удобно в студии: раздел «Душа».
- **Память / Обо мне.md** — что он о вас знает. Читает перед каждым ответом. Лишнее можно просто стереть.
- **Напоминания.md** — активные напоминания, обновляется сам.

Смотреть всё это удобно в студии: раздел «Папка».
"""

MEMORY_HEAD = """# Обо мне

Что ассистент знает о вас. Он читает это перед каждым ответом и дописывает сам, когда узнаёт что-то
важное надолго. Можно править и стирать — это ваш файл.

"""


def fact_parts(fact):
    """Факт → (о чём, что): «Бюджет на мебель для гостиной — 65 тысяч» → («бюджет на мебель для гостиной», «65 тысяч»).
    О чём — до тире, двоеточия или первого числа; не меньше трёх слов (иначе слишком общо, чтобы заменять). Иначе ("", "")."""
    f = re.sub(r"^со слов пользователя:\s*", "", (fact or "").strip(), flags=re.I)
    m = re.match(r"^(.+?)(?:\s+[—–-]\s+|:\s+)(.+)$", f)
    if not m:
        return "", ""
    subj = re.sub(r"[^\w\s]", "", m.group(1).lower().replace("ё", "е")).strip()
    subj = " ".join(subj.split())
    if len(subj.split()) < 3 or re.match(r"(?:в|во|на|к|с|по|до|после|завтра|сегодня|послезавтра|когда|если)\b", subj) \
            or re.search(r"\d|понедельник|вторник|сред|четверг|пятниц|суббот|воскресен", subj):
        return "", ""                              # «в среду в 15:00 — встреча»: планы на разные дни не заменяют друг друга
    return subj, m.group(2).strip()


_DEFAULT_OK = []


def default_dir():
    """Папка по умолчанию, в которую правда можно писать. «Документы» бывают сломаны: перенесены на отключённый диск,
    удалены чистильщиком, ссылка в никуда — тогда FileNotFoundError на каждом шаге (19.10: 342 сбоя синхронизации
    за сутки у одного человека, дневник не пишется). Тогда — ~/Dewiar; один раз сказать в журнале."""
    if _DEFAULT_OK:
        return _DEFAULT_OK[0]
    for i, cand in enumerate((DEFAULT_DIR, FALLBACK_DIR)):
        try:
            cand.mkdir(parents=True, exist_ok=True)
            if cand.is_dir():
                if i:
                    log.warning("Папка «%s» недоступна — рабочая папка Dewiar: %s (сменить — студия → «Папка»)", DEFAULT_DIR, cand)
                _DEFAULT_OK.append(cand)
                return cand
        except OSError as e:
            log.debug("Рабочая папка %s: %s", cand, e)
    return DEFAULT_DIR                                  # ничего не вышло — как раньше (ошибка покажется там, где пишут)


class WorkspaceError(Exception):
    pass


NOTE_ATT_MAX = 20 * 1048576
NOTE_IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
NOTE_LINK_RX = re.compile(r"(?:📎\s*)?(!?)\[[^\]\n]*\]\((Вложения/[^)\s]+)\)")    # ссылки на вложения в тексте заметки
# Шапка заметки (Obsidian, перенос из Google Keep и других программ): в начале файла строки «ключ: значение» между
# «---» (или «--»). 28.10, пользователь: «source: Google Keep, id: … — это не то» — шапка показывалась текстом, а в
# списке — «-- source: Google Keep id: …». Теперь она не показывается и не попадает в отрывок; из неё берутся метки
# (tags), цвет (color / «цвет: BROWN») и «закреплено» (pinned) — и при правке в студии сохраняется как была.
FRONT_RX = re.compile(r"\A\ufeff?(-{2,3})[ \t]*\n((?:[ \t]*(?:[\w\-а-яёА-ЯЁ]+[ \t]*:.*|-[ \t].*|)\n)*?)\1[ \t]*(?:\n|\Z)")


def note_front(text):
    """-> (шапка как словарь, текст без шапки). Без шапки — ({}, text). Значения — строки; список меток — tags."""
    m = FRONT_RX.match(str(text or ""))
    if not m or not m.group(2).strip():
        return {}, str(text or "")
    meta, key = {}, ""
    for line in m.group(2).splitlines():
        li = re.match(r"\s*-\s+(.*)", line)
        if li and key:                                       # список под ключом: tags:\n  - a\n  - b
            meta.setdefault(key + "[]", []).append(li.group(1).strip().strip("\"'"))
            continue
        kv = re.match(r"\s*([\w\-а-яёА-ЯЁ]+)\s*:\s*(.*)", line)
        if kv:
            key = kv.group(1).lower()
            meta[key] = kv.group(2).strip()
    tags = []
    for k in ("tags", "tag", "labels", "метки"):
        raw = meta.get(k + "[]") or [x for x in re.split(r"[,;]", (meta.get(k) or "").strip("[] ")) if x.strip()]
        tags += [str(x).strip().strip("\"'").lstrip("#") for x in raw if str(x).strip()]
    meta = {k: v for k, v in meta.items() if not k.endswith("[]")}
    if tags:
        meta["tags"] = list(dict.fromkeys(tags))
    else:
        meta.pop("tags", None)
    col = re.search(r"(?:^|\b)(?:colou?r|цвет)\s*:?\s*([A-Za-zА-Яа-яЁё_]+)", " ".join(f"{k}: {v}" for k, v in meta.items() if isinstance(v, str)))
    if col and col.group(1).upper() not in ("DEFAULT", "NONE", "WHITE"):
        meta["color"] = col.group(1).upper()
    return meta, str(text)[m.end():]



def _clean_name(name, default="заметка"):
    """Имя файла или папки: без знаков, запрещённых в Windows, без точек и пробелов по краям, до 80 знаков.
    Им же sync.py чистит имена, пришедшие из облака."""
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", " ", (name or "").strip())
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name or default)[:80]


def _human_date(d=None):
    d = d or dt.datetime.now()
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}, {d:%H:%M}"


class Workspace:
    def __init__(self, settings):
        self.s = settings

    @property
    def root(self) -> Path:
        # DEWIAR_WORKSPACE важнее настройки: так проверки не трогают настоящую папку
        p = os.environ.get("DEWIAR_WORKSPACE") or ((self.s.get("workspace", "path") or "").strip() if self.s else "")
        r = Path(os.path.expanduser(p)) if p else default_dir()
        # №309 (пакет 27.10): папка на сетевом диске Z: — safe() отдаёт путь после resolve() (\\сервер\…), а relative_to
        # сравнивал его с «Z:\» — «is not in the subpath», дневник и заметки падали часами. Корень — тоже раскрытый
        try:
            return r.resolve()
        except (OSError, RuntimeError):
            return r

    def ensure(self):
        """Создаёт главные папки, README и «Обо мне», если их нет. -> корень."""
        r = self.root
        for f in FOLDERS:
            (r / f).mkdir(parents=True, exist_ok=True)
        if not (r / "README.md").exists():
            (r / "README.md").write_text(README, encoding="utf-8")
        if not (r / MEMORY).exists():
            (r / MEMORY).write_text(MEMORY_HEAD, encoding="utf-8")
        return r

    def safe(self, rel) -> Path:
        """Путь внутри папки ассистента — и никуда больше. resolve() раскрывает «..» и ссылки до проверки,
        поэтому выйти наружу не помогает и символическая ссылка внутри папки."""
        root = self.ensure().resolve()
        p = (root / str(rel or "").lstrip("/")).resolve()
        if p != root and root not in p.parents:
            raise WorkspaceError("этот путь вне папки ассистента")
        return p

    # ---------- для студии ----------

    def prune_empty(self):
        """Убирает пустые подпапки (заметку перенесли или удалили, модель создала папку и ничего не положила):
        иначе в «Папке» студии копится мусор. Главные папки остаются. -> сколько убрано."""
        root, n = self.ensure(), 0
        for top in FOLDERS:
            base = root / top
            if not base.is_dir():
                continue
            for d in sorted((x for x in base.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)):
                try:
                    if not any(d.iterdir()):
                        d.rmdir()
                        n += 1
                except OSError:
                    pass
        return n

    def remove_dir(self, rel):
        """Подпапку (не главную и не папку задачи) — в корзину целиком."""
        p = self.safe(rel)
        parts = Path(str(rel)).parts
        if not p.is_dir() or len(parts) < 2:
            raise WorkspaceError("главные папки удалять нельзя — только то, что внутри")
        if parts[0] == "Задачи":
            raise WorkspaceError("папку задачи удаляйте в разделе «Задачи» — там же её план и журнал")
        files = [x for x in p.rglob("*") if x.is_file()]
        import guard
        guard.trash([{"path": str(p), "dir": True, "files": len(files), "size": sum(x.stat().st_size for x in files)}])
        return True

    def tree(self, max_items=800):
        """Дерево папки для студии: до max_items элементов и 6 уровней, без скрытых. Попутно убирает пустые подпапки."""
        self.prune_empty()
        root = self.ensure()
        count = [0]

        def walk(d, depth):
            items = []
            try:
                entries = sorted(d.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except OSError:
                return items
            for p in entries:
                if p.name.startswith(".") or p.name == "__pycache__" or count[0] >= max_items:
                    continue
                count[0] += 1
                st = p.stat()
                node = {"name": p.name, "path": p.relative_to(root).as_posix(), "mtime": st.st_mtime}
                if p.is_dir():
                    node["type"] = "dir"
                    node["children"] = walk(p, depth + 1) if depth < 6 else []
                else:
                    node["type"] = "file"
                    node["size"] = st.st_size
                items.append(node)
            return items
        return {"root": str(root), "items": walk(root, 0)}

    def _vault_path(self, rel):
        """«obsidian:Путь/Заметка.md» — файл из подключённого хранилища Obsidian (только чтение), не выходя за него.
        vault_fn подставляет ядро."""
        v = self.vault_fn() if getattr(self, "vault_fn", None) else None
        if not v:
            raise WorkspaceError("Obsidian не подключён")
        v = Path(v).resolve()
        p = (v / str(rel)[len("obsidian:"):].lstrip("/")).resolve()
        if v not in p.parents:
            raise WorkspaceError("путь вне хранилища")
        return p

    def read(self, rel, limit=300_000):
        """-> {path, text, size, mtime, truncated} или {…, binary: True} для нетекстовых файлов; PDF и Word — текстом."""
        p = self._vault_path(rel) if str(rel).startswith("obsidian:") else self.safe(rel)
        if not p.is_file():
            raise WorkspaceError("файла нет")
        if p.suffix.lower() in (".pdf", ".docx", ".odt"):          # документы — текстом (как в «Знаниях»)
            try:
                from knowledge import extract
                text = extract(p)
                return {"path": rel, "text": text[:limit], "size": p.stat().st_size, "mtime": p.stat().st_mtime,
                        "truncated": len(text) > limit, "extracted": True}
            except Exception:  # noqa: BLE001 — текст не извлёкся: покажем как обычный файл
                pass
        if p.suffix.lower() not in TEXT_EXT and p.stat().st_size > 0:
            return {"path": rel, "binary": True, "size": p.stat().st_size, "mtime": p.stat().st_mtime}
        data = p.read_bytes()[:limit]
        return {"path": rel, "text": data.decode("utf-8", errors="replace"), "size": p.stat().st_size,
                "mtime": p.stat().st_mtime, "truncated": p.stat().st_size > limit}

    # ---------- студия: «Память» — заметки слева, редактор справа ----------

    def write(self, rel, text):
        """Сохранить текст заметки из редактора студии (только текстовые файлы внутри папки ассистента)."""
        p = self.safe(rel)
        if p.suffix.lower() not in (".md", ".txt"):
            raise WorkspaceError("править здесь можно только заметки (.md, .txt)")
        if p.is_dir():
            raise WorkspaceError("это папка")
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")               # через временный файл: оборванная запись не испортит заметку
        tmp.write_text(str(text or "").replace("\r\n", "\n"), encoding="utf-8")
        os.replace(tmp, p)
        st = p.stat()
        return {"path": rel, "size": st.st_size, "mtime": st.st_mtime}

    def notes(self, q="", limit=400):
        """Все заметки (Заметки/**/*.md, и с телефона тоже) — новые сверху; q — слова через пробел, все должны найтись в
        названии или тексте (без учёта регистра и «ё»). -> [{path, title, folder, mtime, size, snippet}] для студии."""
        base = self.safe("Заметки")
        if not base.is_dir():
            return []
        norm = lambda t: str(t or "").lower().replace("ё", "е")
        words = [w for w in norm(q).split() if w]
        out = []
        for f in base.rglob("*.md"):
            try:
                st = f.stat()
                text = f.read_text(encoding="utf-8", errors="replace")[:200_000]
            except OSError:
                continue
            meta, text = note_front(text)                  # шапка «---» (Obsidian, Google Keep) — не в отрывок
            body = re.sub(r"^\s*#[^\n]*\n+(\*[^\n]*\*\n+)?", "", text.lstrip()).strip()     # без заголовка и даты
            folder = "/".join(f.relative_to(base).parts[:-1])
            hay = norm(f.stem + "\n" + body + "\n" + folder)
            if words and not all(w in hay for w in words):
                continue
            clean = NOTE_LINK_RX.sub("", body).strip()     # строки-ссылки на вложения — не в отрывок (обрезанная выглядела «![Картинка 16.10…»)
            at = norm(clean).find(words[0]) if words else -1
            snip = clean[max(0, at - 50): max(0, at - 50) + 180] if at > 50 else clean[:180]
            atts = NOTE_LINK_RX.findall(body)              # вложения: первая картинка — миниатюрой в списке
            img = next((u for bang, u in atts if bang), "")
            if img:
                import urllib.parse
                img = (f.parent / urllib.parse.unquote(img)).relative_to(self.root).as_posix()
            out.append({"path": f.relative_to(self.root).as_posix(), "title": f.stem, "mtime": st.st_mtime, "size": st.st_size,
                        "folder": folder, "snippet": re.sub(r"\s+", " ", snip).strip(), "att": len(atts), "img": img,
                        "tags": meta.get("tags") or [], "color": meta.get("color", ""), "source": meta.get("source", "")})
        out.sort(key=lambda x: -x["mtime"])
        return out[:limit]

    # ---------- вложения заметок: фото и файлы рядом с заметкой ----------
    # <папка заметки>/Вложения/<имя заметки>/<файл>; в тексте — строка-ссылка в конце: «![имя](Вложения/…)» для фото,
    # «📎 [имя](Вложения/…)» для файла (пути с %20 — так их понимают и Obsidian, и любой просмотрщик Markdown)

    def note_attach(self, rel, name, data):
        """Положить файл к заметке (только «Заметки/…»). -> {line, path, kind, name}; строку ссылки студия ставит в текст сама."""
        p = self.safe(rel)
        if p.suffix.lower() != ".md" or not p.is_file() or Path(str(rel)).parts[:1] != ("Заметки",):
            raise WorkspaceError("прикреплять можно только к заметке из «Заметок»")
        if len(data) > NOTE_ATT_MAX:
            raise WorkspaceError(f"файл больше {NOTE_ATT_MAX // 1048576} МБ")
        ext = re.sub(r"[^a-z0-9]", "", Path(str(name or "")).suffix.lower())[:8]
        stem = _clean_name(Path(str(name or "")).stem, "файл")[:60]
        d = p.parent / "Вложения" / _clean_name(p.stem)
        d.mkdir(parents=True, exist_ok=True)
        out, n = d / (stem + ("." + ext if ext else "")), 2
        while out.exists():
            out, n = d / (f"{stem} ({n})" + ("." + ext if ext else "")), n + 1
        out.write_bytes(data)
        link = out.relative_to(p.parent).as_posix().replace("%", "%25").replace(" ", "%20").replace("(", "%28").replace(")", "%29")
        kind = "image" if "." + ext in NOTE_IMG else "file"
        label = out.name.replace("]", ")").replace("[", "(")
        return {"line": (f"![{label}]({link})" if kind == "image" else f"📎 [{label}]({link})"),
                "path": out.relative_to(self.ensure().resolve()).as_posix(), "kind": kind, "name": out.name}

    def note_with_files(self, title, text, files, folder="Напоминания"):
        """Заметка с вложениями одним вызовом (напоминание с картинками: «напомни завтра в 10» + два снимка) —
        «Заметки/<folder>/<title>.md», файлы рядом (note_attach), строки-ссылки в конце текста.
        files — [(имя, байты)]. -> {path, att: [{kind, name, path}]}."""
        rel = self.save_note(title, text, folder)
        lines, att = [], []
        for name, data in list(files)[:12]:
            try:
                r = self.note_attach(rel, name, data)
            except WorkspaceError as e:
                log.info("Вложение «%s» к заметке не легло: %s", name, e)
                continue
            lines.append(r["line"])
            att.append({"kind": r["kind"], "name": r["name"], "path": r["path"]})
        if lines:
            p = self.safe(rel)
            body = p.read_text(encoding="utf-8").rstrip("\n")
            self.write(rel, body + "\n\n" + "\n".join(lines) + "\n")
        return {"path": rel, "att": att}

    def note_atts(self, rel):
        """Вложения заметки по строкам-ссылкам её текста -> [{kind, name, path}] (пути — от корня папки ассистента)."""
        import urllib.parse
        try:
            p = self.safe(rel)
            text = p.read_text(encoding="utf-8", errors="replace")
        except (OSError, WorkspaceError):
            return []
        out = []
        for bang, link in NOTE_LINK_RX.findall(text):
            f = p.parent / urllib.parse.unquote(link)
            if f.is_file():
                out.append({"kind": "image" if bang and f.suffix.lower() in NOTE_IMG else "file", "name": f.name,
                            "path": f.relative_to(self.ensure().resolve()).as_posix()})
        return out

    def note_file(self, rel):
        """Картинка заметки для показа в студии: -> {url: data:…} (до NOTE_ATT_MAX)."""
        import base64
        import mimetypes
        p = self.safe(rel)
        if not p.is_file() or p.suffix.lower() not in NOTE_IMG:
            raise WorkspaceError("это не картинка заметки")
        if p.stat().st_size > NOTE_ATT_MAX:
            raise WorkspaceError("картинка слишком большая для просмотра")
        mt = mimetypes.guess_type(p.name)[0] or "image/png"
        return {"url": f"data:{mt};base64," + base64.b64encode(p.read_bytes()).decode()}

    def new_note(self, title, folder="Заметки", text=""):
        """Новая заметка из студии: в главной папке или внутри «Заметок», со свободным именем. -> путь."""
        folder = folder if folder in FOLDERS or str(folder).startswith("Заметки") else "Заметки"
        base = self.safe(folder)
        base.mkdir(parents=True, exist_ok=True)
        title = _clean_name(title, "Новая заметка")
        p, n = base / f"{title}.md", 2
        while p.exists():
            p, n = base / f"{title} ({n}).md", n + 1
        p.write_text(f"# {p.stem}\n\n*{_human_date()}*\n\n{text}".rstrip() + "\n", encoding="utf-8")
        return p.relative_to(self.ensure()).as_posix()

    def rename(self, rel, title):
        p = self.safe(rel)
        if not p.is_file():
            raise WorkspaceError("файла нет")
        if rel in (MEMORY.as_posix(), "README.md"):
            raise WorkspaceError("этот файл переименовывать нельзя")
        q = p.with_name(_clean_name(title) + p.suffix)
        if q == p:
            return rel
        if q.exists():
            raise WorkspaceError("заметка с таким названием уже есть")
        p.rename(q)
        return q.relative_to(self.ensure()).as_posix()

    def remove(self, rel):
        """Заметку — в корзину (как всё удаление в Dewiar). «Обо мне» и README не удаляются: без них ломается память."""
        p = self.safe(rel)
        if not p.is_file():
            raise WorkspaceError("файла нет")
        if rel in (MEMORY.as_posix(), "README.md"):
            raise WorkspaceError("этот файл удалять нельзя — его можно только очистить")
        import guard
        items = [{"path": str(p), "dir": False, "files": 1, "size": p.stat().st_size}]
        att = p.parent / "Вложения" / _clean_name(p.stem)        # вложения заметки — в корзину вместе с ней
        if p.suffix.lower() == ".md" and att.is_dir():
            files = [x for x in att.rglob("*") if x.is_file()]
            items.append({"path": str(att), "dir": True, "files": len(files), "size": sum(x.stat().st_size for x in files)})
        guard.trash(items)
        return True

    # ---------- для ассистента ----------

    def save_note(self, title, text, folder="", append=False):
        """Заметка от ассистента — всегда в «Заметках» (подпапка — по последней части folder). Существующую
        не затирает: append дописывает, иначе создаётся «… (2)». -> путь от корня."""
        base = self.safe("Заметки")
        parts = [x for x in re.split(r"[\\/]+", str(folder or "").strip()) if x.strip()]
        if parts and parts[0] == "Заметки":
            parts = parts[1:]
        # модель в задаче просит положить заметку «в папку задачи» или в другую главную папку — из этого в «Заметках»
        # рождались бы подпапки-двойники «Задачи …»; файлы задачи пишутся в её папку, а заметка — просто в «Заметки»
        folder = "" if not parts or parts[0] in FOLDERS or parts[0] in ("Задачи", "Финансы") else parts[-1]
        if folder:
            base = self.safe(str(Path("Заметки") / _clean_name(folder, "разное")))
        base.mkdir(parents=True, exist_ok=True)
        title = _clean_name(title)
        p = base / f"{title}.md"
        text = (text or "").strip()
        if p.exists() and append:
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"\n\n*{_human_date()}*\n\n{text}\n")
        else:
            if p.exists():                                   # не затираем: новая заметка с номером
                n = 2
                while (base / f"{title} ({n}).md").exists():
                    n += 1
                p = base / f"{title} ({n}).md"
            p.write_text(f"# {title}\n\n*{_human_date()}*\n\n{text}\n", encoding="utf-8")
        return p.relative_to(self.root).as_posix()

    def list_add(self, name, items):
        """«Добавь молоко в список покупок» — пункт «- молоко» в заметку-список (создаётся, если нет).
        Уже имеющиеся пункты (без учёта регистра) не дублируются. -> (путь, добавленные пункты)."""
        base = self.safe("Заметки")
        base.mkdir(parents=True, exist_ok=True)
        title = _clean_name(name, "Список")
        p = base / f"{title}.md"
        old = p.read_text(encoding="utf-8") if p.exists() else f"# {title}\n\n"
        have = {ln[2:].strip().lower() for ln in old.splitlines() if ln.startswith("- ")}
        new = [i for i in items if i.strip().lower() not in have]
        if new:
            with open(p, "w", encoding="utf-8") as f:
                f.write(old.rstrip("\n") + "\n" + "".join(f"- {i}\n" for i in new))
        return p.relative_to(self.root).as_posix(), new

    def find(self, query, limit=8):
        """Простой поиск по .md/.txt папки: слово ищется по основе (без двух последних букв — грубо снимает
        окончания). -> [{path, snippet}] по убыванию числа совпадений."""
        root = self.ensure()
        words = [w for w in re.findall(r"\w+", (query or "").lower()) if len(w) > 2]
        found = []
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in {".md", ".txt"} or any(x.startswith(".") for x in p.parts):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            low = (p.stem + " " + text).lower()
            score = sum(low.count(w[:max(3, len(w) - 2)]) for w in words) if words else 1
            if score:
                i = min((low.find(w[:max(3, len(w) - 2)]) for w in words if w[:max(3, len(w) - 2)] in low), default=0)
                snippet = text[max(0, i - 80): i + 220].replace("\n", " ").strip()
                found.append((score, p.relative_to(root).as_posix(), snippet))
        found.sort(key=lambda x: -x[0])
        return [{"path": f, "snippet": s} for _, f, s in found[:limit]]

    # Своя память персонажа (0.56, «Персонажи» → «Своя память»): mem_owner() — имя персонажа, у которого своя память и
    # который сейчас отвечает (ядро ставит), иначе "" — общая «Обо мне». who=None — по mem_owner(), "" — общая, имя — его.
    mem_owner = None

    def _mem(self, who=None):
        if who is None:
            try:
                who = self.mem_owner() if callable(self.mem_owner) else ""
            except Exception:  # noqa: BLE001
                who = ""
        if not who:
            return MEMORY, MEMORY_HEAD
        return persona_mem_rel(who), persona_mem_head(who)

    def remember(self, fact, who=None):
        """Дописывает строку в «Обо мне» (или в свою память персонажа) в формате «- факт _(дд.мм.гггг)_» (его разбирает
        _FACT в sync.py). Уже известное (текст есть в файле) не повторяет. -> фраза для ответа."""
        fact = re.sub(r"\s+", " ", (fact or "").strip())
        if not fact:
            raise WorkspaceError("пустой факт")
        rel, head = self._mem(who)
        p = self.safe(str(rel))
        p.parent.mkdir(parents=True, exist_ok=True)
        old = p.read_text(encoding="utf-8") if p.exists() else head
        if fact.lower().rstrip(".") in old.lower():
            return "Это я уже знаю."
        subj, val = fact_parts(fact)
        if subj:                                   # «Бюджет на мебель — 70 тысяч» после «— 50 тысяч»: обновить, а не копить
            lines = old.split("\n")
            for i, ln in enumerate(lines):
                m = re.match(r"^- (.+?)(?: _\(\d\d\.\d\d\.\d{4}\)_)?\s*$", ln.strip())
                if not m:
                    continue
                o_subj, o_val = fact_parts(m.group(1))
                if o_subj != subj or not o_val:
                    continue
                hist = re.search(r"\(раньше: (.+?)(?:; менял\w* \d+ раз\w*)?\)\s*\.?$", o_val)
                was = re.sub(r"\s*\(.*\)\s*\.?$", "", o_val).rstrip(" .")        # значение без пояснений в скобках
                chain = (hist.group(1).split(" → ") if hist else []) + [was]
                body = re.sub(r"\s*\(.*\)\s*\.?$", "", fact).rstrip(" .")       # пояснения модели в скобках — история их заменяет
                if re.sub(r"\s*\(.*\)\s*$", "", fact_parts(body)[1]).rstrip(" .") == was:
                    return "Это я уже знаю."
                prev = " → ".join(chain)
                n = len(chain)
                word = "раза" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "раз"
                lines[i] = f"- {body} (раньше: {prev}; менялось {n} {word}). _({dt.date.today():%d.%m.%Y})_"
                p.write_text("\n".join(lines), encoding="utf-8")
                return f"Обновил (раньше: {prev})."
        if not p.exists():
            p.write_text(head, encoding="utf-8")
        with open(p, "a", encoding="utf-8") as f:
            f.write(f"- {fact} _({dt.date.today():%d.%m.%Y})_\n")
        return "Запомнил."

    def memory_get(self, who=None):
        rel, head = self._mem(who)
        p = self.safe(str(rel))
        text = p.read_text(encoding="utf-8") if p.exists() else head
        return text[len(head):] if text.startswith(head) else text

    def memory_set(self, body, who=None):
        body = (body or "").strip()
        rel, head = self._mem(who)
        p = self.safe(str(rel))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(head + (body + "\n" if body else ""), encoding="utf-8")
        return True

    def memory_text(self, limit=2500, who=None):
        """«Обо мне» без шапки — для подсказки модели; при переполнении остаются последние limit знаков (новое важнее)."""
        rel, _ = self._mem(who)
        try:
            text = (self.root / rel).read_text(encoding="utf-8")
        except OSError:
            return ""
        body = text.split("\n\n", 2)[-1] if text.startswith("# Обо мне") else text
        body = body.strip()
        return body[-limit:] if len(body) > limit else body

    def diary(self, entry, who=""):
        """Дневная запись «### ЧЧ:ММ · кто» в файл сегодняшнего дня. -> путь."""
        entry = (entry or "").strip()
        if not entry:
            raise WorkspaceError("пустая запись")
        now = dt.datetime.now()
        p = self.safe(str(Path("Дневник") / f"{now:%Y-%m-%d}.md"))
        new = not p.exists()
        with open(p, "a", encoding="utf-8") as f:
            if new:
                f.write(f"# Дневник — {now.day} {MONTHS[now.month - 1]} {now.year}\n")
            f.write(f"\n### {now:%H:%M}{' · ' + who if who else ''}\n\n{entry}\n")
        return p.relative_to(self.root).as_posix()

    def diary_night(self, day, got, head):
        """Ночная запись о дне — раздел «## head» в файле того дня; повторная («записать сейчас», потом ночью)
        заменяет прежнюю. head начинается с «🌙» (NIGHT_HEAD в diary.py) — по нему diary_days находит её."""
        p = self.safe(str(Path("Дневник") / f"{day:%Y-%m-%d}.md"))
        text = p.read_text(encoding="utf-8") if p.exists() else f"# Дневник — {day.day} {MONTHS[day.month - 1]} {day.year}\n"
        text = re.sub(r"\n## " + re.escape(head) + r".*?(?=\n### \d|\n## |\Z)", "", text, flags=re.S).rstrip() + "\n"
        title = (f" · «{got['title']}»" if got.get("title") else "") + (f" {got['mood']}" if got.get("mood") else "")
        sec = f"\n## {head}{title}\n\n{got['text'].strip()}\n"
        if got.get("tomorrow"):
            sec += "\n**На завтра:**\n" + "".join(f"- {x}\n" for x in got["tomorrow"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text + sec, encoding="utf-8")
        return p.relative_to(self.root).as_posix()

    def diary_days(self, titles=None):
        """Дни дневника для студии: дата, заголовок и настроение ночной записи, сколько записей, начало текста."""
        titles, out = titles or {}, []
        d = self.ensure() / "Дневник"
        for p in sorted(d.glob("*.md"), reverse=True):
            try:
                day = dt.date.fromisoformat(p.stem)
                text = p.read_text(encoding="utf-8")
            except (ValueError, OSError):
                continue
            body = re.sub(r"^# .*\n", "", text).strip()
            night = re.search(r"^## 🌙[^\n]*\n+(.+?)(?:\n\n|\Z)", body, re.M | re.S)
            first = night.group(1) if night else re.sub(r"^#+ .*$", "", body, flags=re.M).strip().split("\n\n")[0]
            t = titles.get(day.isoformat()) or {}
            out.append({"day": day.isoformat(), "path": p.relative_to(self.root).as_posix(), "title": t.get("title", ""),
                        "mood": t.get("mood", ""), "who": t.get("who", ""), "night": bool(night), "count": len(re.findall(r"^(?:### |## 🌙)", body, re.M)),
                        "preview": re.sub(r"\s+", " ", first)[:220], "text": text})
        return out[:120]

    def lab_write(self, name, content):
        """Файл в «Лаборатории» (скрипты — сразу исполняемые). -> путь."""
        name = str(name or "").strip().lstrip("/")
        if not name or ".." in Path(name).parts:
            raise WorkspaceError("нужно имя файла")
        p = self.safe(str(Path("Лаборатория") / name))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content or "", encoding="utf-8")
        if p.suffix in (".sh", ".py"):
            p.chmod(0o755)
        return p.relative_to(self.root).as_posix()

    def _lab_env(self, lab):
        """Окружение скриптов лаборатории: guard подкладывает sitecustomize через PYTHONPATH, и Python-скрипт может
        удалять файлы только в лаборатории и во временной папке (DEWIAR_ALLOW_DEL). Вывод — в UTF-8."""
        import tempfile
        import guard
        lab_root = self.root / "Лаборатория"
        try:
            from settings import STATE_DIR
            pp = guard.site_dir(STATE_DIR)
        except Exception:  # noqa: BLE001
            pp = guard.site_dir(Path(tempfile.gettempdir()) / "dewiar-guard")
        old = os.environ.get("PYTHONPATH", "")
        return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONPATH=pp + (os.pathsep + old if old else ""),
                    DEWIAR_ALLOW_DEL=os.pathsep.join([str(lab_root.resolve()), os.path.realpath(tempfile.gettempdir())]))

    def lab_run(self, name, args="", timeout=120):
        """Запускает скрипт лаборатории (папка скрипта — рабочая), вывод пишет рядом в «имя.log».
        -> {code, output (последние 4000 знаков), log}; code -1 — остановлен по timeout."""
        p = self.safe(str(Path("Лаборатория") / str(name or "").lstrip("/")))
        if not p.is_file():
            raise WorkspaceError(f"в лаборатории нет файла {name}")
        win = os.name == "nt"
        py = sys.executable
        if win and py.lower().endswith("pythonw.exe"):          # у pythonw нет консоли и вывода — берём python.exe рядом
            py = py[:-len("pythonw.exe")] + "python.exe"
        if p.suffix == ".py":
            cmd = [py, str(p)]
        elif p.suffix == ".sh" and (not win or shutil.which("bash")):
            cmd = ["bash", str(p)]
        elif win and p.suffix == ".ps1":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(p)]
        elif win and p.suffix in (".bat", ".cmd"):
            cmd = ["cmd", "/c", str(p)]
        else:
            raise WorkspaceError("запускать можно .py, .ps1 и .bat" if win else "запускать можно .py и .sh")
        import shlex
        cmd += shlex.split(args or "")
        try:
            r = subprocess.run(cmd, cwd=str(p.parent), capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                               env=self._lab_env(p.parent), creationflags=0x08000000 if win else 0)   # CREATE_NO_WINDOW: без мелькающей консоли
            out, code = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip(), r.returncode
        except subprocess.TimeoutExpired as e:
            out, code = f"{(e.stdout or '')}\nОстановлено: дольше {timeout} с".strip(), -1
        log_path = p.with_suffix(p.suffix + ".log")
        log_path.write_text(f"$ {' '.join(cmd[1:])}\n# {_human_date()}, код {code}\n\n{out}\n", encoding="utf-8")
        return {"code": code, "output": out[-4000:], "log": log_path.relative_to(self.root).as_posix()}

    def sync_reminders(self, items):
        """Пересобирает «Напоминания.md» — только для чтения (в Obsidian он идёт в одну сторону, ONE_WAY)."""
        try:
            lines = ["# Напоминания", "", "Обновляется само. Отменить: «Агент, отмени напоминание …».", ""]
            for x in sorted(items, key=lambda i: i.get("at", "")):
                try:
                    when = _human_date(dt.datetime.fromisoformat(x["at"]))
                except (KeyError, ValueError):
                    when = x.get("at", "")
                try:
                    from when import describe_repeat
                    rep = describe_repeat(x.get("repeat"))
                except Exception:  # noqa: BLE001
                    rep = ""
                lines.append(f"- **{when}** — {x.get('text', '')}" + (f" _({rep})_" if rep else "") +
                             (" _(на паузе)_" if x.get("paused") else ""))
            if not items:
                lines.append("_Сейчас напоминаний нет._")
            (self.ensure() / "Напоминания.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            log.warning("Напоминания.md не обновлён: %s", e)
