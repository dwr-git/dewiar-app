"""Obsidian: хранилище заметок пользователя и папка ассистента — вместе.

  • Зеркало: в хранилище — папка «DEWIAR» (имя настраивается; папка со старым именем «Dewiar» переименовывается,
    _migrate) с FOLDERS из рабочей папки ассистента и оглавлением «DEWIAR.md» (_write_index, пишется только туда).
    Сверка двусторонняя по отпечаткам прошлой сверки (obsidian-sync.json), раз в 20 секунд и по кнопке. Заметка,
    положенная прямо в «DEWIAR» или в свою подпапку, у ассистента — в «Заметках» (alias), в хранилище остаётся на месте.
    Удалили с одной стороны — с другой файл уходит в корзину, не пропадает; правка побеждает удаление. Изменили
    с обеих сторон — новее остаётся на месте, другая версия рядом («… (из Obsidian).md» / «… (от ассистента).md»).
  • Поиск: ассистент ищет и по всему хранилищу (vault_files), но чужие заметки не меняет — пишет только в свою папку.
  • Всё хранилище между компьютерами синхронизирует core/sync.py (вид vault, sync_all), минуя папку ассистента.
Сам Obsidian для работы не нужен: хранилище — обычная папка с Markdown-файлами."""
import hashlib
import json
import logging
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger("dewiar.obsidian")

FOLDERS = ("Заметки", "Дневник", "Память")      # что из папки ассистента живёт и в хранилище
ONE_WAY = ("Напоминания.md",)                    # только из папки ассистента (файл пересобирается сам)
LOOSE = "Заметки"                                # заметки, положенные в хранилище мимо этих папок, — у ассистента здесь
PRIVATE = ("Память/Уроки задач.md",)             # служебное — в хранилище не выносим
DEFAULT_FOLDER = "DEWIAR"                        # заглавными — заметнее в списке файлов Obsidian
OLD_FOLDER = "Dewiar"                            # старое имя папки — переименовывается в DEFAULT_FOLDER
MAX_FILE = 20 << 20                              # файлы больше 20 МБ не синхронизируем
MAX_SEARCH_FILES = 8000
SKIP_DIRS = {".obsidian", ".trash", ".git", "node_modules"}


class ObsidianError(Exception):
    pass


def _config_files():
    """Где установленный Obsidian хранит список хранилищ (obsidian.json) на каждой платформе."""
    home = Path.home()
    if sys.platform == "win32":
        yield Path(os.environ.get("APPDATA") or home / "AppData/Roaming") / "obsidian" / "obsidian.json"
    elif sys.platform == "darwin":
        yield home / "Library/Application Support/obsidian/obsidian.json"
    else:
        yield Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "obsidian" / "obsidian.json"
        yield home / ".var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json"     # Flatpak
        yield home / "snap/obsidian/current/.config/obsidian/obsidian.json"            # Snap


def detect():
    """Хранилища, которые знает установленный Obsidian: [{"path", "name"}]; открытое сейчас — первым, затем по времени."""
    found = {}
    for cf in _config_files():
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for v in (d.get("vaults") or {}).values():
            p = v.get("path")
            if p and Path(p).is_dir():
                # ts — в мс; +10¹³ ставит открытое хранилище выше любого времени
                found[str(Path(p))] = max(found.get(str(Path(p)), 0), int(v.get("ts") or 0) + (10 ** 13 if v.get("open") else 0))
    return [{"path": p, "name": Path(p).name} for p, _ in sorted(found.items(), key=lambda x: -x[1])]


