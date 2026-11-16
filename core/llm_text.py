"""Ответ модели как текст (llm.py): размышления вслух (ThinkStripper), вызовы действий не по протоколу — DSML DeepSeek,
[скобки], теги <tool_call>, голый JSON — в обычный вызов; разбор вызова и починка оборванного JSON."""

import json
import re

from llm_base import log


# Начало «размышлений вслух» без тегов: модель рассуждает про себя (часто по-английски), а потом пишет </think>
# (тег <think> уже стоит в шаблоне сервера) или «assistantfinal» (gpt-oss). Такое начало придерживаем, пока не станет ясно.
_REASON_START = re.compile(
    r"^\s*(okay|ok,|alright|so,|hmm|well,|let me|let's|let us|i need|i should|i'll|i will|i must|first,|we need|we have|we should|"
    r"the user|user (asks|wants|is|said)|looking at|analy[sz]|thinking|reasoning|"
    r"хорошо, пользовател[ьяю](?![а-яё])|итак, пользовател[ьяю](?![а-яё])|пользователь (спрашивает|просит|хочет|сказал|написал|пишет)|"
    r"мне нужно (понять|разобраться|ответить|вызвать|сначала)|так, пользовател[ьяю](?![а-яё]))", re.I)   # «Итак, пользовательские данные…» — это ответ, не рассуждение


_REASON_WORDS = {"okay", "ok", "alright", "so", "hmm", "well", "let", "i", "first", "we", "the", "user", "looking",
                 "analysis", "analyzing", "analysing", "analyze", "thinking", "reasoning", "хорошо", "итак", "пользователь",
                 "мне", "так"}


_FINAL_MARK = re.compile(r"</think>|<\|channel\|>final<\|message\|>|(?<![a-z])assistantfinal", re.I)


_HARMONY = re.compile(r"<\|[a-z_]+\|>")


class ThinkStripper:
    """Вырезает размышления «думающих» моделей прямо из потока: <think>…</think>, а также рассуждение без
    открывающего тега (…</think> ответ) и формат gpt-oss (analysis… assistantfinal ответ).
    Начало ответа придерживается, пока не ясно, рассуждение это или ответ (обычно — первые ~60 символов)."""

    GATE = 60            # столько символов начала смотрим, прежде чем отдавать текст
    CAP = 20000          # дальше не ждём конца рассуждения

    def __init__(self):
        self.buf, self.inside = "", False
        self.gate = True     # начало ответа ещё не отдано
        self.dropped = 0     # сколько символов рассуждений выброшено (для «модель только думала»)

    def _gate(self):
        """Решить судьбу начала ответа. -> "" — ещё не ясно, ждём; None — решено (рассуждение срезано
        или его нет), буфер разбирает основной цикл feed()."""
        b = self.buf
        m = _FINAL_MARK.search(b)
        if m:                                             # всё до метки — рассуждение
            self.dropped += m.start()
            self.buf, self.gate, self.inside = b[m.end():].lstrip(), False, False
            return None
        i = b.find("<think>")
        if i >= 0 and not b[:i].strip():
            self.gate = False                             # обычный <think>…</think> — разберёт основной цикл
            return None
        lead = b.lstrip()
        if _REASON_START.match(lead) or lead.lower().startswith(("analysis", "<|start|>", "<|channel|>")):
            if len(b) < self.CAP:
                return ""                                 # похоже на рассуждение — ждём метку конца
            self.gate = False                             # слишком долго — отдаём как есть
            return None
        w = re.match(r"([^\W\d_]+)[\W\d_]", lead)
        if w and w.group(1).lower() not in _REASON_WORDS:  # первое слово — не начало рассуждения: отдаём сразу
            self.gate = False
            return None
        if len(lead) < self.GATE and "\n" not in lead.strip():
            return ""
        self.gate = False
        return None

    def feed(self, s):
        """Очередной кусок потока -> текст, который уже можно отдать (может быть пустым)."""
        self.buf += s
        if self.gate:
            if self._gate() == "":
                return ""
        out = ""
        while True:
            if self.inside:
                i = self.buf.find("</think>")
                if i < 0:
                    self.dropped += max(0, len(self.buf) - 8)
                    self.buf = self.buf[-8:]
                    return self._clean(out)
                self.dropped += i
                self.buf, self.inside = self.buf[i + 8:], False
            else:
                i = self.buf.find("<think>")
                if i < 0:
                    keep = 0
                    for k in range(1, 9):                       # возможно, тег разрезан на куски
                        if self.buf.endswith("</think>"[:k]) or self.buf.endswith("<think>"[:k]):
                            keep = max(keep, k)
                    out += self.buf[:len(self.buf) - keep]
                    self.buf = self.buf[len(self.buf) - keep:]
                    return self._clean(out)
                out += self.buf[:i]
                self.buf, self.inside = self.buf[i + 7:], True

    @staticmethod
    def _clean(t):
        return _HARMONY.sub("", t.replace("</think>", ""))

    def finish(self):
        """Конец ответа: что осталось в запасе. Начало так и не прояснилось и похоже на рассуждение без ответа — ""."""
        b, self.buf = self.buf, ""
        if self.inside:
            self.dropped += len(b)
            return ""
        if self.gate:
            self.gate = False
            m = _FINAL_MARK.search(b)
            if m:
                self.dropped += m.start()
                return self._clean(b[m.end():].strip())
            letters = re.findall(r"[A-Za-zА-Яа-яЁё]", b[:1500])
            latin = sum(c.isascii() for c in letters) / max(1, len(letters))
            if _REASON_START.match(b.lstrip()) and len(b) > 400 and (latin > 0.5 or re.search(r"пользовател[ьяю](?![а-яё])", b[:300], re.I)):
                self.dropped += len(b)                    # длинное рассуждение без ответа (по-английски или «пользователь …»)
                return ""
        return self._clean(b)


