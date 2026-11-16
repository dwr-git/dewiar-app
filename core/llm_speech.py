"""Текст для озвучки (llm.py): поток — на фразы (SentenceSplitter), код и разметку — не читать вслух (CodeFilter,
speakable)."""

import re


_SENT_END = re.compile(r"([.!?…]+[»\")]?)(\s+)")


class SentenceSplitter:
    """Режет поток текста на фразы для озвучки. Законченное предложение (знак конца и пробел за ним) отдаёт сразу,
    даже короткое («Да.»); первую фразу без знака конца — как можно раньше (можно по запятой, после 60 символов),
    чтобы голос зазвучал через доли секунды; дальше режет по запятой только очень длинные (220+). Кусок без букв
    («1.» в нумерованном списке) концом предложения не считается — ждёт продолжения."""

    def __init__(self):
        self.buf = ""
        self.first = True

    def feed(self, s):
        self.buf += s
        out = []
        while True:
            # ищем первый конец предложения, перед которым есть буквы: search() на одном и том же коротком
            # совпадении в начале буфера останавливал бы деление на фразы до конца ответа
            m = next((m for m in _SENT_END.finditer(self.buf) if re.search(r"[^\W\d_]", self.buf[:m.start()])), None)
            if m:
                out.append(self.buf[:m.end(1)].strip())
                self.buf = self.buf[m.end():]
                self.first = False
                continue
            nl = self.buf.find("\n")
            if nl >= 0:
                piece = self.buf[:nl].strip()
                self.buf = self.buf[nl + 1:]
                if piece:
                    out.append(piece)
                    self.first = False
                continue
            limit = 60 if self.first else 220
            if len(self.buf) > limit:
                cut = max(self.buf.rfind(", ", 0, limit + 40), self.buf.rfind(" — ", 0, limit + 40))
                if cut > 25:
                    out.append(self.buf[:cut + 1].strip())
                    self.buf = self.buf[cut + 2:]
                    self.first = False
                    continue
            break
        return [x for x in out if x]

    def flush(self):
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []


class CodeFilter:
    """Код вслух не читаем: блоки ```…``` и строки-команды (sudo …, $ …, >>> …) заменяем фразой NOTE —
    один раз за ответ. Работает на потоке, до деления на фразы; обычный текст проходит без задержки,
    придерживается только начало строки, пока не ясно, команда ли это."""

    NOTE = "Команды и код — на экране. "
    _CMD = re.compile(r"^\s*(\$ |sudo |>>> |#!/)")
    # строка разметки: <div…, </p>, <!DOCTYPE — не вслух; строчные теги в начале фразы (<b>, <i>, <a>) — текст, теги снимет speakable
    _TAG = re.compile(r"^\s*<(?:[!?]|/?(?!(?:b|i|u|s|em|strong|a|span|br|mark|small|sup|sub|code)\b)[A-Za-z])")
    _HTML_ON = re.compile(r"^\s*<(?:!doctype|html|style|script|head|body)\b", re.I)
    _HTML_OFF = re.compile(r"</(?:html|style|script|head|body)\s*>\s*$", re.I)
    _ACTS = ("[в этом ответе выполнено", "[узнано инструментами")   # пометки истории (engine_answer.team_window)

    def __init__(self):
        self.pend, self.code, self.told, self.skip, self.start = "", False, False, False, True
        self.want, self.lang = False, ""                 # открыли ```: язык ещё читается; схема (mermaid) — молча
        self.html = False                                # внутри HTML-документа или <style>/<script> — молчим до закрытия

    def _note(self):
        if self.told:
            return ""
        self.told = True
        return self.NOTE

    def feed(self, s):
        out = ""
        for ch in s:
            if self.start:                                # начало строки: решаем, код это или текст
                self.pend += ch
                lead = self.pend.lstrip(" \t")
                if ch == "\n":
                    if not self.code and not self.skip:
                        out += self.pend
                    self.pend, self.skip = "", False
                    continue
                if lead.startswith("```"):
                    self.code, self.start, self.skip, self.pend = not self.code, False, True, ""
                    if self.code:
                        self.want, self.lang = True, ""   # «Команды и код — на экране» — когда станет ясен язык блока
                    continue
                if self.code:
                    if len(lead) >= 3 or (lead and not "```".startswith(lead)):
                        self.start, self.skip, self.pend = False, True, ""
                    continue
                if lead.startswith(self._ACTS):           # пометка истории «[в этом ответе выполнено…]» — вслух не читаем
                    self.start, self.skip, self.pend = False, True, ""
                    continue
                if lead and ("```".startswith(lead) or "$ ".startswith(lead) or "sudo ".startswith(lead)
                             or ">>> ".startswith(lead) or "#!/".startswith(lead) or any(a.startswith(lead) for a in self._ACTS)):
                    continue                              # ещё не ясно — ждём пару символов
                if self._CMD.match(self.pend):
                    out += self._note()
                    self.start, self.skip, self.pend = False, True, ""
                    continue
                if re.match(r"<[!/?]?[A-Za-z]{0,10}$", lead):
                    continue                              # «<», «<di», «</bo» — тег это или «< 5»: ждём конца имени
                if self.html or self._TAG.match(self.pend):   # разметка — вся строка мимо голоса
                    out += self._note()
                    self.line, self.start, self.skip, self.pend = self.pend, False, True, ""
                    continue
                if lead:
                    out += self.pend
                    self.pend, self.start = "", False
                continue
            if ch == "\n":
                ln = getattr(self, "line", "")
                if self._HTML_ON.match(ln):
                    self.html = True                      # <!DOCTYPE, <html, <style, <script — молчим до закрытия
                if self.html and self._HTML_OFF.search(ln):
                    self.html = False                     # </html>, </style>, </script> — дальше снова обычный текст
                self.line = ""
                if self.want:
                    out += self._lang_note()
                if not self.skip and not self.code:
                    out += ch
                self.start, self.skip = True, False
                continue
            if not self.skip and not self.code:
                out += ch
            elif self.want:
                self.lang += ch
            elif self.skip:
                self.line = getattr(self, "line", "") + ch
        return out

    def _lang_note(self):
        """Строка открытия блока прочитана: схема (```mermaid) — на экране картинкой, о ней молчим; код — одна фраза."""
        self.want = False
        return "" if self.lang.strip().lower() == "mermaid" else self._note()

    def flush(self):
        p, self.pend = self.pend, ""
        return "" if self.code or self.skip or self._CMD.match(p) or p.lstrip().startswith("```") else p


