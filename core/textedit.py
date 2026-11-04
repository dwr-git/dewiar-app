"""Правка текста куском — общее для кода (codework.CodeWork.edit) и задач (tasks: file_edit). Выпуск 2 «Больших задач»
(docs/HARNESS.md): старый кусок → новый; не нашёлся точно — неточный поиск без учёта отступов и пробелов (fuzzy_find,
только если совпадение одно) с переносом отступов (reindent); несколько совпадений — «встречается N раз, строки …»; не
нашёлся совсем — самый похожий кусок с номерами строк (nearest). После правки — проверка синтаксиса (.py, .json, .html)."""
import difflib
import re


class EditError(ValueError):
    """Правка не применена: текст — «что случилось — как исправить»."""


def _norm_line(ln):
    return " ".join(ln.split())


def fuzzy_find(text, old):
    """Найти old в text, не глядя на отступы и пробелы внутри строк. -> (начало, конец, строки файла) или None.
    Только если совпадение одно."""
    want = [_norm_line(x) for x in old.strip("\n").split("\n")]
    while want and not want[-1]:
        want.pop()
    if not want or not any(want):
        return None
    lines = text.split("\n")
    hits = []
    for i in range(len(lines) - len(want) + 1):
        if all(_norm_line(lines[i + k]) == want[k] for k in range(len(want))):
            hits.append(i)
            if len(hits) > 1:
                return None
    if not hits:
        return None
    i = hits[0]
    start = sum(len(x) + 1 for x in lines[:i])
    end = start + sum(len(x) + 1 for x in lines[i:i + len(want)]) - 1
    return start, end, lines[i:i + len(want)]


def reindent(old, file_lines, new):
    """Отступы new — как в файле: строки new сопоставляются со строками old (difflib), и каждая берёт отступ своей
    строки файла плюс свою разницу с old; вставленные — от предыдущей строки. Так правка с «плоскими» отступами
    модели ложится в файл с правильной вложенностью."""
    ind = lambda x: len(x) - len(x.lstrip())                       # noqa: E731
    old_l = old.strip("\n").split("\n")
    while old_l and not old_l[-1].strip():
        old_l.pop()
    new_l = new.strip("\n").split("\n")
    sm = difflib.SequenceMatcher(None, [_norm_line(x) for x in old_l], [_norm_line(x) for x in new_l], autojunk=False)
    pair = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("equal", "replace"):
            for k in range(min(i2 - i1, j2 - j1)):
                pair[j1 + k] = i1 + k
    out, prev = [], None
    for j, ln in enumerate(new_l):
        if not ln.strip():
            out.append("")
            continue
        if j in pair and pair[j] < len(file_lines):
            i = pair[j]
            d = ind(file_lines[i]) + ind(ln) - ind(old_l[i])
        elif prev:
            d = prev[1] + ind(ln) - prev[0]
        else:
            d = ind(file_lines[0]) + ind(ln) - ind(old_l[0])
        d = max(0, d)
        out.append(" " * d + ln.lstrip())
        prev = (ind(ln), d)
    return "\n".join(out)


def nearest(text, old, reread="code_read"):
    """Подсказка: самый похожий кусок файла с номерами строк (когда фрагмент не нашёлся)."""
    want = old.strip("\n").split("\n")
    lines = text.split("\n")
    if not lines or not want:
        return ""
    n = len(want)
    best, at = 0.0, 0
    key = "\n".join(_norm_line(x) for x in want)
    for i in range(0, max(1, len(lines) - n + 1)):
        r = difflib.SequenceMatcher(None, key, "\n".join(_norm_line(x) for x in lines[i:i + n])).quick_ratio()
        if r > best:
            best, at = r, i
    if best < 0.5:
        return f" Похожего куска нет — прочитай файл ({reread}) заново."
    body = "\n".join(f"{j + 1:5d}  {lines[j]}" for j in range(at, min(len(lines), at + n)))
    return f" Самый похожий кусок (строки {at + 1}–{at + n}):\n{body}"


def lines_of(text, old):
    """Номера строк, где начинается каждое вхождение old."""
    return [text[:m.start()].count("\n") + 1 for m in re.finditer(re.escape(old), text)]


def apply_edit(text, old, new, replace_all=False, reread="file_read"):
    """Заменить old на new в text. -> (новый текст, строка начала, пометка). Нельзя однозначно — EditError с советом."""
    if not old:
        raise EditError("old пустой. Как исправить: укажи кусок, который заменить (для нового файла — write_file).")
    n = text.count(old)
    if n > 1 and not replace_all:
        at = lines_of(text, old)
        raise EditError(f"кусок встречается {n} раз (строки {', '.join(map(str, at[:10]))}{'…' if n > 10 else ''}). Как исправить: "
                        "добавь в old соседние строки, чтобы кусок был единственным, или replace_all=true — заменить все.")
    note = ""
    if n == 0:                                         # слабые модели путают отступы и пробелы в конце строк — ищем мягче
        span = fuzzy_find(text, old)
        if span is None:
            raise EditError("кусок не найден. Как исправить: скопируй его из файла точно (с отступами), перечитав "
                            f"нужные строки ({reread})." + nearest(text, old, reread))
        a_, b_, file_lines = span
        new = reindent(old, file_lines, new)
        # рецензия 0.83: заменять именно найденное место, а не первое вхождение того же текста (оно могло быть в
        # комментарии выше — «# пример:     return x»)
        return text[:a_] + new + text[b_:], text[:a_].count("\n") + 1, " (кусок найден без учёта отступов и пробелов — проверь результат)"
    line = text.find(old)
    line = text[:line].count("\n") + 1
    out = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    if replace_all and n > 1:
        note += f" (заменено вхождений: {n})"
    return out, line, note


def syntax_error(text, suffix):
    """Синтаксис файла по расширению: .py, .json, .html. -> "" или «что не так» (строка и причина)."""
    suffix = (suffix or "").lower()
    try:
        if suffix == ".py":
            compile(text, "file", "exec")
        elif suffix == ".json":
            import json
            json.loads(text)
        elif suffix in (".html", ".htm"):
            return html_error(text)
    except SyntaxError as e:
        return f"SyntaxError, строка {e.lineno}: {e.msg}" + (f": {e.text.strip()[:120]}" if e.text else "")
    except ValueError as e:
        return f"JSON не разбирается: {e}"
    return ""


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "param", "keygen"}
CHECKED = {"html", "head", "body", "div", "section", "main", "header", "footer", "nav", "ul", "ol", "table", "script", "style",
           "article", "aside", "form", "select", "svg"}


def html_error(text):
    """HTML: незакрытые или лишние закрывающие теги среди блочных (div, section, script, style…). -> "" или описание."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.bad = [], ""

        def handle_starttag(self, tag, attrs):
            if tag in CHECKED and tag not in VOID:
                self.stack.append((tag, self.getpos()[0]))

        def handle_endtag(self, tag):
            if tag not in CHECKED or self.bad:
                return
            if not any(t == tag for t, _ in self.stack):
                self.bad = f"лишний </{tag}> в строке {self.getpos()[0]}"
                return
            while self.stack:
                t, ln = self.stack.pop()
                if t == tag:
                    break
                self.bad = f"<{t}> из строки {ln} не закрыт до </{tag}> в строке {self.getpos()[0]}"
                return
    p = P()
    try:
        p.feed(text)
        p.close()
    except Exception as e:  # noqa: BLE001
        return f"HTML не разбирается: {e}"
    if p.bad:
        return p.bad
    if p.stack:
        t, ln = p.stack[-1]
        return f"<{t}> из строки {ln} не закрыт"
    return ""