# вызов голым JSON прямо в тексте: {"name": "money_report", "arguments": {…}} — часто с одиноким «</tool_call>» после
# (модель забыла открывающий тег). Узнаём по имени-идентификатору и ключу аргументов сразу за ним — обычный JSON для
# человека («{"name": "Иван", "age": 30}») так не выглядит.
_BARE_CALL = re.compile(r'\{\s*"(?:name|tool_name|function_name|tool)"\s*:\s*"[A-Za-z_][\w.-]*"\s*,\s*'
                        r'"(?:arguments|args|parameters|params|input)"\s*:')


# DeepSeek (V3.2+) пишет вызовы своим языком DSML, а не <tool_call> (пакет 27.10, №301: в ответе было видно
# «<｜DSML｜invoke name="weather">…», вызов не выполнялся, а температура дальше была выдуманной):
#   <｜DSML｜function_calls><｜DSML｜invoke name="weather"><｜DSML｜parameter name="city" string="true">Москва</｜DSML｜parameter>
#   </｜DSML｜invoke></｜DSML｜function_calls>
# Переводим в привычный <tool_call>{json}</tool_call> ещё в потоке — дальше всё как у Qwen.
# №348 (пакет 27.10, DeepSeek v4.1 через polza.ai): «<DSML calls><DSML invoke name="lab_write"><DSML parameter name="arguments"
# string="false">{json}» — без «｜», «calls» вместо «function_calls», все аргументы одним JSON — модель читала это вслух.
# №448, №460 (ПК 0.76, DeepSeek напрямую, 31.10–01.11): фоновая задача «повторяла одно и то же» и вставала через пару
# шагов — модель звала действия, а Dewiar их не узнавал. У №448 «｜» стояли и перед «>» («<｜DSML calls｜>» — в журнале
# после drop_cjk это выглядело как «<DSML calls>»), у №460 сервер выбросил служебное «｜DSML｜» целиком:
# «<tool_calls><invoke name="remember"><parameter name="fact">…</parameter></invoke></tool_calls>». Поэтому «｜», «|»
# и «▁» допускаются в любом месте тега, а «DSML» — необязателен (без него — только function_calls/tool_calls и
# invoke с name=, чтобы не путать с обычным текстом).
_DB = r"[\s｜|▁]*"                                   # «｜», «|», «▁» и пробелы внутри тега


_DO = r"<" + _DB + r"(?:DSML" + _DB + r")?"


_DC = r"<" + _DB + r"/" + _DB + r"(?:DSML" + _DB + r")?"


_DSML_OPEN = re.compile(r"<" + _DB + r"DSML" + _DB + r"(?:function[_▁]calls|tool[_▁]calls|calls|invoke)\b|"
                        r"<" + _DB + r"(?:function[_▁]calls|tool[_▁]calls)" + _DB + r">|"
                        r"<" + _DB + r"invoke[\s｜|▁]+name=\"")


