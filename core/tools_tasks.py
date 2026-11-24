"""Действия модели: фоновые задачи (начать, состояние, дополнить, остановить, продолжить) и позвать персонажа."""

import re
from pathlib import Path
from tools_base import ToolError


def _tm(ctx):
    """TaskManager (tasks.py) из ctx, иначе ToolError."""
    tm = ctx.get("tasks")
    if tm is None:
        raise ToolError("фоновые задачи недоступны")
    return tm


def _net_note():
    """Честно: что именно получит код задачи с сетью в этой песочнице (S3) — своя сеть или сеть компьютера целиком."""
    try:
        import sandbox
        return sandbox.net_note(sandbox.mode())
    except Exception:  # noqa: BLE001
        return "сеть этого компьютера, включая локальные службы"


def _wants_net(a):
    """start_task(network=true): модель просит сеть для кода задачи (строку «true» тоже понимаем)."""
    v = (a or {}).get("network")
    return v is True or str(v).strip().lower() == "true"


FOLDER_ROOTS = ("Documents", "Документы", "Desktop", "Рабочий стол", "Downloads", "Загрузки", "OneDrive")


def guess_folders(goal, home=None, limit=4000):
    """№935 (20.11, 1.0.44: «основываясь на структуре папки „Тренировка“» — задача не видела папку и стояла, пока человек не
    дал доступ сам; «это всё сказано в файлах задания»). Папки, названные в цели: полный путь, который есть на диске, или имя
    в кавычках после слова «папка» — если такая папка одна в Документах, на рабочем столе, в Загрузках (до 4 уровней).
    Весь диск и домашняя папка целиком — никогда. -> [полные пути]."""
    out = []
    text = str(goal or "")
    for m in re.finditer(r"(?:(?<![\w:/.])[A-Za-z]:\\|(?<![\w:/.])/(?=\w)|~/)[^\s«»\"'<>|*?]+", text):
        fp = Path(m.group(0).rstrip(".,;:)»")).expanduser()
        try:
            if fp.is_dir() and fp.resolve() != Path(fp.resolve().anchor) and fp.resolve() != Path.home().resolve():
                out.append(str(fp.resolve()))
        except OSError:
            continue
    names = {n.strip() for n in re.findall(r"папк\w*\s+[«\"'„“]([^»\"'“”]{2,60})[»\"'“”]", text, re.I)}
    if names:
        home = Path(home or Path.home())
        hits = {n: [] for n in names}
        seen = 0
        for r in FOLDER_ROOTS:
            base = home / r
            if not base.is_dir():
                continue
            stack = [(base, 0)]
            while stack and seen < limit:
                d, depth = stack.pop()
                try:
                    kids = [x for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")]
                except OSError:
                    continue
                for k in kids:
                    seen += 1
                    for n in names:
                        if k.name.casefold() == n.casefold():
                            hits[n].append(k)
                    if depth < 3:
                        stack.append((k, depth + 1))
        for n, xs in hits.items():
            if len(xs) == 1:                               # одна такая — она; несколько — пусть спросит
                out.append(str(xs[0].resolve()))
    return list(dict.fromkeys(out))


def t_start_task(a, ctx):
    goal = (a.get("goal") or "").strip()
    if not goal:
        raise ToolError("опиши цель задачи")
    on = (a.get("on") or "").strip()
    if on and ctx.get("remote_task"):                  # «на рабочем компьютере…» (0.56): задача названному своему компьютеру
        try:
            r = ctx["remote_task"](on, a.get("title") or "", goal, (a.get("if_off") or "").strip())
        except ValueError as e:
            raise ToolError(str(e)) from e
        if r is not None:
            return r
    ask = _start_ask(a, ctx, goal)                     # HARNESS 7: большую задачу — сначала «план, срок, цена — начинаю?»
    if ask:
        return ask
    try:
        fl = a.get("folders") or []
        fl = [fl] if isinstance(fl, str) else [str(x) for x in fl if str(x).strip()]
        found = [x for x in guess_folders(goal) if x not in fl]
        if found:                                          # №935: папку назвали в цели — задача видит её сразу
            fl += found
        kw = {"folders": fl} if fl else {}
        if _wants_net(a):                                  # сеть для кода задачи — с «да» человека (Toolbox.guard)
            kw["net"] = True
        t = _tm(ctx).create(a.get("title") or goal[:50], goal, a.get("project") or "", **kw)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return (f"Задача «{t.title}» запущена в фоне. План и журнал — в папке «Задачи» и в студии. Результата ЕЩЁ НЕТ — он "
            "появится через несколько минут или дольше. Скажи пользователю одной фразой, что взялся и сообщишь, когда будет "
            "готово; не говори «готово», «сделал», «вот презентация» — это неправда, пока задача не закончилась.")


def _start_ask(a, ctx, goal):
    """HARNESS, выпуск 7 (как у среды Claude: ясное — делать сразу, дорогое — один вопрос до старта). По завершённым задачам
    того же вида: обычно дольше EST_ASK_MIN минут или дороже EST_ASK_TOKENS — не запускаем, а просим модель сказать
    человеку план в двух фразах, срок и цену и спросить «начинаю?». confirmed=true — человек согласился; дело по
    расписанию (_unattended) — спросить некого, запускаем. Оценки нет (мало истории) — запускаем сразу. -> текст или ""."""
    if a.get("confirmed") or a.get("_unattended"):
        return ""
    try:
        from tasks import EST_ASK_MIN, EST_ASK_TOKENS
        est = _tm(ctx).estimate(goal)
    except Exception:  # noqa: BLE001
        return ""
    if not est.get("n") or (est["minutes"] < EST_ASK_MIN and est["tokens"] < EST_ASK_TOKENS):
        return ""
    price = ""
    f = ctx.get("talers_for_tokens")
    if callable(f):
        try:
            tl = f(est["tokens"])
            price = f", около {tl:.2f} талера" if tl else ""
        except Exception:  # noqa: BLE001
            price = ""
    return (f"НЕ ЗАПУЩЕНО — сначала спроси. Похожие задачи ({est['n']}) обычно идут около {est['minutes']} мин и тратят около "
            f"{(str(round(est['tokens'] / 1e6, 1)).replace('.', ',') + ' млн') if est['tokens'] >= 1e6 else str(est['tokens'] // 1000) + ' тыс.'} токенов{price}. Скажи человеку план в двух фразах, срок и цену и спроси: «начинаю?». "
            "Согласится — вызови start_task снова с теми же полями и confirmed=true; захочет короче — сузь цель.")


POD_RU = {"working": "готовится", "done": "готов", "error": "не получился", "stopped": "остановлен"}


def _podcasts_brief(ctx, days=3):
    """Подкасты за последние дни (№788: «мой подкаст готов?» — task_status отвечал «задач нет», хотя выпуск был готов
    и ждал в «Подкастах»). -> строка для модели или ""."""
    import time
    eng = ctx.get("engine")
    try:
        pods = eng.podcasts.list() if eng is not None and hasattr(eng, "podcasts") else []
    except Exception:  # noqa: BLE001 — подкасты не главное в ответе о задачах
        return ""
    since = time.time() - days * 86400
    pods = [x for x in pods if x.get("status") == "working" or (x.get("created") or 0) >= since][:3]
    if not pods:
        return ""
    out = []
    for x in pods:
        d = int(x.get("duration") or 0)
        ln = f" — {d // 60}:{d % 60:02d}" if d and x.get("status") == "done" else ""
        out.append(f"«{x.get('title')}» — {POD_RU.get(x.get('status'), x.get('status'))}{ln}"
                   + (f" ({x['error'][:120]})" if x.get("status") == "error" and x.get("error") else ""))
    return "Подкасты (слушать — студия → «Подкасты»): " + "; ".join(out)


def t_task_status(a, ctx):
    tm = _tm(ctx)
    items = tm.list()
    pods = _podcasts_brief(ctx)
    if not items:
        return pods or "Задач пока нет."
    from tasks import tasks_brief
    head = tasks_brief(items)
    lines = [head + " (начни ответ с этой фразы; подробности — если спросят)"] if head else []
    for x in items[:6]:
        prog = x.get("progress") or [0, 0]
        extra = f", план {prog[0]} из {prog[1]}" if prog[1] else ""
        q = f", вопрос: {x['question']}" if x.get("question") else ""
        w = f", ждёт: {x['wait_reason']}" if x.get("status") == "sleeping" and x.get("wait_reason") else ""
        lines.append(f"«{x['title']}» — {x['status_ru']}, шагов {x.get('steps', 0)}{extra}{q}{w}"
                     + (f". Итог: {x['result'][:300]}" if x.get("result") else ""))
    try:                                                    # главное из блокнота текущей задачи — что уже известно
        cur = tm.get("")
        nb = cur.notebook() if cur.status != "done" else ""
        facts = [ln.strip() for ln in nb.splitlines() if ln.strip().startswith("- ")][:8]
        if facts:
            lines.append(f"Блокнот «{cur.title}»:\n" + "\n".join(facts))
    except (KeyError, AttributeError, OSError):
        pass
    if pods:
        lines.append(pods)
    return "\n".join(lines)


def t_remove_task(a, ctx):
    """24.10, владелец: «попросил удалить задачу — она долго рассказывала, что не умеет»."""
    tm = _tm(ctx)
    try:
        t = tm.get(str(a.get("name") or "").strip() or "\u0000")
    except KeyError as e:
        raise ToolError(f"{e}. Задачи: " + ", ".join(f"«{x['title']}»" for x in tm.list()[:8])) from e
    title = t.title
    tm.delete(t.id)
    return f"Задача «{title}» удалена — напоминаний о ней больше не будет."


def t_tell_task(a, ctx):
    """№551 (04.11): «я спросил дать права — молчит». Задача «Анализ кода и БД проекта» час ходила по своей папке, не зная, где
    проект, а «может, тебе дать доступ» уходило в разговор — передать задаче было нечем. Теперь разговор передаёт задаче
    сообщение, ответ на её вопрос или папки человека (папки — только после «да» человека, см. Toolbox.guard)."""
    tm = _tm(ctx)
    text = (a.get("text") or "").strip()
    fl = a.get("folders") or []
    fl = [fl] if isinstance(fl, str) else [str(x) for x in fl if str(x).strip()]
    if not text and not fl:
        raise ToolError("что передать задаче: text (сообщение, ответ) или folders (папки)")
    try:
        t = tm.get(a.get("name") or "")
    except KeyError as e:
        raise ToolError(str(e)) from e
    if fl:
        have = list(t.data.get("folders") or [])
        add = []
        for x in fl:
            fp = Path(x).expanduser()
            if not fp.is_dir():
                raise ToolError(f"папки нет: {x}")
            if fp.resolve() == Path(fp.resolve().anchor):
                raise ToolError(f"«{fp.resolve()}» — это весь диск; задаче можно дать только конкретную папку")
            if str(fp.resolve()) not in have:
                add.append(str(fp.resolve()))
        if add:
            t.data["folders"] = have + add
            t.save()
        text = ((text + "\n\n") if text else "") + ("Пользователь дал задаче доступ к папкам: " + "; ".join(add or fl)
                                                     + ". Читай и ищи в них без вопросов, менять — только с разрешения.")
    try:
        tm.tell(t.id, text)
    except ValueError as e:
        raise ToolError(str(e)) from e
    return (f"Передала задаче «{t.title}»" + (f" доступ к папкам: {'; '.join(fl)}" if fl else "")
            + ". Задача продолжит с этим — результата ещё нет, не говори, что готово.")


def t_stop_task(a, ctx):
    try:
        t = _tm(ctx).stop(a.get("name") or "")
    except KeyError as e:
        raise ToolError(str(e)) from e
    return f"Задача «{t.title}» остановлена."


def t_resume_task(a, ctx):
    try:
        t = _tm(ctx).start(a.get("name") or "")
    except KeyError as e:
        raise ToolError(str(e)) from e
    return f"Продолжаю задачу «{t.title}»."


def t_call_persona(a, ctx):
    fn = ctx.get("call_persona")
    if fn is None:
        raise ToolError("переключение персонажей недоступно")
    task = str(a.get("task") or "").strip()[:1500]
    return fn(str(a.get("name", "")), task) if task else fn(str(a.get("name", "")))
