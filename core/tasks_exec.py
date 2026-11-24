"""Фоновые задачи, часть «исполнение» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
рабочая папка, Python и оболочка, песочница, git, службы, снимки и откат."""
import os
import re
from pathlib import Path

import quality as Q
import sandbox as SBX
import snapshots as SNAP
from tasks_base import log, _NOFOLLOW, _regular, _wr
import tasks_base as TB  # подменяемые в проверках имена — через основу


class ExecMixin:
    def _work(self, t, name, args):
        """Инструменты мастерской (WORK_TOOLS)."""
        # №986 (23.11): задача «застряла» — 8 раз запускала run_python с кодом «[убрано из памяти: 3543 знаков]»: модель
        # повторяла свой старый вызов, а большой код в нём память уже заменила пометкой. Пометка — не код и не текст:
        # говорим прямо, что делать, а не «SyntaxError»
        stub = next((k for k, v in (args or {}).items() if isinstance(v, str) and v.lstrip().startswith("[убрано из памяти")), "")
        if stub:
            return (f"Ошибка: в «{stub}» — пометка памяти «[убрано из памяти…]», а не {'код' if stub == 'code' else 'содержимое'}. "
                    "Старый большой текст из памяти убран — не повторяй прошлый вызов, напиши "
                    + ("код заново целиком (короче, по частям: сначала данные в файл, потом код, что читает файл)" if stub == "code"
                       else "содержимое заново целиком или возьми его из файла (read_file)") + ".")
        if name in ("write_file", "file_edit"):                # выпуск 5: перед записью в outputs/ — снимок (раз на шаг)
            try:
                p0, f0 = self._area(t, args.get("path"))
                if f0 is None and p0.relative_to(t.dir.resolve()).parts[:1] == ("outputs",):
                    self._snap(t, f"{name} {p0.relative_to(t.dir.resolve()).as_posix()}")
            except (ValueError, OSError):
                pass                                       # путь плохой — скажет сам инструмент
        if name in ("file_read", "read_file", "file_edit", "file_grep", "file_glob"):
            return self._file_tools(t, name, args)
        if name == "write_file":
            p, f = self._area(t, args.get("path"), write=True)
            blind = self._blind_overwrite(t, p, args)
            if blind:
                return blind
            if f is not None:                              # папка человека (с его разрешения): пишем туда как есть
                p.parent.mkdir(parents=True, exist_ok=True)
                with open(p, "a" if args.get("append") else "w", encoding="utf-8") as fh:
                    fh.write(args.get("content") or "")
                t.data["seen"] = list(dict.fromkeys((t.data.get("seen") or []) + [str(p.resolve())]))[-300:]   # своё — дальше можно
                t.journal(f"📄 записал {p} ({p.stat().st_size} байт)")
                return f"Файл {p} — {p.stat().st_size} байт."
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a" if args.get("append") else "w", encoding="utf-8") as f:
                f.write(args.get("content") or "")
            size = p.stat().st_size
            hint = ""
            if p.suffix.lower() in (".html", ".htm"):
                txt = p.read_text(encoding="utf-8", errors="replace")
                if "</html>" not in txt.lower():
                    hint = " (нет </html> — если файл пишется частями, допиши; иначе проверь)"
            t.journal(f"📄 {'дописал' if args.get('append') else 'записал'} {p.relative_to(t.dir).as_posix()} ({size} байт)")
            t.data["authored"] = (list(dict.fromkeys((t.data.get("authored") or []) + [p.relative_to(t.dir).as_posix()])))[-300:]
            warn = Q.quick_check(p, p.relative_to(t.dir).as_posix())
            if warn:
                t.journal(warn)
            return f"Файл {p.relative_to(t.dir).as_posix()} — {size} байт{hint}." + (f"\n{warn} Почини до запуска." if warn else "")
        if name == "list_files":
            out = []
            for p in sorted(t.dir.rglob("*")):
                rel = p.relative_to(t.dir)
                if p.is_file() and not p.is_symlink() and not rel.parts[0].startswith(("рабочая копия", "_run", "_src", SNAP.DIR)) and p.name not in ("задача.json", "задача.json.tmp", "история.json", "история.json.tmp", "журнал.md"):
                    out.append(f"{rel.as_posix()} — {p.stat().st_size} байт")
            lab = self._lab_files(t)
            if lab:                                    # №368: что задача положила в «Лабораторию» (lab_write, lab_run)
                root = self.host.workspace.root / "Лаборатория"
                out += ["", "В «Лаборатории» (lab_write/lab_run) за время задачи:"] + \
                       [f"Лаборатория/{p.relative_to(root).as_posix()} — {p.stat().st_size} байт" for p in lab]
            return "\n".join(out[:300]) or "Папка пуста."
        if name == "run_python":
            # выпуск 5: в песочнице (bwrap или охрана) — без вопроса: код пишет только в папку задачи, личное не видит, и
            # задача не встаёт на паузу, когда человека нет рядом. Под охраной (guard) и без песочницы — как до выпуска 5:
            # разрешение раз на задачу (рецензия выпуска 5: охрану Python обходят в несколько строк — это не песочница)
            if not SBX.real_sandbox(self._sbx_mode(t)) and not self.host.code_auto_run() and not t.data.get("py_ok"):
                okd, why = self._permit(t, "run_python", f"Задача «{t.title}» хочет запускать свои скрипты Python в папке задачи. Разрешить для этой задачи?")
                if not okd:
                    return why + " Без запуска кода: write_file."
                t.data["py_ok"] = True
                t.save()
            return self._run_python(t, args.get("code") or "", int(args.get("timeout") or 180))
        if name == "run_shell":
            return self._run_shell(t, str(args.get("command") or "").strip(), int(args.get("timeout") or 180))
        if name == "rewind":
            return self._rewind_tool(t, args)
        if name == "show":
            p = self._path(t, args.get("path"))
            # 16.11 (Кодер правил сайт человека: «первый раз „Посмотреть“ показал, потом — старый вариант, а в его папке —
            # старое»): задача над проектом работает в «рабочей копии» — показываем файл оттуда (живой), а не
            # одноимённый, записанный когда-то рядом в папке задачи
            if t.data.get("project"):
                rel0 = str(args.get("path") or "").strip().lstrip("/\\")
                wc = t.dir / "рабочая копия"
                if rel0 and not rel0.startswith("рабочая копия") and (wc / rel0).is_file():
                    p = self._path(t, "рабочая копия/" + rel0)
            if not p.is_file():
                return "Такого файла нет — сначала создай его."
            rel = p.relative_to(t.dir).as_posix()
            outs = [o for o in t.data.get("outputs") or [] if o.get("path") != rel]
            outs.append({"path": rel, "title": (args.get("title") or p.stem)[:120], "time": TB.dt.datetime.now().isoformat(timespec="seconds")})
            t.data["outputs"] = outs[-30:]
            t.save()
            self._emit(t)
            t.journal(f"👁 Показал пользователю: {rel}")
            return f"Показано пользователю: {rel} (студия → «Задачи» → «Результаты»)."
        if name == "transcribe":
            src = str(args.get("path") or "").strip()
            # источник можно взять и вне папки задачи: из папки ассистента или по полному пути
            cands = [t.dir / src, self.host.workspace.root / src, Path(os.path.expanduser(src))]
            p = next((c for c in cands if c.is_file() and not c.is_symlink()), None)
            if p is None:
                return "Файл не найден — укажи путь в папке задачи (например downloads/лекция.mp4) или полный путь."
            t.data["activity"] = "расшифровываю запись…"
            self._emit(t)
            self._snap(t, f"transcribe {p.name}")
            segs = self.host.transcribe_file(p, cancel=t.cancel)
            out = t.dir / "outputs"
            out.mkdir(parents=True, exist_ok=True)

            def ts(x, srt=False):                       # секунды -> [мм:сс] / [ч:мм:сс] или 00:00:00,000 для .srt
                h, m, s_ = int(x // 3600), int(x % 3600 // 60), x % 60
                return f"{h:02d}:{m:02d}:{int(s_):02d},{int((s_ % 1) * 1000):03d}" if srt else (f"{h}:{m:02d}:{int(s_):02d}" if h else f"{m:02d}:{int(s_):02d}")
            txt = "\n".join(f"[{ts(a)}] {x}" for a, b, x in segs)
            _wr(out / f"{p.stem}.txt", txt + "\n", root=t.dir)
            _wr(out / f"{p.stem}.srt", "\n".join(f"{i}\n{ts(a, True)} --> {ts(b, True)}\n{x}\n" for i, (a, b, x) in enumerate(segs, 1)),
                root=t.dir)
            t.journal(f"🎙 Расшифровал {p.name}: {len(segs)} фрагментов")
            return (f"Готово: outputs/{p.stem}.txt и outputs/{p.stem}.srt ({len(segs)} фрагментов). Начало:\n" + txt[:6000]
                    + ("\n…(дальше — в файле, читай file_read)" if len(txt) > 6000 else ""))
        if name == "download":
            import httpx
            url = str(args.get("url") or "").strip()
            if not url.startswith(("http://", "https://")):
                return "Нужна ссылка http(s)://"
            nm = re.sub(r'[\\/:*?"<>|]', "_", (args.get("name") or url.split("?")[0].rstrip("/").rsplit("/", 1)[-1] or "file"))[:120]
            dst = t.dir / "downloads" / nm
            dst.parent.mkdir(parents=True, exist_ok=True)
            _wr(dst, b"", root=t.dir)                      # B2: ни ссылки на месте файла, ни папки-ссылки наружу
            got = 0
            with httpx.stream("GET", url, follow_redirects=True, timeout=httpx.Timeout(20, read=120),
                              headers={"User-Agent": "Mozilla/5.0 (Dewiar)"}) as r:
                r.raise_for_status()
                with os.fdopen(os.open(dst, os.O_WRONLY | os.O_TRUNC | _NOFOLLOW | getattr(os, "O_BINARY", 0)), "wb") as f:
                    for b_ in r.iter_bytes(1 << 16):
                        got += len(b_)
                        if got > 500 << 20:
                            raise ValueError("файл больше 500 МБ — не качаю")
                        if t.cancel.is_set():
                            raise ValueError("задачу остановили")
                        f.write(b_)
            t.journal(f"⬇ Скачал {nm} ({got // 1024} КБ)")
            return f"Скачано: downloads/{nm} ({got // 1024} КБ)."
        return "неизвестный инструмент"

    @staticmethod
    def _py_env(t, ff):
        """Окружение скриптов задачи. Безопасность: sitecustomize из guard.site_dir разрешает удалять файлы только
        в папке задачи и во временной папке (DEWIAR_ALLOW_DEL). UTF-8 для вывода, Agg — matplotlib без окон,
        FFMPEG — путь к ffmpeg программы."""
        import tempfile
        import guard
        pp = guard.site_dir(t.dir / "_run")
        allow = os.pathsep.join([str(t.dir.resolve()), os.path.realpath(tempfile.gettempdir())])
        old = os.environ.get("PYTHONPATH", "")
        return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", MPLBACKEND="Agg", FFMPEG=ff,
                    PYTHONPATH=pp + (os.pathsep + old if old else ""), DEWIAR_ALLOW_DEL=allow)

    def _run_python(self, t, code, timeout):
        """Сохранить код шагом _run/шагN.py и выполнить в папке задачи в песочнице (до 600 с) -> код выхода, вывод и
        подсказка по ошибке."""
        m = self._sbx_mode(t)
        if not m:
            return ("Ошибка: запуск кода здесь недоступен — нет песочницы. Как исправить: обойдись без кода (файлы — write_file) "
                    "и напиши в итоге, что не удалось посчитать.")
        n = len(list(t.dir.glob("_run/*.py"))) + 1
        f = t.dir / "_run" / f"шаг{n}.py"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(code, encoding="utf-8")
        (t.dir / "outputs").mkdir(exist_ok=True)
        try:
            from eyes import ffmpeg_path
            ff = ffmpeg_path() or ""
        except Exception:  # noqa: BLE001
            ff = ""
        timeout = max(5, min(600, timeout))
        env = self._py_env(t, ff) if m == "off" else {"FFMPEG": ff}
        try:
            r = self._sandboxed(t, m, [self._task_python(), str(f)], timeout, f"run_python, шаг {n}", env, tools=[ff] if ff else ())
        except SBX.SandboxError as e:
            return f"Ошибка: {e}. Обойдись без кода."
        if r.cancelled:
            return "Задачу остановили — код прерван."
        if r.timed_out:
            return (f"Остановлено по времени ({timeout} с): все процессы кода завершены. Делай работу частями: сохраняй "
                    "прогресс в файл.")
        if r.oversize:
            return self._oversize(t)
        out = (r.out + ("\n[stderr]\n" + r.err if r.err.strip() else "")).strip()
        t.journal(f"🐍 Python (шаг {n}): код {r.code}")
        hint = Q.error_hint(out) if r.code else ""
        if r.code:
            q = self._q(t)
            q["errors"] = (q["errors"] + [{"tool": "run_python", "text": (r.err.strip() or out)[-240:]}])[-10:]
        # длинный вывод целиком — в _out/, модели — начало и конец (_offload в _tool, общий для всех инструментов)
        return f"Код выхода {r.code}.\n{out or '(вывода нет)'}" + (f"\n\n{hint}" if hint else "")

    def _run_shell(self, t, cmd, timeout):
        """run_shell (выпуск 5): команда в папке задачи. В bwrap — без вопроса (изоляция настоящая); в режиме охраны и без
        песочницы команда оболочки ничем не ограничена, кроме папки, окружения и времени, — как code_run: с разрешения
        человека (или с автозапуском из настроек). Запрещённое защитой (guard.check_command) — никогда."""
        if not cmd:
            return "Ошибка: пустая команда. Как исправить: command — что выполнить, например «ls -la outputs»."
        m = self._sbx_mode(t)
        if not m:
            return "Ошибка: команды здесь недоступны — нет песочницы. Как исправить: обойдись без них."
        import guard
        v = guard.check_command(cmd, cwd=str(t.dir))
        if v["level"] == "block":
            t.journal(f"🛡 Защита не дала: {cmd} — {v['reason']}")
            return f"Защита Dewiar запретила эту команду: {v['reason']}. Найди другой путь."
        if not SBX.real_sandbox(m):
            # под охраной команда оболочки ничем не заперта — спрашиваем всегда, даже при автозапуске кода (N3)
            warn = guard.describe_warn(v) + " " if v["level"] == "warn" else ""
            if True:
                okd, why = self._permit(t, "run_shell" + (":" + cmd[:300] if warn else ""), f"Задача «{t.title}»: {warn}выполнить в папке задачи «{cmd[:300]}»?")
                if not okd:
                    return why
        (t.dir / "outputs").mkdir(exist_ok=True)
        timeout = max(5, min(600, timeout))
        try:
            r = self._sandboxed(t, m, SBX.shell_argv(cmd), timeout, "run_shell " + cmd[:120], {})
        except SBX.SandboxError as e:
            return f"Ошибка: {e}."
        if r.cancelled:
            return "Задачу остановили — команда прервана."
        if r.timed_out:
            return f"Остановлено по времени ({timeout} с): все процессы команды завершены. Делай работу частями."
        if r.oversize:
            return self._oversize(t)
        out = (r.out + ("\n[stderr]\n" + r.err if r.err.strip() else "")).strip()
        t.journal(f"⌨ Команда: {self._short(cmd, 120)} — код {r.code}")
        if r.code:
            q = self._q(t)
            q["errors"] = (q["errors"] + [{"tool": "run_shell", "text": (r.err.strip() or out)[-240:]}])[-10:]
        return f"Код выхода {r.code}.\n{out or '(вывода нет)'}"

    def _oversize(self, t):
        lim = self.MAX_BYTES or 0
        t.journal(f"🛑 Папка задачи выросла больше {lim >> 20} МБ — код остановлен.")
        return (f"Остановлено: папка задачи больше {lim >> 20} МБ — здесь это предел. Как исправить: удали лишнее (большие "
                "промежуточные файлы) и делай результат компактнее.")

    def _git_state(self, t):
        """Задача по коду: файл (или папка) «рабочая копия/.git» до запуска кода — содержимое (B3)."""
        g = t.dir / "рабочая копия" / ".git"
        try:
            if g.is_symlink() or not g.exists():
                return None
            return ("file", g.read_bytes()) if g.is_file() else ("dir", None)
        except OSError:
            return None

    def _git_check(self, t, was):
        """После кода: «рабочая копия/.git» — как был (код мог направить его на свой gitdir с core.fsmonitor — а git по копии
        Dewiar и code_run запускают вне песочницы)."""
        if was is None:
            return
        g = t.dir / "рабочая копия" / ".git"
        try:
            if was[0] == "file":
                if g.is_symlink() or not g.is_file() or g.read_bytes() != was[1]:
                    if g.is_symlink() or g.is_file():
                        g.unlink()
                    elif g.is_dir():
                        import shutil
                        shutil.rmtree(g, ignore_errors=True)
                    g.write_bytes(was[1])
                    t.journal("🛡 Код задачи менял «рабочая копия/.git» — вернул как было.")
        except OSError:
            log.debug("рабочая копия/.git", exc_info=True)

    def _sbx_mode(self, t):
        """Режим песочницы для кода задачи: "bwrap" | "landlock" (настоящая изоляция) | "guard" (охрана, с разрешения
        человека) | "off"; "" — кода здесь нет (облако без bubblewrap)."""
        return SBX.mode()

    def _sbx_prompt(self, t, light=False):
        """Строка о песочнице для неизменной подсказки задачи (режим и сеть меняются редко — начало запроса из кэша)."""
        m = self._sbx_mode(t)
        if not m:
            return ""
        if light:
            return ("\nПЕСОЧНИЦА: код пишет только в папку задачи" + ("" if t.data.get("net") else ", сети у кода нет")
                    + ". Испортил outputs/ — rewind(step).")
        return ("\n\nПЕСОЧНИЦА: " + SBX.describe(m, bool(t.data.get("net"))) + ". Командная строка — run_shell. Испортил "
                "файлы в outputs/ — rewind(step=N) вернёт их как перед шагом N (без step — список снимков).")

    def _task_python(self):
        import sys
        py = sys.executable
        if os.name == "nt" and py.lower().endswith("pythonw.exe"):     # pythonw не даёт stdout — скрипту нужен python.exe
            py = py[:-len("pythonw.exe")] + "python.exe"
        return py

    def _sbx_kw(self, t):
        """Что видит код задачи: данные человеком папки — только чтение; папка ассистента — закрыта (кроме папки задачи)."""
        try:
            ws = str(self.host.workspace.root)
        except Exception:  # noqa: BLE001
            ws = ""
        prot = self.PROTECT + (("рабочая копия/.git",) if (t.dir / "рабочая копия" / ".git").exists() else ())
        return dict(grants=[str(f) for f in self._folders(t)], net=bool(t.data.get("net")), hide=[ws] if ws else [],
                    protect=prot, strict=False, max_bytes=self.MAX_BYTES)

    def _sandboxed(self, t, m, argv, timeout, why, env, tools=()):
        """Снимок outputs/ → запуск в песочнице → служебные файлы задачи как были -> SBX.Result."""
        self._snap(t, why)
        before = self._svc_state(t)
        git0 = self._git_state(t)
        r = None
        try:
            r = SBX.run(argv, t.dir, timeout=timeout, env=env, cancel=t.cancel, m=m, python=self._task_python(),
                        tools=tools, **self._sbx_kw(t))
            return r
        finally:
            if r is not None and r.links:              # B2: ссылки наружу, оставленные кодом, — удалены (sandbox.purge_links)
                links = self._relink_work(t, r.links)
                if links:
                    t.journal("🛡 Код задачи оставил ссылки за пределы папки задачи (или особые файлы) — удалил: "
                              + ", ".join(links[:8]) + (f" и ещё {len(links) - 8}" if len(links) > 8 else ""))
            self._svc_check(t, before)
            self._git_check(t, git0)

    def _relink_work(self, t, links):
        """Ссылки рабочей копии, которые были в проекте ещё до задачи (проект/shared → ../ext), sandbox.purge_links убрал как
        «ведущие наружу» — возвращаем их как в проекте, иначе они выглядели бы удалёнными, и «Принять» удалил бы их в проекте
        (вторая рецензия). Код и Dewiar по ним не ходят: codework.path() — только внутри копии. -> остальные пути (для журнала)."""
        code = t.code()
        rest = []
        for rel in links:
            pre = "рабочая копия" + os.sep
            if code is not None and rel.startswith(pre):
                w = rel[len(pre):]
                src, dst = code.project / w, code.work / w
                try:
                    if src.is_symlink() and not os.path.lexists(dst):
                        os.symlink(os.readlink(src), dst)
                        continue
                except OSError:
                    pass
            rest.append(rel)
        return rest

    def _svc_state(self, t):
        """Служебные файлы до запуска кода: какие есть и содержимое небольших (учёт, критерии, план, блокнот, итог)."""
        st = {}
        for n in self.PROTECT:
            p = t.dir / n
            if p.is_file() and n in self.SVC_RESTORE and p.stat().st_size <= 4 << 20:
                st[n] = p.read_bytes()
            else:
                st[n] = True if p.exists() else None
        return st

    def _svc_check(self, t, before):
        """После кода: служебное, которое код всё же изменил (обход охраны в режиме guard) или создал, — назад. Состояние
        задачи (задача.json) переписывается из памяти — подделанные папки, сеть и прочее не доживут до перезапуска."""
        fixed = []
        for n, was in before.items():
            p = t.dir / n
            try:
                if p.is_symlink() or (os.path.lexists(p) and not p.is_dir() and not _regular(p)):
                    p.unlink()                             # служебное — ссылкой или FIFO/сокетом: Dewiar по нему не пойдёт
                    fixed.append(n)
                    continue
                if was is None and p.exists():             # создал код (Dewiar в это время их не пишет), в том числе _snap
                    (p.unlink() if not p.is_dir() else __import__("shutil").rmtree(p, ignore_errors=True))
                    fixed.append(n)
                elif isinstance(was, bytes) and (not p.is_file() or p.read_bytes() != was):
                    if p.is_symlink() or p.is_dir():
                        p.unlink() if p.is_symlink() else __import__("shutil").rmtree(p, ignore_errors=True)
                    p.write_bytes(was)
                    fixed.append(n)
            except OSError:
                log.debug("служебный файл %s", n, exc_info=True)
        try:
            t.save()
        except OSError:
            pass
        if fixed:
            t.journal("🛡 Код задачи менял служебные файлы (" + ", ".join(fixed) + ") — вернул как было.")

    def _snap(self, t, why):
        """Перед записью в outputs/ — снимок «как перед шагом N» (раз на шаг; snapshots.py). Не вышло — один раз в журнал."""
        try:
            seq, no = SNAP.Snapshots(t.dir).take(int(t.data.get("steps") or 0), why)
        except (OSError, SNAP.SnapError) as e:
            seq, no = None, f"ошибка диска ({e})"
        if no and not t.data.get("snap_told"):
            t.data["snap_told"] = True
            t.journal(f"📸 Снимок outputs/ не сделан: {no} — этот шаг откатить не получится.")
        return seq

    def _rewind_tool(self, t, args):
        try:
            sn = SNAP.Snapshots(t.dir)
        except (OSError, SNAP.SnapError) as e:
            return f"Ошибка: {e}"
        if args.get("step") in (None, ""):
            ls = sn.listing()
            if not ls:
                return "Снимков пока нет: outputs/ ещё не менялся."
            lines = [(f"перед шагом {x['step']}" if x["kind"] == "step" else f"снимок №{x['seq']} ({x['why']})")
                     + f" — {x['time'][11:16]}, файлов {x['files']}" + (f" ({x['why']})" if x["kind"] == "step" and x["why"] else "")
                     for x in ls[:20]]
            return "Снимки outputs/ (новые первыми):\n" + "\n".join(lines) + "\nОткат: rewind(step=N) — outputs/ станет как перед шагом N."
        try:
            msg = sn.rewind(int(t.data.get("steps") or 0), step=int(args.get("step")))
        except (SNAP.SnapError, ValueError, TypeError) as e:
            return f"Ошибка: {e}"
        except OSError as e:
            return f"Ошибка: откатить не вышло ({e}). Как исправить: проверь outputs/ (file_glob)."
        self._after_rewind(t, msg)
        return msg + " Проверь outputs/ (file_glob) и продолжай с этого места."

    def _after_rewind(self, t, msg, who="задача"):
        outs = [o for o in t.data.get("outputs") or [] if (t.dir / str(o.get("path") or "")).is_file()]
        t.data["outputs"] = outs
        t.journal(f"⏪ Откат ({who}): {msg}")
        t.save()
        self._emit(t)
