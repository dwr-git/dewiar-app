#!/usr/bin/env python3
"""Храповик языков (0.88): сколько в интерфейсах осталось русского текста МИМО словарей — по каждому файлу. Число может
только уменьшаться: новый текст пишется ключом (t("…") в коде, data-i18n в разметке), старый переводится постепенно.

    python3 tools/i18n_ratchet.py            # таблица: файл — сейчас / предел
    python3 tools/i18n_ratchet.py --update   # опустить пределы до нынешних (после перевода части строк)

Пределы — tests/i18n_baseline.json; проверка — tests/i18n_test.py. Считается: строка в кавычках с кириллицей в .js
(комментарии не в счёт), в .html — текст и title/placeholder/aria-label/alt с кириллицей без data-i18n…, плюс строки
встроенных <script>. Комментарии программистам остаются русскими (владелец 11.11)."""
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "tests" / "i18n_baseline.json"
CYR = re.compile(r"[А-Яа-яЁё]")
GLOBS = ["ui/*.html", "ui/studio/*.js", "ui/assets/*.js", "android/assets/www/*.js", "android/assets/www/*.html"]
SKIP = {"ui/assets/i18n.data.js",
        "ui/assets/speechnorm.js", "android/assets/www/exam.js"}   # русская речь и фразы экзамена — не интерфейс
REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^")


def js_strings(src):
    """Строковые литералы JS (без комментариев и регулярных выражений) -> список строк. Грубый, но устойчивый разбор."""
    out, i, n, last = [], 0, len(src), ""
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and (last in REGEX_BEFORE or last == ""):
            j, cls = i + 1, False                       # регулярное выражение: пропускаем до закрывающего /
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    cls = True
                elif src[j] == "]":
                    cls = False
                elif src[j] == "/" and not cls:
                    break
                j += 1
            i, last = j + 1, "x"
            continue
        if c in "'\"`":
            j, buf = i + 1, []
            while j < n and src[j] != c:
                if src[j] == "\\":
                    buf.append(src[j:j + 2])
                    j += 2
                    continue
                if c != "`" and src[j] == "\n":
                    break
                buf.append(src[j])
                j += 1
            out.append("".join(buf))
            i, last = j + 1, "x"
            continue
        if not c.isspace():
            last = c if c in REGEX_BEFORE else "x"
            if c.isalnum() or c == "_":                   # слово: return/typeof перед / — значит регулярка
                m = re.match(r"[A-Za-z_$][\w$]*", src[i:])
                if m:
                    last = "(" if m.group(0) in ("return", "typeof", "case", "in", "of") else "x"
                    i += len(m.group(0))
                    continue
        i += 1
    return out


class _Html(HTMLParser):
    ATTRS = ("title", "placeholder", "aria-label", "alt")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.count, self.script = [], 0, []
        self._in = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in self.ATTRS:
            if k in a and CYR.search(a[k] or "") and f"data-i18n-{k}" not in a:
                self.count += 1
        if tag in ("script", "style"):
            self._in = tag
        if tag not in ("br", "img", "input", "meta", "link", "hr", "source", "wbr", "area", "base", "col", "embed", "param", "track"):
            self.stack.append("data-i18n" in a)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._in = None
        if self.stack and tag not in ("br", "img", "input", "meta", "link", "hr", "source", "wbr"):
            self.stack.pop()

    def handle_data(self, data):
        if self._in == "script":
            self.script.append(data)
            return
        if self._in == "style":
            return
        if CYR.search(data) and not (self.stack and self.stack[-1]):
            self.count += 1


def count(path):
    src = Path(path).read_text(encoding="utf-8", errors="replace")
    if str(path).endswith(".html"):
        p = _Html()
        p.feed(src)
        return p.count + sum(1 for s in js_strings("\n".join(p.script)) if CYR.search(s))
    return sum(1 for s in js_strings(src) if CYR.search(s))


def files():
    out = []
    for g in GLOBS:
        out += [p for p in sorted(ROOT.glob(g)) if p.relative_to(ROOT).as_posix() not in SKIP]
    return out


def current():
    return {p.relative_to(ROOT).as_posix(): count(p) for p in files()}


def main():
    now = current()
    base = json.loads(BASE.read_text(encoding="utf-8")) if BASE.exists() else {}
    if "--update" in sys.argv or not base:
        new = {k: min(v, base.get(k, v)) if base else v for k, v in now.items()}
        BASE.write_text(json.dumps(new, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"пределы записаны: {sum(new.values())} строк в {len(new)} файлах")
        return 0
    bad = 0
    for k, v in sorted(now.items()):
        lim = base.get(k, 0)
        mark = "ПРЕВЫШЕН" if v > lim else ""
        bad += v > lim
        if v or lim:
            print(f"{k}: {v} / {lim} {mark}")
    print(f"всего: {sum(now.values())} (пределы {sum(base.values())})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
