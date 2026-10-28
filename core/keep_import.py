"""Перенос заметок из Google Keep (0.58; 28.10, пользователь с 318 заметками из Keep: «теги слева, цвет, закреплять
вверху, поиск — визуально легко ориентироваться»). Источник — архив Google Takeout («Keep» в takeout.google.com):
zip целиком или распакованная папка; внутри Takeout/Keep/*.json — по файлу на заметку, рядом — картинки.

Каждая заметка Keep → «Заметки/Google Keep/<название>.md»: шапка (source: Google Keep, keep: <имя файла>, метки, цвет,
закреплено, в архиве), «# название», текст или список дел («- [ ] …», «- [x] …»), ссылки-вложения Keep — строками,
картинки — во «Вложения» рядом (как у всех заметок). Время правки — как в Keep. Удалённые в Keep (isTrashed) — не
переносятся. Повторный перенос того же архива не создаёт копий: уже перенесённые узнаются по keep: в шапке."""

import json
import logging
import os
import re
import zipfile
from pathlib import Path

log = logging.getLogger("dewiar.keep")
FOLDER = "Заметки/Google Keep"
COLORS = {"RED", "ORANGE", "YELLOW", "GREEN", "TEAL", "BLUE", "CERULEAN", "DARK_BLUE", "PURPLE", "PINK", "BROWN", "GRAY", "GREY"}


class _Src:
    """zip или папка — одинаково: names() и read(name)."""

    def __init__(self, path):
        self.path = Path(path)
        self.zip = zipfile.ZipFile(self.path) if self.path.is_file() else None

    def names(self):
        if self.zip:
            return self.zip.namelist()
        return [p.relative_to(self.path).as_posix() for p in self.path.rglob("*") if p.is_file()]

    def read(self, name):
        if self.zip:
            return self.zip.read(name)
        return (self.path / name).read_bytes()


def _title(n):
    t = (n.get("title") or "").strip()
    if not t:
        first = (n.get("textContent") or "").strip().splitlines() or [((n.get("listContent") or [{}])[0] or {}).get("text", "")]
        t = (first[0] if first else "").strip()[:60] or "Заметка из Keep"
    return t


def _clean(name):
    name = re.sub(r'[\\/:*?"<>|\n\r\t]+', " ", name).strip(" .")
    return (name or "Заметка")[:80]


def import_keep(ws, path, progress=None):
    """ws — Workspace; path — zip Takeout или папка. -> {"added", "skipped", "trashed", "errors", "folder"}."""
    src = _Src(path)
    names = src.names()
    jsons = [n for n in names if n.lower().endswith(".json") and "/keep/" in ("/" + n.lower())]
    if not jsons:
        jsons = [n for n in names if n.lower().endswith(".json")]
    if not jsons:
        raise ValueError("в архиве нет заметок Google Keep — нужен архив Google Takeout с «Keep»")
    by_base = {Path(n).name: n for n in names}
    base = ws.safe(FOLDER)
    base.mkdir(parents=True, exist_ok=True)
    seen = set()
    from workspace import note_front
    for f in base.glob("*.md"):
        try:
            meta, _ = note_front(f.read_text(encoding="utf-8", errors="replace")[:2000])
        except OSError:
            continue
        if meta.get("keep"):
            seen.add(meta["keep"])
    out = {"added": 0, "skipped": 0, "trashed": 0, "errors": 0, "folder": FOLDER}
    for i, name in enumerate(sorted(jsons)):
        if progress:
            progress(i, len(jsons))
        try:
            n = json.loads(src.read(name).decode("utf-8", errors="replace"))
        except (ValueError, KeyError, OSError):
            out["errors"] += 1
            continue
        if not isinstance(n, dict) or not ({"textContent", "listContent", "title"} & set(n)):
            continue                                        # не заметка (служебный json)
        if n.get("isTrashed"):
            out["trashed"] += 1
            continue
        kid = Path(name).name
        if kid in seen:
            out["skipped"] += 1
            continue
        title = _title(n)
        stem = _clean(title)
        p, k = base / f"{stem}.md", 2
        while p.exists():
            p, k = base / f"{stem} ({k}).md", k + 1
        body = (n.get("textContent") or "").strip()
        if n.get("listContent"):
            body = "\n".join(f"- [{'x' if it.get('isChecked') else ' '}] {str(it.get('text') or '').strip()}" for it in n["listContent"]
                             if str(it.get("text") or "").strip())
        links = [a for a in (n.get("annotations") or []) if a.get("url") and a["url"] not in body]
        if links:
            body += ("\n\n" if body else "") + "\n".join(
                (f"[{a['title'].strip()}]({a['url']})" if (a.get("title") or "").strip() else a["url"]) for a in links)
        tags = [str((lb or {}).get("name") or "").strip() for lb in n.get("labels") or []]
        tags = [t for t in tags if t]
        fm = ["source: Google Keep", f"keep: {kid}"]
        if tags:
            fm.append("tags: [" + ", ".join(t.replace(",", " ") for t in tags) + "]")
        col = str(n.get("color") or "").upper()
        if col in COLORS:
            fm.append(f"color: {col}")
        if n.get("isPinned"):
            fm.append("pinned: true")
        if n.get("isArchived"):
            fm.append("archived: true")
        text = "---\n" + "\n".join(fm) + "\n---\n\n# " + title.replace("\n", " ") + "\n\n" + body + "\n"
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
        rel = p.relative_to(ws.root).as_posix()
        lines = []
        for att in n.get("attachments") or []:
            fp = Path(str(att.get("filePath") or "")).name
            src_name = by_base.get(fp) or by_base.get(Path(fp).stem + ".jpg") or by_base.get(Path(fp).stem + ".jpeg")
            if not src_name:
                continue
            try:
                r = ws.note_attach(rel, Path(src_name).name, src.read(src_name))
                lines.append(r["line"])
            except Exception as e:  # noqa: BLE001
                log.info("Keep: вложение %s не перенесено: %s", fp, e)
        if lines:
            with p.open("a", encoding="utf-8") as fh:
                fh.write("\n" + "\n".join(lines) + "\n")
        ts = (n.get("userEditedTimestampUsec") or n.get("createdTimestampUsec") or 0) / 1e6
        if ts > 0:
            try:
                os.utime(p, (ts, ts))
            except OSError:
                pass
        seen.add(kid)
        out["added"] += 1
    log.info("Keep: перенесено %d, уже были %d, удалённых в Keep %d, ошибок %d", out["added"], out["skipped"], out["trashed"], out["errors"])
    return out