_DSML_END = re.compile(_DC + r"(?:function[_▁]calls|tool[_▁]calls|calls)" + _DB + r">|" + _DC + r"invoke" + _DB + r">(?![\s\S]*" + _DO + r"invoke)")


_DSML_INVOKE = re.compile(_DO + r"invoke[\s｜|▁]+name=\"([^\"]+)\"" + _DB + r">([\s\S]*?)(?:" + _DC + r"invoke" + _DB + r">|$)")


_DSML_STRAY = re.compile(r"<" + _DB + r"/" + _DB + r"DSML" + _DB + r"(?:function[_▁]calls|tool[_▁]calls|calls)" + _DB + r">|"
                         r"<" + _DB + r"/" + _DB + r"(?:function[_▁]calls|tool[_▁]calls)" + _DB + r">")   # внешний «</DSML calls>» после invoke


_DSML_PARAM = re.compile(_DO + r"parameter[\s｜|▁]+name=\"([^\"]+)\"(?:[\s｜|▁]+string=\"(true|false)\")?" + _DB + r">([\s\S]*?)"
                         + _DC + r"parameter" + _DB + r">")


_DSML_WORDS = ("DSML", "function_calls", "function▁calls", "tool_calls", "tool▁calls", "invoke")


def _dsml_part(tail):
    """Хвост потока «<…» без «>» — может оказаться началом тега DSML («<｜DS», «<tool_ca», «<invoke na»): придержать."""
    if len(tail) > 48 or ">" in tail or not tail.startswith("<"):
        return False
    s = re.sub(r"^<[\s｜|▁/]*", "", tail)
    w = (re.match(r"[A-Za-z_▁]*", s) or [""])[0]
    if not s:
        return True
    return bool(w) and any(k.startswith(w) or w.startswith(k) for k in _DSML_WORDS)


def dsml_calls(text):
    """Текст с DSML -> строка из <tool_call>{json}</tool_call> (пустая — вызовов нет)."""
    out = []
    for name, body in _DSML_INVOKE.findall(text or ""):
        args = {}
        for k, is_str, v in _DSML_PARAM.findall(body):
            v = v.strip()
            if is_str == "false":
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            args[k] = v
        if list(args) == ["arguments"] and isinstance(args["arguments"], dict):    # все аргументы одним JSON (№348)
            args = args["arguments"]
        out.append("<tool_call>" + json.dumps({"name": name, "arguments": args}, ensure_ascii=False) + "</tool_call>")
    return "".join(out)


class DSMLFilter:
    """Поток текста -> тот же поток, где блоки DSML заменены на <tool_call>. Начало «<｜DSML…», разрезанное между
    кусками, придерживается."""

    def __init__(self):
        self.buf, self.inside = "", False

    def feed(self, s):
        self.buf += s
        out = ""
        while True:
            if self.inside:
                m = _DSML_END.search(self.buf)
                if not m:
                    return out
                out += dsml_calls(self.buf[:m.end()])
                self.buf, self.inside = self.buf[m.end():], False
                continue
            m = _DSML_OPEN.search(self.buf)
            st = _DSML_STRAY.search(self.buf)
            if st and (not m or st.start() < m.start()):          # хвост «</DSML calls>» — убрать
                out += self.buf[:st.start()]
                self.buf = self.buf[st.end():]
                continue
            if m:
                out += self.buf[:m.start()]
                self.buf, self.inside = self.buf[m.start():], True
                continue
            i = self.buf.rfind("<")                               # «<｜DSML…», «<tool_ca…», разрезанное между кусками
            keep = len(self.buf) - i if i >= 0 and _dsml_part(self.buf[i:]) else 0
            out += self.buf[:len(self.buf) - keep]
            self.buf = self.buf[len(self.buf) - keep:]
            return out

    def tail(self):
        t, self.buf = self.buf, ""
        if self.inside:
            self.inside = False
            return dsml_calls(t) or t
        return t


# №603 (Mac, «Dewiar Облако / DWR Chat Qwen 3.8», 07.11): «Лира вызывает search_documents — и останавливается; следующим
# сообщением уже отвечает по найденному». По журналу вызова в эти ходы не было вовсе: модель писала его ТЕКСТОМ —
# «[Вызов инструмента: search_documents, query=LIRA_02_OPERATING_SYSTEM]» (54–128 знаков), ход кончался, а человек видел
# строку как «вызвала». Такую запись (и английскую «[Tool call: …]») с известным именем функции переводим в <tool_call>.
_BR_OPEN = re.compile(r"\[\s*(?:вызов\s+инструмента|вызываю\s+инструмент|инструмент|tool[\s_]*call|calling\s+tool|function\s+call)\s*:\s*", re.I)


