#!/usr/bin/env python3
"""Словари языков -> ui/assets/i18n.data.js (window.DW_I18N) для окон студии, виджета и телефона.

    python3 tools/i18n_build.py          # собрать
    python3 tools/i18n_build.py --check  # собрано ли из нынешних словарей (tests/i18n_test.py)

Источник — data/i18n/<язык>.json (ru — исходный). Ключи в выходном файле — по алфавиту, чтобы правка одной строки
давала одну строку разницы. С 0.95 — ещё перевод по тексту: data/i18n/text/<язык>.json {"Русская строка": "перевод"}
-> ui/assets/i18n.tx.js, window.DW_TX (ui/assets/i18n.js переводит им всё, что на странице, — разметку и дорисованное
кодом). Отдельным файлом: русским он не нужен — i18n.js подгружает его, только когда язык не русский."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "i18n"
OUT = ROOT / "ui" / "assets" / "i18n.data.js"
OUT_TX = ROOT / "ui" / "assets" / "i18n.tx.js"
HEAD = ("/* Собрано tools/i18n_build.py из data/i18n/*.json — руками не править: правьте словари и соберите заново. */\n"
        "window.DW_I18N = ")


def build():
    data = {}
    for p in sorted(SRC.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        data[p.stem] = {k: d[k] for k in sorted(d)}
    tx = {}
    for p in sorted((SRC / "text").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        tx[p.stem] = {norm(k): v for k, v in sorted(d.items()) if v and norm(k)}
    return (HEAD + json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True).replace("\n", "") + ";\n",
            "/* Собрано tools/i18n_build.py из data/i18n/text/*.json — руками не править. */\n"
            + "window.DW_TX = " + json.dumps(tx, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + ";\n")


def norm(s):
    """Ключ перевода по тексту: пробелы и переносы схлопнуты (как в i18n.js)."""
    return re.sub(r"\s+", " ", s).strip()


def main():
    s, stx = build()
    if "--check" in sys.argv:
        ok = (OUT.exists() and OUT.read_text(encoding="utf-8") == s
              and OUT_TX.exists() and OUT_TX.read_text(encoding="utf-8") == stx)
        print("i18n.data.js, i18n.tx.js: " + ("собраны из нынешних словарей" if ok else "устарели — python3 tools/i18n_build.py"))
        return 0 if ok else 1
    OUT.write_text(s, encoding="utf-8")
    OUT_TX.write_text(stx, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(s)} байт, {OUT_TX.relative_to(ROOT)}: {len(stx)} байт")
    src = json.loads((SRC / "ru.json").read_text(encoding="utf-8"))
    for p in sorted(SRC.glob("*.json")):                  # сколько переведено: недостающее берётся из en, затем ru
        d = json.loads(p.read_text(encoding="utf-8"))
        have = sum(1 for k in src if k in d)
        print(f"  {p.stem}: {have} из {len(src)} строк ({have * 100 // max(1, len(src))} %) — {d.get('lang.name', '?')}")
    for p in sorted((SRC / "text").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        print(f"  по тексту, {p.stem}: {sum(1 for v in d.values() if v)} строк (что осталось — tools/i18n_texts.py {p.stem})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
