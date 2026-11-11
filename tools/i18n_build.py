#!/usr/bin/env python3
"""Словари языков -> ui/assets/i18n.data.js (window.DW_I18N) для окон студии, виджета и телефона.

    python3 tools/i18n_build.py          # собрать
    python3 tools/i18n_build.py --check  # собрано ли из нынешних словарей (tests/i18n_test.py)

Источник — data/i18n/<язык>.json (ru — исходный). Ключи в выходном файле — по алфавиту, чтобы правка одной строки
давала одну строку разницы."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "i18n"
OUT = ROOT / "ui" / "assets" / "i18n.data.js"
HEAD = ("/* Собрано tools/i18n_build.py из data/i18n/*.json — руками не править: правьте словари и соберите заново. */\n"
        "window.DW_I18N = ")


def build():
    data = {}
    for p in sorted(SRC.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        data[p.stem] = {k: d[k] for k in sorted(d)}
    return HEAD + json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True).replace("\n", "") + ";\n"


def main():
    s = build()
    if "--check" in sys.argv:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == s
        print("i18n.data.js: " + ("собран из нынешних словарей" if ok else "устарел — python3 tools/i18n_build.py"))
        return 0 if ok else 1
    OUT.write_text(s, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(s)} байт")
    src = json.loads((SRC / "ru.json").read_text(encoding="utf-8"))
    for p in sorted(SRC.glob("*.json")):                  # сколько переведено: недостающее берётся из en, затем ru
        d = json.loads(p.read_text(encoding="utf-8"))
        have = sum(1 for k in src if k in d)
        print(f"  {p.stem}: {have} из {len(src)} строк ({have * 100 // max(1, len(src))} %) — {d.get('lang.name', '?')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
