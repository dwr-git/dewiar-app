"""Действия модели: папка ассистента — заметки, память, дневник, страницы, поиск по записям, «Совет ИИ», подкаст,
идеи, календарь, справка по программе."""

import json
import re

from datetime import datetime
from pathlib import Path
from tools_base import ToolError
import tools_base as base          # DRY, EXAM_LAUNCH, launch — через основу: проверки подменяют их там


def _ws(ctx):
    """Папка ассистента (workspace.py) из ctx. Все пути инструментов к ней проходят через её проверки (ws.safe)."""
    ws = ctx.get("workspace")
    if ws is None:
        raise ToolError("папка ассистента недоступна")
    return ws


def _ws_call(fn):
    """Выполнить fn, превратив WorkspaceError в ToolError."""
    from workspace import WorkspaceError
    try:
        return fn()
    except WorkspaceError as e:
        raise ToolError(str(e)) from e


def t_watch(a, ctx):
    """«Дозор» (engine_watch.py): присмотреть за экраном, папкой или страницей и сказать, когда готово."""
    eng = ctx.get("watch")
    if eng is None:
        raise ToolError("«Дозор» здесь недоступен")
    act = str(a.get("action") or "add")
    if act == "list":
        pub = eng.watch_public()
        act_ = [x for x in pub["items"] if x["status"] == "active"]
        if not act_:
            return "Дозоров сейчас нет."
        return "Идут дозоры: " + "; ".join(f"{x['title']} (id {x['id']}, последний раз: {x.get('note') or 'ещё не смотрела'})" for x in act_)
    if act == "stop":
        n = eng.watch_stop(str(a.get("id") or ""))
        return f"Остановлено дозоров: {n}." if n else "Нечего останавливать — дозоров нет."
    try:
        it = eng.watch_add(a)
    except ValueError as e:
        raise ToolError(str(e)) from e
    mins = max(1, round(it["every"] / 60)) if it["every"] >= 60 else 0
    how = {"screen": f"буду смотреть на экран раз в {mins} мин", "file": "слежу за папкой",
           "page": f"проверяю страницу раз в {mins} мин"}[it["kind"]]
    hrs = round((it["until"] - it["created"]) / 3600, 1)
    return (f"Дозор начат: «{it['title']}» — {how}, до {hrs:g} ч. Как только будет готово — скажу здесь и пришлю на телефон. "
            "Скажи об этом одной-двумя фразами; если смотришь на экран — что снимки никуда не сохраняются.")


def t_save_link(a, ctx):
    """«Сохрани это видео / статью / ссылку» (0.58, «Заметки как Keep, только умнее»): заметка с ссылкой — в студии она
    карточкой с обложкой и названием; метка «интересное» (и свои), пересказ — если модель его дала."""
    url = str(a.get("url") or "").strip()
    if not re.match(r"https?://\S+$", url):
        raise ToolError("нужна ссылка целиком, с https://")
    lm = ctx.get("linkmeta")
    meta = {}
    if lm is not None:
        try:
            meta = lm.get(url)
        except Exception:  # noqa: BLE001
            meta = {}
    title = (str(a.get("title") or "").strip() or meta.get("title") or meta.get("site") or "Ссылка")[:80]
    summary = str(a.get("summary") or "").strip()
    tags = ["интересное"] + [str(t).strip().lstrip("#") for t in (a.get("tags") or []) if str(t).strip().lstrip("#")]
    body = url + ("\n\n" + summary if summary else "")
    w = _ws(ctx)
    rel = _ws_call(lambda: w.save_note(title, body))
    import workspace as _W
    f = w.safe(rel)
    f.write_text(_W.note_front_set(f.read_text(encoding="utf-8"), {"tags": list(dict.fromkeys(tags))}), encoding="utf-8")
    kind = "видео" if meta.get("video") else "ссылку"
    return (f"Сохранила {kind} в «Заметки» с меткой «интересное»: «{title}»" + (" — с пересказом." if summary else ".")
            + " Скажи коротко, что сохранила.")