def _hash(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _files(base):
    """{относительный путь: Path} — файлы папки без скрытых (с точкой) и больше MAX_FILE."""
    out = {}
    if not base.is_dir():
        return out
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if any(x.startswith(".") for x in rel.parts) or not p.is_file():
            continue
        try:
            if p.stat().st_size > MAX_FILE:
                continue
        except OSError:
            continue
        out[rel.as_posix()] = p
    return out


class Obsidian:
    def __init__(self, settings, workspace, state_dir, emit=None):
        self.s, self.ws = settings, workspace
        self.state_path = Path(state_dir) / "obsidian-sync.json"
        self.emit = emit or (lambda *a, **k: None)
        self._lock = threading.Lock()
        self.last = {"time": 0, "stats": {}, "error": ""}
        self._bad = set()                # файлы, которые не читаются/не пишутся: в журнал — один раз

    # ---------- настройки ----------

    def cfg(self):
        c = (self.s.get("obsidian") if self.s else None) or {}
        folder = (c.get("folder") or "").strip()
        return {"vault": (c.get("vault") or "").strip(), "folder": DEFAULT_FOLDER if folder in ("", OLD_FOLDER) else folder,
                "search": c.get("search", True) is not False, "sync_all": bool(c.get("sync_all"))}

    def sync_all(self):
        """«Всё хранилище — одинаковое на всех компьютерах» включено и хранилище на месте (core/sync.py, вид vault).
        Пока хранилище недоступно — False: sync.py тогда не принимает чужие правки хранилища."""
        return bool(((self.s.get("obsidian") if self.s else None) or {}).get("sync_all")) and self.vault() is not None

    def vault(self):
        v = self.cfg()["vault"]
        if not v:
            return None
        p = Path(os.path.expanduser(v))
        return p if p.is_dir() else None

    def mirror(self):
        """Папка ассистента в хранилище; имя из настроек без недопустимых в Windows знаков."""
        v = self.vault()
        if v is None:
            return None
        name = "".join(ch for ch in self.cfg()["folder"] if ch not in '\\/:*?"<>|').strip(". ") or DEFAULT_FOLDER
        return v / name

    def _migrate(self, v):
        """Папка со старым именем «Dewiar» → «DEWIAR», если имя не выбрано вручную и «DEWIAR» ещё нет;
        сохранённое в настройках старое имя заменяем на новое."""
        c = (self.s.get("obsidian") if self.s else None) or {}
        if (c.get("folder") or "").strip() not in ("", OLD_FOLDER):
            return
        try:
            names = set(os.listdir(v))
        except OSError:
            return
        if OLD_FOLDER in names and DEFAULT_FOLDER not in names and (v / OLD_FOLDER).is_dir():
            try:
                os.rename(v / OLD_FOLDER, v / DEFAULT_FOLDER)
                log.info("Obsidian: папка «%s» → «%s»", OLD_FOLDER, DEFAULT_FOLDER)
            except OSError as e:
                log.warning("Obsidian: папку не переименовать: %s", e)
                return
        if c.get("folder"):
            self.s.update({"obsidian": {"folder": DEFAULT_FOLDER}})

    def connected(self):
        return self.vault() is not None

    def public(self):
        c, v = self.cfg(), self.vault()
        n = 0
        if v is not None:
            try:
                n = len(json.loads(self.state_path.read_text(encoding="utf-8")).get("files", {}))
            except (OSError, ValueError):
                n = 0
        return {"connected": v is not None, "vault": c["vault"], "name": v.name if v else "", "folder": c["folder"],
                "search": c["search"], "sync_all": c["sync_all"], "missing": bool(c["vault"]) and v is None, "synced": n,
                "last": self.last["time"], "stats": self.last["stats"], "error": self.last["error"],
                "open": f"obsidian://open?vault={quote(v.name)}" if v else "", "vaults": detect()}

    def connect(self, path, folder=None):
        """Подключить хранилище и сразу сверить. Рабочую папку ассистента (и папки внутри неё) не принимаем:
        зеркало оказалось бы внутри самого себя."""
        p = Path(os.path.expanduser((path or "").strip()))
        if not str(path or "").strip() or not p.is_dir():
            raise ObsidianError("такой папки нет — выберите папку хранилища Obsidian")
        if p.resolve() == Path(self.ws.root).resolve() or Path(self.ws.root).resolve() in p.resolve().parents:
            raise ObsidianError("это папка самого ассистента — выберите хранилище Obsidian")
        patch = {"vault": str(p)}
        if folder:
            patch["folder"] = folder
        self.s.update({"obsidian": patch})
        self.sync()
        return self.public()

    def set(self, patch):
        p = {k: patch[k] for k in ("search", "folder", "sync_all") if k in patch}
        for k in ("search", "sync_all"):
            if k in p:
                p[k] = bool(p[k])
        if p:
            self.s.update({"obsidian": p})
        return self.public()

    def forget(self):
        """Отключить. Файлы в хранилище остаются — это уже ваши заметки."""
        self.s.update({"obsidian": {"vault": ""}})
        try:
            self.state_path.unlink()
        except OSError:
            pass
        self.last = {"time": 0, "stats": {}, "error": ""}
        return self.public()

    # ---------- синхронизация ----------

    def _load_state(self, key):
        """-> (files {путь у ассистента: хэш на прошлой сверке}, alias {путь у ассистента: путь в папке хранилища},
        прочее). Если папка-зеркало сменилась (key — её полный путь), прошлые отпечатки не годятся: начинаем заново,
        иначе отсутствие файлов в новой папке сошло бы за их удаление."""
        try:
            d = json.loads(self.state_path.read_text(encoding="utf-8"))
            extra = {k: v for k, v in d.items() if k not in ("mirror", "files", "alias")}
            if d.get("mirror") == key:
                return d.get("files") or {}, d.get("alias") or {}, extra
            return {}, {}, extra
        except (OSError, ValueError):
            pass
        return {}, {}, {}

    def _save_state(self, key, files, alias=None, extra=None):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        d = dict(extra or {}, mirror=key, files=files, alias=alias or {})
        tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_path)

    @staticmethod
    def _copy(src, dst):
        # через временный файл: Obsidian не увидит недописанную заметку; copy2 сохраняет время правки — по нему
        # решаются конфликты
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".dewiar-tmp")
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)

    @staticmethod
    def _trash(p, trash_dir, rel):
        """Переносит файл в корзину trash_dir/rel (при совпадении имени — с датой) и убирает опустевшие подпапки."""
        dst = trash_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            dst = dst.with_name(f"{dst.stem} ({time.strftime('%Y-%m-%d %H-%M-%S')}){dst.suffix}")
        shutil.move(str(p), str(dst))
        d, parts = Path(p).parent, Path(rel).parts           # опустевшие подпапки не оставляем (главные остаются)
        for i in range(len(parts) - 1, 0, -1):
            if i == 1 and parts[0] in FOLDERS:
                break
            try:
                d.rmdir()
            except OSError:
                break
            d = d.parent

    def sync(self):
        """Двусторонняя сверка рабочей папки ассистента и его папки в хранилище (mirror).
        -> счётчики {to_vault, from_vault, conflicts, trashed}; {} — хранилища нет или ошибка (она в self.last)."""
        with self._lock:
            v = self.vault()
            if v is not None:
                self._migrate(v)
            mir = self.mirror()
            if mir is None:
                self.last["error"] = "хранилище не найдено — проверьте папку" if self.cfg()["vault"] else ""
                return {}
            try:
                st = self._sync(mir)
                self.last = {"time": time.time(), "stats": st,
                             "error": f"пропущено файлов: {st['skipped']} — нет доступа (сетевая папка или права)" if st.get("skipped") else ""}
            except OSError as e:
                self.last["error"] = f"не получилось: {e}"
                log.warning("Obsidian: %s", e)
                return {}
        if any(v for k, v in st.items() if k != "skipped"):
            log.info("Obsidian: %s", st)
            self.emit("obsidian", **self.public())
        return st

    def _sync(self, mir):
        """a — файлы у ассистента, b — в хранилище (под путями ассистента), state — отпечатки прошлой сверки.
        Отпечаток совпал с прошлым, а с другой стороны файла нет — значит, там удалили; иначе — копируем."""
        root = Path(self.ws.ensure())
        key = str(mir.resolve())
        state, alias, extra = self._load_state(key)
        st = {"to_vault": 0, "from_vault": 0, "conflicts": 0, "trashed": 0}
        index = f"{mir.name}.md"
        a = {}
        for f in FOLDERS:
            a.update({f"{f}/{r}": p for r, p in _files(root / f).items() if f"{f}/{r}" not in PRIVATE})
        # хранилище: свои папки — один в один; заметка прямо в «DEWIAR» или в своей подпапке — у ассистента в «Заметках»
        rev = {v: k for k, v in alias.items()}
        b = {}
        for r, p in _files(mir).items():
            if r in ONE_WAY or r == index or r in PRIVATE:
                continue
            if r.split("/", 1)[0] in FOLDERS and "/" in r:
                b[r] = p
                continue
            ws_rel = rev.get(r)
            if not ws_rel:
                q, n = Path(LOOSE) / r, 2
                cand = q.as_posix()
                while ((cand in a and _hash(a[cand]) != _hash(p)) or (mir / cand).exists() or cand in alias):   # имя занято
                    cand = q.with_name(f"{q.stem} ({n}){q.suffix}").as_posix()
                    n += 1
                ws_rel = cand
                alias[ws_rel], rev[r] = r, ws_rel
            b[ws_rel] = p
        vp = lambda rel: mir / alias.get(rel, rel)                              # где файл лежит в хранилище
        mir.mkdir(parents=True, exist_ok=True)
        new_state = {}
        for rel in sorted(set(a) | set(b)):
            pa, pb, known = a.get(rel), b.get(rel), state.get(rel)
            try:
                if pa and not pb:
                    if known and _hash(pa) == known:                 # удалили в Obsidian — у ассистента в корзину (правленый — вернём)
                        self._trash(pa, root / ".Корзина", rel)
                        st["trashed"] += 1
                        continue
                    self._copy(pa, vp(rel))
                    st["to_vault"] += 1
                    new_state[rel] = _hash(pa)
                elif pb and not pa:
                    if known and _hash(pb) == known:                 # удалили у ассистента — в корзину Obsidian
                        self._trash(pb, mir.parent / ".trash" / mir.name, alias.get(rel, rel))
                        st["trashed"] += 1
                        continue
                    self._copy(pb, root / rel)
                    st["from_vault"] += 1
                    new_state[rel] = _hash(pb)
                else:
                    ha, hb = _hash(pa), _hash(pb)
                    if ha == hb:
                        new_state[rel] = ha
                    elif known == ha:                                # правили только в Obsidian
                        self._copy(pb, pa)
                        st["from_vault"] += 1
                        new_state[rel] = hb
                    elif known == hb:                                # правил только ассистент
                        self._copy(pa, pb)
                        st["to_vault"] += 1
                        new_state[rel] = ha
                    else:                                            # правили оба: свежее — на место, другое — рядом с пометкой, откуда оно
                        newer_a = pa.stat().st_mtime >= pb.stat().st_mtime
                        keep, other = (pa, pb) if newer_a else (pb, pa)
                        side = "из Obsidian" if newer_a else "от ассистента"
                        p = Path(rel)
                        alt = p.with_name(f"{p.stem} ({side}){p.suffix}").as_posix()
                        if rel in alias:
                            va = Path(alias[rel])
                            alias[alt] = va.with_name(f"{va.stem} ({side}){va.suffix}").as_posix()
                        self._copy(other, root / alt)
                        self._copy(other, vp(alt))
                        self._copy(keep, pb if newer_a else pa)
                        h = _hash(keep)
                        new_state[rel] = h
                        new_state[alt] = _hash(other)
                        st["conflicts"] += 1
            except OSError as e:                               # один файл недоступен (сетевая папка, нет прав) — остальные сверяем
                if known:                                        # отпечаток прошлой сверки сохраняем: в следующий раз — как раньше
                    new_state[rel] = known
                st["skipped"] = st.get("skipped", 0) + 1
                if rel not in self._bad:                         # в журнал — один раз на файл, не каждые 20 с (отчёт №408)
                    self._bad.add(rel)
                    log.warning("Obsidian: пропускаю «%s»: %s", rel, e)
        for name in ONE_WAY:                                     # напоминания — только в хранилище, для чтения
            src = root / name
            if src.is_file():
                dst = mir / name
                if not dst.exists() or _hash(dst) != _hash(src):
                    self._copy(src, dst)
        self._write_index(mir, index, new_state, alias)
        extra = self._snippet(mir, extra)
        self._save_state(key, new_state, {k: v for k, v in alias.items() if k in new_state}, extra)
        return st

    # ---------- чтобы папка в Obsidian была заметной и полезной ----------

    def _write_index(self, mir, index, files, alias):
        """«DEWIAR.md» — оглавление папки: что ассистент знает, дневник, заметки. Пересобирается каждой сверкой и
        только в хранилище, правки в нём не сохраняются. Имя и дни дневника даёт index_info(), если её подставило ядро."""
        try:
            info = self.index_info() if getattr(self, "index_info", None) else {}
        except Exception:  # noqa: BLE001
            info = {}
        name, f = info.get("name") or "ассистент", mir.name
        link = lambda rel, title=None: f"[[{f}/{Path(alias.get(rel, rel)).with_suffix('').as_posix()}" + (f"|{title}]]" if title else "]]")
        notes = sorted((r for r in files if r.startswith("Заметки/") and r.endswith(".md")),
                       key=lambda r: -(Path(self.ws.root, r).stat().st_mtime if Path(self.ws.root, r).exists() else 0))[:12]
        days = info.get("days") or []
        out = [f"# {f}", "",
               f"> Папка вашего ассистента ({name}). Здесь — его заметки и списки, дневник и то, что он о вас знает. "
               "Правьте и добавляйте: положите заметку сюда или в «Заметки» — ассистент увидит её через минуту.",
               "> *Эту страницу он обновляет сам — правки в ней не сохранятся.*", ""]
        out += ["## Что я о вас знаю", f"- {link('Память/Обо мне.md', 'Обо мне')} — читаю перед каждым ответом, можно править", ""]
        if days:
            out.append("## Дневник")
            for d in days[:7]:
                t = f" — «{d['title']}» {d.get('mood') or ''}".rstrip() if d.get("title") else ""
                out.append(f"- {link('Дневник/' + d['day'] + '.md', d.get('label') or d['day'])}{t}")
            out.append("")
        if notes:
            out.append("## Заметки и списки")
            out += [f"- {link(r, Path(r).stem)}" for r in notes]
            out.append("")
        if (Path(self.ws.root) / "Напоминания.md").exists():
            out += ["## Напоминания", f"- [[{f}/Напоминания|Что напомнить и когда]]", ""]
        text = "\n".join(out)
        p = mir / index
        try:
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                p.write_text(text, encoding="utf-8")
        except OSError as e:
            log.debug("Obsidian: оглавление: %s", e)

    def _snippet(self, mir, extra):
        """Папка ассистента выделена в списке файлов Obsidian (цвет и ✦) — CSS-фрагмент хранилища. Включаем один раз:
        выключили в настройках Obsidian («Оформление → Фрагменты CSS») — больше не трогаем."""
        obs = mir.parent / ".obsidian"
        if not obs.is_dir():
            return extra
        sel = f'.nav-folder-title[data-path="{mir.name}"]'
        css = ("/* Dewiar: папка ассистента заметна в списке файлов. Файл создал Dewiar — можно удалить или выключить. */\n"
               f"{sel} {{ font-weight: 700; color: #9C8CFF; }}\n"
               f"{sel} .nav-folder-title-content::before {{ content: \"✦ \"; color: #D07CFF; }}\n")
        try:
            sn = obs / "snippets" / "dewiar.css"
            if not sn.exists() or sn.read_text(encoding="utf-8") != css:
                sn.parent.mkdir(parents=True, exist_ok=True)
                sn.write_text(css, encoding="utf-8")
            if not extra.get("snippet_on"):
                ap = obs / "appearance.json"
                d = json.loads(ap.read_text(encoding="utf-8")) if ap.exists() else {}
                if isinstance(d, dict):
                    on = list(d.get("enabledCssSnippets") or [])
                    if "dewiar" not in on:
                        d["enabledCssSnippets"] = on + ["dewiar"]
                        tmp = ap.with_name(ap.name + ".dewiar-tmp")
                        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
                        os.replace(tmp, ap)
                    extra = dict(extra, snippet_on=True)
        except (OSError, ValueError) as e:
            log.debug("Obsidian: оформление папки: %s", e)
        return extra

    def loop(self, stopping, every=20):
        """Сверка раз в every секунд. Хранилище на сетевом диске пропало (19.10: «Превышен таймаут семафора»,
        «сетевое имя более недоступно» — 49 сбоев за ночь) — пробуем всё реже, до 10 минут, и пишем об этом один раз."""
        wait, fails = 3, 0                                   # первая сверка — вскоре после запуска (переименовать папку, оглавление)
        while not stopping.wait(wait):
            wait = every
            if self.cfg()["vault"]:
                try:
                    self.sync()
                    if fails:
                        log.info("Obsidian: хранилище снова доступно")
                    fails = 0
                except OSError as e:
                    fails += 1
                    wait = min(600, every * 2 ** min(fails, 5))
                    if fails == 1:
                        log.warning("Obsidian: хранилище недоступно (%s) — пробую реже, пока не появится", e)
                    else:
                        log.debug("Obsidian: хранилище всё ещё недоступно: %s", e)
                except Exception:  # noqa: BLE001 — синхронизация не должна ронять ядро
                    log.exception("Obsidian: синхронизация")

    # ---------- поиск ----------

    def search_root(self):
        """Для поиска по заметкам: (папка хранилища, что пропустить) или None."""
        if not self.cfg()["search"]:
            return None
        v, mir = self.vault(), self.mirror()
        return (v, mir.name if mir else "") if v else None


def vault_files(vault, skip_top=""):
    """Markdown-файлы хранилища для поиска (без служебных папок и без папки ассистента — она уже в поиске)."""
    n = 0
    for dirpath, dirs, files in os.walk(vault):
        rel_dir = Path(dirpath).relative_to(vault)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIP_DIRS
                   and not (rel_dir == Path(".") and d == skip_top)]
        for f in files:
            if f.lower().endswith((".md", ".txt")) and not f.startswith("."):
                yield Path(dirpath) / f
                n += 1
                if n >= MAX_SEARCH_FILES:
                    return