_BR_WORDS = ("вызов инструмента", "вызываю инструмент", "инструмент", "tool call", "tool_call", "calling tool", "function call")


_BR_CALL = re.compile(r"\s*([A-Za-z_][\w.-]*)\s*(?:(?:[,;(]|(?=\{))\s*([\s\S]*?))?\)?\s*\]")


BR_MAX = 700                       # длиннее весь ответ — это уже рассказ, а не «вызов текстом» (№603: 54–128 знаков)


# Рецензия 0.86: скобочная запись — не настоящий вызов, её легко подсунуть пересказом письма или страницы. Поэтому только
# хвостом короткого ответа (строка в конце, не в кавычках и не в ```), только в ходе, где внешних текстов ещё не читали,
# и всё, кроме чтения, — через «Выполнить?» (engine_tools: call["bracket"]).
_BR_POS = re.compile(r"(?:^|\n|[.!?…]\s+|:\s+)$")


def bracket_call(text, known):
    """«[Вызов инструмента: name, k=v, k2="v 2"]» -> строка <tool_call>{json}</tool_call> или "" (не вызов / чужое имя).
    В JSON — метка "_bracket": вызов разобран из скобок (см. ToolTagStripper.calls)."""
    m = _BR_OPEN.match(text or "")
    c = _BR_CALL.match(text, m.end()) if m else None
    if not c or c.group(1) not in known or text[c.end():].strip():
        return ""
    args, raw = {}, (c.group(2) or "").strip()
    if raw.startswith("{"):
        try:
            args = json.loads(raw)
        except ValueError:
            args = {}
        if not isinstance(args, dict):
            return ""
    else:
        for part in re.split(r"[,;]\s*(?=[A-Za-z_][\w-]*\s*[=:])", raw):
            kv = re.match(r"\s*([A-Za-z_][\w-]*)\s*[=:]\s*([\s\S]*)", part)
            if kv:
                v = kv.group(2).strip().strip("`").strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]
                elif v.startswith("«") and v.endswith("»"):
                    v = v[1:-1]
                try:
                    v = json.loads(v) if re.fullmatch(r"-?\d+(?:\.\d+)?|true|false|\[.*\]|\{.*\}", v) else v
                except ValueError:
                    pass
                args[kv.group(1)] = v
    return "<tool_call>" + json.dumps({"name": c.group(1), "arguments": args, "_bracket": 1}, ensure_ascii=False) + "</tool_call>"


def _br_place_ok(before):
    """Может ли скобочная запись начаться здесь: начало строки или после конца фразы, и не внутри ``` или кавычек."""
    if not _BR_POS.search(before):
        return False
    if before.count("```") % 2 or before.count("«") > before.count("»") or before.count('"') % 2 or before.count("`") % 2:
        return False
    return True


class BracketCallFilter:
    """Поток -> тот же поток; «[Вызов инструмента: …]» хвостом короткого ответа — в <tool_call> (только в tail()).
    С подходящего места «[Выз…» поток придерживается до конца: пришёл текст после «]» — это был просто текст."""

    def __init__(self, owner):
        self.owner, self.buf, self.seen, self.held = owner, "", "", False

    def _ok(self):
        return bool(self.owner.known) and not getattr(self.owner, "no_bracket", False)

    def feed(self, s):
        self.buf += s
        out = ""
        while True:
            if self.held:
                j = self.buf.find("]")
                if j >= 0 and self.buf[j + 1:].strip():               # после «]» есть текст — не хвост, обычный текст
                    self.held = False
                    out, self.seen, self.buf = out + self.buf[0], self.seen + self.buf[0], self.buf[1:]
                    continue
                if len(self.seen) + len(self.buf) > BR_MAX:
                    self.held = False
                    out, self.seen, self.buf = out + self.buf, self.seen + self.buf, ""
                return out
            i = self.buf.find("[")
            if i < 0 or not self._ok():
                out, self.seen, self.buf = out + self.buf, self.seen + self.buf, ""
                return out
            out, self.seen, self.buf = out + self.buf[:i], self.seen + self.buf[:i], self.buf[i:]
            if _br_place_ok(self.seen) and len(self.seen) < BR_MAX:
                m = _BR_OPEN.match(self.buf)
                head = re.sub(r"\s+", " ", self.buf[1:].lstrip().lower())
                if m or (len(self.buf) < 40 and "]" not in self.buf and any(w.startswith(head) or head.startswith(w) for w in _BR_WORDS)):
                    if m:
                        self.held = True
                        continue
                    return out                                      # «[Выз» — может оказаться записью вызова
            out, self.seen, self.buf = out + self.buf[0], self.seen + self.buf[0], self.buf[1:]

    def tail(self):
        t, self.buf = self.buf, ""
        conv = bracket_call(t, self.owner.known) if self._ok() and _br_place_ok(self.seen) and len(self.seen) + len(t) <= BR_MAX else ""
        self.held = False
        if conv:
            log.info("🛠 Вызов записан текстом в конце ответа — выполню как вызов (через «Выполнить?», если это не чтение)")
        self.seen += t
        return conv or t


