"""Фоновые задачи, часть «окно модели» (примесь TaskManager, core/tasks.py; чистое ядро 1.0.10 — docs/CORE_PLAN.md):
сообщения человека, свёртка и сжатие истории, окно и запас, бюджет, обрезка вызовов, сбои и циклы."""
import json
import re

import quality as Q
from llm import est_tokens
from tasks_base import (
    ACCESS_RX, COMPACT_AT, CYCLES, keep_facts, log, NO_TRIM, NOTEBOOK_HEAD, _now, TRIM_AFTER, WIN_DEFAULT)
import tasks_base as TB  # подменяемые в проверках имена — через основу


class ContextMixin:
    @staticmethod
    def _short(v, n=300):
        """Значение одной строкой для журнала, не длиннее n."""
        v = v["text"] if isinstance(v, dict) else str(v)
        v = v.replace("\n", " ⏎ ")
        return v if len(v) <= n else v[:n] + "…"

    @staticmethod
    def _add_user(msgs, text):
        """Сообщение «от пользователя» в разговор задачи (два подряд — склеиваем: не все модели это принимают)."""
        if msgs and msgs[-1].get("role") == "user" and isinstance(msgs[-1].get("content"), str):
            msgs[-1] = dict(msgs[-1], content=msgs[-1]["content"] + "\n\n" + text)
        else:
            msgs.append({"role": "user", "content": text})

    @staticmethod
    def _note_human(t, text):
        """Ответ человека (ask_user) и его сообщение задаче — сразу в блокнот, раздел «Ответы человека»: при сжатии памяти
        они не теряются (рецензия 0.83: «Казань» пропадала после сжатия)."""
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        if not text:
            return
        nb = t.notebook() or NOTEBOOK_HEAD
        line = f"- {text[:1500]} _({TB.dt.datetime.now():%d.%m %H:%M})_"
        head = "## Ответы человека\n"
        if head in nb:
            nb = nb.replace(head, head + line + "\n", 1)
        else:
            m = re.search(r"^# .*\n+", nb)
            at = m.end() if m else 0
            nb = nb[:at] + head + line + "\n\n" + nb[at:]
        t.set_notebook(nb)

    def _consolidate(self, t, prof, dropped):
        """Важное из шагов, которые уходят из разговора, — в блокнот (переписывает модель). Не вышло — дописываем
        в блокнот краткие действия и результаты как есть, чтобы факты не потерялись."""
        lines = []

        def res(txt):
            txt = str(txt or "")
            return ("Ответ человека" if txt.startswith(("Ответ пользователя", "Ответ на твой вопрос")) else "Результат") + f": {txt[:1500]}"
        for m in dropped:
            c = m.get("content")
            role = m.get("role")
            for x in m.get("tool_calls") or []:
                f = x.get("function") or {}
                lines.append(f"Действие: {f.get('name')} {str(f.get('arguments'))[:300]}")
            if isinstance(c, list):                    # Claude: text, tool_use, tool_result — блоками (рецензия 0.83)
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        lines.append(f"Действие: {b.get('name')} {json.dumps(b.get('input') or {}, ensure_ascii=False)[:300]}")
                    elif b.get("type") == "tool_result":
                        bc = b.get("content")
                        lines.append(res("".join(x.get("text", "") for x in bc if isinstance(x, dict)) if isinstance(bc, list) else bc))
                    elif b.get("type") == "text" and b.get("text"):
                        lines.append(f"{'Модель' if role == 'assistant' else 'Сообщение'}: {b['text'][:1500]}")
            elif c:
                lines.append(res(c) if role == "tool" else f"{'Модель' if role == 'assistant' else 'Сообщение'}: {str(c)[:1500]}")
        # окно модели маленькое — и переписка блокнота короче (иначе она сама не влезет: выпуск 1); слова человека — всегда
        human = [ln for ln in lines if ln.startswith(("Ответ человека", "Сообщение"))]
        lim = max(2000, min(24000, int(int(t.data.get("win") or WIN_DEFAULT) * 3 * 0.3)))
        rest = "\n".join(ln for ln in lines if ln not in human)[-max(500, lim - len("\n".join(human))):]
        text = "\n".join(human)[:lim] + ("\n" if human else "") + rest
        try:
            from llm import stream_chat
            out = "".join(stream_chat(prof, "Ты ведёшь блокнот долгой задачи. Ответь только новым текстом блокнота в Markdown.",
                                      [{"role": "user", "content":
                                        f"Цель задачи: {t.goal}\n\nБлокнот сейчас:\n{t.notebook() or NOTEBOOK_HEAD}\n\n"
                                        f"Ранние шаги, которые уходят из памяти:\n{text}\n\nПерепиши блокнот: сохрани всё, что "
                                        "в нём было, и добавь важное из этих шагов — факты, номера, коды, суммы, ответы людей "
                                        "и компаний, договорённости, что уже сделано, чего ждём, что дальше. Разделы: Что "
                                        "известно / Что решено / Файлы — что в каждом / Ошибки и как обошли / Чего ждём / "
                                        "Что дальше. Числа, коды, адреса и пути — дословно. Коротко, без воды."}],
                                      cancel=t.cancel)).strip()
            out = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", out)
            if len(out) > 40:
                t.set_notebook(keep_facts(t.notebook() or "", out))
                t.journal("🧠 Ранние шаги ушли из памяти — главное перенесено в блокнот.")
                return
        except Exception as e:  # noqa: BLE001
            log.info("Блокнот задачи не обновился моделью: %s", e)
        keep = [ln for ln in lines if ln.startswith(("Результат", "Действие", "Сообщение", "Ответ человека"))]
        t.set_notebook((t.notebook() or NOTEBOOK_HEAD).rstrip() + "\n\n## Из ранних шагов (кратко)\n"
                       + "\n".join("- " + ln[:300] for ln in keep)[-6000:])
        t.journal("🧠 Ранние шаги ушли из памяти — их краткие итоги дописаны в блокнот.")

    def _compact(self, t, prof, msgs, budget=None):
        """Разговор задачи больше budget символов: старые шаги (до ~60% бюджета) убираем, важное из них — в блокнот,
        подробности остаются в журнале. Первое сообщение (цель) остаётся. Режем по сообщению модели, чтобы ответы
        инструментов не остались без своих вызовов — такую историю модели отвергают."""
        budget = budget or TB.BUDGET
        size = lambda m: len(json.dumps(m, ensure_ascii=False))  # noqa: E731
        total = sum(size(m) for m in msgs)
        if total <= budget:
            return msgs
        # выпуск 1: сначала дешевле — убрать старые результаты и большие тексты в вызовах (даже в последних шагах, если
        # одного шага хватает, чтобы не влезть: write_file на 10 тыс. знаков при окне 8 тыс.) — шаги и факты остаются
        for keep in (TRIM_AFTER // 2, 2, 0):
            msgs, n = self._trim(t, msgs, keep=keep)
            total = sum(size(m) for m in msgs)
            if n:
                t.journal(f"🧹 Старые результаты убраны из памяти ({n}) — память задачи упёрлась в окно модели.")
            if total <= budget:
                return msgs
        if len(msgs) <= 3:
            return msgs
        k = 1
        while k < len(msgs) - 2 and total > budget * 0.6:
            total -= size(msgs[k])
            k += 1
        while k < len(msgs) - 1 and msgs[k].get("role") != "assistant":
            k += 1
        dropped = msgs[1:k]
        if not dropped:
            return msgs
        self._consolidate(t, prof, dropped)
        first = dict(msgs[0])
        note = "(ранние шаги убраны из памяти — главное перенесено в блокнот задачи, подробности — в журнале)"
        if note not in str(first.get("content")):
            first["content"] = f"{first.get('content')}\n\n{note}"
        return [first] + msgs[k:]

    @staticmethod
    def _window(prof):
        """Окно модели в токенах: из профиля (context_window), у своего сервера — спросить (llm.context_window: LM Studio,
        Ollama, vLLM), у Claude — 200 тыс., иначе WIN_DEFAULT. Ошибка «не хватило окна» уменьшает его для задачи (_run)."""
        try:
            w = int(prof.get("context_window") or prof.get("ctx") or 0)
        except (TypeError, ValueError):
            w = 0
        if not w and prof.get("kind") == "anthropic":
            w = 200000
        if not w:
            try:
                from llm import context_window
                w = int(context_window(prof) or 0)
            except Exception:  # noqa: BLE001
                w = 0
        return w or WIN_DEFAULT

    @staticmethod
    def _reserve(t, prof):
        """Место под ответ модели (токенов): лимит ответа профиля, но не больше четверти окна. Его же задача и шлёт модели
        как max_tokens (рецензия 0.83: окно 4 тыс. — запрос + 2048 на ответ не помещались, задача падала на первом шаге)."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        return max(256, min(int(prof.get("max_tokens") or 2048), win // 4))

    def _fit_reserve(self, t, prof, system, specs, msgs, state=""):
        """max_tokens для запроса: место под ответ (_reserve), но не больше, чем осталось в окне после самого запроса с
        запасом (0.90: окно 4 тыс., длинный путь папки задачи и 13 инструментов — неизменная часть сама ~3,1 тыс.;
        запрос + 1024 переваливал за окно, и сервер отказывал). Не меньше 256 — короче ответ не нужен."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        r = self._reserve(t, prof)
        need = (self._size(system) + (self._size([{"type": "function", "function": x} for x in specs]) if specs else 0)
                + self._size(msgs) + self._size(state))
        return max(256, min(r, win - need - max(64, win // 32)))

    @staticmethod
    def _win_key(prof):
        return f"{prof.get('base_url') or ''}|{prof.get('model') or ''}"

    @staticmethod
    def _size(x):
        return est_tokens(json.dumps(x, ensure_ascii=False))

    def _budget(self, t, prof, system, specs, state):
        """Сколько знаков истории можно держать: доля окна COMPACT_AT минус подсказка, инструменты, состояние и запас на
        ответ; не больше BUDGET (у больших окон — как раньше: дольше держать дороже)."""
        win = int(t.data.get("win") or WIN_DEFAULT)
        reserve = self._reserve(t, prof)                                       # место под ответ (vLLM: запрос + max_tokens ≤ окна)
        # как на деле уходит серверу: строки в JSON (переводы строк — «\\n»), инструменты — в обёртке {"type": "function"}
        fixed = self._size(system) + (self._size([{"type": "function", "function": x} for x in specs]) if specs else 0) + self._size(state)
        # запас ~3 % окна: оценка знаками неточна, а в результатах шагов бывают переменные числа (секунды, время) — при
        # окне 4 тыс. запрос «впритык» (0.84: 4107 из 4096 под нагрузкой) сервер отвергал
        return max(1200, min(TB.BUDGET, (min(int(win * COMPACT_AT), win - reserve - max(64, win // 32)) - fixed) * 3))

    @staticmethod
    def _calls_of(m):
        """Вызовы в сообщении модели (любой протокол) -> [(id, name, args)]; prompt-режим — по тегам <tool_call>."""
        out = []
        for x in m.get("tool_calls") or []:                               # OpenAI
            f = x.get("function") or {}
            try:
                a = json.loads(f.get("arguments") or "{}")
            except ValueError:
                a = {}
            out.append((x.get("id"), f.get("name"), a if isinstance(a, dict) else {}))
        c = m.get("content")
        if isinstance(c, list):                                          # Claude
            out += [(b.get("id"), b.get("name"), b.get("input") or {}) for b in c if isinstance(b, dict) and b.get("type") == "tool_use"]
        elif isinstance(c, str) and "<tool_call>" in c:                  # функции текстом
            for j in re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", c, re.S):
                try:
                    d = json.loads(j)
                    out.append((None, d.get("name"), d.get("arguments") or {}))
                except ValueError:
                    pass
        return out

    @staticmethod
    def _stub(name, args, text):
        """Заглушка вместо старого результата: что это было и где взять снова."""
        hint = ""
        for k in ("path", "url", "query", "command", "pattern", "name"):
            if isinstance(args, dict) and args.get(k):
                hint = str(args[k])[:160]
                break
        m = re.search(r"_out/[^\s\]:]+\.txt|_explore/[^\s\]:]+\.md", text or "")
        where = f"целиком — {m.group(0)}" if m else ("перечитай, если нужно" if hint else "повтори, если нужно")
        return f"[убрано из памяти: результат {name}" + (f" ({hint})" if hint else "") + f" — {where}]"

    def _trim(self, t, msgs, keep=None):
        """Чистка: результаты инструментов старше keep шагов (кроме ответов человека и итогов частей) — заглушкой
        «[убрано из памяти: …]», большие тексты в старых вызовах (содержимое write_file, код run_python) — короткой пометкой.
        Шаги и порядок действий остаются — модель видит, что делала. -> (новый список, сколько убрано)."""
        keep = TRIM_AFTER if keep is None else keep
        steps = [i for i, m in enumerate(msgs) if m.get("role") == "assistant" and self._calls_of(m)]
        if len(steps) <= keep:
            return msgs, 0
        cut = steps[-keep] if keep else len(msgs)
        # keep=0 — только большие тексты в вызовах (и в последнем шаге); результат последнего шага модель ещё не видела —
        # его не трогаем никогда (иначе после сжатия она получала заглушку вместо ответа инструмента)
        cut_res = steps[-max(keep, 1)]
        out, n = [dict(m) for m in msgs], 0
        calls = {}
        last_calls = []
        for i in range(len(out)):
            if i >= cut:
                break
            m = out[i]
            cs = self._calls_of(m) if m.get("role") == "assistant" else []
            if cs:
                last_calls = cs
                for cid, nm, a in cs:
                    calls[cid] = (nm, a)
                # большие тексты в аргументах старых вызовов
                if m.get("tool_calls"):
                    tc = []
                    for x in m["tool_calls"]:
                        f = dict(x.get("function") or {})
                        try:
                            a = json.loads(f.get("arguments") or "{}")
                        except ValueError:
                            a = None
                        if isinstance(a, dict):
                            a2 = self._slim_args(f.get("name"), a)
                            if a2 is not a:
                                f["arguments"] = json.dumps(a2, ensure_ascii=False)
                                n += 1
                        tc.append(dict(x, function=f))
                    m["tool_calls"] = tc
                elif isinstance(m.get("content"), list):
                    bl = []
                    for b in m["content"]:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            a2 = self._slim_args(b.get("name"), b.get("input") or {})
                            if a2 is not (b.get("input") or {}):
                                b = dict(b, input=a2)
                                n += 1
                        bl.append(b)
                    m["content"] = bl
                continue
            if i >= cut_res:
                continue
            if m.get("role") == "tool":                                  # OpenAI
                nm, a = calls.get(m.get("tool_call_id"), ("?", {}))
                c = m.get("content")
                if isinstance(c, str) and len(c) > 400 and nm not in NO_TRIM and not c.startswith("[убрано"):
                    m["content"] = self._stub(nm, a, c)
                    n += 1
            elif m.get("role") == "user" and isinstance(m.get("content"), list):   # Claude: tool_result
                bl = []
                for b in m["content"]:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        nm, a = calls.get(b.get("tool_use_id"), ("?", {}))
                        parts = b.get("content")
                        txt = "".join(x.get("text", "") for x in parts if isinstance(x, dict)) if isinstance(parts, list) else str(parts or "")
                        if len(txt) > 400 and nm not in NO_TRIM and not txt.startswith("[убрано") and \
                                not any(isinstance(x, dict) and x.get("type") == "image" for x in (parts if isinstance(parts, list) else [])):
                            b = dict(b, content=[{"type": "text", "text": self._stub(nm, a, txt)}])
                            n += 1
                    bl.append(b)
                m["content"] = bl
            elif m.get("role") == "user" and isinstance(m.get("content"), str) and "<tool_response>" in m["content"]:
                parts = re.split(r"(<tool_response>\n?.*?\n?</tool_response>)", m["content"], flags=re.S)
                k, changed = 0, False
                for j, part in enumerate(parts):
                    if part.startswith("<tool_response>"):
                        nm, a = (last_calls[k][1], last_calls[k][2]) if k < len(last_calls) else ("?", {})
                        k += 1
                        body = part[len("<tool_response>"):-len("</tool_response>")].strip()
                        if len(body) > 400 and nm not in NO_TRIM and not body.startswith("[убрано"):
                            parts[j] = f"<tool_response>\n{self._stub(nm, a, body)}\n</tool_response>"
                            changed = True
                            n += 1
                if changed:
                    m["content"] = "".join(parts)
        return out, n

    @staticmethod
    def _slim_args(name, a):
        """Аргументы старого вызова без больших текстов (тот же объект, если убирать нечего)."""
        big = {k: v for k, v in a.items() if isinstance(v, str) and len(v) > 1500}
        if not big:
            return a
        a2 = dict(a)
        for k, v in big.items():
            where = f" — в файле {a.get('path')}" if a.get("path") else ""
            a2[k] = f"[убрано из памяти: {len(v)} знаков{where}]"
        return a2

    def _fail(self, t, e, bug=False):
        """Задача остановилась с ошибкой: статус, журнал, след для уроков, голос и уведомление, пульс и журнал сбоев."""
        msg = str(e) or e.__class__.__name__
        if bug:
            msg = f"внутренняя ошибка программы ({e.__class__.__name__}: {msg}) — уже записана для разработчика"
        kind = "loop" if msg.startswith("застрял") else ("bug" if bug else ("idle_model" if "не взялась за дело" in msg else "failed"))
        if not bug and ACCESS_RX.search(msg):
            kind = "access"                           # нет прав на файл или папку — ночью повторять бесполезно (night.NO_RETRY)
        t.data.update(status="failed", error=msg, fail_kind=kind, failed_at=_now())   # fail_kind — для ночного обхода (night.py)
        t.journal(f"⚠ Ошибка: {msg}")
        self._trace(t, "loop_detected" if kind == "loop" else ("bug" if bug else "failed"))
        self._problem(f"Задача{' (программа)' if bug else ''}: {e.__class__.__name__ if bug else ''} {str(e)[:200]}".replace("  ", " "))
        if not t.data.get("parent"):
            self.host.announce(f"Задача «{t.title}» остановилась с ошибкой: {msg}")
            self._push(f"⚠ Задача остановилась: {t.title}", msg[:200], critical=True)

    @staticmethod
    def _transient(e):
        """Сбой, который проходит сам: сеть, перегрузка, таймаут, пустой ответ сервера. Узнаём по тексту ошибки
        (сообщения llm.py и серверов) — такой сбой даёт повтор по RETRY_MIN, а не провал задачи."""
        m = str(e).lower()
        return any(k in m for k in ("не отвеч", "не ответил вовремя", "недоступ", "timeout", "timed out", "connect", "подключ", "соедин",
                                    "502", "503", "504", "перегруж", "overload", "temporar", "пустой ответ", "ошибкой 5",
                                    "время вышло", "rate limit", "429", "слишком много запросов", "подождите минуту",
                                    "без текста"))

    def _cycles(self):
        """Сколько кругов по max_steps задача идёт сама: DEWIAR_TASK_CYCLES, настройка tasks.cycles или 15."""
        if CYCLES:
            return CYCLES
        try:
            return max(1, int(self.host.s.get("tasks", "cycles") or 15))
        except (AttributeError, TypeError, ValueError):
            return 15

    @staticmethod
    def _progress_sig(t):
        """Отпечаток продвижения: план (сколько отмечено), блокнот, файлы-результаты и файлы в папке задачи. Служебное
        (Q.SERVICE: скрипты шагов _run/, длинные выводы _out/, опора _src/, журнал, история…) — не продвижение: №551 — каждый
        run_python оставлял _run/шагN.py, и задача час крутила скрипты, а «буксует» не срабатывало."""
        import hashlib
        try:
            files = sorted(f"{p.relative_to(t.dir)}:{p.stat().st_size}" for p in t.dir.rglob("*")
                           if p.is_file() and not p.is_symlink() and p.relative_to(t.dir).parts[0] not in Q.SERVICE and "рабочая копия" not in p.parts
                           and not p.name.endswith(".tmp"))
        except OSError:
            files = []
        h = hashlib.sha1("\n".join([t.plan(), t.notebook(), json.dumps(t.data.get("outputs") or []), *files[:2000]]).encode()).hexdigest()
        return h[:16]

    def _setting_int(self, key, default, lo, hi):
        """Целая настройка tasks.<key> в пределах [lo, hi]; не задана или не число — default."""
        try:
            v = int(self._opt(key) or 0)
        except (TypeError, ValueError):
            v = 0
        return max(lo, min(hi, v)) if v else default
