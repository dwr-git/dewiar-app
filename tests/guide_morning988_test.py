"""№988 (23.11, телефон): «Не могу найти „утренний обзор“ новостей… Ассистент посылает то в „дела“, то в „настройки“ —
„ещё“». В руководстве не было, где он на телефоне: «Настройки» → «Слух и голос» → «Сам замечает, что вы вернулись».
Теперь — есть, и поиск руководства телефона (app_help) находит его по словам человека."""
import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    c or fails.append(m)


src = (ROOT / "android/www-src/app/19-close.js").read_text(encoding="utf-8")
i = src.index("function guideFind("); j = src.index("\n}\n", i) + 3
js = "const window = { DEWIAR_GUIDE: " + (ROOT / "data/guide.json").read_text(encoding="utf-8") + " };\n" + src[i:j] + \
     "\nconsole.log(JSON.stringify(guideFind('Где утренний обзор новостей, я его отключил').map(s => s.id)));"
import tempfile
jf = Path(tempfile.mkdtemp()) / "g.js"; jf.write_text(js, encoding="utf-8")
r = subprocess.run(["node", str(jf)], capture_output=True, text=True, timeout=30)
ids = json.loads(r.stdout or "[]") if r.returncode == 0 else r.stderr[:300]
g = {s["id"]: s for s in json.loads((ROOT / "data/guide.json").read_text(encoding="utf-8"))}
ok("phone-basics" in ids and any("Сам замечает, что вы вернулись" in h for h in g["phone-basics"]["how"]),
   f"«где утренний обзор» — руководство телефона находит, где он: {ids}")
st = (ROOT / "android/www-src/app/15-leisure-settings.js").read_text(encoding="utf-8")
ok('voice: "Слух и голос"' in st and "Сам замечает, что вы вернулись" in st, "в руководстве — те же названия, что на экране")
print("ИТОГ: " + ("всё прошло" if not fails else f"провалов {len(fails)}"))
sys.exit(1 if fails else 0)
