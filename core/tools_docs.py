"""Действия модели: документы и файлы — поиск по документам и Знаниям, чтение и распознавание (OCR), поиск и
замена в Word/Excel, архивы, Радар, лаборатория, навыки."""

import json
import os
import re

from pathlib import Path
from tools_base import log, ToolError
from tools_notes import _ws, _ws_call
from tools_pc import pictures_dir
import tools_base as base          # DRY, launch — через основу: проверки подменяют их там


def t_search_documents(a, ctx):
    kn = ctx.get("knowledge")
    if not kn:
        raise ToolError("папка «Знания» недоступна")
    q = str(a.get("query") or "").strip()
    mine = []
    try:                                           # Отзыв 17.11 «книги»: папки текущего персонажа — первыми (его книги, его база)
        mine = list((ctx.get("persona_folders") or (lambda: []))() or [])
    except Exception:  # noqa: BLE001
        mine = []
    if a.get("file"):                              # отзыв 19.11 (двойник автора, 12 книг): одна книга — искать в ней или читать подряд
        return _doc_read(kn, a, q, mine)
    if not q:
        raise ToolError("что искать? Назови ключевые слова (query) или файл (file), чтобы читать его подряд")
    try:                                           # мозг — облако Dewiar: кандидатов больше, лучшие выберет реранкер
        rr = (ctx.get("kb_rerank") or (lambda: None))()
    except Exception:  # noqa: BLE001
        rr = None
    n = 30 if rr else 5
    res = kn.search(q, limit=n, within=mine) if mine else []
    if len(res) < n:
        seen = {(r["path"], r["text"][:80]) for r in res}
        res += [r for r in kn.search(q, limit=n) if (r["path"], r["text"][:80]) not in seen][:n - len(res)]
    if rr:
        try:
            res = rr(q, res)[:6]
        except Exception:  # noqa: BLE001
            res = res[:5]
    if not res:
        return "В документах («Знания» и свои папки) ничего подходящего не нашлось."
    if ctx.get("sources"):                         # под ответом — кнопки «открыть» найденных файлов (Engine._turn_sources)
        try:
            ctx["sources"]([{"key": r["key"], "name": Path(r["path"]).name, "label": r["path"]} for r in res])
        except Exception:  # noqa: BLE001
            pass
    return "\n\n".join(f"[Файл «{Path(r['path']).name}» — {r['path']}{_pos(r)}]\n{r['text']}" for r in res) + \
        "\n\nОтвечай по этим отрывкам и назови файл, откуда взято (по имени, например «Регламент.pdf»). Если ответа в них нет — так и скажи." + \
        ("\nНужно больше контекста (вся глава, что было дальше) — читай подряд: search_documents с file и from." if any("of" in r for r in res) else "")


def _pos(r):
    return f" · отрывок {r['i'] + 1} из {r['of']}" if r.get("of") else ""


def _doc_read(kn, a, q, mine):
    """search_documents с file: поиск внутри одной книги (есть query) или чтение подряд с отрывка from (нет query)."""
    key = (kn.find_file(a["file"], within=mine) if mine else None) or kn.find_file(a["file"])
    if not key:
        raise ToolError(f"файла «{a['file']}» среди прочитанных нет. Есть ли он в «Моих файлах» или в папке персонажа? "
                        "Имя можно назвать частью («Книга 3»)")
    if q:
        res = kn.search(q, limit=6, key=key)
        if not res:
            return f"В «{kn.label(key)}» по словам «{q}» ничего не нашлось — попробуй другие слова или читай подряд (from)."
        return "\n\n".join(f"[«{Path(r['path']).name}»{_pos(r)}]\n{r['text']}" for r in res) + \
            "\n\nЧитать подряд с нужного места — search_documents с file и from (номер отрывка)."
    if a.get("from") in (None, ""):                   # без from — оглавление (если есть главы): сразу открыть нужную
        ol = kn.outline(key)
        if len(ol) >= 2:
            r0 = kn.passages(key, 0, chars=1)
            return (f"[«{Path(kn.label(key)).name}» · оглавление · всего отрывков {r0['total'] if r0 else '?'}]\n"
                    + "\n".join(f"- {t} — from {i + 1}" for t, i in ol)
                    + "\n\nЧитай нужную главу: search_documents с file и from (номер отрывка из оглавления); "
                    "с начала книги — from 1.")
    try:
        start = max(0, int(a.get("from") or 1) - 1)
    except (TypeError, ValueError):
        start = 0
    r = kn.passages(key, start)
    if not r:
        raise ToolError(f"в «{kn.label(key)}» нет текста")
    more = (f"\n\n…дальше: search_documents с file «{a['file']}» и from {r['end'] + 1} (всего отрывков {r['total']})."
            if r["end"] < r["total"] else "\n\n(конец файла)")
    return f"[«{Path(r['path']).name}» · отрывки {r['start'] + 1}–{r['end']} из {r['total']}]\n{r['text']}{more}"


