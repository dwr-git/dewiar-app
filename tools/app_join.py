"""Телефон по частям (чистое ядро, 1.0.18 — docs/CORE_PLAN.md): исходник интерфейса телефона и веб-версии лежит частями
в android/www-src/app/NN-имя.js, а android/assets/www/app.js собирается из них склейкой — слово в слово, тем же одним
файлом. Так у людей ничего не меняется: один <script>, тот же порядок исполнения (при разрезе на несколько <script>
обещания и продолжения await, запущенные при загрузке, выполнялись бы между частями — раньше, чем загрузятся следующие).

Часть = шапка (строки «//@ …» в начале: что в ней) + текст как был. Править — части, затем:
    python3 tools/app_join.py            собрать app.js
    python3 tools/app_join.py --check    app.js совпадает со склейкой частей? (tests/app_parts_test.py)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = ROOT / "android/www-src/app"
OUT = ROOT / "android/assets/www/app.js"
HEAD = ("/* app.js СОБРАН из частей android/www-src/app/*.js (tools/app_join.py) — править части, не этот файл; "
        "склейку проверяет tests/app_parts_test.py. */\n")


def body(text):
    """Текст части без шапки «//@ …»."""
    lines = text.splitlines(keepends=True)
    k = 0
    while k < len(lines) and lines[k].startswith("//@"):
        k += 1
    return "".join(lines[k:])


def parts():
    return sorted(PARTS.glob("[0-9][0-9]-*.js"))


def joined():
    return HEAD + "".join(body(p.read_text(encoding="utf-8")) for p in parts())


def main():
    want = joined()
    if "--check" in sys.argv:
        have = OUT.read_text(encoding="utf-8")
        if have != want:
            print("app.js не совпадает со склейкой частей android/www-src/app — правили app.js напрямую? Перенесите правку в "
                  "часть и соберите: python3 tools/app_join.py")
            sys.exit(1)
        print(f"app.js = склейка {len(parts())} частей")
        return
    OUT.write_text(want, encoding="utf-8")
    print(f"app.js собран из {len(parts())} частей: {want.count(chr(10))} строк")


if __name__ == "__main__":
    main()