class ToolTagStripper:
    """Вызовы функций прямо в тексте ответа — <tool_call>{json}</tool_call> (родной формат Qwen/Hermes).
    Нужен, когда сервер сам их не разбирает (vLLM без --tool-call-parser) или функции описаны в тексте
    (tools_prompt). Такие куски вырезаются из текста и не озвучиваются; calls() -> разобранные вызовы.
    Так же — вызов голым JSON посреди текста ({"name": …, "arguments": …}) и одинокий «</tool_call>» без открывающего.
    Текст после вызова не отдаётся: результата функции ещё нет — дальше модель сочиняет его сама (настоящий ответ
    будет следующим ходом, с результатом)."""

    OPEN, CLOSE = "<tool_call>", "</tool_call>"

    def __init__(self):
        self.buf, self.inside, self.found, self.after, self.dropped = "", False, [], False, ""
        self.known = set()          # имена функций этого запроса: голый JSON с другим именем (или без функций) — текст
        self.dsml = DSMLFilter()    # вызовы DeepSeek (DSML) — сначала в <tool_call>
        self.br = BracketCallFilter(self)   # «[Вызов инструмента: …]» текстом (№603) — тоже в <tool_call>

    def _bare_end(self):
        """inside == "bare": конец JSON вызова в buf -> индекс после него или -1 (ещё не пришёл целиком)."""
        try:
            _, end = json.JSONDecoder().raw_decode(self.buf)
            return end
        except ValueError:
            return -1

    def feed(self, s):
        self.buf += self.dsml.feed(self.br.feed(s))
        out = ""
        while True:
            if self.inside == "bare":
                end = self._bare_end()
                if end < 0:
                    return out
                try:
                    name = _call_parts(json.loads(self.buf[:end]))[0]
                except (ValueError, TypeError, AttributeError):
                    name = None
                if name not in self.known:                 # не наша функция — это просто текст с JSON
                    if self.after:
                        self.dropped += self.buf[:end]
                    else:
                        out += self.buf[:end]
                    self.buf, self.inside = self.buf[end:], False
                    continue
                self.found.append(self.buf[:end])
                rest = self.buf[end:].lstrip()
                if rest.startswith(self.CLOSE):
                    rest = rest[len(self.CLOSE):]
                elif self.CLOSE.startswith(rest) and rest:
                    self.buf, self.after = rest, True       # «</tool_» — дождёмся конца тега
                    self.inside = "close"
                    return out
                self.buf, self.inside, self.after = rest, False, True
            elif self.inside == "close":
                if self.buf.startswith(self.CLOSE):
                    self.buf = self.buf[len(self.CLOSE):]
                elif self.CLOSE.startswith(self.buf):
                    return out
                self.inside = False
            elif self.inside:
                i = self.buf.find(self.CLOSE)
                if i < 0:
                    return out
                self.found.append(self.buf[:i])
                self.buf, self.inside, self.after = self.buf[i + len(self.CLOSE):], False, True
            else:
                cands = [(k, kind) for k, kind in ((self.buf.find(self.OPEN), "open"), (self.buf.find(self.CLOSE), "stray"))
                         if k >= 0]
                m = _BARE_CALL.search(self.buf) if self.known else None
                if m:
                    cands.append((m.start(), "bare"))
                if not cands:
                    keep = 0
                    for tag in (self.OPEN, self.CLOSE):
                        for k in range(1, len(tag)):
                            if self.buf.endswith(tag[:k]):
                                keep = max(keep, k)
                    b = self.buf.rfind("{") if self.known else -1   # «{"name": "mo…» — может оказаться вызовом, придержим
                    if b >= 0 and "}" not in self.buf[b:] and len(self.buf) - b < 160:
                        keep = max(keep, len(self.buf) - b)
                    if not self.after:
                        out += self.buf[:len(self.buf) - keep]
                    else:
                        self.dropped += self.buf[:len(self.buf) - keep]
                    self.buf = self.buf[len(self.buf) - keep:]
                    return out
                k, kind = min(cands)
                if not self.after:
                    out += self.buf[:k]
                else:
                    self.dropped += self.buf[:k]
                if kind == "open":
                    self.buf, self.inside = self.buf[k + len(self.OPEN):], True
                elif kind == "stray":                       # «</tool_call>» без открывающего: JSON перед ним уже
                    self.buf = self.buf[k + len(self.CLOSE):]   # разобран как голый вызов или был текстом — тег не читаем
                else:
                    self.buf, self.inside = self.buf[k:], "bare"

    def tail(self):
        """Конец потока: придержанное на случай разрезанного «<tool_call>» — оказалось обычным текстом."""
        br = self.br.tail()
        rest = self.dsml.feed(br) + self.dsml.tail() if br else self.dsml.tail()
        if rest:
            out = self.feed("")
            self.buf += rest
            out2 = self.feed("")
            if out + out2:
                return out + out2 + (self.tail() or "")
        if self.inside:
            return ""
        t, self.buf = self.buf, ""
        if self.after:                                  # текст после вызова — только если вызов так и не разобрался
            return "" if any(parse_tool_call(r) for r in self.found) else self.dropped + t
        return t

    def calls(self):
        if self.inside in (True, "bare") and self.buf.strip():   # модель не закрыла тег или JSON — берём как есть
            self.found.append(self.buf)
            self.buf, self.inside = "", False
        out = []
        for raw in self.found:
            c = parse_tool_call(raw)
            if c:
                if isinstance(c.get("args"), dict) and '"_bracket": 1' in raw:   # из скобок (№603) — engine спросит «Выполнить?»
                    c["args"].pop("_bracket", None)
                    c["bracket"] = True
                out.append(c)
            else:
                log.warning("Вызов функции в тексте не разобран: %r", raw[:300])
        return out