PAGE_CSS = """:root{color-scheme:light dark;--bg:#f6f4fb;--card:#fff;--ink:#1d1b26;--mut:#6b6880;--acc:#6d5ce8;--line:#e6e2f2}
@media (prefers-color-scheme:dark){:root{--bg:#14131b;--card:#1e1c28;--ink:#eeeaf8;--mut:#9d98b4;--acc:#a99cff;--line:#2e2b3d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 "Manrope","Segoe UI",Ubuntu,system-ui,sans-serif}
main{max-width:860px;margin:0 auto;padding:48px 20px 80px}h1{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.01em}
h2{font-size:22px;margin:0 0 10px;color:var(--acc)}h3{font-size:18px;margin:18px 0 6px}p,li{max-width:70ch}
.lead{color:var(--mut);margin:0 0 30px}section,article{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:22px 26px;margin:0 0 18px}
ul,ol{padding-left:22px}li{margin:3px 0}table{border-collapse:collapse;width:100%}td,th{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
img{max-width:100%;border-radius:14px}a{color:var(--acc)}footer{color:var(--mut);font-size:13px;margin-top:30px}"""


def page_html(title, html):
    """Готовая страница: полный HTML — как есть; кусок (секции, списки) — в оформление Dewiar с заголовком."""
    import html as _h
    body = str(html or "").strip()
    body = re.sub(r"^```(?:html)?\s*|\s*```$", "", body)
    if re.search(r"<html[\s>]|<!doctype", body, re.I):
        return body
    t = _h.escape(title)
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{t}</title><style>{PAGE_CSS}</style></head><body><main><h1>{t}</h1>{body}"
            f"<footer>Собрала Лира · Dewiar · {datetime.now().strftime('%d.%m.%Y')}</footer></main></body></html>")


