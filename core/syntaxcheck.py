"""Проверка синтаксиса файла сразу после записи (харнесс 1.0.30, по образцу Aigen: «готовность определяет программа, а не
слово модели»). Маленькая модель чаще всего ломает скобку или кавычку и узнаёт об этом в конце — теперь сразу, в ответе
того же действия, со строкой.

syntax_error(text, suffix) -> "" или «что не так, строка N». Только то, в чём уверены: лучше пропустить ошибку, чем
поднять ложную тревогу (модель начнёт «чинить» верный файл).
  .py — compile; .json — json; .html/.htm — парность блочных тегов (textedit.html_error) и встроенные <script> (JS, JSON);
  .js .mjs .cjs .ts — node --check (если есть, только .js-семейство), иначе встроенный разбор js_scan: парность скобок,
  закрытость строк, шаблонных строк и комментариев, регулярные выражения отличаются от деления по предыдущему знаку;
  .css — парность фигурных скобок и закрытость комментариев; .yaml/.yml — yaml.safe_load (если стоит PyYAML);
  .toml — tomllib; .xml/.svg — xml.etree; .sh/.bash — bash -n (если есть bash); .php — php -l (если есть php).
Внешние программы — с таймаутом 5 с; нет программы — проверка пропускается молча."""
import json
import os
import re
import shutil
import subprocess
import tempfile

_TIMEOUT = 5
_WIN = os.name == "nt"


