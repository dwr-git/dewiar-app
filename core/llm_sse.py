"""Поток ответа сервера модели (llm.py): разбор строк SSE и NDJSON (длинные строки, поля кроме data, [DONE]) и сборка
ответа из кусков (_Collector: текст, размышления, вызовы действий, расход токенов); что из вопроса прочитано вне
хода (turn_read_outside)."""

import httpx
import json
import re

from llm_base import LLMError, log
from llm_hints import drop_cjk
from llm_net import net_calls_filter, NET_SERVER_RX
from llm_text import repair_json, ThinkStripper, ToolTagStripper


class _Collector:
    """Разбор ответа любого из форматов: поток OpenAI (SSE), один JSON целиком, поток Ollama (NDJSON),
    события Anthropic. Текст ответа отдельно от «размышлений» (их только считает — reasoning, в символах)
    и от вызовов функций (поле tool_calls и теги в тексте). fmt, finish, raw_head — для журнала при пустом ответе."""

    def __init__(self, anthropic=False):
        self.anthropic = anthropic
        self.strip = ThinkStripper()
        self.tags = ToolTagStripper()
        self.calls = {}
        self.reasoning = 0
        self.finish = ""
        self.fmt = ""
        self.raw_head = ""
        self._pend, self._pend_n = [], 0  # недочитанный JSON по кускам (pending — склеенный, когда нужен)
        self.sse = False                  # пришла хоть одна строка «data:» — пустая строка заканчивает событие
        self.junk = 0                     # выброшенных строк потока, которые не JSON («data: ping», оборванный кусок)
        self.no_cjk = False
        self.usage = None                 # {"prompt": N, "cached": M | None} — если сервер посчитал (last_usage)
        self.llamacpp = False             # в ответе были timings — сервер llama.cpp (_llamacpp)
        self.out = None                   # токенов в ответе — если сервер посчитал (take_usage; задачи: t.data["quality"])
        self.net = False                  # ответил узел «Сети Лиры» — вызовы из текста не разбираем, из поля — только безопасные
        self.net_q = ""                   # сам вопрос человека (аргументы вызовов узла — только из него)
        self.net_enums = frozenset()

    def _take_usage(self, obj):
        """Подсчёт токенов подсказки: OpenAI/vLLM (usage + prompt_tokens_details.cached_tokens), llama.cpp (timings.cache_n),
        Anthropic (message_start: cache_read_input_tokens), Ollama (prompt_eval_count — без кэша)."""
        u = obj.get("usage") if isinstance(obj.get("usage"), dict) else None
        # ответ: OpenAI/vLLM completion_tokens, Claude output_tokens (message_delta), llama.cpp predicted_n, Ollama eval_count
        _o = (u or {}).get("completion_tokens", (u or {}).get("output_tokens"))
        if _o is None and isinstance(obj.get("timings"), dict):
            _o = obj["timings"].get("predicted_n")
        if _o is None and obj.get("done"):
            _o = obj.get("eval_count")
        if isinstance(_o, (int, float)) and _o:
            self.out = int(_o)
        if self.anthropic and obj.get("type") == "message_start":
            u0 = (obj.get("message") or {}).get("usage") or {}
            rd = int(u0.get("cache_read_input_tokens") or 0)
            self.usage = {"prompt": int(u0.get("input_tokens") or 0) + rd + int(u0.get("cache_creation_input_tokens") or 0), "cached": rd}
            return
        tm = obj.get("timings") if isinstance(obj.get("timings"), dict) else None
        if tm:
            self.llamacpp = True                  # llama.cpp (и сборки на нём): дальше просим cache_prompt
        if tm and "cache_n" in tm and "prompt_n" in tm:
            self.usage = {"prompt": int(tm.get("prompt_n") or 0) + int(tm.get("cache_n") or 0), "cached": int(tm.get("cache_n") or 0)}
            return
        if u and u.get("prompt_tokens") is not None and not self.anthropic:
            det = u.get("prompt_tokens_details") if isinstance(u.get("prompt_tokens_details"), dict) else {}
            c = det.get("cached_tokens", u.get("cached_tokens"))
            if c is None:                         # DeepSeek: prompt_cache_hit_tokens; Kimi — cached_tokens наверху (выше)
                c = u.get("prompt_cache_hit_tokens")
            self.usage = {"prompt": int(u.get("prompt_tokens") or 0), "cached": int(c) if isinstance(c, (int, float)) else None}
            return
        if obj.get("done") and obj.get("prompt_eval_count") is not None:
            self.usage = {"prompt": int(obj.get("prompt_eval_count") or 0), "cached": None}

    def _call(self, idx, cid="", name="", args=""):
        c = self.calls.setdefault(idx, {"id": "", "name": "", "args": ""})
        c["id"] = cid or c["id"]
        c["name"] = name or c["name"]
        c["args"] += args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)

    def feed_obj(self, obj):
        """-> кусок текста ответа (может быть пустым)."""
        if not isinstance(obj, dict):
            return ""
        if obj.get("error") and not obj.get("choices"):
            e = obj["error"]
            raise LLMError(e.get("message", str(e)) if isinstance(e, dict) else str(e))
        piece = ""
        try:
            self._take_usage(obj)
        except (TypeError, ValueError):
            pass
        if self.anthropic:
            typ = obj.get("type")
            if typ == "content_block_start" and obj.get("content_block", {}).get("type") == "tool_use":
                cb = obj["content_block"]
                self._call(obj.get("index", len(self.calls)), cb.get("id"), cb.get("name"))
            elif typ == "content_block_delta":
                d = obj.get("delta", {})
                if d.get("type") == "input_json_delta":
                    self._call(obj.get("index", 0), args=d.get("partial_json", ""))
                elif d.get("type") == "thinking_delta":
                    self.reasoning += len(d.get("thinking", ""))
                else:
                    piece = d.get("text", "")
            elif typ == "message_delta":
                self.finish = obj.get("delta", {}).get("stop_reason") or self.finish
        elif "choices" in obj:
            ch = (obj.get("choices") or [{}])[0]
            self.finish = ch.get("finish_reason") or self.finish
            d = ch.get("delta") or ch.get("message") or {}
            self.fmt = self.fmt or ("openai-stream" if "delta" in ch else "openai-json")
            piece = d.get("content") or ""
            self.reasoning += len(d.get("reasoning_content") or d.get("reasoning") or "")
            for i, tc in enumerate(d.get("tool_calls") or []):
                fn = tc.get("function") or {}
                self._call(tc.get("index", i), tc.get("id", ""), fn.get("name", ""), fn.get("arguments") or "")
        elif "message" in obj or "done" in obj:                    # родной формат Ollama
            self.fmt = self.fmt or "ollama"
            m = obj.get("message") or {}
            piece = m.get("content") or ""
            self.reasoning += len(m.get("thinking") or "")
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                self._call(len(self.calls), "", fn.get("name", ""), fn.get("arguments") or {})
            if obj.get("done"):
                self.finish = obj.get("done_reason") or "stop"
        d0 = self.strip.dropped
        piece = self.strip.feed(piece)
        self.reasoning += self.strip.dropped - d0
        out = self.tags.feed(piece)
        return drop_cjk(out) if self.no_cjk else out

    def flush(self):
        """Конец потока: придержанное начало ответа."""
        d0 = self.strip.dropped
        piece = self.strip.finish()
        self.reasoning += self.strip.dropped - d0
        out = (self.tags.feed(piece) if piece else "") + self.tags.tail()
        return drop_cjk(out) if self.no_cjk else out

    PENDING_MAX = 256 * 1024              # рецензия 0.87: JSON, разбитый на строки, длиннее — выбросить

    @property
    def pending(self):
        return "".join(self._pend)

    @pending.setter
    def pending(self, v):
        self._pend, self._pend_n = ([v], len(v)) if v else ([], 0)

    def _pend_add(self, s):
        if self._pend and self.sse:
            self._pend.append("\n")
        self._pend.append(s)
        self._pend_n += len(s) + 1

    def feed_line(self, line):
        """Строка ответа сервера (SSE «data: …» или строка JSON) -> кусок текста ответа.

        Идея №171 (10.11: «при прямом подключении по IP поток обрывается посреди генерации, хотя запрос завершается 200»):
        одна строка не-JSON в потоке — «data: ping», «id: 7», «retry: 3000», оборванный кусок — раньше оседала в pending,
        и каждая следующая строка склеивалась с ней и не разбиралась: текст молча кончался, хотя сервер дописывал ответ.
        Теперь поля SSE id/retry/event и комментарии пропускаем, не-JSON выбрасываем, пустая строка заканчивает событие
        (недочитанное — выбросить), а целый JSON после мусора разбираем сам по себе."""
        if len(self.raw_head) < 600:
            self.raw_head += line[:600] + "\n"
        s = line.strip()
        if s.startswith(":") and NET_SERVER_RX.match(s):
            self.net = True
        if not s:
            if self._pend and self.sse:                      # конец события SSE — его данные целиком
                return self._feed_pending(end=True)
            return ""
        if s.startswith(":") or _SSE_FIELD_RX.match(s):
            return ""
        if s.startswith("data:"):
            self.sse = True
            s = s[5:].strip()
            if s == "[DONE]" or not s:
                return ""
        if self._pend:
            # склеиваем и разбираем, только когда строка может закрыть JSON (рецензия 0.87: раньше — на каждой строке,
            # квадратично); целый объект после мусора — сам по себе
            closes = s.endswith(("}", "]"))
            obj = _json_dict(s) if closes and s.startswith("{") else None
            if obj is not None:
                self._drop("недочитанный кусок перед целым JSON", self.pending)
                return self.feed_obj(obj)
            self._pend_add(s)
            if self._pend_n > self.PENDING_MAX:
                self._drop("слишком длинный кусок без конца JSON", self._pend[0])
                return ""
            if closes:
                try:
                    obj = json.loads(self.pending)
                except ValueError:
                    return ""
                self.pending = ""
                return self.feed_obj(obj)
            return ""
        try:
            obj = json.loads(s)
        except ValueError:
            if s[:1] in "{[" and len(s) <= self.PENDING_MAX:
                self.pending = s                               # JSON целиком, разбитый на строки
            else:
                self._drop("строка не JSON", s)               # «data: ping», «keep-alive»
            return ""
        if not isinstance(obj, (dict, list)):
            self._drop("строка не объект JSON", s)
            return ""
        return self.feed_obj(obj)

    def _feed_pending(self, end=False):
        try:
            obj = json.loads(self.pending)
        except ValueError:
            if end:
                self._drop("событие SSE без целого JSON", self._pend[0] if self._pend else "")
            return ""
        self.pending = ""
        return self.feed_obj(obj)

    def _drop(self, why, text):
        self.junk += 1
        if self.junk <= 3:
            log.info("Поток модели: пропускаю %s: %r", why, str(text)[:120])
        self.pending = ""

    def tool_calls(self):
        """-> [{"id", "name", "args"}] — из поля tool_calls и из тегов в тексте (им — номера с 1000, после родных).
        Нечитаемые аргументы — {"_raw": текст}; спасённые repair_json помечены "_truncated"."""
        tagged = self.tags.calls()
        if self.net and tagged:
            log.warning("🌐 Сеть Лиры: узел прислал вызовы текстом (%s) — не выполняю", ", ".join(str(c.get("name")) for c in tagged)[:200])
            tagged = []
        for i, c in enumerate(tagged):
            self.calls[1000 + i] = {"id": f"call_t{i}", "name": c["name"], "args": json.dumps(c["args"], ensure_ascii=False)}
            if c.get("bracket"):
                self.calls[1000 + i]["bracket"] = True
        out = []
        for i in sorted(self.calls):
            c = self.calls[i]
            if not c["name"]:
                continue
            try:
                args = json.loads(c["args"]) if c["args"].strip() else {}
            except ValueError:
                args = repair_json(c["args"])
                if args is None:
                    args = {"_raw": c["args"]}
                else:
                    args["_truncated"] = True              # ответ оборвался по длине — аргументы закрыли сами
            out.append(dict({"id": c["id"] or f"call_{i}", "name": c["name"], "args": args}, **({"bracket": True} if c.get("bracket") else {})))
        return net_calls_filter(out, self.net_q, self.net_enums) if self.net else out