# вслух не читаем то, что на слух бессмысленно: ссылки, пути к файлам (outputs/news.html), расширения файлов; сокращения —
# полными словами (иначе голос читает «т ч», «т е»). «км/ч», «и/или», «6/10» и имена сайтов (dewiar.pro) остаются.
_FILE_EXT = r"(?:html?|pdf|pptx?|docx?|xlsx?|csv|json|md|txt|py|js|css|zip|png|jpe?g|svg|mp3|wav|mp4)"


_SPEAK = [(r"(?:https?://|www\.)\S+", ""),
          (r"(?<![\w.])(?:[~/]?[\w.-]+/)+[\w-]+\." + _FILE_EXT + r"\b", ""),
          (r"(?<![\w.])(?:/?[A-Za-z0-9_.~-]+/){2,}[A-Za-z0-9_.-]*", ""),
          (r"(?<![\w.])([\w-]+)\." + _FILE_EXT + r"\b", r"\1"),
          (r"\bв т\.\s?ч\.", "в том числе"), (r"\bт\.\s?е\.", "то есть"), (r"\bи т\.\s?д\.", "и так далее"),
          (r"\bи т\.\s?п\.", "и тому подобное"), (r"\bт\.\s?к\.", "так как"), (r"\bнапр\.", "например"),
          (r":\s*[—–-]\s+", ": "),                                         # «Файл: — …» после вырезанного пути
          (r"\s+(?:и|или|в|на|по|из)\s*(?=[.,;:!?]|$)", ""),                # «… в report и .»
          (r"\s+([:,;—–-])\s*(?=[:,;.!?—–]|$)", ""), (r"\(\s*\)", "")]


_MD = [(re.compile(r"```.*?```", re.S), " "), (re.compile(r"`([^`]*)`"), r"\1"),
       (re.compile(r"<(script|style)\b.*?</\1\s*>", re.S | re.I), " "),          # HTML вслух не читаем (28.10: «зачитывала
       (re.compile(r"<!--.*?-->|<!doctype[^>]*>|</?[A-Za-z][\w:-]*(?:\s[^<>]*)?/?>", re.S | re.I), " "),   # все теги»)
       (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"), *[(re.compile(a, re.I), b) for a, b in _SPEAK],
       (re.compile(r"[*_#>|~]+"), ""), (re.compile(r"^\s*[-•]\s+", re.M), ""),
       (re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]"), ""), (re.compile(r"\s+"), " ")]


def speakable(text):
    """Текст для голоса: без разметки Markdown, кода, эмодзи, ссылок и путей к файлам; сокращения — полными словами."""
    for rx, rep in _MD:
        text = rx.sub(rep, text)
    return text.strip()
