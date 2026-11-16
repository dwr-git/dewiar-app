"""Фоновые задачи, часть «файлы» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
пути и папки задачи, чтение и запись, поиск по маске и обход, файловые действия."""
import os
import re
from pathlib import Path

import quality as Q
import sandbox as SBX
import snapshots as SNAP
from tasks_base import LIST_MAX


class FilesMixin:
    @staticmethod
    def _path(t, rel):
        """Безопасность: путь от модели -> абсолютный внутри папки задачи; «..», абсолютные пути и ссылки наружу — ValueError."""
        rel = str(rel or "").strip()
        root = t.dir.resolve()
        try:                                     # модель дала полный путь внутри папки задачи — берём его часть от папки
            ab = Path(rel).expanduser().resolve()
            if Path(rel).expanduser().is_absolute() and (root in ab.parents or ab == root):
                rel = str(ab.relative_to(root))
        except (OSError, ValueError):
            pass
        rel = rel.lstrip("/\\")
        p = (t.dir / rel).resolve()
        if not rel or (t.dir.resolve() not in p.parents and p != t.dir.resolve()):
            raise ValueError("путь вне папки задачи. Как исправить: пиши относительный путь в папке задачи, например "
                             "outputs/app.html")
        return p

    @staticmethod
    def _folders(t):
        """Папки, которые человек дал задаче (start_task folders): [Path] — только существующие."""
        out = []
        for f in t.data.get("folders") or []:
            try:
                p = Path(f).expanduser().resolve()
            except OSError:
                continue
            if p.is_dir():
                out.append(p)
        return out

    def _area(self, t, rel, write=False):
        """Путь от модели в области задачи (выпуск 2): папка задачи (относительный путь) или папки, которые человек дал
        задаче (полный путь). -> (путь, папка человека или None). Вне области — ValueError «что случилось — как исправить».
        Запись в папку человека — только с разрешением (раз на папку за задачу), иначе — в копию в outputs/."""
        raw = str(rel or "").strip()
        try:
            ab = Path(raw).expanduser()
            if ab.is_absolute():
                ab = ab.resolve()
                for f in self._folders(t):
                    if ab == f or f in ab.parents:
                        try:
                            ws = [str(self.host.workspace.root)]
                        except Exception:  # noqa: BLE001
                            ws = []
                        if SBX.is_private(ab, grants=self._folders(t), hide=ws, root=t.dir):
                            # S1: дали всю ~ или ~/.config — ~/.ssh, папки Dewiar, .env всё равно закрыты
                            raise ValueError(f"«{ab}» — личное (ключи, пароли, настройки Dewiar, профиль браузера); задаче "
                                             "его не давали, хоть оно и внутри данной папки. Как исправить: обойдись без него")
                        if write:
                            key = f"write:{f}"
                            if key not in (t.data.get("write_ok") or []):
                                okd, why = self._permit(t, key, f"Задача «{t.title}» хочет изменить файлы в вашей папке {f}. Разрешить?")
                                if not okd:
                                    raise ValueError(f"человек не разрешил менять файлы в {f}. Как исправить: сделай копию "
                                                     "в outputs/ (file_read → write_file) и правь её. " + why)
                                t.data["write_ok"] = (t.data.get("write_ok") or []) + [key]
                                t.journal(f"✍ Разрешено менять файлы в {f}")
                        return ab, f
        except OSError:
            pass
        try:
            if Path(raw).expanduser().is_absolute():
                ab = Path(raw).expanduser().resolve()
                if not (ab == t.dir.resolve() or t.dir.resolve() in ab.parents):
                    raise ValueError("вне")
            p = self._path(t, raw)
        except (ValueError, OSError):
            p = None
        if p is not None:
            rel = p.relative_to(t.dir.resolve()).parts
            if write and rel and (rel[0] in Q.SERVICE or rel[0].startswith("рабочая копия")):
                # рецензия 0.84: запись в _src/, задачи.json, критерии.json, блокнот… подделывала опору проверки и учёт
                raise ValueError(f"«{rel[0]}» — служебный файл задачи, его ведёт Dewiar. Как исправить: план — todo_update, "
                                 "критерии — set_criteria, блокнот — remember или notes, результаты — в outputs/")
            return p, None
        fs = self._folders(t)
        if True:
            raise ValueError(f"путь «{raw}» вне папки задачи" + (" и данных ей папок (" + ", ".join(map(str, fs)) + ")" if fs else "")
                             + ". Как исправить: пиши относительный путь в папке задачи (outputs/…)"
                             + (", а в папках человека — полный путь" if fs else ", а нужную папку попроси человека дать задаче")) from None

    def _shown(self, t, p, f):
        """Путь для ответа модели: в папке задачи — относительный, в папке человека — полный."""
        return p.relative_to(t.dir.resolve()).as_posix() if f is None else str(p)

    @classmethod
    def _load_text(cls, p):
        """Текстовый файл -> (текст с переводами строк \\n, кодировка, был ли CRLF). Кодировка: UTF-8 (с BOM — utf-8-sig),
        иначе cp1251 (рецензия 0.83: file_edit портил cp1251 и CRLF). Не текст или слишком большой — ValueError с советом."""
        size = p.stat().st_size
        if size > cls.READ_MAX:
            raise ValueError(f"{p.name} — {size // (1 << 20)} МБ, это слишком много для чтения целиком. Как исправить: "
                             "ищи в нём file_grep или разбери кодом (run_python) по частям")
        data = p.read_bytes()
        if b"\0" in data[:8192]:
            raise ValueError(f"{p.name} — не текстовый файл ({size} байт). Как исправить: разбери его кодом (run_python: "
                             "pypdf, openpyxl, Pillow…)")
        enc = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            enc = "cp1251"
            text = data.decode(enc, errors="replace")
        crlf = b"\r\n" in data
        return (text.replace("\r\n", "\n") if crlf else text), enc, crlf

    @staticmethod
    def _save_text(p, text, enc, crlf):
        """Записать так же, как было: та же кодировка и те же переводы строк. Символ не кодируется — ValueError."""
        if crlf:
            text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        try:
            data = text.encode(enc)
        except UnicodeEncodeError as e:
            raise ValueError(f"в файле кодировка {enc}, а в правке есть символ «{text[e.start:e.end]}», которого в ней нет. "
                             "Как исправить: замени его (например, кавычки «» на \"\") или сделай копию файла в UTF-8 (write_file)") from None
        p.write_bytes(data)

    def _read_lines(self, t, p, args, name="file_read"):
        """Кусок файла с номерами строк, не больше _out_max знаков: «показаны строки a–b из N; дальше — start=…»."""
        try:
            text = self._load_text(p)[0]
        except ValueError as e:
            return f"Ошибка: {e}."
        lines = text.splitlines()
        if not lines:
            return "(файл пуст)"
        a, b = max(1, int(args.get("start") or 1)), int(args.get("end") or 0)
        if a > len(lines):
            return f"Ошибка: в файле {len(lines)} строк, а start={a}. Как исправить: start от 1 до {len(lines)}."
        b = min(len(lines), b or a + 399)
        lim, out, size = self._out_max(t), [], 0     # кусок — не больше ~_out_max знаков: история не раздувается
        for i in range(a, b + 1):
            ln = f"{i}: {lines[i - 1]}"
            if out and size + len(ln) > lim:
                b = i - 1
                break
            out.append(ln if len(ln) <= lim else ln[:lim] + f"…(строка обрезана, в ней {len(lines[i - 1])} знаков)")
            size += len(ln) + 1
        return "\n".join(out) + (f"\n… показаны строки {a}–{b} из {len(lines)}; дальше — {name} с start={b + 1}" if b < len(lines) else "")

    def _limit(self, t, items, what, how):
        """Ограничитель ответов: не больше LIST_MAX строк и ~_out_max знаков, дальше — «показано 1–200 из 5000, сузь: …»
        (Anthropic «Writing tools»: ответ с пределом и подсказкой, как сузить)."""
        lim, size, k = self._out_max(t) - 200, 0, 0
        for x in items[:LIST_MAX]:
            if k and size + len(x) + 1 > lim:
                break
            size += len(x) + 1
            k += 1
        if k >= len(items):
            return "\n".join(items)
        return "\n".join(items[:k]) + f"\n… показано 1–{k} из {len(items)} {what}. Сузь: {how}."

    def _scan_root(self, t, args):
        """Где искать (file_grep, file_glob): path — подпапка задачи или папка человека (полный путь); пусто — папка задачи."""
        raw = str(args.get("path") or "").strip()
        if not raw or raw in (".", "./"):
            return t.dir.resolve(), None
        p, f = self._area(t, raw)
        if not p.exists():
            raise ValueError(f"нет папки «{raw}». Как исправить: посмотри file_glob без path, что есть в папке задачи")
        return p, f

    @staticmethod
    def _glob_rx(pattern):
        """Шаблон file_glob -> регулярное выражение по относительному пути: ** — любые папки, * и ? — внутри имени.
        Безопасность (рецензия 0.83): «..» и полный путь в шаблоне — отказ: шаблон не выводит из области задачи."""
        pat = str(pattern or "**/*").replace("\\", "/").strip() or "**/*"
        parts = pat.split("/")
        if pat.startswith("/") or re.match(r"^[A-Za-z]:", pat) or ".." in parts or pat.startswith("~"):
            raise ValueError("в шаблоне «..» или полный путь. Как исправить: шаблон — внутри папки (например **/*.csv), "
                             "а папку человека передай в path полным путём")
        out, i = "", 0
        while i < len(pat):
            if pat.startswith("**/", i):
                out, i = out + "(?:.*/)?", i + 3
            elif pat.startswith("**", i):
                out, i = out + ".*", i + 2
            elif pat[i] == "*":
                out, i = out + "[^/]*", i + 1
            elif pat[i] == "?":
                out, i = out + "[^/]", i + 1
            else:
                out, i = out + re.escape(pat[i]), i + 1
        return re.compile(out + r"\Z", re.I if os.name == "nt" else 0)

    def _walk(self, t, root, pattern="**/*"):
        """Файлы под root по шаблону. Через os.walk с пределом WALK_MAX, без перехода по ссылкам на папки; файл-ссылка,
        ведущая наружу root, пропускается (рецензия 0.83: symlink и «..» выводили из области задачи). Сортировка — потом."""
        rx = self._glob_rx(pattern)
        root_r = Path(root).resolve()
        task_r = t.dir.resolve()
        out, seen = [], 0
        for dp, dns, fns in os.walk(root_r, followlinks=False):
            d = Path(dp)
            if d == task_r:
                dns[:] = [x for x in dns if not x.startswith(("рабочая копия", "_run", "_src", SNAP.DIR))]
            for fn in fns:
                seen += 1
                if seen > self.WALK_MAX:
                    break
                p = d / fn
                if fn in self.SKIP_SCAN and d == task_r:
                    continue
                rel = p.relative_to(root_r).as_posix()
                if not rx.match(rel):
                    continue
                try:
                    real = p.resolve()
                except OSError:
                    continue
                if not (real == root_r or root_r in real.parents) or not real.is_file():
                    continue
                out.append(p)
            if seen > self.WALK_MAX:
                break
        return sorted(out)

    def _file_tools(self, t, name, args):
        """file_read, file_edit, file_grep, file_glob (выпуск 2 «Руки задачи»)."""
        if name in ("file_read", "read_file"):
            p, f = self._area(t, args.get("path"))
            if not p.is_file():
                if f is None:
                    # №516: путь из find_notes («Заметки/….md») — это папка ассистента, а не папка задачи: читаем оттуда
                    try:
                        from tools import t_read_file
                        w = self.host.workspace.safe(str(args.get("path") or ""))
                        if w.is_file():
                            return t_read_file({"path": w.relative_to(self.host.workspace.root.resolve()).as_posix()},
                                               {"workspace": self.host.workspace})
                    except Exception:  # noqa: BLE001
                        pass
                return (f"Такого файла нет: «{args.get('path')}». Как исправить: посмотри file_glob (или list_files), "
                        "как он называется.")
            t.data["seen"] = list(dict.fromkeys((t.data.get("seen") or []) + [str(p.resolve())]))[-300:]   # выпуск 8, п.5
            return self._read_lines(t, p, args, name)
        if name == "file_edit":
            import textedit as TE
            p, f = self._area(t, args.get("path"), write=True)
            if not p.is_file():
                return f"Ошибка: файла «{args.get('path')}» нет. Как исправить: новый файл создай write_file, а путь проверь file_glob."
            try:
                text, enc, crlf = self._load_text(p)
            except ValueError as e:
                return f"Ошибка: {e}."
            old_, new_ = (str(args.get(k) or "").replace("\r\n", "\n") for k in ("old", "new"))
            try:
                out, line, note = TE.apply_edit(text, old_, new_, bool(args.get("replace_all")))
            except TE.EditError as e:
                return f"Ошибка: {e}"
            bad = TE.syntax_error(out, p.suffix)
            if bad and not TE.syntax_error(text, p.suffix):
                return (f"Ошибка: после правки {p.name} не разбирается ({bad}) — файл НЕ изменён. Как исправить: поправь new "
                        "(скобки, кавычки, закрывающие теги) и повтори file_edit.")
            try:
                self._save_text(p, out, enc, crlf)
            except ValueError as e:
                return f"Ошибка: {e}. Файл НЕ изменён."
            shown = self._shown(t, p, f)
            t.journal(f"✏ Правка {shown}, строка {line}{note}")
            if f is None:                                  # написано моделью — не опора для сверки итога (_given, _data_files)
                t.data["authored"] = (list(dict.fromkeys((t.data.get("authored") or []) + [shown])))[-300:]
            n_new = str(args.get("new") or "").count("\n")
            return f"Изменён {shown}, строки {line}–{line + n_new}{note}." + (f" ⚠ Файл и до правки не разбирался: {bad}." if bad else "")
        if name == "file_glob":
            root, f = self._scan_root(t, args)
            pat = str(args.get("pattern") or "**/*").strip() or "**/*"
            files = self._walk(t, root, pat if "/" in pat or "**" in pat or ".." in pat else "**/" + pat)
            base = t.dir.resolve() if f is None else root
            items = [f"{(p.relative_to(base).as_posix() if f is None else str(p))} — {p.stat().st_size} байт" for p in files]
            if not items:
                return f"Ничего не нашлось по «{pat}»" + (f" в {root}" if f else "") + ". Как исправить: шаблон шире (**/*) или другая папка (path)."
            return self._limit(t, items, "файлов", "шаблон точнее (отчёты/*.md, **/*2024*.csv) или path — подпапка")
        if name == "file_grep":
            pat = str(args.get("pattern") or "")
            try:
                rx = re.compile(pat, re.I)
            except re.error as e:
                rx = re.compile(re.escape(pat), re.I)
                if not pat:
                    return f"Ошибка: пустой pattern ({e}). Как исправить: что искать — слово или регулярное выражение."
            root, f = self._scan_root(t, args)
            g = str(args.get("glob") or "").strip()
            files = [root] if root.is_file() else self._walk(t, root, (g if "/" in g or "**" in g or ".." in g else "**/" + g) if g else "**/*")
            hits, nfiles = [], 0
            base = t.dir.resolve() if f is None else None
            for p in files:
                try:
                    if p.stat().st_size > 5 << 20:
                        continue
                    data = p.read_bytes()
                except OSError:
                    continue
                if b"\0" in data[:4096]:
                    continue                               # не текст
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = data.decode("cp1251", errors="replace")
                got = False
                for i, ln in enumerate(text.splitlines(), 1):
                    if rx.search(ln):
                        where = p.relative_to(base).as_posix() if base is not None and base in p.parents else str(p)
                        hits.append(f"{where}:{i}: {ln.strip()[:200]}")
                        got = True
                nfiles += got
            if not hits:
                return f"Совпадений с «{pat}» нет (просмотрено файлов: {len(files)}). Как исправить: другое слово или шаблон шире, glob пустой."
            return self._limit(t, hits, f"совпадений в {nfiles} файлах", "pattern точнее, glob (*.csv) или path — подпапка")
        return "неизвестный инструмент"