def t_ask_knowledge(a, ctx):
    """Вопрос к Знаниям на сайте Dewiar (account.py); base — база или раздел библиотеки по названию."""
    acc = ctx.get("account")
    if not acc:
        raise ToolError("аккаунт недоступен")
    from account import AccountError
    base = None
    want = str(a.get("base") or "").strip().lower().replace("ё", "е")
    if want:                                           # «в разделе „История РФ“» — база по названию: точное, потом часть
        try:
            bases = acc.scope()["bases"]
        except AccountError:
            bases = []
        base = next((b for b in bases if b["label"].lower().replace("ё", "е") == want), None) or \
            next((b for b in bases if want in b["label"].lower().replace("ё", "е")), None)
        if not base:
            names = ", ".join(f"«{b['label']}»" for b in bases[:15])
            raise ToolError(f"нет базы «{a.get('base')}». Есть: {names or 'ни одной'}")
    try:
        r = acc.ask(a.get("question", ""), base=base)
    except AccountError as e:
        raise ToolError(str(e)) from e
    src = ("\nИсточники: " + "; ".join(r["sources"])) if r["sources"] else ""
    return (r["answer"] or "В Знаниях ничего не нашлось.") + src


def t_create_skill(a, ctx):
    sk = ctx.get("skills")
    if sk is None:
        raise ToolError("навыки недоступны")
    name = sk.save(a.get("name", ""), a.get("description", ""), a.get("instructions", ""))
    return f"Навык «{name}» создан и уже работает. Его можно поправить в студии → «Плагины» → «Навыки»."


def _ocr_vision(ctx):
    """Модель со зрением для распознавания текста (Engine.ocr_vision) или None."""
    eng = ctx.get("engine")
    return getattr(eng, "ocr_vision", None) if eng is not None else None


def _ocr_say(p, ctx, pages=None, limit=12000):
    """Скан PDF или картинка -> текст для модели: «В скане распознан текст: …» (идея №68: на сканах модели падали или
    отвечали пусто). OCRError — ToolError со словами, что поставить."""
    import ocr
    vision = _ocr_vision(ctx)
    try:
        if p.suffix.lower() == ".pdf":
            r = ocr.ocr_pdf_ex(p, pages=pages, vision=vision)
            if r["error"] and not r["text"]:
                raise ocr.OCRError(r["error"])
            text, done = r["text"], r["ocr_pages"]
            head = (f"В скане распознан текст (страницы {', '.join(map(str, done[:12]))}{'…' if len(done) > 12 else ''} — "
                    "распознаны, возможны опечатки):" if done else "Текст PDF:")
            tail = (f"\n(ещё {r['skipped']} стр. без текста не распознаны — попроси номера страниц: pages)" if r["skipped"] else "")
        else:
            text, _ = ocr.recognize(p, vision=vision)
            head, tail = "На картинке распознан текст (возможны опечатки):", ""
    except ocr.OCRError as e:
        raise ToolError(str(e)) from e
    if not text.strip():
        return f"{p.name}: текста не нашлось — похоже, там только изображение без надписей." + tail
    cut = text[:limit]
    return f"{head}\n{cut}" + ("\n…(дальше обрезано)" if len(cut) < len(text) else "") + tail