def _arg_value(v):
    v = v.strip()
    try:
        return json.loads(v)                            # числа, true/false, списки, объекты
    except ValueError:
        return v


_NAME_KEYS = ("name", "tool_name", "tool", "function_name")


_ARGS_KEYS = ("arguments", "args", "parameters", "params", "input", "tool_input", "action_input")


def _call_parts(obj):
    """{"name"|"tool_name"|"tool"|"function": …, "arguments"|"args"|"parameters"|"input": …} -> (имя, аргументы).
    Модели без родных функций пишут вызов кто как (Ollama с «chat»: {"tool_name": …, "arguments": …})."""
    fn = obj.get("function")
    if isinstance(fn, dict):
        return fn.get("name"), fn.get("arguments", next((obj[k] for k in _ARGS_KEYS if k in obj), {}))
    name = next((obj[k] for k in _NAME_KEYS if isinstance(obj.get(k), str) and obj[k].strip()), None) \
        or (fn if isinstance(fn, str) else None)
    return name, next((obj[k] for k in _ARGS_KEYS if k in obj), {})


class BareCallCatcher:
    """Вызов функции голым JSON без тегов: модель в режиме «функции текстом» пишет весь ответ как
    {"tool_name": "write_file", "arguments": {...}} (или ```json …```, или несколько таких подряд).
    Ответ, который начинается с «{» или «`», придерживаем до конца: если это вызовы известных функций — это действия,
    а не текст (его не озвучиваем и не считаем «рассуждением»); иначе отдаём текст как был."""

    def __init__(self, known):
        self.known, self.mode, self.buf = set(known or ()), None, ""

    def feed(self, s):
        if not self.known or self.mode == "pass":
            return s
        self.buf += s
        if self.mode is None:
            head = self.buf.lstrip()
            if not head:
                return ""
            self.mode = "hold" if head[0] in "{`" else "pass"
            if self.mode == "pass":
                out, self.buf = self.buf, ""
                return out
        return ""

    def finish(self):
        """-> (текст, вызовы)."""
        buf, self.buf = self.buf, ""
        if self.mode != "hold":
            return buf, []
        calls = self.parse(buf, self.known)
        return ("", calls) if calls else (buf, [])

    @staticmethod
    def parse(text, known):
        t = re.sub(r"```[a-zA-Z]*|</?tool_call>", " ", text).strip()
        dec, i, out = json.JSONDecoder(), 0, []
        while i < len(t):
            if t[i].isspace() or t[i] in ",;":
                i += 1
                continue
            try:
                obj, i = dec.raw_decode(t, i)
            except ValueError:
                obj = repair_json(t[i:])                 # ответ оборвался по длине посреди аргументов
                if not isinstance(obj, dict):
                    return []
                name, args = _call_parts(obj)
                if isinstance(args, dict):
                    obj = dict(obj, **{k: dict(args, _truncated=True) for k in _ARGS_KEYS if k in obj})
                i = len(t)
            for o in (obj if isinstance(obj, list) else [obj]):
                name, args = _call_parts(o) if isinstance(o, dict) else (None, None)
                if name not in known:
                    return []
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except ValueError:
                        args = {"_raw": args}
                out.append({"name": name, "args": args if isinstance(args, dict) else {}})
        return out