def md_html(text):
    """Заметка Markdown -> HTML для страницы (show_page с file): заголовки, списки, задачи, цитаты, код, ссылки, жирный и
    курсив. Всё экранируется — HTML внутри заметки показывается текстом, а не выполняется."""
    import html as _h

    def inline(t):
        t = _h.escape(t, quote=False)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: f'<a href="{_h.escape(m.group(2))}">{m.group(1)}</a>', t)
        t = re.sub(r"(?<![\"'>=])(https?://[^\s<]+)", lambda m: f'<a href="{m.group(1)}">{m.group(1)}</a>', t)
        return t
    out, para, lst, code = [], [], None, None

    def flush():
        nonlocal para, lst
        if para:
            out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
            para = []
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{x}</li>" for x in lst[1]) + f"</{lst[0]}>")
            lst = None
    for line in str(text or "").replace("\r\n", "\n").split("\n"):
        if code is not None:
            if line.strip().startswith("```"):
                out.append("<pre><code>" + _h.escape("\n".join(code)) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        st = line.strip()
        if st.startswith("```"):
            flush()
            code = []
            continue
        m = re.match(r"(#{1,6})\s+(.*)", st)
        if m:
            flush()
            n = min(6, len(m.group(1)) + 1)
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
            continue
        m = re.match(r"[-*+]\s+(?:\[([ xX])\]\s+)?(.*)", st) or re.match(r"(\d+)[.)]\s+(.*)", st)
        if m:
            kind = "ol" if st[:1].isdigit() else "ul"
            if para:
                flush()
            if lst and lst[0] != kind:
                flush()
            item = inline(m.group(2))
            if kind == "ul" and m.group(1):
                item = ("☑ " if m.group(1).lower() == "x" else "☐ ") + item
            lst = lst or (kind, [])
            lst[1].append(item)
            continue
        if st.startswith(">"):
            flush()
            out.append("<blockquote>" + inline(st.lstrip("> ")) + "</blockquote>")
            continue
        if not st:
            flush()
            continue
        if lst:
            flush()
        para.append(st)
    if code is not None:
        out.append("<pre><code>" + _h.escape("\n".join(code)) + "</code></pre>")
    flush()
    return "\n".join(out)


def t_show_page(a, ctx):
    """«Покажи в браузере красиво» (28.10, пользователь: «нашла рецепты, но создала кучу питоновских скриптов, а HTML — не в
    файле, а в чате, и начала зачитывать его со всеми тегами»): страница — файлом в «Страницы», сразу в браузере."""
    title = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", str(a.get("title") or "").strip())[:80].strip() or "Страница"
    html = str(a.get("html") or "")
    src = str(a.get("file") or "").strip()
    if src:
        # своя заметка или файл — показываем как есть, без пересказа моделью (28.10, отзыв: «попросил вывести мою заметку
        # в браузере — она отказалась перепечатывать текст и показала кусочек»): текст берём с диска сами
        r = _ws_call(lambda: _ws(ctx).read(src, limit=400000))
        if r.get("binary"):
            raise ToolError(f"«{r['path']}» — не текстовый файл, его так не показать")
        body = r["text"]
        if not a.get("title"):
            title = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", Path(str(r.get("path") or src)).stem)[:80].strip() or title
        html = (body if str(r.get("path") or src).lower().endswith((".html", ".htm")) else md_html(body)) + (
            "\n<p><i>…(дальше обрезано)</i></p>" if r.get("truncated") else "")
        if not html.strip():
            raise ToolError("файл пустой")
    if len(html.strip()) < 20 and not src:
        raise ToolError("нужно содержимое страницы — html с разделами, списками или таблицей")
    w = _ws(ctx)
    root = _ws_call(lambda: w.ensure()) / "Страницы"
    root.mkdir(parents=True, exist_ok=True)
    f = root / f"{title}.html"
    f.write_text(page_html(title, html), encoding="utf-8")
    if ctx.get("server") and not (base.DRY or base.EXAM_LAUNCH):
        # сервер без окна (main.py --server): открыть некому — честно отдаём файл, а не «открыла в браузере»
        return (f"Страница «{title}» готова и сохранена файлом «Страницы/{f.name}» в папке Dewiar; браузера здесь нет (Dewiar "
                "работает на сервере без экрана), поэтому открыть её некому. Скажи одной фразой, что страница сохранена и где "
                "файл; не говори, что открыла. HTML в ответе не повторяй.")
    base.launch_browser(f)                 # в браузере, а не в программе, которой отдан .html (26.11: редактор кода)
    return (f"Страница «{title}» открыта в браузере (файл — «Страницы/{f.name}» в папке Dewiar). Скажи одной фразой, что "
            "открыла. HTML в ответе не повторяй.")


def t_debate(a, ctx):
    """«Пусть модели поспорят: …» (0.62, debate.py): две модели отвечают и возражают друг другу — итог подводит Лира."""
    import debate as DB
    s = ctx.get("settings")
    if s is None:
        raise ToolError("спор моделей — в программе Dewiar")
    try:
        a_, b_ = DB.pick_pair(s)
        return DB.context(DB.run(a.get("question") or "", a_, b_))
    except DB.DebateError as e:
        raise ToolError(str(e)) from e


def t_council(a, ctx):
    """«Собери совет: …», «посоветуйся с командой» (0.67, council.py): персонажи обсуждают вопрос в студии («Совет ИИ» —
    открывается сама). Ждать минуту-две молча нельзя: отвечаем сразу, итог Лира скажет сама, когда совет закончит."""
    eng = ctx.get("engine")
    if eng is None or not hasattr(eng, "council"):
        raise ToolError("«Совет ИИ» — в программе Dewiar на компьютере")
    from council import CouncilError
    try:
        r = eng.council.start(a.get("question") or "", None, announce=True)
    except CouncilError as e:
        raise ToolError(str(e)) from e
    eng.emit("council", sid=r["sid"], open=True)
    names = ", ".join(m["name"] for m in r["members"])
    return (f"Совет собран: {names}. Они обсуждают вопрос в студии «Совет ИИ» (открылась) — мнения, спор и итог; итог прозвучит "
            "сам, когда совет закончит. Скажи об этом одной фразой, без своего ответа на вопрос.")


def t_make_podcast(a, ctx):
    """«Лира, сделай подкаст по этому файлу / ссылке / теме» (0.87, podcast.py): выпуск готовится в фоне несколько минут —
    отвечаем сразу, о готовности Лира скажет сама; выпуск — в студии «Подкасты» (открывается)."""
    eng = ctx.get("engine")
    if eng is None or not hasattr(eng, "podcasts"):
        raise ToolError("подкасты — в программе Dewiar на компьютере")
    from podcast import PodcastError, STYLES
    files = a.get("files") or []
    if isinstance(files, str):
        files = [files]
    urls = a.get("urls") or ([a["url"]] if a.get("url") else [])
    if isinstance(urls, str):
        urls = [urls]
    try:
        mins = int(a.get("minutes") or 10)
    except (TypeError, ValueError):
        mins = 10
    mins = min((5, 10, 20), key=lambda m: abs(m - mins))
    style = a.get("style") if a.get("style") in STYLES else "simple"
    if base.EXAM_LAUNCH:                                   # экзамен: вызов записан, выпуск не делается (облако не тратится)
        base.launch(["make_podcast", json.dumps({"topic": str(a.get("topic") or "")[:200], "urls": urls[:5], "files": files[:10],
                                            "minutes": mins, "style": style}, ensure_ascii=False)])
        return (f"Подкаст начат: ведут Лира и Патрик, около {mins} минут, подача — {STYLES[style].lower()}. Готовится в фоне — "
                f"ход виден в студии «Подкасты»; когда будет готов, скажу сама. Скажи об этом одной-двумя фразами.")
    try:
        r = eng.podcasts.start({"topic": str(a.get("topic") or "")[:3000], "urls": [str(u) for u in urls][:5], "paths": [str(f) for f in files][:10]},
                               {"minutes": mins, "style": style}, announce=True)
        est = eng.podcasts.estimate(mins, 0, (), len(urls), a.get("topic") or "")
    except PodcastError as e:
        raise ToolError(str(e)) from e
    eng.emit("podcast", id=r["id"], open=True)
    h = r["hosts"]
    cost = f" Примерно {str(est['talers']).replace('.', ',')} талера." if est.get("talers") else ""
    return (f"Подкаст начат: ведут {h['a']['name']} и {h['b']['name']}, около {mins} минут, подача — {STYLES[style].lower()}. "
            f"Готовится в фоне примерно {est.get('wait') or mins} мин — ход виден в студии «Подкасты» (открылась); когда будет готов, "
            f"скажу сама.{cost} Скажи об этом одной-двумя фразами и не пересказывай материал сам.")


def t_writing_today(a, ctx):
    """«Сколько я написал сегодня?» (0.68, writing.py): прирост слов в своих текстах из папок «Документов»."""
    w = ctx.get("writing")
    if w is None:
        raise ToolError("«Пишу» — в программе Dewiar на компьютере")
    return w.text()


def t_month_summary(a, ctx):
    """«Как прошёл мой месяц?», «итоги октября» (0.61, month.py): данные месяца — модели, рассказать тепло."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("итоги месяца — в программе Dewiar")
    import month as M
    ym = str(a.get("month") or "").strip()
    if ym in ("", "this", "текущий", "этот"):
        ym = None
    elif ym in ("prev", "last", "прошлый"):
        ym = M.prev_ym()
    elif not re.match(r"^\d{4}-\d{2}$", ym):
        raise ToolError("месяц — в виде 2026-10, или prev — прошлый")
    return M.context(M.gather(eng, ym)) + "\n\n" + M.PROMPT


IDEA_OK_RX = re.compile(r"иде[яюиейа]|предлож|разработчик|в\s+(?:приложени|программ)|добав(?:ь|ьте|ить)\b|\bотправ\w*|\bпередай|"
                        r"^\s*(?:ну\s+)?(?:да|давай|ага|конечно|хорошо|согласен|согласна|отправь|предложи|можно)\b", re.I)


def t_suggest_idea(a, ctx):
    """«Предложи идею разработчику» (0.61): через ядро (ideas.suggest) — похожая есть: голос за неё; нет — новая."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("идеи — только в программе Dewiar")
    try:                                        # идеи №360/361: «совет агентов» ушёл разработчику идеей — только по просьбе
        said = str((ctx.get("turn_text") or (lambda: ""))() or "")
    except Exception:  # noqa: BLE001
        said = ""
    if said and not IDEA_OK_RX.search(said):
        raise ToolError("идею разработчику отправляют, только когда человек сам просит или соглашается. Сейчас он просил "
                        "другое — ответь на его вопрос сам, ничего не отправляя")
    import ideas
    try:
        return ideas.suggest(eng, a.get("title") or "", a.get("text") or "")
    except ideas.IdeasError as e:
        raise ToolError(str(e)) from e


def t_save_note(a, ctx):
    from workspace import WorkspaceError
    ws = _ws(ctx)
    if a.get("append"):
        # №516: «дописать в существующую» — ищем её по названию (как update_note), а не только точное имя в «Заметках»;
        # не нашлась — новая заметка, и так и говорим (раньше молча рождалась вторая, а модель считала, что дописала)
        try:
            ws.find_note(a.get("title", ""))
        except WorkspaceError as e:
            rel = _ws_call(lambda: ws.save_note(a.get("title", ""), a.get("text", ""), a.get("folder", ""), False))
            why = "Подходящих заметок несколько" if "несколько" in str(e) else "Такой заметки не было"
            return f"{why} — создал новую: {rel}. Если нужно было дописать в другую — найди её find_notes и вызови update_note с её путём."
        # нашлась — дописываем; не вышло (например, заметка не в UTF-8) — честная ошибка, а не тихая новая заметка
        return t_update_note({"note": a.get("title", ""), "text": a.get("text", "")}, ctx)
    rel = _ws_call(lambda: ws.save_note(a.get("title", ""), a.get("text", ""), a.get("folder", ""), False))
    return f"Записал в папку Dewiar: {rel}"


def t_update_note(a, ctx):
    """№516/№517: дописать в существующую заметку (по пути из find_notes или по названию). Ответ однозначный: записано,
    куда и сколько — модель не должна гадать, получилось ли (Лира говорила «не смогла сохранить», а заметка уже была)."""
    mode = "top" if str(a.get("where") or "").lower() in ("top", "начало", "вверх", "сверху") else "append"
    rel, n, size = _ws_call(lambda: _ws(ctx).update_note(a.get("note") or a.get("title") or a.get("path") or "", a.get("text", ""), mode))
    title = Path(rel).stem
    return (f"Готово, сохранено: {'в начало заметки' if mode == 'top' else 'в конец заметки'} «{title}» ({rel}) дописано {n} "
            f"знаков, прежний текст на месте; теперь в заметке {size} знаков. Повторно не вызывай — скажи пользователю, что "
            f"заметка «{title}» обновлена.")


def t_app_help(a, ctx):
    import guide
    return guide.answer(a.get("query") or "", a.get("where") or "")


def t_calendar_list(a, ctx):
    """Календарь по дням (engine.calendar_month: события, напоминания, заметки, задачи, деньги); не больше 300 строк."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("календарь недоступен")
    import datetime as _dt
    end = _dt.date.fromisoformat(a.get("to") or _dt.date.today().isoformat())
    start = _dt.date.fromisoformat(a.get("from") or (end - _dt.timedelta(days=6)).isoformat())
    out, y, m = [], start.year, start.month
    turn = getattr(eng, "turn", None)
    habit = getattr(turn, "habit", None) if getattr(turn, "no_habits", False) else None   # ход-итог: без привычек (engine_answer)
    while (y, m) <= (end.year, end.month):
        days = eng.calendar_month(y, m)["days"]
        for d in sorted(days):
            if start.isoformat() <= d <= end.isoformat():
                for it in days[d]:
                    if habit is not None and it.get("type") == "reminder" and (it.get("kind") in ("job", "brief") or habit(it.get("title"), it.get("rid") or it.get("id"))):
                        continue                                 # привычка или само дело по расписанию — в итог не идут
                    if it["type"] == "money":
                        out.append(f"{d} деньги: {'+' if it['kind'] == 'income' else '−'}{it['amount']} {it['currency']} {it['title']}")
                    else:
                        kind = {"reminder": "сделано" if it.get("done") else "напоминание", "note": "заметка",
                                "diary": "дневник", "task": "задача", "event": f"событие ({it.get('cal', 'календарь')})"}.get(it["type"], it["type"])
                        tm = (it.get("time") or "") + (f"–{it['end']}" if it.get("end") else "")
                        out.append(f"{d} {tm} {kind}: {it.get('title', '')}".replace("  ", " ") + (f", {it['place']}" if it.get("place") else ""))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return "\n".join(out[-300:]) or "За этот период в календаре ничего нет."


NOTES_GENERIC = re.compile(r"^(?:заметк\w*|все|всё|мои|мой|моих|последн\w*|покажи|прочитай|список|какие|есть|что|там|запис\w*|сохран\w*)$")


def _latest_notes(ctx, lead=""):
    """Последние заметки — когда просят «покажи заметки» или по словам ничего нет (иначе Лира отвечала «заметок нет»)."""
    try:
        lst = _ws(ctx).notes()
    except Exception:  # noqa: BLE001
        lst = []
    if not lst:
        return "Заметок пока нет."
    rows = [f"{n['path']}: {n['title']} — {n['snippet'][:200]}" + (f" [вложений: {n['att']}]" if n.get("att") else "") for n in lst[:10]]
    return lead + f"Всего заметок: {len(lst)}. Последние (новые сверху):\n" + "\n".join(rows) + "\n\nЦеликом — read_file с путём."


def _memory_hits(ctx, q):
    """Строки «Обо мне» к запросу (по началу слов) — или последние, если совпадений нет. Экзамен 11.10: «запомни: на работе
    отчёт, дизайнер, сайт» → новый разговор → «вспомни, что я говорил про работу» — модель искала в заметках и календаре,
    ничего не нашла по слову «работа» и ответила «ничего не записано», хотя всё было в памяти. -> текст или ""."""
    try:
        body = _ws(ctx).memory_text(limit=6000)
    except Exception:  # noqa: BLE001
        return ""
    facts = [ln.strip()[2:] for ln in body.splitlines() if ln.strip().startswith("- ")]
    if not facts:
        return ""
    stems = {w[:5] if len(w) > 5 else w for w in re.findall(r"[а-яa-z0-9]{4,}", q.lower().replace("ё", "е")) if not NOTES_GENERIC.match(w)}
    hit = [f for f in facts if any(st in f.lower().replace("ё", "е") for st in stems)]
    recent = [f for f in facts[-8:] if f not in hit]
    if hit:                                   # и недавние: «работа» могла быть сказана другими словами («начальник просил…»)
        return "Из твоей памяти «Обо мне»:\n" + "\n".join("- " + f for f in hit[-12:]) + \
            ("\nНедавно запомнено (может быть о том же):\n" + "\n".join("- " + f for f in recent) if recent else "")
    return "В памяти «Обо мне» по этим словам ничего, вот последние записи (может, это оно):\n" + "\n".join("- " + f for f in facts[-10:])


def _chat_hits(ctx, q, days=14):
    """Что человек сам говорил в прошлых разговорах (лента «Чата», chatlog.py) по словам запроса — и соседние его реплики
    того же разговора (±20 мин): «на работе три дела…» и «ещё начальник просил презентацию» — одно, хотя слова «работа»
    во второй нет. Экзамен 0.38.47: модель сказала «записала», не вызвав remember, а через новый разговор на «вспомни, что я
    говорил про работу» нашла только память о ремонте. -> текст или ""."""
    log_ = ctx.get("chatlog")
    if log_ is None:
        return ""
    stems = {w[:5] if len(w) > 5 else w for w in re.findall(r"[а-яa-z0-9]{4,}", q.lower().replace("ё", "е")) if not NOTES_GENERIC.match(w)}
    if not stems:
        return ""
    import time as _t
    since = _t.time() - days * 86400
    # 0.86: беседы — сказанное в отложенной беседе («Новая беседа» в «Чате») тоже вспоминается (chatlog.recent)
    pool = log_.recent(since) if hasattr(log_, "recent") else list(getattr(log_, "items", []))
    mine = [x for x in pool[-2000:] if x.get("role") == "user" and x.get("ts", 0) >= since and x.get("text")]
    hit = [i for i, x in enumerate(mine) if any(st in x["text"].lower().replace("ё", "е") for st in stems)]
    if not hit:
        return ""
    keep = sorted({j for i in hit for j in range(len(mine)) if abs(mine[j]["ts"] - mine[i]["ts"]) <= 1200})[-12:]
    return "Ты сам(а) говорил(а) в прошлых разговорах:\n" + "\n".join(
        f"- {_t.strftime('%d.%m %H:%M', _t.localtime(mine[j]['ts']))} — {mine[j]['text'][:300]}" for j in keep)


def t_find_notes(a, ctx):
    """Сначала поиск recall.py (ранжированный, с Obsidian), ничего — простой поиск по папке ассистента. К найденному —
    строки памяти «Обо мне» (_memory_hits): «вспомни, что я говорил…» часто про запомненное, а не про заметки."""
    q = str(a.get("query", "") or "")
    if not [w for w in re.split(r"[\s,.]+", q.lower().replace("ё", "е")) if len(w) > 2 and not NOTES_GENERIC.match(w)]:
        return _latest_notes(ctx)
    mem = _memory_hits(ctx, q)
    said = _chat_hits(ctx, q)
    tail = ("\n\n" + mem if mem else "") + ("\n\n" + said if said else "")
    rc = ctx.get("recall")
    if rc is not None:
        res = rc.search(a.get("query", ""), limit=8)
        if res:
            return "\n".join(f"{r['path']}: {r['snippet'][:300]}" for r in res) + \
                "\n\nЦеликом — read_file с путём." + tail
    res = _ws_call(lambda: _ws(ctx).find(a.get("query", "")))
    if not res:
        return _latest_notes(ctx, "В заметках по этим словам ничего не нашлось. ") + tail
    return "\n".join(f"{r['path']}: {r['snippet']}" for r in res) + tail


def t_remember(a, ctx):
    rep = a.get("replace")                    # №919: только когда исправляют — иначе вызов как раньше (и у подмен в проверках)
    r = _ws_call(lambda: _ws(ctx).remember(a.get("fact", ""), replace=rep) if rep else _ws(ctx).remember(a.get("fact", "")))
    if r == "Это я уже знаю.":                 # экзамен 13.10: на вопрос «сколько раз я менял бюджет?» — «Запомнила» вместо ответа
        return ("Это уже есть в памяти — ничего нового. Если пользователь задал вопрос, ответь на него по памяти (с прежними "
                "значениями, если они там есть); не говори «запомнила» и «записала».")
    return r


def t_write_diary(a, ctx):
    who = ctx["persona_name"]() if ctx.get("persona_name") else ""
    rel = _ws_call(lambda: _ws(ctx).diary(a.get("entry", ""), who))
    return f"Записал в дневник ({rel})."