def t_read_file(a, ctx):
    r = _ws_call(lambda: _ws(ctx).read(a.get("path", ""), limit=12000))
    rel = str(r.get("path") or "")
    ext = Path(rel).suffix.lower()
    if ext == ".pdf" or (r.get("binary") and ext in OCR_EXTS):     # скан PDF, фото документа — распознать (№68)
        try:
            p = _ws(ctx)._vault_path(rel) if rel.startswith("obsidian:") else _ws(ctx).safe(rel)
        except Exception:  # noqa: BLE001
            p = None
        if p is not None and p.is_file():
            if ext != ".pdf":
                return _ocr_say(p, ctx)
            import ocr
            try:
                if ocr.pdf_needs_ocr(p):
                    return _ocr_say(p, ctx, pages=a.get("pages"))
            except ToolError as e:
                if not r.get("text", "").strip():
                    raise
                log.info("read_file: сканы в %s не распознались: %s", rel, e)
    if r.get("binary"):
        return f"{r['path']} — не текстовый файл ({r['size']} байт)."
    return r["text"] + ("\n…(дальше обрезано)" if r.get("truncated") else "")


OCR_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


def _doc_path(a, ctx, exts=None):
    """Документ для doc_find / doc_replace: полный путь, путь в папке ассистента или имя файла из «Входящих» (то, что
    человек прислал) — самый свежий с таким именем."""
    import docedit as DE
    raw = str(a.get("path") or "").strip().strip("«»\"'")
    if not raw:
        raise ToolError("какой документ? Назови файл (путь или имя из «Входящих»)")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        try:
            p = _ws(ctx).safe(raw)
        except Exception:  # noqa: BLE001
            p = Path(raw)
    # №1152 (28.11): назвали путь (с папками) — ищем ровно его: нет — так и говорим, а не правим похожий файл из «Входящих»
    if not p.is_file() and not re.search(r"[\\/]", raw):
        try:
            inbox = _ws(ctx).ensure() / "Входящие"
            cands = sorted((x for x in inbox.rglob("*") if x.is_file() and x.suffix.lower() in (exts or DE.EXTS)
                            and (x.name == Path(raw).name or Path(raw).stem.lower() in x.stem.lower())),
                           key=lambda x: x.stat().st_mtime, reverse=True)
            p = cands[0] if cands else p
        except Exception:  # noqa: BLE001
            pass
    if not p.is_file():
        raise ToolError(f"документа «{raw}» не нашла — пришли его ещё раз или назови полный путь")
    if exts is not None:
        return p
    if p.suffix.lower() not in DE.EXTS:
        raise ToolError(f"«{p.name}»: точечно правлю Word, Excel, PowerPoint и OpenOffice (docx, xlsx, pptx, odt). PDF — "
                        "сначала сохранить в Word.")
    return p


def _ws_rel(p, ctx):
    try:
        return Path(p).resolve().relative_to(_ws(ctx).root.resolve()).as_posix()
    except (ValueError, OSError, AttributeError):
        return str(p)


def t_doc_find(a, ctx):
    """Где в документе встречается текст — как grep, до правки: чтобы заменить ровно то, что нужно."""
    import docedit as DE
    p = _doc_path(a, ctx)
    if not str(a.get("text") or "").strip():          # №892: пустой поиск давал «найдено 40: Дата, Дата…» вместо содержимого
        raise ToolError(f"что найти в «{p.name}»? Чтобы прочитать документ или таблицу целиком — read_file "
                        f"с путём {_ws_rel(p, ctx)}")
    try:
        hits = DE.find(p, str(a.get("text") or ""), whole=bool(a.get("whole_word")))
    except DE.DocEditError as e:
        raise ToolError(str(e)) from e
    if not hits:
        return f"В «{p.name}» «{a.get('text')}» не встречается."
    return (f"«{p.name}»: найдено {len(hits)}" + (" (показаны первые 40)" if len(hits) >= 40 else "") + ":\n"
            + "\n".join(f"- {h['part']}, абзац {h['para']}: {h['text']}" for h in hits))