# путь Windows в тексте вызова: «D:\…» или «\\сервер\…» после кавычки, пробела или скобки (GitHub №29)
WIN_PATH_RX = re.compile(r"""((?:^|(?<=[\s"'(=:,\[{]))(?:[A-Za-z]:|\\\\(?=\w)))((?:\\+[^\\"\s<>|*?]+)+\\*)""")


def _loads_loose(s):
    """json.loads, а не вышло — мягче (№390, 28.10: «Вызов функции в тексте не разобран» — run_python с кодом, где модель
    написала настоящие переводы строк внутри строки и «\\'» — JSON их не принимает, задача «застряла»): переводы строк и
    табы внутри строк (strict=False), «\\'» → «'», чужие экранирования «\\в» → «\\\\в». -> объект или None."""
    try:
        return json.loads(s)
    except ValueError:
        pass
    # GitHub №29 (29.10): «D:\\Demo\\new\\test.txt» без экранирования — «\\n» и «\\t» в пути становились переводом строки и
    # табуляцией. Путь Windows (буква диска или \\\\сервер) — обратные слеши в нём буквальные: удваиваем до разбора
    s = WIN_PATH_RX.sub(lambda m: m.group(1) + re.sub(r"\\+", lambda b: "\\\\", m.group(2)), s)
    t = re.sub(r"\\(.)", lambda m: m.group(0) if m.group(1) in '"\\/bfnrtu' else ("'" if m.group(1) == "'" else "\\\\" + m.group(1)), s, flags=re.S)
    try:
        return json.loads(t, strict=False)
    except ValueError:
        return None


