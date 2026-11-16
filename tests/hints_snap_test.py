"""Снимок подсказок к просьбе (чистое ядро 1.0.12, docs/CORE_PLAN.md): какие фразы какую справку модели включают
(answer_rules.turn_hints). Перестройка подсказок обязана его не менять; намеренное изменение — `--update` и в коммит.

    python3 tests/hints_snap_test.py            — сравнить с tests/snap/hints.json
    python3 tests/hints_snap_test.py --update   — записать снимок заново"""
import hashlib, json, os, sys
from pathlib import Path
ROOT = Path(os.environ.get("DEWIAR_ROOT") or Path(__file__).resolve().parent.parent)
sys.path[:0] = [str(ROOT), str(ROOT / "core")]
from answer_rules import turn_hints  # noqa: E402

PHRASES = ["сделай плагин, который считает калории", "поправь мой плагин", "сделай сайт для кофейни", "поправь сайт",
           "покажи в браузере рецепты", "открой страницу со списком", "собери совет по переезду", "сколько я написал сегодня?",
           "прочитай https://example.com/a и перескажи", "что на https://ya.ru", "я еду в Сочи на выходные, что взять?",
           "какая погода в Сочи", "нарисуй схему процесса продаж", "сделай схему", "привет", "напиши стих\n\nВложения: a.png",
           "сделай сайт и схему", "оформи красиво подборку фильмов", "спроси совет у команды", "what did I write today?"]
TOOLS = {"нет": [], "все": ["plugin_create", "site_create", "council", "writing_today", "read_webpage", "weather"],
         "сайты": ["site_create"], "погода": ["weather"]}


def snap():
    out = {}
    for p in PHRASES:
        for k, names in TOOLS.items():
            ask0, ctx, sys_ = turn_hints(p, [{"name": n} for n in names])
            out[f"{p} | {k}"] = {"ask0": ask0, "ctx": [hashlib.sha1(c.encode()).hexdigest()[:10] + " " + c[:60] for c in ctx],
                                 "system": hashlib.sha1(sys_.encode()).hexdigest()[:10] if sys_ else ""}
    return out


ref = ROOT / "tests/snap/hints.json"
now = snap()
if "--update" in sys.argv:
    ref.write_text(json.dumps(now, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("снимок записан:", ref, len(now))
    sys.exit(0)
old = json.loads(ref.read_text(encoding="utf-8"))
diff = [k for k in set(old) | set(now) if old.get(k) != now.get(k)]
print(("✅ " if not diff else "❌ ") + f"подсказки к просьбам — как в снимке ({len(now)} случаев)" + (f": отличаются {diff[:5]}" if diff else ""))
print("ИТОГ:", "всё прошло" if not diff else "провалов 1")
sys.exit(1 if diff else 0)