def t_archive_open(a, ctx):
    """Архив .zip, который прислал человек: безопасно распаковать рядом и сказать, что внутри (владелец 12.11)."""
    import docedit as DE
    p = _doc_path(a, ctx, exts={".zip", ".rar", ".7z"})
    try:
        r = DE.unpack(p)
    except DE.DocEditError as e:
        raise ToolError(str(e)) from e
    fs = r["files"]
    size = lambda n: f"{n / 1048576:.1f} МБ" if n >= 1048576 else f"{max(1, n // 1024)} КБ"   # noqa: E731
    lines = [f"- {f} ({size(n)})" for f, n in fs[:60]]
    return (f"Распаковала «{p.name}» в папку «{Path(r['dir']).name}» рядом: {len(fs)} файлов"
            + (f", пропущено небезопасных {len(r['skipped'])}" if r["skipped"] else "") + ":\n" + "\n".join(lines)
            + (f"\n… и ещё {len(fs) - 60}" if len(fs) > 60 else "")
            + f"\nПапка: {r['dir']}. Читать файл — read_file с полным путём; документы Office править — doc_find / doc_replace; "
            "обработать много файлов и собрать результат — start_task (навык archive). Скажи коротко, что в архиве.")


def t_insight_ask(a, ctx):
    """«Радар» (docs/RADAR.md): бриф, тренды и разобранные материалы ниши человека — по запросу или самое важное."""
    eng = ctx.get("engine")
    if eng is None:
        raise ToolError("Радар работает в программе на компьютере")
    import engine_insight
    return fit_json(engine_insight.ask_tool(eng, str(a.get("query") or "")), 9000)


def fit_json(obj, limit):
    """JSON не длиннее limit — без обрыва посреди строки (№1147, 28.11: [:9000] резал объект и модель получала битый JSON).
    Длинно — убираем последние элементы самых длинных списков и отмечаем «_cut»; потом — укорачиваем длинные строки."""
    import copy
    d = copy.deepcopy(obj)
    s = json.dumps(d, ensure_ascii=False)
    for _ in range(400):
        if len(s) <= limit:
            return s
        lists = [v for v in (d.values() if isinstance(d, dict) else []) if isinstance(v, list) and v]
        lists += [w for v in (d.values() if isinstance(d, dict) else []) if isinstance(v, dict) for w in v.values() if isinstance(w, list) and w]
        if not lists:
            break
        max(lists, key=lambda x: len(json.dumps(x, ensure_ascii=False))).pop()
        if isinstance(d, dict):
            d["_cut"] = "не всё вошло — уточни вопрос, если нужно больше"
        s = json.dumps(d, ensure_ascii=False)

    def short(v, n):
        if isinstance(v, str):
            return v if len(v) <= n else v[:n] + "…"
        if isinstance(v, list):
            return [short(x, n) for x in v]
        if isinstance(v, dict):
            return {k: short(x, n) for k, x in v.items()}
        return v
    for n in (600, 300, 120, 60):
        s = json.dumps(short(d, n), ensure_ascii=False)
        if len(s) <= limit:
            return s
    return json.dumps({"_cut": "ответ слишком большой — уточни вопрос"}, ensure_ascii=False)


def t_doc_replace(a, ctx):
    """Точечная замена в документе Office (владелец 12.11): оформление, таблицы, колонтитулы не трогаются; оригинал цел —
    результат рядом «(исправлено)»."""
    import docedit as DE
    p = _doc_path(a, ctx)
    reps = a.get("replacements") or []
    if isinstance(reps, dict):
        reps = [{"find": k, "replace": v} for k, v in reps.items()]
    pairs = [(str(x.get("find") or ""), str(x.get("replace") or "")) for x in reps if isinstance(x, dict)]
    if not pairs and a.get("find"):
        pairs = [(str(a["find"]), str(a.get("replace") or ""))]
    out = None
    if str(a.get("save_as") or "").strip():                 # «такой же план на этот год» — новое имя рядом с образцом
        nm = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", str(a["save_as"])).strip()[:120]
        out = p.with_name(nm if nm.lower().endswith(p.suffix.lower()) else nm + p.suffix)
        if out.resolve() == p.resolve():
            raise ToolError("save_as — другое имя: образец не перезаписываю")
    try:
        r = DE.replace(p, pairs, out=out, whole=bool(a.get("whole_word")))
    except DE.DocEditError as e:
        raise ToolError(str(e)) from e
    done = [f"«{f}» → «{t}»: {n}" for (f, t), n in zip(pairs, r["counts"]) if n]
    if not r["out"]:
        return (f"В «{p.name}» ничего из этого не нашлось: " + ", ".join(f"«{x}»" for x in r["missing"]) +
                ". Проверь написание (doc_find) — файл не менялся.")
    opener = ctx.get("show_file")
    if callable(opener):
        try:
            opener(r["out"])
        except Exception:  # noqa: BLE001
            pass
    return (f"Готово: «{Path(r['out']).name}» рядом с оригиналом (оригинал не тронут). Заменено: " + "; ".join(done)
            + (". Не нашлось: " + ", ".join(f"«{x}»" for x in r["missing"]) if r["missing"] else "")
            + ". Оформление, таблицы и колонтитулы — как были. Скажи коротко, сколько и что заменено, и где файл.")