_DONE_RX = re.compile(r"^\s*data:\s*\[DONE\]\s*$")


_SSE_FIELD_RX = re.compile(r"^(?:event|id|retry)\s*:", re.I)      # поля SSE, кроме data — не текст ответа


def _stream_lines(r, col):
    """Строки потока ответа. Сервер уже сказал, что ответ окончен (finish_reason / done), и закрыл соединение без
    завершающего куска — это конец ответа, а не обрыв (идея №171: ответ целиком помечался ошибкой)."""
    try:
        yield from sse_lines(r.iter_bytes(), cancel=getattr(col, "cancel", None))
    except (httpx.RemoteProtocolError, httpx.ReadError) as e:
        if not col.finish:
            raise
        log.info("Поток модели: сервер закрыл соединение после конца ответа (%s) — ответ целый", str(e)[:120])


def _json_dict(s):
    """Строка — целый объект JSON -> dict, иначе None."""
    if not s.startswith("{"):
        return None
    try:
        obj = json.loads(s)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


SSE_LINE_MAX = 8 * 1024 * 1024          # символов в одной строке потока: длиннее — выбросить (рецензия 0.87)


_EOL_RX = re.compile(r"\r\n|\r|\n")


def sse_lines(chunks, cancel=None, limit=None):
    """Куски байт ответа -> строки текста. Сами, не по заголовкам сервера: всегда UTF-8 (буква, разрезанная между
    кусками, собирается целой; сервер без charset или с чужим charset не превращает её в «Ð»), концы строк \n, \r\n и
    \r — в том числе \r в конце одного куска и \n в начале следующего (идея №171).
    Рецензия 0.87: конец строки ищем только в новом куске (недописанная строка — списком кусков), строка длиннее limit
    выбрасывается до своего конца, cancel проверяется на каждом куске — и посреди длинной строки."""
    import codecs
    limit = SSE_LINE_MAX if limit is None else limit
    dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
    cur, size, cr, skip = [], 0, False, False
    for chunk in chunks:
        if cancel is not None and cancel.is_set():
            return
        if not chunk:
            continue
        text = dec.decode(chunk)
        if cr and text.startswith("\n"):
            text = text[1:]                                   # «\r» | «\n» на стыке кусков — один конец строки
        if not text:
            cr = False
            continue
        cr = text.endswith("\r")
        start = 0
        for m in _EOL_RX.finditer(text):
            piece = text[start:m.start()]
            start = m.end()
            if skip:
                skip = False
                continue
            if size + len(piece) > limit:
                log.info("Поток модели: строка длиннее %d символов — пропускаю", limit)
            else:
                cur.append(piece)
                yield "".join(cur)
            cur, size = [], 0
        rest = text[start:]
        if rest and not skip:
            size += len(rest)
            if size > limit:
                log.info("Поток модели: строка длиннее %d символов — пропускаю до её конца", limit)
                cur, size, skip = [], 0, True
            else:
                cur.append(rest)
    rest = dec.decode(b"", final=True)
    if not skip and (cur or rest) and size + len(rest) <= limit:
        yield "".join(cur) + rest


def turn_read_outside(messages):
    """В этом ходе модель уже видела тексты не от человека: результаты действий (страница, письмо, файл, поиск) или
    вложения к сообщению -> True. Тогда «[Вызов инструмента: …]» текстом не выполняем (рецензия 0.86: пересказ письма)."""
    msgs = list(messages or [])
    last = None
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        c = m.get("content")
        if m.get("role") == "user" and not (isinstance(c, str) and c.lstrip().startswith("<tool_response>")):
            last = i
            break
    if last is None:
        return False
    c = msgs[last].get("content")
    txt = c if isinstance(c, str) else " ".join(str(x.get("text") or "") for x in c or [] if isinstance(x, dict))
    if "\n\nВложения:" in txt:
        return True
    return any(m.get("role") == "tool" or m.get("tool_calls") or (m.get("role") == "user" and isinstance(m.get("content"), str)
               and m["content"].lstrip().startswith("<tool_response>")) for m in msgs[last + 1:])