def _tool(cmd, text, suffix):
    """Запустить проверку внешней программой на временном файле -> (код, вывод) или None (программы нет / сбой запуска)."""
    exe = shutil.which(cmd[0])
    if not exe:
        return None
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        r = subprocess.run([exe] + cmd[1:] + [path], capture_output=True, text=True, timeout=_TIMEOUT, encoding="utf-8",
                           errors="replace", stdin=subprocess.DEVNULL, **({"creationflags": 0x08000000} if _WIN else {}))
        return r.returncode, (r.stdout + "\n" + r.stderr).replace(path, "file")
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# --------------------------------------------------------------- JavaScript ---------------------------------------------------------------
_OPEN, _CLOSE = "([{", ")]}"
_PAIR = {")": "(", "]": "[", "}": "{"}
# после этих слов «/» начинает регулярное выражение, а не деление
_RX_WORDS = {"return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "throw", "case", "do", "else", "yield", "await"}


def js_scan(src):
    """Встроенный разбор JS без внешних программ. -> "" или «что не так, строка N». Сообщает только то, в чём уверен:
    незакрытая строка, шаблонная строка, комментарий или регулярное выражение; скобка без пары."""
    i, n, line = 0, len(src), 1
    stack = []                       # (скобка, строка) ; для шаблонов — ("${", строка)
    prev = ""                        # последний значимый знак или слово — решает, «/» это деление или регулярное выражение
    tmpl = []                        # глубина стека, на которой открыта подстановка ${ … } шаблонной строки
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r\f\v ﻿":
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            if j < 0:
                return f"комментарий /* из строки {line} не закрыт"
            line += src.count("\n", i, j)
            i = j + 2
            continue
        if c in "'\"":
            start, j = line, i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    if j + 1 < n and src[j + 1] == "\n":
                        line += 1
                    j += 2
                    continue
                if src[j] == "\n":
                    return f"строка в кавычках {c} из строки {start} не закрыта до конца строки"
                j += 1
            if j >= n:
                return f"строка в кавычках {c} из строки {start} не закрыта"
            i, prev = j + 1, "a"
            continue
        if c == "`" or (c == "}" and tmpl and len(stack) == tmpl[-1] and stack and stack[-1][0] == "${"):
            if c == "}":                 # конец подстановки ${ … } — продолжаем шаблонную строку
                stack.pop()
                tmpl.pop()
            start, j = line, i + 1
            while j < n:
                d = src[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "\n":
                    line += 1
                if d == "`":
                    break
                if d == "$" and j + 1 < n and src[j + 1] == "{":
                    break
                j += 1
            if j >= n:
                return f"шаблонная строка ` из строки {start} не закрыта"
            if src[j] == "`":
                i, prev = j + 1, "a"
            else:
                stack.append(("${", line))
                tmpl.append(len(stack))
                i, prev = j + 2, "("
            continue
        if c == "/":
            if prev == "" or prev in "(,=:[!&|?{};+-*%<>~^" or prev in _RX_WORDS:
                start, j, cls = line, i + 1, False
                while j < n:
                    d = src[j]
                    if d == "\\":
                        j += 2
                        continue
                    if d == "\n":
                        return f"регулярное выражение / из строки {start} не закрыто до конца строки"
                    if d == "[":
                        cls = True
                    elif d == "]":
                        cls = False
                    elif d == "/" and not cls:
                        break
                    j += 1
                if j >= n:
                    return f"регулярное выражение / из строки {start} не закрыто"
                j += 1
                while j < n and (src[j].isalpha()):
                    j += 1
                i, prev = j, "a"
                continue
            i, prev = i + 1, "/"
            continue
        if c in _OPEN:
            stack.append((c, line))
            i, prev = i + 1, c
            continue
        if c in _CLOSE:
            if not stack:
                return f"лишняя «{c}» в строке {line}"
            top, ln = stack[-1]
            if top == "${" or top != _PAIR[c]:
                want = {"(": ")", "[": "]", "{": "}", "${": "}"}[top]
                return f"«{top}» из строки {ln} закрыта «{c}» в строке {line} (ждали «{want}»)"
            stack.pop()
            i, prev = i + 1, (")" if c == ")" else "a" if c == "]" else "}")
            continue
        m = re.match(r"[A-Za-z_$\u0080-￿][\w$\u0080-￿]*", src[i:i + 64])
        if m:
            w = m.group(0)
            prev = w if w in _RX_WORDS else "a"
            i += len(w)
            continue
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            m = re.match(r"[0-9a-fA-FxXoObBn_.eE]+", src[i:i + 64])
            i += len(m.group(0)) if m else 1
            prev = "a"
            continue
        if c == "+" and i + 1 < n and src[i + 1] == "+" or c == "-" and i + 1 < n and src[i + 1] == "-":
            i, prev = i + 2, "a"     # x++ / y-- : после них «/» — деление
            continue
        prev = c
        i += 1
    if stack:
        top, ln = stack[-1]
        return f"«{'${' if top == '${' else top}» из строки {ln} не закрыта" if top != "${" else f"подстановка ${{ из строки {ln} не закрыта"
    return ""


def js_error(text, suffix=".js"):
    """JS: node --check (точнее), иначе встроенный разбор. TypeScript — только встроенный (node его не разбирает)."""
    if suffix in (".js", ".mjs", ".cjs"):
        r = _tool(["node", "--check"], text, suffix)
        if r is not None and r[0] != 0 and suffix == ".js":
            r2 = _tool(["node", "--check"], text, ".mjs")   # import/export или await наверху — модуль, а не ошибка
            if r2 is not None and r2[0] == 0:
                return ""
        if r is not None:
            code, out = r
            if code == 0:
                return ""
            m = re.search(r"file:(\d+)", out)
            msg = next((ln.strip() for ln in out.splitlines() if re.match(r"\s*(SyntaxError|ReferenceError)", ln)), "")
            if msg:                  # node отвечает не про синтаксис (нет node_modules и т. п.) — не наше дело
                return (f"строка {m.group(1)}: " if m else "") + msg[:160]
            return ""
    return js_scan(text)


# --------------------------------------------------------------- остальное ---------------------------------------------------------------
def _html_scripts(text):
    """Встроенные <script> страницы: JS — разбор, JSON — json; строка — в координатах файла. Шаблоны пропускаем."""
    for m in re.finditer(r"(?is)<script\b([^>]*)>(.*?)</script>", text):
        attrs, body = m.group(1).lower(), m.group(2)
        if not body.strip() or re.search(r"\bsrc\s*=", attrs):
            continue
        typ = (re.search(r"\btype\s*=\s*[\"']?([^\"'\s>]+)", attrs) or [None, ""])[1]
        base = text.count("\n", 0, m.start(2))
        if typ in ("application/json", "application/ld+json", "importmap"):
            try:
                json.loads(body)
            except ValueError as e:
                return f"JSON в <script> (строка {base + 1}): {e}"
            continue
        if typ and typ not in ("text/javascript", "module", "application/javascript", "text/babel") or "{{" in body or "{%" in body or "<?" in body:
            continue
        bad = js_scan(body)
        if bad:
            return "в <script>: " + re.sub(r"(строк\w*) (\d+)", lambda x: f"{x.group(1)} {int(x.group(2)) + base}", bad)
    return ""


def css_error(text):
    """CSS: незакрытый комментарий, фигурная скобка без пары (строки в кавычках пропускаем)."""
    i, n, line, stack = 0, len(text), 1, []
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
        elif c == "/" and text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                return f"комментарий /* из строки {line} не закрыт"
            line += text.count("\n", i, j)
            i = j + 2
            continue
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        elif c == "{":
            stack.append(line)
        elif c == "}":
            if not stack:
                return f"лишняя «}}» в строке {line}"
            stack.pop()
        i += 1
    return f"«{{» из строки {stack[-1]} не закрыта" if stack else ""


def syntax_error(text, suffix):
    """Синтаксис файла по расширению. -> "" или «что не так» (со строкой)."""
    suffix = (suffix or "").lower()
    text = text or ""
    try:
        if suffix in (".py", ".pyw"):
            compile(text, "file", "exec")
        elif suffix == ".json":
            json.loads(text)
        elif suffix in (".html", ".htm"):
            from textedit import html_error
            return html_error(text) or _html_scripts(text)
        elif suffix in (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"):
            if suffix in (".tsx", ".jsx"):
                return ""           # JSX/TSX — разметка внутри кода, встроенный разбор её не понимает
            return js_error(text, suffix)
        elif suffix == ".css":
            return css_error(text)
        elif suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError:
                return ""
            try:
                list(yaml.safe_load_all(text))
            except yaml.YAMLError as e:
                mark = getattr(e, "problem_mark", None)
                return (f"YAML, строка {mark.line + 1}: " if mark else "YAML: ") + str(getattr(e, "problem", "") or e)[:160]
        elif suffix == ".toml":
            try:
                import tomllib
            except ImportError:
                return ""
            try:
                tomllib.loads(text)
            except tomllib.TOMLDecodeError as e:
                return f"TOML: {e}"
        elif suffix in (".xml", ".svg"):
            import xml.etree.ElementTree as ET
            try:
                ET.fromstring(text.encode("utf-8"))
            except ET.ParseError as e:
                return f"XML, строка {e.position[0]}: {str(e).split(':')[0]}"
        elif suffix in (".sh", ".bash"):
            r = None if _WIN else _tool(["bash", "-n"], text, suffix)
            if r and r[0] != 0:
                ln = next((x for x in r[1].splitlines() if x.strip()), "")
                return re.sub(r"^file:\s*", "", ln.strip())[:200]
        elif suffix == ".php":
            r = _tool(["php", "-l"], text, suffix)
            if r and r[0] != 0:
                ln = next((x for x in r[1].splitlines() if "error" in x.lower()), "")
                return re.sub(r"\s+in file", "", ln.strip())[:200]
    except SyntaxError as e:
        return f"SyntaxError, строка {e.lineno}: {e.msg}" + (f": {e.text.strip()[:120]}" if e.text else "")
    except ValueError as e:
        return f"JSON не разбирается: {e}"
    except RecursionError:
        return ""
    return ""