# куда смотреть, если назвали только имя файла («распознай скан.pdf»): папки, куда файлы обычно попадают
OCR_DIRS = ("Загрузки", "Downloads", "Рабочий стол", "Desktop", "Документы", "Documents", "Изображения", "Pictures")


def _ocr_path(a, ctx):
    """Путь из просьбы -> файл: полный путь или ~/…, затем папка ассистента, потом «Загрузки», «Рабочий стол»,
    «Документы», «Изображения» по имени. Только картинки и PDF — инструмент не читает другие файлы."""
    raw = str(a.get("path") or "").strip().strip("«»\"'")
    if not raw:
        raise ToolError("назови файл: путь к картинке или PDF")
    cands = [Path(os.path.expanduser(raw))]
    try:
        cands.append(_ws(ctx).safe(raw))
    except Exception:  # noqa: BLE001
        pass
    if not Path(raw).is_absolute():
        homes = [Path.home()] + ([pictures_dir().parent] if pictures_dir().parent != Path.home() else [])
        cands += [h / d / raw for h in homes for d in OCR_DIRS]
        if "/" not in raw and "\\" not in raw:              # только имя — ещё по всей папке ассистента («Входящие», заметки)
            try:
                cands += [next(iter(_ws(ctx).ensure().rglob(raw)), None)]
            except Exception:  # noqa: BLE001
                pass
    cands = [c for c in cands if c is not None]
    for c in cands:
        try:
            if c.is_file():
                if c.suffix.lower() not in OCR_EXTS | {".pdf"}:
                    raise ToolError(f"{c.name} — не картинка и не PDF; текст обычных файлов читает read_file")
                return c
        except OSError:
            continue
    raise ToolError(f"файла «{raw}» не нашлось — уточни полный путь")


def t_ocr(a, ctx):
    """Распознать текст на картинке или в скане PDF; install — поставить распознавание (ocr.install, в фоне)."""
    if a.get("install"):
        eng = ctx.get("engine")
        if eng is None or not hasattr(eng, "ocr_install_start"):
            raise ToolError("поставить отсюда нельзя")
        return eng.ocr_install_start()
    return _ocr_say(_ocr_path(a, ctx), ctx, pages=a.get("pages"))


def t_lab_write(a, ctx):
    rel = _ws_call(lambda: _ws(ctx).lab_write(a.get("name", ""), a.get("content", "")))
    return f"Файл сохранён: {rel}"


def t_lab_run(a, ctx):
    if base.DRY:                                              # тесты: записываем и всё равно запускаем (скрипт — в лаборатории)
        base.launch(["lab_run", a.get("name", "")])
    r = _ws_call(lambda: _ws(ctx).lab_run(a.get("name", ""), a.get("args", "")))
    return f"Код завершения {r['code']}. Вывод (полностью — {r['log']}):\n{r['output'] or '(пусто)'}"


def _transcripts(ctx):
    T = ctx.get("transcripts")
    if T is None or not T.on():
        raise ToolError("Расшифровка — плагин: включите его в «Плагинах» → «Расшифровка» (студия на компьютере)")
    return T


def t_transcribe(a, ctx):
    """Плагин «Расшифровка» (1.0.33): аудио или видео -> текст с метками времени и .srt; идёт в фоне, готово — Лира скажет."""
    try:
        return _transcripts(ctx).tool_start(a.get("path") or "", a.get("name") or "")
    except ValueError as e:
        raise ToolError(str(e)) from e


def t_transcripts(a, ctx):
    """Расшифровки: список, поиск фразы по всем записям (с метками времени) или текст одной записи — для выжимки и вопросов."""
    try:
        return _transcripts(ctx).tool_find(a.get("query") or "", a.get("id") or "", a.get("name") or "")
    except ValueError as e:
        raise ToolError(str(e)) from e
