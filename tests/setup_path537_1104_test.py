"""№537 (04.11, ПК 0.82.0): «ругается на путь» — на снимке установщик с сайта, обновление поверх Dewiar, который давно стоит
в папке профиля с русским именем и работает, и вопрос «В пути есть русские буквы… голоса и слух могут не заработать. Всё
равно ставить сюда?». Теперь: Dewiar уже стоит в этой папке — не спрашиваем (ставим поверх, как обновление); новая папка с
русскими буквами — вопрос спокойнее и понятнее: Dewiar будет работать, «Да» — сюда, «Нет» — выбрать другую."""
import os, re, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


nsi = (ROOT / "packaging/windows/dewiar.nsi").read_text(encoding="utf-8")
f = nsi[nsi.index("Function DirLeave"):]
f = f[:f.index("FunctionEnd")]
ok(f.index('${FileExists} "$INSTDIR\\app\\ui\\app.py"') < f.index("NONASCII") and "Return" in f.split("NONASCII")[0],
   "Dewiar уже стоит в выбранной папке — без вопроса про русские буквы")
box = re.search(r'MessageBox MB_YESNO\|MB_ICONQUESTION "([^"]+)"', f)
t = box.group(1) if box else ""
ok("Dewiar будет работать" in t and "«Да» — ставить сюда" in t and "«Нет» — выбрать другую папку" in t, "вопрос понятный: что будет и что нажать")
ok("могут не заработать" not in t and "MB_ICONEXCLAMATION" not in f, "без пугающего «могут не заработать» и восклицательного знака")
ok("/SD IDYES IDYES +2" in f and "Abort" in f, "«Нет» — назад к выбору папки, тихая установка — как прежде")
print("ALL OK" if not fails else f"FAILS: {len(fails)}")
sys.exit(1 if fails else 0)
