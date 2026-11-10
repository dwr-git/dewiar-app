"""Что голос не читает: ссылки, пути к файлам и расширения (итог задачи «Файл: outputs/news.html — …» звучал целиком),
сокращения «в т.ч.», «т.е.» — словами. «км/ч», «и/или», «6/10» и имена сайтов остаются. Компьютер и телефон — одинаково."""
import os, subprocess, sys, json
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "core"))
from llm import speakable  # noqa: E402
fails = []


def ok(c, m):
    print(("✅ " if c else "❌ ") + m)
    if not c:
        fails.append(m)


CASES = {
    "Презентация готова. Файл: outputs/news20261005.html — самодостаточный HTML, в т.ч. на телефоне.":
        "Презентация готова. Файл: самодостаточный HTML, в том числе на телефоне.",
    "Скорость 60 км/ч, и/или 6/10.": "Скорость 60 км/ч, и/или 6/10.",
    "Сохранила в report.pdf и /home/user/Документы/план.docx.": "Сохранила в report.",
    "Подробнее: https://weather.rambler.ru/v-minske/ — там всё.": "Подробнее: там всё.",
    "Т.е. завтра дождь, т.к. циклон.": "то есть завтра дождь, так как циклон.",
    "Сайт dewiar.pro работает.": "Сайт dewiar.pro работает.",
}
bad = {k: speakable(k) for k, v in CASES.items() if speakable(k) != v}
ok(not bad, "компьютер: ссылки, пути и сокращения" + (f": {bad}" if bad else ""))
src = (ROOT / "android/assets/www/app.js").read_text(encoding="utf-8")
a, b = src.index("const FILE_EXT"), src.index("function speechText")
# с ui/assets/speechnorm.js, как в приложении (№561: speechText — через DewiarSpeech.clean)
js = "global.window = {};\n" + (ROOT / "ui/assets/speechnorm.js").read_text(encoding="utf-8") + "\n" + src[a:src.index("\n}\n", b) + 3] + "\nconst EMOJI=/[\\u2600-\\u27BF]/g;\nconsole.log(JSON.stringify(" + json.dumps(list(CASES)) + ".map(speechText)));"
r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
got = json.loads(r.stdout or "[]")
badj = {k: g for (k, v), g in zip(CASES.items(), got) if g != v.replace("то есть завтра", "то есть завтра")}
ok(len(got) == len(CASES) and not badj, "телефон — так же" + (f": {badj} {r.stderr[:200]}" if badj or r.stderr else ""))
print("ALL OK" if not fails else f"ошибок: {len(fails)}")
sys.exit(1 if fails else 0)