def parse_tool_call(raw):
    """Вызов функции из текста ответа → {"name", "args"} или None. Модели пишут его по-разному:
      Qwen/Hermes:   {"name": "f", "arguments": {...}}
      GLM-4.5/5:     f<arg_key>k</arg_key><arg_value>v</arg_value>…
      Qwen3-Coder:   <function=f><parameter=k>v</parameter>…</function>
      и просто:      f {"k": "v"}   или   f"""
    raw = (raw or "").strip()
    if not raw:
        return None
    if "<tool_call>" in raw:                           # 0.38.49: первый вызов оборван, следом второй в своём <tool_call>
        for part in reversed([x for x in raw.split("<tool_call>") if x.strip()]):
            c = parse_tool_call(part)
            if c:
                return c
        return None
    # экзамен 0.38.46 (Qwen): «<\n\nfunction=code_list>» — переводы строк внутри тега
    raw = re.sub(r"<\s*(function|parameter)\s*=\s*", r"<\1=", raw)
    raw = re.sub(r'^<\s*(function|name|tool)"\s*:', r'{"\1":', raw)       # 0.38.48: «<function": "web_search", "arguments": {…}}»
    m = re.search(r"<function=([\w.\-]+)>(.*?)(?:</function>|$)", raw, re.S)
    if m:
        args = {k: _arg_value(v) for k, v in re.findall(r"<parameter=([\w.\-]+)>(.*?)(?:</parameter>|(?=<parameter=)|$)", m.group(2), re.S)}
        if not args:                                   # <function=code_read><path>a.py</path></function> — ключи тегами
            args = {k: _arg_value(v) for k, v in re.findall(r"<([A-Za-z_][\w\-]*)>(.*?)</\1>", m.group(2), re.S)}
        return {"name": m.group(1), "args": args}
    m = re.match(r"([A-Za-z_][\w.\-]*)\s*(.*)$", raw, re.S)
    nm = re.match(r'^\{?\s*"?(?:function\s+name|function_name|name)\s*=\s*"?([A-Za-z_][\w.\-]*)"?\s*\}?\s*$', raw)
    if nm:                                             # 0.38.49: {"function name="set_reminder"} — одно имя, без аргументов
        return {"name": nm.group(1), "args": {}}
    if m and "<arg_key>" in m.group(2):
        pairs = re.findall(r"<arg_key>\s*(.*?)\s*</arg_key>\s*<arg_value>(.*?)</arg_value>", m.group(2), re.S)
        return {"name": m.group(1), "args": {k: _arg_value(v) for k, v in pairs}}
    # экзамен 14.10 (Qwen): перевод строки внутри ключа — {"\n\nname": …}; имя функции первой строкой — {"use_skill", "name": …}
    raw = re.sub(r'"\s+(name|arguments|parameters|function)"(\s*:)', r'"\1"\2', raw)
    bare = re.match(r'\{\s*"([A-Za-z_][\w.\-]*)"\s*,\s*(.*)\}\s*$', raw, re.S)
    if bare:
        try:
            rest = json.loads("{" + bare.group(2) + "}")
            if isinstance(rest, dict):
                return {"name": bare.group(1), "args": rest}
        except ValueError:
            pass
    # экзамен 0.38.46: имя отдельным объектом, аргументы — следующим: {"function": "show_images"}\n{"query": …}
    two = re.match(r'\{\s*"(?:function|name|tool|tool_name)"\s*:\s*"([A-Za-z_][\w.\-]*)"\s*\}\s*(\{.*\})', raw, re.S)
    if two:
        try:
            rest = json.loads(two.group(2))
            if isinstance(rest, dict):
                return {"name": two.group(1), "args": rest}
        except ValueError:
            pass
    j = re.search(r"\{.*\}", raw, re.S)
    obj = _loads_loose(j.group(0)) if j else None
    if isinstance(obj, dict):
        if m and j.start() > 0 and re.fullmatch(r"[A-Za-z_][\w.\-]*\s*", raw[:j.start()]):
            return {"name": m.group(1), "args": obj}       # f {"k": "v"} — имя впереди важнее ключей внутри
        name, args = _call_parts(obj)
        if name:
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"_raw": args}
            return {"name": name, "args": args if isinstance(args, dict) else {}}
        if m and j.start() > 0 and re.fullmatch(r"[A-Za-z_][\w.\-]*\s*", raw[:j.start()]):
            return {"name": m.group(1), "args": obj}       # f {"k": "v"}
    if m and re.fullmatch(r"[A-Za-z_][\w.\-]*", raw):
        return {"name": raw, "args": {}}                   # просто имя функции без аргументов
    return None


def tools_prompt(tools):
    """Описание функций для системного запроса — в формате шаблона Qwen/Hermes, который многие модели знают."""
    lines = "\n".join(json.dumps({"type": "function", "function": t}, ensure_ascii=False) for t in tools)
    return ("\n\n# Инструменты\nТы можешь вызывать функции. Их описания — внутри <tools></tools>:\n<tools>\n"
            + lines + "\n</tools>\n\nЧтобы вызвать функцию, выведи ровно так и больше ничего:\n<tool_call>\n"
            '{"name": "<имя функции>", "arguments": {<аргументы>}}\n</tool_call>\n'
            "Результат придёт в <tool_response></tool_response>. Если функция не нужна — просто отвечай.")


def repair_json(raw):
    """Оборванный по лимиту длины JSON аргументов ({"path": "a.html", "content": "<html>… — без конца) — закрываем
    строку и скобки, чтобы спасти уже написанное. -> dict или None."""
    t = (raw or "").strip()
    if not t.startswith("{"):
        return None
    stack, in_str, esc = [], False, False
    for ch in t:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    tail = t
    if in_str:
        tail = tail[:-1] if esc else tail
        tail += '"'
    tail = re.sub(r",\s*$", "", tail)
    for _ in range(3):
        try:
            d = json.loads(tail + "".join(reversed(stack)))
            return d if isinstance(d, dict) else None
        except ValueError:
            tail = re.sub(r',\s*"[^"]*"\s*:?\s*$', "", tail)     # оборвалось на имени поля — отрежем его
    return None
