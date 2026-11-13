#!/usr/bin/env python3
"""Перевод по тексту (0.95): что из интерфейса ещё не переведено и как добавить перевод.

    python3 tools/i18n_texts.py en                        # сколько осталось, по файлам
    python3 tools/i18n_texts.py en --file hud.html --out todo.json   # недостающее одного файла -> {"Русский": ""}
    python3 tools/i18n_texts.py en --merge done.json      # перевод (тот же вид, заполненный) -> data/i18n/text/en.json

Строки — те же, что считает храповик (tools/i18n_ratchet.py): текст разметки, title/placeholder/aria-label/alt и литералы
кода; литерал режется по тегам на куски, ${…} — «{1}», «{2}» (в переводе подстановки можно переставить). Перевод
пишется в data/i18n/text/<язык>.json, окна получают его через ui/assets/i18n.data.js (python3 tools/i18n_build.py).
Без --phone — компьютер (студия, виджет, окна); с --phone — только телефон (android/assets/www); с --data — тексты из
данных, которые показывают окна: «Что я умею» (data/tricks.json), руководство (data/guide.json), плагины Dewiar
(data/plugins/*/plugin.json — без подсказок модели: task, words, skills)."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import i18n_ratchet as R  # noqa: E402

ROOT = R.ROOT
TEXT = ROOT / "data" / "i18n" / "text"
CODE = re.compile(r"=>|\bfunction\b|\$\(|core\.call|\.forEach\(|;\s*\}")   # кусок кода, который разбор принял за строку


class _Pieces(R._Html):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for k in self.ATTRS:
            if k in a and R.CYR.search(a[k] or "") and f"data-i18n-{k}" not in a:
                self.found += R.pieces(a[k], js=False)
        super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._in == "script":
            self.script.append(data)
            return
        if self._in == "style":
            return
        if R.CYR.search(data) and not (self.stack and self.stack[-1]):
            self.found += R.pieces(data, js=False)


def file_pieces(p):
    src = p.read_text(encoding="utf-8", errors="replace")
    out = []
    if p.suffix == ".html":
        h = _Pieces()
        h.feed(src)
        out += h.found
        lits = R.js_strings("\n".join(h.script))
    else:
        lits = R.js_strings(src)
    for s in lits:
        if R.CYR.search(s):
            out += R.pieces(s)
    return out


SKIP_KEYS = {"id", "about", "where", "quick", "task", "words", "uses", "skills", "key", "type", "icon", "color", "version",
             "author", "kw", "keywords", "match", "prompt", "default", "value", "go", "open", "video", "poster", "img"}


def data_pieces():
    """Строки данных, которые окна показывают как есть (руководство, «Что я умею», плагины)."""
    out = []

    def walk(v, key=""):
        if key in SKIP_KEYS:
            return
        if isinstance(v, str):
            if R.CYR.search(v):
                out.extend(R.pieces(v, js=False))
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(x, k)
    files = [ROOT / "data/tricks.json", ROOT / "data/guide.json"] + sorted((ROOT / "data/plugins").glob("*/plugin.json"))
    for f in files:
        try:
            walk(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    try:                                                     # «Что нового» — последние выпуски
        walk([{k: e.get(k) for k in ("items",)} for e in json.loads((ROOT / "data/whatsnew.json").read_text(encoding="utf-8"))[:6]])
    except (OSError, ValueError):
        pass
    walk(sites_meta())
    return out


def sites_meta():
    """Подписи редактора сайтов (то же, что ядро отдаёт студии в sites_meta: шаблоны, палитры, шрифты, стили, разделы)."""
    sys.path.insert(0, str(ROOT / "core"))
    try:
        import sites_kit as K
    except Exception:  # noqa: BLE001
        return {}
    return {"templates": [{"title": K.TEMPLATES[k]["title"], "sub": K.TEMPLATES[k]["sub"]} for k in K.TEMPLATE_ORDER],
            "palettes": [v["title"] for v in K.PALETTES.values()],
            "fonts": [{"title": v["title"], "sub": v["sub"]} for v in K.FONTS.values()],
            "styles": [{"title": v["title"], "sub": v["sub"]} for v in K.STYLES.values()],
            "radii": [v["title"] for v in K.RADII.values()], "menus": K.MENUS, "headers": K.HEADERS, "tones": K.TONES,
            "marks": [v[0] for v in K.MARKS.values()], "logo_styles": K.LOGO_STYLES,
            "legal": {"fields": K.LEGAL_FIELDS, "docs": K.LEGAL_DOCS},
            "blocks": [{"title": v["title"], "sub": v["sub"], "variants": v["variants"], "fields": v["fields"],
                        "items": v.get("items")} for v in K.BLOCKS.values()]}


def todo(lang, phone=False, only="", data=False):
    have = json.loads((TEXT / f"{lang}.json").read_text(encoding="utf-8")) if (TEXT / f"{lang}.json").exists() else {}
    have = {R.norm(k) for k, v in have.items() if v}
    per = {}
    if data:
        miss = [s for s in data_pieces() if s not in have]
        return {"data": miss} if miss else {}
    for p in R.files():
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("android/") != phone or (only and only not in rel):
            continue
        miss = [s for s in file_pieces(p) if s not in have and not CODE.search(s)]
        if miss:
            per[rel] = miss
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lang")
    ap.add_argument("--file", default="")
    ap.add_argument("--phone", action="store_true")
    ap.add_argument("--data", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--merge")
    a = ap.parse_args()
    path = TEXT / f"{a.lang}.json"
    if a.merge:
        cur = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        new = json.loads(Path(a.merge).read_text(encoding="utf-8"))
        bad = [k for k, v in new.items() if v and sorted(re.findall(r"\{\d\}", k)) != sorted(re.findall(r"\{\d\}", v))]
        if bad:
            print("подстановки {1}… в переводе не совпадают с исходной строкой:", bad[:5])
            return 1
        n = 0
        for k, v in new.items():
            if v and v.strip():
                cur[R.norm(k)] = v.strip()
                n += 1
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(sorted(cur.items())), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"{path.relative_to(ROOT)}: +{n}, всего {len(cur)}")
        return 0
    per = todo(a.lang, a.phone, a.file, a.data)
    if a.out:
        seen = {}
        for rel, miss in per.items():
            for s in miss:
                seen.setdefault(s, "")
        Path(a.out).write_text(json.dumps(seen, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"{a.out}: {len(seen)} строк")
        return 0
    total = set()
    for rel, miss in sorted(per.items(), key=lambda kv: -len(set(kv[1]))):
        print(f"{rel}: {len(set(miss))}")
        total |= set(miss)
    print(f"осталось: {len(total)} разных строк")
    return 0


if __name__ == "__main__":
    sys.exit(main())
