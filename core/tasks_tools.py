"""Фоновые задачи, часть «действия» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
каталог и поиск действий, вызов, разрешения, вывод — большие ответы в файл."""
import re
from pathlib import Path

from codework import CodeError
from tasks_base import (
    ASK_DECLINES, ASK_SILENT, CODE_TOOLS, FIND_TOOL, log, NOTEBOOK_HEAD, _now, OUT_MAX, PART_TOOLS, PROFILE_CHAT,
    PROFILE_TASK, PROFILE_WORK, RETRY_SAFE, RETRY_SEC, SKIP_IN_TASK, SUB_TOOLS, TASK_TOOLS, TINY_DROP, TINY_WIN,
    WIN_DEFAULT, WORK_TOOLS, _wr)
import tasks_base as TB  # подменяемые в проверках имена — через основу


class ToolsMixin:
    def _catalog(self, t):
        """Все инструменты, которые задача МОЖЕТ получить: имя -> описание. Инструменты чата (кроме SKIP_IN_TASK) +
        свои (TASK_TOOLS, WORK_TOOLS — одноимённые инструменты чата заменяются своими) + код (только у задачи с проектом)
        + части (не у части) + find_tool."""
        cat = {}
        for x in self.host.toolbox.specs():
            if x["name"] not in SKIP_IN_TASK:
                cat.setdefault(x["name"], x)
        own = dict(TASK_TOOLS, **WORK_TOOLS)
        if t.data.get("project"):
            own.update(CODE_TOOLS)
        if not t.data.get("parent"):                       # часть сама частей не раздаёт
            own.update({k: (d.replace("{pm}", str(self._parts_max())), p) for k, (d, p) in PART_TOOLS.items()})
        own.update(SUB_TOOLS)                              # выпуск 6: разведчик и проверяющий — и у частей
        own.update(FIND_TOOL)
        for n, (d, prm) in own.items():
            cat[n] = {"name": n, "description": d, "parameters": prm}
        return cat

    def _specs(self, t):
        """Инструменты задачи (выпуск 1): постоянный профиль ≈20 штук в неизменном порядке + подключённые через find_tool
        (t.data["tools_on"]) — в конце, по порядку подключения: список только растёт с конца, начало запроса не меняется.
        Лёгкий режим (маленькое окно) — без частей и навыков."""
        cat = self._catalog(t)
        light = bool(t.data.get("light"))
        names = list(PROFILE_TASK) + list(PROFILE_WORK)
        names += [n for n in PROFILE_CHAT if not (light and n in ("use_skill", "read_skill_file"))]
        if t.data.get("project"):
            names += list(CODE_TOOLS)
        names.append("explore")                            # выпуск 6: разведчик — и в лёгком режиме (маленькому окну он нужнее всего)
        if not light:
            names.append("verify")
            names += list(PART_TOOLS)
        names += list(FIND_TOOL)
        tiny = int(t.data.get("win") or WIN_DEFAULT) < TINY_WIN
        if tiny:                                           # окно меньше 6 тыс.: самое нужное, остальное — find_tool
            names = [n for n in names if n not in TINY_DROP]
        names += [n for n in t.data.get("tools_on") or [] if n not in names]
        out = [cat[n] for n in dict.fromkeys(names) if n in cat]
        if tiny:                                           # …и описания — до первой фразы
            out = [dict(x, description=self._first(x.get("description") or "")) for x in out]
        return out

    @staticmethod
    def _first(d):
        m = re.match(r"(.+?[.!?])(?:\s|$)", d, re.S)
        return (m.group(1) if m else d)[:160]

    @staticmethod
    def _stems(text):
        """Слова для поиска инструмента: нижний регистр, первые 5 букв (грубая основа: «напоминание» ~ «напомни»)."""
        return {w[:5] for w in re.findall(r"[a-zа-яё0-9]{3,}", (text or "").lower().replace("_", " "))}

    def _connect(self, t, name):
        on = list(t.data.get("tools_on") or [])
        if name not in on:
            on.append(name)
            t.data["tools_on"] = on
            t.journal(f"🧰 Подключил инструмент: {name}")

    def _find_tool(self, t, args):
        """find_tool: подходящие инструменты по описанию; connect — подключить до конца задачи."""
        cat = self._catalog(t)
        active = {x["name"] for x in self._specs(t)}
        want = str(args.get("connect") or args.get("name") or "").strip()
        q = str(args.get("query") or "").strip()
        if not want and q in cat:
            want = q
        if want:
            if want in active:
                return f"Инструмент {want} уже доступен — вызывай его."
            if want in cat:
                self._connect(t, want)
                return f"Подключил {want}: {cat[want]['description'][:400]}\nТеперь вызывай его как обычно."
            return self._unknown(t, want)
        qs = self._stems(q)
        scored = []
        for n, x in cat.items():
            if n in active:
                continue
            words = self._stems(n + " " + x.get("description", ""))
            sc = len(qs & words) + (3 if n.lower() in q.lower() else 0)
            if sc:
                scored.append((-sc, n))
        scored.sort()
        if not scored:
            return ("Ничего подходящего не нашлось. Сейчас доступны: " + ", ".join(sorted(active)) + ". Опиши, что нужно "
                    "сделать, другими словами — или обойдись этими.")
        top = [n for _, n in scored[:5]]
        return ("Подходящие инструменты (подключить — find_tool с connect=<имя>, или просто вызови его):\n" +
                "\n".join(f"- {n} — {cat[n]['description'][:220]}" for n in top))

    def _unknown(self, t, name):
        """Модель позвала инструмент, которого нет: понятная ошибка с тем, что есть (а не «выключен пользователем», №…:
        подсказки называли read_page, а на компьютере — read_webpage)."""
        import difflib
        active = [x["name"] for x in self._specs(t)]
        near = difflib.get_close_matches(name, list(self._catalog(t)), n=2, cutoff=0.6)
        return (f"Ошибка: нет такого инструмента «{name}»." + (f" Похоже, нужен: {', '.join(near)}." if near else "")
                + " Есть: " + ", ".join(active) + ". Другие — через find_tool(query).")

    def _coerce(self, t, name, args):
        """Привести аргументы к схеме инструмента (слабые модели шлют список вместо строки и т. п.), см. tools.coerce_args."""
        from tools import coerce_args
        spec = self._catalog(t).get(name)
        return coerce_args((spec or {}).get("parameters"), args)

    def _tool(self, t, name, args):
        """Выполнить вызов модели -> текст результата. Любая ошибка — ответом модели («Ошибка: …»), а не падением задачи.
        _truncated ставит llm.py, когда ответ модели оборвался по лимиту длины и аргументы удалось спасти лишь частично."""
        trunc = isinstance(args, dict) and bool(args.pop("_truncated", False))
        try:
            ca = self._coerce(t, name, args)
            r = self._tool_raw(t, name, ca)
            if name in RETRY_SAFE and isinstance(r, str) and r.startswith(("Ошибка", "Поиск не удался", "Страница не открылась")) \
                    and self._transient(r) and "Как исправить" not in r and not t.cancel.is_set():
                # выпуск 2: безопасный инструмент (поиск, чтение, скачивание) упал на сбое сети — пауза и ещё раз, сам
                t.journal(f"↻ {name}: сбой сети ({self._short(r, 120)}) — повторяю через {RETRY_SEC:g} с.")
                t.cancel.wait(RETRY_SEC)
                if not t.cancel.is_set():
                    r = self._tool_raw(t, name, ca)
            self._src_log(t, name, ca, r)                  # выпуск 3: опора для сверки итога — целиком, до обрезки
            if trunc:
                self._q(t)["errors"].append({"tool": name, "text": "ответ оборвался по лимиту длины"})
                if name == "write_file" and isinstance(r, str) and not r.startswith("Ошибка"):
                    tail = str(args.get("content") or "")[-160:]
                    r += ("\n\nВНИМАНИЕ: твой ответ ОБОРВАЛСЯ по лимиту длины — записана только первая часть файла. Он кончается "
                          f"так: «…{tail}». Допиши продолжение (write_file с append=true) кусками не больше ~120 строк, НЕ переписывая "
                          "файл с нуля.")
                else:
                    r = f"{r}\n\n(Твой ответ оборвался по лимиту длины — аргументы могли дойти не целиком: проверь результат. Делай шаги меньше.)"
            return self._offload(t, name, r)
        except Exception as e:  # noqa: BLE001
            log.exception("задача %s: инструмент %s", t.id, name)
            if not isinstance(e, (ValueError, OSError, TimeoutError)):   # не «плохие аргументы», а ошибка в программе
                self._problem(f"Задача, инструмент {name}: {e.__class__.__name__}: {str(e)[:160]}")
            return (f"Ошибка инструмента {name}: {e}. Как исправить: проверь аргументы (строки — строками, пути — как в "
                    "file_glob) и попробуй ещё раз или иначе.")

    def _out_max(self, t):
        """Сколько знаков вывода инструмента держать в истории: OUT_MAX, при маленьком окне — меньше (~10% окна). Окно
        меньше TINY_WIN — без нижней планки 1500 (0.84: при окне 4 тыс. последний результат, которого сжатие не трогает,
        вместе с длинным путём папки выводил запрос за окно)."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        return max(1500 if win >= TINY_WIN else 800, min(OUT_MAX, int(win * 3 * 0.1)))

    def _offload(self, t, name, r):
        """Вывод любого инструмента длиннее _out_max — целиком в _out/<инструмент>-<шаг>.txt, в историю — начало, конец и
        путь (Manus, Anthropic: файловая система как память). read_file и ответы человека не трогаем: read_file сам режет
        куски по размеру, а ответ человека — главное."""
        lim = self._out_max(t)
        if not isinstance(r, str) or len(r) <= lim or name in ("read_file", "file_read", "ask_user", "finish", "wait_parts", "use_skill", "read_skill_file",
                                                   "explore", "verify"):   # у разведчика и проверяющего — свой предел
            return r
        n = int(t.data.get("steps") or 0)
        f = t.dir / "_out" / f"{name}-{n}.txt"
        k = 2
        while f.exists():
            f = t.dir / "_out" / f"{name}-{n}-{k}.txt"
            k += 1
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            _wr(f, r, root=t.dir)
        except OSError:
            return r[:lim] + "\n…(вывод обрезан)"
        rel = f.relative_to(t.dir).as_posix()
        head, tail = int(lim * 0.65), int(lim * 0.25)
        return (r[:head] + f"\n…[вывод {len(r)} знаков — целиком в файле {rel}: читай его file_read кусками (start/end), "
                "не запускай заново]…\n" + r[-tail:])

    def _tool_raw(self, t, name, args):
        """Собственно выполнение. Сначала свои инструменты задачи, потом инструменты ассистента — с теми же
        включателями, защитой и подтверждениями, что в чате (toolbox.policy/guard, host.confirm).
        Может надолго блокировать поток: ask_user ждёт ответа, confirm — решения человека."""
        if name == "update_plan":
            plan = (args.get("plan") or "").strip()
            if not plan.startswith("#"):
                plan = f"# {t.title}\n\n**Цель:** {t.goal}\n\n{plan}"
            _wr(t.dir / "план.md", plan + "\n")
            done, total = plan.count("[x]") + plan.count("[X]"), len(re.findall(r"\[[ xX]\]", plan))
            weak = self._sync_md(t, plan)                 # выпуск 4: и в задачи.json (совместимость Markdown ↔ JSON)
            if weak:
                done -= len(weak)
                t.journal("📋 Отмечены без доказательства — в списке дел «в работе»: " + "; ".join(weak)[:300])
            t.data["progress"] = [done, total]
            return f"План сохранён ({done} из {total} пунктов выполнено)." + (
                "\nОтмечены [x] без доказательства — считаю их «в работе»: " + "; ".join(weak[:6]) + ". Допиши в пункт доказательство "
                "(путь к файлу, ссылку или вывод с цифрами: «- [x] свести данные — outputs/свод.csv») или отметь через todo_update "
                "с evidence." if weak else "")
        if name == "todo_update":
            return self._todo_update(t, args)
        if name == "set_criteria":
            return self._set_criteria(t, args)
        if name == "log":
            t.journal("📝 " + (args.get("text") or ""))
            return "Записано."
        if name == "spawn_parts":
            return self._spawn_parts(t, args.get("parts") or [])
        if name == "explore":
            return self._explore(t, args)
        if name == "verify":
            return self._verify_tool(t, args)
        if name == "wait_parts":
            return self._wait_parts(t, float(args.get("minutes") or 60))
        if name == "ask_user":
            q = (args.get("question") or "").strip()
            t.data.update(status="waiting", question=q, question_was=q, asked_at=_now(), ask_reminded=False)
            t.save()
            self._emit(t)
            t.journal(f"❓ Вопрос пользователю: {q}")
            self._push(f"❓ Задача «{t.title}» спрашивает", q[:200], critical=True)
            t.answer_ev.clear()
            t.answer = None
            self.host.ask_user(t, q)
            while not t.answer_ev.wait(1):                # раз в секунду — проверить, не остановили ли задачу
                if t.cancel.is_set():
                    break
            t.data.update(status="running", question="")
            t.save()
            self._emit(t)
            if t.cancel.is_set():
                return "Задачу остановили."
            t.journal(f"💬 Ответ: {t.answer}")
            self._note_human(t, f"На вопрос «{q[:200]}»: {t.answer}")
            return f"Ответ пользователя: {t.answer}"
        if name == "remember":
            fact = re.sub(r"\s+", " ", (args.get("fact") or "").strip())
            if not fact:
                return "Пустой факт — нечего записать."
            nb = t.notebook() or NOTEBOOK_HEAD
            line = f"- {fact} _({TB.dt.datetime.now():%d.%m %H:%M})_"
            if "## Что известно" in nb:
                nb = nb.replace("## Что известно\n", "## Что известно\n" + line + "\n", 1)
            else:
                nb = nb.rstrip() + "\n" + line + "\n"
            t.set_notebook(nb)
            t.journal(f"📌 В блокнот: {fact}")
            return "Записано в блокнот."
        if name == "notes":
            t.set_notebook(args.get("text") or "")
            t.journal("📒 Блокнот переписан.")
            return "Блокнот обновлён."
        if name == "notify":
            text = (args.get("text") or "").strip()
            if not text:
                return "Пустое сообщение."
            import time as _t
            last = t.data.get("notified_at") or 0
            if not args.get("important") and _t.time() - last < 60:     # не чаще раза в минуту, кроме срочного
                t.journal(f"🔕 (не отправил — прошло меньше минуты) {text}")
                return "Только что уже сообщал — это записал в журнал. Сообщи позже, когда будет что-то новое."
            t.data["notified_at"] = _t.time()
            t.journal(f"📣 Сообщил: {text}")
            self._push(f"📌 {t.title}", text, critical=bool(args.get("important")))
            return "Сообщение отправлено пользователю."
        if name == "wait":
            reason = (args.get("reason") or "").strip() or "проверить, что изменилось"
            when = None
            if args.get("until"):
                try:
                    when = TB.dt.datetime.fromisoformat(str(args["until"]).strip().replace(" ", "T"))
                except ValueError:
                    return "Время не понял — until в виде YYYY-MM-DDTHH:MM (местное время) или minutes."
            elif args.get("minutes") is not None:
                try:
                    when = TB.dt.datetime.now() + TB.dt.timedelta(minutes=max(0.05, float(args["minutes"])))
                except (TypeError, ValueError):
                    return "minutes — число минут."
            on = self._wake_on(t, args)                   # выпуск 8, п.7: ждать события, а не гадать со временем
            if isinstance(on, str):
                return on
            if when is None and on:
                when = TB.dt.datetime.now() + TB.dt.timedelta(days=3)  # событие — главное; крайний срок по умолчанию — 3 дня
            if when is None:
                return "Скажи, когда вернуться: minutes или until (или on_file / on_mail — по событию)."
            if when < TB.dt.datetime.now():
                return "Это время уже прошло — проверь сейчас."
            when = min(when, TB.dt.datetime.now() + TB.dt.timedelta(days=30))   # не дальше месяца
            # sleep_now — сигнал циклу _run выйти после этого шага; будит _scheduler
            t.data.update(status="sleeping", wake_at=when.isoformat(timespec="seconds"), wait_reason=reason, sleep_now=True,
                          wake_on=on or None)
            t.save()
            ev = ("; или как только " + " / ".join(x for x in (f"появится или изменится «{Path(on['file']).name}»" if on.get("file") else "",
                                                              f"придёт письмо «{on['mail']}»" if on.get("mail") else "") if x)) if on else ""
            t.journal(f"⏳ Жду до {when:%d.%m %H:%M}{ev}: {reason}")
            return f"Хорошо, вернусь к задаче {when:%d.%m в %H:%M}{ev} (или раньше, если пользователь напишет)."
        if name == "finish":
            # невыполненные пункты плана — один раз напоминаем, дальше — проверки качества (_finish_gates)
            plan = t.plan()
            todo = [m.strip() for m in re.findall(r"^\s*[-*]\s*\[ \]\s*(.+)$", plan, re.M)]
            if todo and not t.data.get("finish_checked"):
                t.data["finish_checked"] = True
                t.journal("✋ Проверка перед итогом: в плане есть невыполненные пункты.")
                return ("Прежде чем закончить, проверь цель. В плане не отмечено: " + "; ".join(todo[:8]) + ". Если это "
                        "сделано — отметь в плане (update_plan) и снова вызови finish. Если ждёшь чего-то внешнего — wait. "
                        "Если сделать нельзя — так и напиши в итоге и снова вызови finish.")
            note = self._finish_gates(t, (args.get("summary") or "").strip())
            if note:
                return note
            summary = self._russian((args.get("summary") or "").strip()) or "Готово."
            if t.data.get("unfinished"):                 # №368: честное «не выполнено» — остановка, а не успех
                # экзамен 0.99 (15.11): «Не выполнено: проверка не согласилась…» — и ниже «**Готово — поездка спланирована**»,
                # «0 ошибок»: человек читал два противоречащих итога. Заголовок «Готово» из рассказа задачи убираем
                summary = re.sub(r"\A\s*(?:#+\s*)?\**\s*готово\b[^\n]*\n+", "", summary, flags=re.I) or summary
                summary = (f"**Не выполнено:** {t.data['unfinished']}.\n\nЧто успела (так считает сама задача — проверка с "
                           f"итогом не согласилась, перепроверьте):\n\n{summary}")
            _wr(t.dir / "итог.md", f"# Итог: {t.title}\n\n{summary}\n")
            t.data.update(result=summary, finished=True)
            return "Задача завершена." if not t.data.get("unfinished") else "Задача остановлена: не выполнено."
        if name in WORK_TOOLS:
            try:
                return self._work(t, name, args)
            except Exception as e:  # noqa: BLE001
                return f"Ошибка: {e}"
        if name in CODE_TOOLS:
            c = t.code()
            if c is None:
                return "У задачи нет проекта."
            try:
                c.prepare()
                if name == "code_list":
                    return c.list(args.get("pattern", ""))
                if name == "code_read":
                    return c.read(args.get("path", ""), args.get("start") or 1, args.get("end"))
                if name == "code_search":
                    return c.search(args.get("pattern", ""), args.get("glob", ""))
                if name == "code_edit":
                    return c.edit(args.get("path", ""), args.get("old", ""), args.get("new", ""))
                if name == "code_write":
                    return c.write(args.get("path", ""), args.get("content", ""))
                if name == "code_delete":
                    return c.delete(args.get("path", ""))
                if name == "code_diff":
                    return c.diff(limit=30000) or "Изменений пока нет."
                if name == "code_undo":
                    return c.undo(args.get("steps") or 1)
                if name == "code_process":
                    return c.process(args.get("action") or "status", args.get("id") or "")
                if name == "code_run":
                    # безопасность: та же проверка команд (guard.check_command), что в чате; опасное — только с согласия человека,
                    # остальное — без вопроса, если в настройках разрешён автозапуск кода
                    cmd = args.get("command", "")
                    import guard
                    v = guard.check_command(cmd, cwd=str(c.work))
                    if v["level"] == "block":
                        t.journal(f"🛡 Защита не дала: {cmd} — {v['reason']}")
                        return f"Защита Dewiar запретила эту команду: {v['reason']}. Найди другой путь."
                    warn = guard.describe_warn(v) + " " if v["level"] == "warn" else ""
                    if warn or not self.host.code_auto_run():
                        okd, why = self._permit(t, "code_run" + (":" + cmd if warn else ""), f"Задача «{t.title}»: {warn}выполнить в проекте «{cmd}»?")
                        if not okd:
                            return why
                    if args.get("background"):
                        return c.start_bg(cmd)
                    return c.run(cmd, args.get("timeout") or 180)
            except CodeError as e:
                return f"Ошибка: {e}"
            except OSError as e:                     # №222: «Access is denied» на сетевой папке — ошибка шага, а не сбой программы
                return f"Ошибка: нет доступа к файлу {getattr(e, 'filename', '') or ''} ({e.strerror or e}). Обойди этот файл или выбери другую папку."
        if name == "find_tool":
            return self._find_tool(t, args)
        # обычные инструменты ассистента
        on, need = self.host.toolbox.policy(name)
        if name not in self._catalog(t):
            try:
                from tools import TOOLS as _ALL
            except Exception:  # noqa: BLE001
                _ALL = {}
            if not on and name in _ALL and name not in SKIP_IN_TASK:
                return f"Инструмент {name} выключен пользователем (студия → «Руки» → «Умения»). Обойдись без него."
            return self._unknown(t, name)
        if not on:
            return f"Инструмент {name} выключен пользователем."
        if name not in {x["name"] for x in self._specs(t)}:
            self._connect(t, name)                     # позвала знакомый инструмент не из профиля — подключаем до конца задачи
        blocked, force, warn_q = self.host.toolbox.guard(name, args)
        if blocked:
            t.journal(f"🛡 Защита не дала: {name} — {blocked}")
            return f"Защита Dewiar запретила это: {blocked}. Так делать нельзя — найди другой путь или спроси пользователя."
        if need or force:
            okd, why = self._permit(t, name, f"Задача «{t.title}»: {warn_q or self.host.toolbox.describe(name, args)}")
            if not okd:
                return why
        try:
            if name == "web_search" and t.data.get("search_url"):     # свой поиск задачи (экзамен Б1: «интернет» из заготовки)
                from tools import search_text, searx_results
                return search_text(searx_results(t.data["search_url"], str(args.get("query") or "")))
            return self.host.toolbox.run(name, args)
        except Exception as e:  # noqa: BLE001
            return f"Ошибка: {e}"

    def _permit(self, t, key, question):
        """Спросить человека разрешение на действие задачи -> (да?, текст для модели при «нет»).
        Отказ запоминается до конца запуска: то же действие (тот же инструмент) больше не спрашиваем, а модели
        говорим обойтись без него. ASK_DECLINES отказов или ASK_SILENT вопросов подряд без ответа — задача встаёт
        на паузу (pause_now), а не спрашивает без конца и не жжёт токены (№54: «Лаборатория: запись?» раз за разом;
        №58: ночью команды по одной каждые 2 минуты, никто не отвечал)."""
        st = self.__dict__.setdefault("_asks", {}).setdefault(t.id, {"no": set(), "declined": 0, "silent": 0})
        # 16.11 (Кодер на Windows: «каждую секунду просил подтверждения вслух, пока не нашёл переключатель»): «Всегда» —
        # это действие в этой задаче больше не спрашиваем; вслух — только первый вопрос задачи, дальше — на экране
        ok_keys = st.setdefault("ok", set())
        if key in ok_keys:
            return True, ""
        quiet = st.get("asked", 0) >= 1
        st["asked"] = st.get("asked", 0) + 1
        if key in st["no"]:                                   # уже отказали, а модель снова за своё — это тоже в счёт
            st["declined"] += 1
            if st["declined"] >= ASK_DECLINES:
                t.data["pause_now"] = ("Вы уже отказали, а задача снова пробует то же самое — остановил её, чтобы не "
                                       "крутилась впустую. Напишите задаче, как быть, или скажите «продолжи задачу».")
            return False, ("Пользователь уже отказал в этом действии — больше не спрашиваю. Не пробуй то же другим способом: "
                           "обойдись без него или спроси (ask_user), что делать.")
        import inspect
        try:
            params = inspect.signature(self.host.confirm).parameters
        except (TypeError, ValueError):
            params = {}
        kw = {k: v for k, v in (("cancel", t.cancel), ("always", True), ("quiet", quiet)) if k in params}
        ans = self.host.confirm(question, **kw)
        if ans == "always":
            ok_keys.add(key)
            t.journal(f"✅ «Всегда» — {key} в этой задаче больше не спрашиваю")
        if ans:
            st["silent"] = 0
            return True, ""
        if t.cancel.is_set():
            return False, "Задачу остановили."
        if ans is None:                                       # никто не ответил за 2 минуты
            st["silent"] += 1
            t.journal(f"❔ Нет ответа на вопрос: {question}")
            if st["silent"] >= ASK_SILENT:
                t.data["pause_now"] = ("Задаю вопросы, а ответа нет — остановился, чтобы не спрашивать впустую. "
                                       "Скажите «продолжи задачу», когда будете рядом.")
            return False, ("Пользователь не ответил (его, видимо, нет рядом). Не спрашивай снова то же самое: сделай то, что "
                           "можно без этого, а вопрос запиши в блокнот («Чего ждём»).")
        st["no"].add(key)
        st["declined"] += 1
        st["silent"] = 0
        t.journal(f"✋ Пользователь отказал: {question}")
        if st["declined"] >= ASK_DECLINES:
            t.data["pause_now"] = (f"Вы отказали {st['declined']} раза — остановился, чтобы не спрашивать без конца. "
                                   "Напишите задаче, как быть, или скажите «продолжи задачу».")
        return False, ("Пользователь отказался. Больше это действие не предлагай и не пробуй его другими командами: обойдись "
                       "без него или спроси (ask_user), как быть.")

    def _tool_on(self, name):
        """Инструмент разговора включён у человека (студия → «Руки» → «Умения»)."""
        if name in WORK_TOOLS or name in TASK_TOOLS:
            return True
        try:
            return bool(self.host.toolbox.policy(name)[0])
        except Exception:  # noqa: BLE001
            return False
