"""Подкасты — сценарий (часть Podcasts, чистое ядро 1.0.18): собрать источники (файлы, ссылки, вопрос), выжимка,
план, ведущие, сценарий и его проверка."""
import base64
import math
import os
import re
import threading
from pathlib import Path
from podcast_base import (
    BLOCKS, CHARS_PER_MIN, CHECK_SYS, _clean, DATA_RULE, DIGEST_SYS, DOC_EXT, FACTS_MAT, FACTS_TOPIC, file_text,
    _json, LINE_MAX, log, material_ok, MAX_BYTES, MAX_FILE, MAX_FILES, MAX_TEXT, NOTES_MAX, parse_script, PART,
    PLAN_SYS, PodcastError, REDUCE_SYS, SCRIPT_SYS, SEGMENTS, _split_long, Stopped, _strip_stage, STYLE_NOTE,
    url_text)


class MakeMixin:
    @staticmethod
    def _save_files(d, files):
        """Файлы из студии ({name, b64}) — в «Материал/» выпуска. Пределы — число, размер каждого и всех вместе."""
        out, total = [], 0
        if not files:
            return out
        m = d / "Материал"
        m.mkdir(exist_ok=True)
        for f in files[:MAX_FILES]:
            name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", Path(str(f.get("name") or "файл")).name)[:120] or "файл"
            if Path(name).suffix.lower() not in DOC_EXT:
                raise PodcastError(f"«{name}» — такой файл я не читаю. Подойдут PDF, Word (DOCX), ODT, EPUB, FB2, RTF, TXT, Markdown, HTML")
            raw = str(f.get("b64") or "")
            if len(raw) > MAX_FILE * 4 // 3 + 100:
                raise PodcastError(f"«{name}» больше {MAX_FILE >> 20} МБ — возьмите главу или часть")
            try:
                data = base64.b64decode(raw.split(",", 1)[1] if raw.startswith("data:") else raw)
            except ValueError:
                raise PodcastError(f"«{name}» не прочитался")
            total += len(data)
            if len(data) > MAX_FILE:
                raise PodcastError(f"«{name}» больше {MAX_FILE >> 20} МБ — возьмите главу или часть")
            if total > MAX_BYTES:
                raise PodcastError(f"файлов вместе больше {MAX_BYTES >> 20} МБ — выберите главное")
            dst, n = m / name, 2
            while dst.exists():
                dst, n = m / f"{Path(name).stem} ({n}){Path(name).suffix}", n + 1
            dst.write_bytes(data)
            out.append(f"Материал/{dst.name}")
        return out

    def _resolve_path(self, p):
        """Путь из просьбы голосом (make_podcast): папка ассистента («Входящие/…»), полный путь или имя в «Загрузках»,
        «Документах», «Рабочем столе». Только документы (DOC_EXT)."""
        raw = str(p).strip().strip("«»\"'")
        cands = []
        try:
            cands.append(self.host.workspace.safe(raw))
        except Exception:  # noqa: BLE001
            pass
        e = Path(os.path.expanduser(raw))
        if e.is_absolute():
            cands.append(e)
        else:
            for sub in ("Загрузки", "Downloads", "Документы", "Documents", "Рабочий стол", "Desktop"):
                cands.append(Path.home() / sub / raw)
            if "/" not in raw and "\\" not in raw:
                try:
                    cands.append(next(iter(Path(self.host.workspace.ensure()).rglob(raw)), None))
                except Exception:  # noqa: BLE001
                    pass
        for c in cands:
            try:
                if c is not None and c.is_file():
                    if c.suffix.lower() not in DOC_EXT:
                        raise PodcastError(f"«{c.name}» — такой файл я не читаю. Подойдут PDF, Word (DOCX), ODT, EPUB, FB2, RTF, TXT, Markdown, HTML")
                    if c.stat().st_size > MAX_FILE:
                        raise PodcastError(f"«{c.name}» больше {MAX_FILE >> 20} МБ — возьмите главу или часть")
                    return c
            except OSError:
                continue
        raise PodcastError(f"файла «{raw}» не нашлось — уточните путь или перетащите файл в студию")

    @staticmethod
    def _copy_files(d, found):
        """Файлы, названные голосом, — копией в «Материал/» выпуска: «Продолжить» читает только оттуда."""
        import shutil
        out = []
        if not found:
            return out
        m = d / "Материал"
        m.mkdir(exist_ok=True)
        total = 0
        for f in found:
            total += f.stat().st_size
            if total > MAX_BYTES:
                raise PodcastError(f"файлов вместе больше {MAX_BYTES >> 20} МБ — выберите главное")
            name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", f.name)[:120] or "файл"
            dst, n = m / name, 2
            while dst.exists():
                dst, n = m / f"{Path(name).stem} ({n}){Path(name).suffix}", n + 1
            shutil.copyfile(f, dst)
            out.append(f"Материал/{dst.name}")
        return out

    def _resolve(self, job, rel):
        f = material_ok(rel, job["dir"])
        if f is None:
            raise PodcastError(f"файла материала «{str(rel)[:80]}» нет в папке выпуска")
        return f

    def _gather(self, job):
        """Материал -> текст «_материал.txt» (уже есть — берём его). -> (текст, источники)."""
        m = job["meta"]
        f = job["dir"] / "_материал.txt"
        if f.is_file():
            return f.read_text(encoding="utf-8"), m.get("sources") or []
        parts, sources, total = [], [], 0
        items = [("file", x) for x in m.get("files") or []] + [("url", u) for u in m.get("urls") or []]
        for i, (kind, x) in enumerate(items):
            self._stage(job, "read", i / max(1, len(items)), f"{i + 1} из {len(items)}" if len(items) > 1 else "")
            left = MAX_TEXT - total
            if left <= 2000:
                sources.append({"kind": kind, "name": Path(str(x)).name if kind == "file" else x, "skipped": True})
                continue
            if kind == "file":
                p = self._resolve(job, x)
                text = file_text(p, left)
                label = p.name
            else:
                label, text = url_text(x, left)
            total += len(text)
            parts.append(f"### {label}\n{text}")
            sources.append({"kind": kind, "name": label if kind == "file" else x, "title": label, "chars": len(text)})
        text = "\n\n".join(parts)
        if total >= MAX_TEXT:
            m["cut"] = True
        f.write_text(text, encoding="utf-8")
        return text, sources

    def _ask(self, job, system, user, max_tokens, temp=0.7):
        """Один запрос к модели (без инструментов) с повтором при сбое сети. -> текст без <think>."""
        from llm import stream_chat, take_usage
        last = None
        for attempt in range(3):
            if job["cancel"].is_set():
                raise Stopped()
            try:
                out = "".join(stream_chat(dict(job["prof"], max_tokens=max_tokens, temperature=temp), system,
                                          [{"role": "user", "content": user}], job["cancel"]))
                if job["cancel"].is_set():
                    raise Stopped()
                u = take_usage() or {}
                us = job["meta"]["usage"]
                us["tin"] += int(u.get("prompt") or (len(system) + len(user)) // 3)
                us["tout"] += int(u.get("out") or len(out) // 3)
                out = _clean(out)
                if out:
                    return out
                last = RuntimeError("модель ответила пустотой")
            except Stopped:
                raise
            except Exception as e:  # noqa: BLE001
                last = e
                log.info("Подкаст: модель не ответила (%d): %s", attempt + 1, e)
            if job["cancel"].wait(2 + 4 * attempt):
                raise Stopped()
        raise PodcastError(f"модель не ответила: {str(last)[:160]}")

    def _digest(self, job, text):
        """Длинный материал -> заметки: каждая часть — отдельным запросом с чистого листа (параллельно по три), потом —
        сводка сводок, если их много. Пишется в «_выжимка.txt» (для «Продолжить»)."""
        f = job["dir"] / "_выжимка.txt"
        if f.is_file():
            return f.read_text(encoding="utf-8")
        chunks, i = [], 0
        while i < len(text):
            end = min(len(text), i + PART)
            if end < len(text):
                cut = max(text.rfind("\n\n", i + PART // 2, end), text.rfind(". ", i + PART // 2, end))
                end = cut + 1 if cut > 0 else end
            chunks.append(text[i:end])
            i = end
        n = len(chunks)
        res = [""] * n
        done = [0]
        lock = threading.Lock()
        err = []

        def one(k):
            try:
                res[k] = self._ask(job, DIGEST_SYS.format(i=k + 1, n=n), f"МАТЕРИАЛ (часть {k + 1} из {n}):\n<<<\n{chunks[k]}\n>>>", 900, 0.3)
            except Stopped:
                pass
            except Exception as e:  # noqa: BLE001
                err.append(e)
            with lock:
                done[0] += 1
                self._stage(job, "digest", done[0] / n * 0.85, f"часть {done[0]} из {n}") if not job["cancel"].is_set() else None
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(one, range(n)))
        if job["cancel"].is_set():
            raise Stopped()
        got = [r for r in res if r]
        if not got:
            raise err[0] if err else PodcastError("выжимка не получилась")
        notes = "\n\n".join(f"[Часть {k + 1}]\n{r}" for k, r in enumerate(res) if r)
        while len(notes) > NOTES_MAX:                     # много частей — сводим группами по шесть
            self._stage(job, "digest", 0.9, "свожу главное")
            groups = [got[k:k + 6] for k in range(0, len(got), 6)]
            words = max(250, int(NOTES_MAX / 7 / max(1, len(groups))))
            got = [self._ask(job, REDUCE_SYS.format(words=words), "МАТЕРИАЛ (заметки по частям):\n<<<\n" + "\n\n".join(g) + "\n>>>", 1600, 0.3)
                   for g in groups]
            notes = "\n\n".join(got)
            if len(groups) == 1:
                notes = notes[:NOTES_MAX]
        f.write_text(notes, encoding="utf-8")
        return notes

    def _lang_note(self, lang):
        return "Весь текст — на английском языке (English)." if lang == "en" else "Весь текст — на русском языке."

    def _plan(self, job, notes):
        m = job["meta"]
        if m.get("plan"):
            return m["plan"]
        b0, b1 = BLOCKS[m["minutes"]]
        sys_ = PLAN_SYS.format(minutes=m["minutes"], b0=b0, b1=b1, style=STYLE_NOTE[m["style"]], lang_note=self._lang_note(m["lang_used"]),
                               data=DATA_RULE if notes else "Материала нет — только тема: опирайся на надёжные общие знания.")
        user = (f"Пожелание человека (тема, на что сделать акцент): {m['topic']}\n\n" if m.get("topic") else "") + \
               (f"МАТЕРИАЛ:\n<<<\n{notes}\n>>>" if notes else "")
        plan = _json(self._ask(job, sys_, user or m.get("title", ""), 1500, 0.6)) or {}
        blocks = [b for b in plan.get("blocks") or [] if isinstance(b, dict) and b.get("title")][:8]
        title = re.sub(r"\s+", " ", re.sub(r"[«»\"“”\x00-\x1f*#]+", "", str(plan.get("title") or ""))).strip(" .")[:70]
        plan = {"title": title or m["title"], "hook": str(plan.get("hook") or "")[:400],
                "blocks": [{"title": str(b["title"])[:120], "points": [str(p)[:300] for p in (b.get("points") or [])][:5]} for b in blocks],
                "takeaways": [str(t)[:300] for t in (plan.get("takeaways") or [])][:4]}
        m["plan"] = plan
        return plan

    def _roles(self, m):
        a, b = m["hosts"]["a"], m["hosts"]["b"]
        fa, fb = a.get("gender") == "female", b.get("gender") == "female"
        if m["style"] == "debate":
            return (f"ведёт спор и защищает одну позицию (за), объясняет ясно, с примерами; уважает {b['name']}, но держит линию.",
                    "стоит на другой позиции (против или «не всё так просто»), задаёт неудобные вопросы, приводит контрпримеры из жизни.")
        return ((f"{'ведущая-рассказчица' if fa else 'ведущий-рассказчик'}: {'разобралась' if fa else 'разобрался'} в материале и "
                 f"объясняет просто, образами и примерами; {'тёплая' if fa else 'тёплый'}, с огоньком, любит «а вот что интересно…»."),
                (f"{'любопытная собеседница' if fb else 'любопытный собеседник'}: спрашивает то, что спросил бы слушатель-новичок, "
                 "удивляется, переспрашивает, иногда спорит и приводит примеры из жизни; с юмором, говорит проще."))

    def _script(self, job, notes, plan):
        m = job["meta"]
        if m.get("lines"):
            return m["lines"]
        a, b = m["hosts"]["a"], m["hosts"]["b"]
        ar, br = self._roles(m)
        sys_ = SCRIPT_SYS.format(a=a["name"], b=b["name"], a_role=ar, b_role=br, style=STYLE_NOTE[m["style"]],
                                 facts=FACTS_MAT if notes else FACTS_TOPIC, lang_note=self._lang_note(m["lang_used"]))
        segs = SEGMENTS[m["minutes"]]
        blocks = plan.get("blocks") or []
        per = max(1, math.ceil(len(blocks) / segs)) if blocks else 0
        target = m["minutes"] * CHARS_PER_MIN
        names = {"a": [a["name"], "A", "А", "Ведущая", "Ведущий 1", "Host A", "Speaker 1"],
                 "b": [b["name"], "B", "Б", "В", "Ведущий", "Ведущий 2", "Host B", "Speaker 2"]}
        lines = []
        plan_txt = (f"Название: {plan.get('title')}\nКрючок: {plan.get('hook')}\n"
                    + "\n".join(f"{k + 1}. {x['title']}: " + "; ".join(x.get("points") or []) for k, x in enumerate(blocks))
                    + "\nГлавное унести: " + "; ".join(plan.get("takeaways") or []))
        for s in range(segs):
            self._stage(job, "script", s / segs, f"часть {s + 1} из {segs}" if segs > 1 else "")
            mine = blocks[s * per:(s + 1) * per] if blocks else []
            first, last = s == 0, s == segs - 1
            chars = int(target / segs)
            task = [f"Напиши {'весь выпуск' if segs == 1 else f'часть {s + 1} из {segs}'} — примерно {chars} знаков текста "
                    f"(≈ {round(chars / CHARS_PER_MIN, 1)} мин речи), {max(14, chars // 140)}–{max(20, chars // 90)} реплик."]
            if first:
                task.append(f"Начни с крючка — сразу с интересного (не с приветствия): {plan.get('hook') or 'неожиданный вопрос по теме'}. "
                            f"Потом коротко и тепло: кто ведёт ({a['name']} и {b['name']}) и о чём выпуск.")
            else:
                task.append("Это продолжение разговора: без приветствий и представлений, подхвати с того места, где остановились.")
            if mine:
                task.append("Блоки этой части: " + "; ".join(x["title"] for x in mine) + ".")
            if last:
                task.append("В конце — итог: 2–3 главные мысли, которые стоит унести (живо, не списком), и короткое прощание.")
            else:
                task.append("Не подводи итог и не прощайся — разговор продолжится.")
            tail = "\n".join(f"{(a if x['who'] == 'a' else b)['name']}: {x['text']}" for x in lines[-6:])
            user = (f"ПЛАН ВЫПУСКА:\n{plan_txt}\n\n" + (f"Пожелание человека: {m['topic']}\n\n" if m.get("topic") else "")
                    + (f"МАТЕРИАЛ:\n<<<\n{notes}\n>>>\n\n" if notes else "")
                    + (f"Конец предыдущей части:\n{tail}\n\n" if tail else "") + "ЗАДАНИЕ: " + " ".join(task))
            raw = self._ask(job, sys_, user, min(8000, int(chars / 2.2) + 800), 0.85)
            got = parse_script(raw, names)
            if len(got) < 4:                                   # модель не держит формат — ещё раз, напомнив его
                raw = self._ask(job, sys_, user + f"\n\nВажно: каждая строка — «{a['name']}: …» или «{b['name']}: …».", min(8000, int(chars / 2.2) + 800), 0.7)
                got = parse_script(raw, names)
            if lines and got and got[0]["who"] == lines[-1]["who"]:
                lines[-1]["text"] += " " + got.pop(0)["text"]
            lines += got
        if len(lines) < 4:
            raise PodcastError("модель не смогла написать диалог — попробуйте ещё раз или другую модель в «Мозге»")
        out = []
        for x in lines:                                      # слишком длинная реплика — слишком долго говорит один
            for k, piece in enumerate(_split_long(x["text"])):
                out.append({"who": x["who"], "text": piece})
        m["lines"] = out
        return out

    def _check(self, job, notes, lines):
        """Сверка с материалом: правки по номерам реплик (не больше трети), что пропущено — в заметку выпуска."""
        m = job["meta"]
        if m.get("checked") or not notes:
            return lines
        a, b = m["hosts"]["a"]["name"], m["hosts"]["b"]["name"]
        fixes, missing, step = {}, [], 70
        for k in range(0, len(lines), step):
            self._stage(job, "check", k / max(1, len(lines)))
            part = "\n".join(f"{n + 1}. {a if x['who'] == 'a' else b}: {x['text']}" for n, x in enumerate(lines[k:k + step], start=k))
            try:
                d = _json(self._ask(job, CHECK_SYS, f"МАТЕРИАЛ:\n<<<\n{notes}\n>>>\n\nСЦЕНАРИЙ (номер. ведущий: реплика):\n{part}", 1800, 0.2)) or {}
            except PodcastError as e:                      # сверка — подстраховка: не вышла — выпуск всё равно будет
                log.info("Подкаст: сверка не вышла: %s", e)
                continue
            for fx in d.get("fixes") or []:
                try:
                    n = int(fx.get("n")) - 1
                except (TypeError, ValueError, AttributeError):
                    continue
                if k <= n < min(len(lines), k + step) and isinstance(fx.get("text"), str):
                    fixes[n] = _strip_stage(re.sub(r"^\s*(?:" + re.escape(a) + "|" + re.escape(b) + r")\s*:\s*", "", fx["text"]))[:LINE_MAX * 2]
            missing += [str(x)[:200] for x in d.get("missing") or [] if x][:5]
        if len(fixes) > max(3, len(lines) // 3):           # «правит» всё подряд — это не сверка, оставим как есть
            log.info("Подкаст: сверка предложила %d правок из %d — не применяю", len(fixes), len(lines))
            fixes = {}
        out = []
        for n, x in enumerate(lines):
            if n in fixes:
                if fixes[n]:
                    out.append({"who": x["who"], "text": fixes[n], "fixed": True})
            else:
                out.append(x)
        m["checked"] = {"fixed": len(fixes), "missing": missing[:6]}
        m["lines"] = out
        return out
